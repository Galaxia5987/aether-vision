from __future__ import annotations

import numpy as np
import pytest

from aether_vision.telemetry.bus import TelemetryBus, TelemetryDelta, normalize_value
from aether_vision.telemetry.dispatcher import TelemetryDispatcher
from aether_vision.telemetry.view import Telemetry


def test_normalize_values() -> None:
    assert normalize_value(np.float32(1.5)) == 1.5
    assert normalize_value(np.int64(3)) == 3
    assert normalize_value(np.array([[1, 2], [3, 4]])) == (1, 2, 3, 4)
    assert normalize_value(np.array([0.5, 1.0], dtype=np.float32)) == (0.5, 1.0)
    assert normalize_value([1, 2.5]) == (1.0, 2.5)
    assert normalize_value([True, False]) == (True, False)
    assert normalize_value(["a", "b"]) == ("a", "b")
    mixed: list[object] = ["a", 1]
    with pytest.raises(TypeError):
        normalize_value(mixed)  # type: ignore[arg-type]


def test_invalid_keys_rejected() -> None:
    bus = TelemetryBus()
    for key in ("", "a//b", "/leading", "spaces here"):
        with pytest.raises(ValueError, match="Invalid telemetry key"):
            bus.put(key, 1)


def test_delta_cursor_tracks_changes_and_removals() -> None:
    bus = TelemetryBus()
    bus.put("a/x", 1)
    bus.put("a/y", 2)
    first = bus.delta_since(0)
    assert first.full
    assert first.values == {"a/x": 1, "a/y": 2}

    bus.put("a/x", 1)  # unchanged value is not a change
    assert bus.delta_since(first.cursor).values == {}

    bus.put("a/x", 5)
    bus.remove_prefix("a/y")
    second = bus.delta_since(first.cursor)
    assert not second.full
    assert second.values == {"a/x": 5}
    assert second.removed == ("a/y",)


def test_scoped_view_and_timer() -> None:
    bus = TelemetryBus()
    stage = Telemetry(bus, "pipeline").scope("stages/detect")
    stage.put("count", 3)
    with stage.timer("latency_ms"):
        pass
    assert bus.get("pipeline/stages/detect/count") == 3
    latency = bus.get("pipeline/stages/detect/latency_ms")
    assert isinstance(latency, float)
    assert latency >= 0.0
    Telemetry(bus, "pipeline").clear()
    assert bus.snapshot() == {}


class _RecordingSink:
    def __init__(self) -> None:
        self.deltas: list[TelemetryDelta] = []
        self.closed = False

    def apply(self, delta: TelemetryDelta) -> None:
        self.deltas.append(delta)

    def close(self) -> None:
        self.closed = True


def test_dispatcher_flushes_on_stop() -> None:
    bus = TelemetryBus()
    sink = _RecordingSink()
    dispatcher = TelemetryDispatcher(bus, [sink], rate_hz=1.0)  # slow on purpose
    dispatcher.start()
    bus.put("late/value", 42)
    dispatcher.stop(2.0)
    merged: dict[str, object] = {}
    for delta in sink.deltas:
        merged.update(delta.values)
    assert merged["late/value"] == 42
    assert sink.closed
