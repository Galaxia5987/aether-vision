from __future__ import annotations

from collections.abc import Callable

from aether_vision.camera.thread import CameraState, CameraThread
from aether_vision.config.models import ReconnectConfig
from aether_vision.core.concurrency import LatestValue
from aether_vision.core.types import FrameSet
from aether_vision.telemetry.bus import TelemetryBus
from aether_vision.telemetry.view import Telemetry
from tests.fakes import ScriptedSource

FAST = ReconnectConfig(
    initial_delay_s=0.01, max_delay_s=0.02, frame_timeout_s=0.01, max_consecutive_timeouts=2
)


def _thread(source: ScriptedSource) -> tuple[CameraThread, LatestValue[FrameSet], TelemetryBus]:
    frames: LatestValue[FrameSet] = LatestValue()
    bus = TelemetryBus()
    thread = CameraThread(lambda: source, frames, FAST, Telemetry(bus, "camera"))
    return thread, frames, bus


def test_retries_until_device_appears(waiter: Callable[..., bool]) -> None:
    source = ScriptedSource(["frame"] * 3, open_failures=3)
    thread, frames, _ = _thread(source)
    thread.start()
    assert waiter(lambda: frames.seq >= 3)
    assert source.recover_calls == [1, 2, 3]
    thread.stop(1.0)
    assert thread.state == CameraState.STOPPED


def test_reconnects_after_error_and_repeated_timeouts(waiter: Callable[..., bool]) -> None:
    source = ScriptedSource(["frame", "error", "frame", "timeout", "timeout", "frame"])
    thread, frames, bus = _thread(source)
    thread.start()
    assert waiter(lambda: frames.seq >= 3)
    assert waiter(lambda: source.opens >= 3)
    assert bus.get("camera/reconnects") == 2
    thread.stop(1.0)
    assert source.closes >= source.opens


def test_single_timeout_does_not_reconnect(waiter: Callable[..., bool]) -> None:
    source = ScriptedSource(["frame", "timeout", "frame"])
    thread, frames, _ = _thread(source)
    thread.start()
    assert waiter(lambda: frames.seq >= 2)
    assert source.opens == 1
    thread.stop(1.0)
