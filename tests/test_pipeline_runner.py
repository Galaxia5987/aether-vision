from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import ClassVar

import pytest
from pydantic import Field

from aether_vision.config.base import RESTART_REQUIRED, ConfigModel
from aether_vision.config.models import PipelineSelection
from aether_vision.core.concurrency import LatestValue
from aether_vision.core.types import FrameSet, StreamKind
from aether_vision.pipeline.base import Pipeline, Stage
from aether_vision.pipeline.registry import register_pipeline
from aether_vision.pipeline.result import PipelineResult
from aether_vision.pipeline.runner import PipelineRunner, PipelineState
from aether_vision.streaming.hub import DebugStreams, StreamHub
from aether_vision.telemetry.bus import TelemetryBus
from tests.fakes import make_frames


class CountingConfig(ConfigModel):
    gain: int = 1
    variant: str = Field("a", json_schema_extra=RESTART_REQUIRED)
    fail: bool = False


class DoubleStage(Stage[int, int]):
    def process(self, value: int) -> int:
        return value * 2


@register_pipeline
class CountingPipeline(Pipeline[CountingConfig]):
    name = "test_counting"
    config_type = CountingConfig
    required_streams = frozenset({StreamKind.COLOR})
    builds: ClassVar[int] = 0
    teardowns: ClassVar[int] = 0
    last_value: ClassVar[int] = 0

    def setup(self) -> None:
        type(self).builds += 1
        self.double = self.add_stage(DoubleStage())

    def process(self, frames: FrameSet) -> PipelineResult:
        if self.config.fail:
            raise RuntimeError("configured to fail")
        type(self).last_value = self.double(frames.frame_number * self.config.gain)
        self.telemetry.put("value", type(self).last_value)
        return self.empty_result(frames)

    def on_teardown(self) -> None:
        type(self).teardowns += 1


Harness = tuple[PipelineRunner, LatestValue[FrameSet], LatestValue[PipelineResult], TelemetryBus]
Waiter = Callable[..., bool]


@pytest.fixture
def harness() -> Iterator[Harness]:
    CountingPipeline.builds = 0
    CountingPipeline.teardowns = 0
    frames: LatestValue[FrameSet] = LatestValue()
    results: LatestValue[PipelineResult] = LatestValue()
    bus = TelemetryBus()
    runner = PipelineRunner(
        frames,
        results,
        PipelineSelection(name="test_counting"),
        bus,
        DebugStreams(StreamHub()),
        max_consecutive_errors=3,
    )
    runner.start()
    yield runner, frames, results, bus
    runner.stop(2.0)


def _feed(frames: LatestValue[FrameSet], stop: threading.Event) -> threading.Thread:
    def run() -> None:
        number = 0
        while not stop.is_set():
            number += 1
            frames.put(make_frames(number))
            stop.wait(0.005)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def test_processes_frames_and_publishes_stage_telemetry(harness: Harness, waiter: Waiter) -> None:
    runner, frames, results, bus = harness
    frames.put(make_frames(5))
    assert waiter(lambda: results.seq >= 1)
    assert CountingPipeline.last_value == 10
    assert runner.state == PipelineState.RUNNING
    assert bus.get("pipeline/test_counting/value") == 10
    assert isinstance(bus.get("pipeline/test_counting/stages/double/latency_ms"), float)


def test_live_setting_is_hot_applied(harness: Harness, waiter: Waiter) -> None:
    runner, frames, results, _ = harness
    assert waiter(lambda: runner.state == PipelineState.RUNNING)
    runner.apply_selection(PipelineSelection(name="test_counting", settings={"gain": 10}))
    seq = results.seq
    frames.put(make_frames(3))
    assert waiter(lambda: results.seq > seq)
    assert CountingPipeline.last_value == 60
    assert CountingPipeline.builds == 1


def test_restart_setting_rebuilds(harness: Harness, waiter: Waiter) -> None:
    runner, _, _, _ = harness
    assert waiter(lambda: CountingPipeline.builds == 1)
    runner.apply_selection(PipelineSelection(name="test_counting", settings={"variant": "b"}))
    assert waiter(lambda: CountingPipeline.builds == 2)
    assert CountingPipeline.teardowns == 1


def test_repeated_errors_rebuild_pipeline(harness: Harness, waiter: Waiter) -> None:
    runner, frames, _, _ = harness
    assert waiter(lambda: runner.state == PipelineState.RUNNING)
    runner.apply_selection(PipelineSelection(name="test_counting", settings={"fail": True}))
    stop = threading.Event()
    _feed(frames, stop)
    try:
        assert waiter(lambda: CountingPipeline.builds >= 2)
        assert runner.last_error
    finally:
        stop.set()


def test_missing_streams_sets_error_state(harness: Harness, waiter: Waiter) -> None:
    runner, frames, results, _ = harness
    frames.put(FrameSet(frame_number=1, capture_time_s=0.0))  # no color
    assert waiter(lambda: runner.state == PipelineState.ERROR)
    assert "missing streams" in runner.last_error
    frames.put(make_frames(2))
    assert waiter(lambda: runner.state == PipelineState.RUNNING)
    assert results.seq >= 1


def test_heartbeat_advances_while_idle(harness: Harness, waiter: Waiter) -> None:
    runner, _, _, _ = harness
    first = runner.heartbeat_s
    assert waiter(lambda: runner.heartbeat_s > first)
