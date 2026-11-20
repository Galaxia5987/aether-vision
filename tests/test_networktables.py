from __future__ import annotations

import json
import math
import time
from collections.abc import Iterator

import ntcore
import pytest

from aether_vision.core.types import BoundingBox, Detection
from aether_vision.networktables.results import FLAT_STRIDE, NetworkTablesResultSink
from aether_vision.networktables.telemetry_sink import NetworkTablesTelemetrySink
from aether_vision.pipeline.result import PipelineResult, Target
from aether_vision.telemetry.bus import TelemetryBus


@pytest.fixture
def instance() -> Iterator[ntcore.NetworkTableInstance]:
    inst = ntcore.NetworkTableInstance.create()
    inst.startLocal()
    yield inst
    ntcore.NetworkTableInstance.destroy(inst)


def test_telemetry_sink_types_and_removal(instance: ntcore.NetworkTableInstance) -> None:
    bus = TelemetryBus()
    sink = NetworkTablesTelemetrySink(instance, "/AV")
    bus.put("a/flag", True)
    bus.put("a/count", 3)
    bus.put("a/ratio", 0.5)
    bus.put("a/name", "hi")
    bus.put("a/xyz", [1.0, 2.0, 3.0])
    sink.apply(bus.delta_since(0))
    assert instance.getBooleanTopic("/AV/a/flag").subscribe(False).get() is True
    assert instance.getIntegerTopic("/AV/a/count").subscribe(0).get() == 3
    assert instance.getDoubleTopic("/AV/a/ratio").subscribe(0.0).get() == 0.5
    assert instance.getStringTopic("/AV/a/name").subscribe("").get() == "hi"
    assert list(instance.getDoubleArrayTopic("/AV/a/xyz").subscribe([]).get()) == [1.0, 2.0, 3.0]

    cursor = bus.delta_since(0).cursor
    bus.remove_prefix("a/name")
    sink.apply(bus.delta_since(cursor))
    assert not instance.getTopic("/AV/a/name").exists()
    sink.close()


def test_result_sink_publishes_targets(instance: ntcore.NetworkTableInstance) -> None:
    sink = NetworkTablesResultSink(instance, "/AV")
    target = Target(
        detection=Detection(BoundingBox(10, 20, 30, 40), 0.9, 2, "note"),
        position_camera=(0.0, 0.0, 2.0),
        position_robot=(2.0, 0.0, 0.5),
        point_count=100,
    )
    now = time.monotonic()
    sink.publish(
        PipelineResult("p", 7, capture_time_s=now - 0.05, completed_time_s=now, targets=(target,))
    )

    flat = list(instance.getDoubleArrayTopic("/AV/results/targets_flat").subscribe([]).get())
    assert len(flat) == FLAT_STRIDE
    assert flat[:6] == [2.0, pytest.approx(0.9), 2.0, 0.0, 0.5, 2.0]
    assert instance.getIntegerTopic("/AV/results/count").subscribe(0).get() == 1
    assert instance.getStringTopic("/AV/results/best/class_name").subscribe("").get() == "note"
    payload = json.loads(instance.getStringTopic("/AV/results/json").subscribe("").get())
    assert payload["targets"][0]["distance_m"] == 2.0

    time.sleep(0.01)
    sink.publish(
        PipelineResult("p", 8, capture_time_s=time.monotonic(), targets=(Target(target.detection),))
    )
    flat = list(instance.getDoubleArrayTopic("/AV/results/targets_flat").subscribe([]).get())
    assert math.isnan(flat[2])
    sink.close()
