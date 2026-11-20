"""Publishes pipeline results to NetworkTables."""

from __future__ import annotations

import json
import math
from typing import Final, SupportsFloat, SupportsIndex

import ntcore

from aether_vision.networktables.timebase import monotonic_to_nt_us, to_server_time_us
from aether_vision.pipeline.result import PipelineResult, Target

#: Values per target in ``results/targets_flat``.
FLAT_STRIDE: Final = 10
FLAT_FIELDS: Final = (
    "class_id",
    "confidence",
    "x",
    "y",
    "z",
    "distance",
    "center_x_px",
    "center_y_px",
    "width_px",
    "height_px",
)


def flatten_target(target: Target) -> list[float]:
    """Robot-frame position; NaN where unknown. Layout documented in :data:`FLAT_FIELDS`."""
    det = target.detection
    position = target.position_robot or (math.nan, math.nan, math.nan)
    distance = target.distance_m if target.distance_m is not None else math.nan
    cx, cy = det.box.center
    return [
        float(det.class_id),
        det.confidence,
        *position,
        distance,
        cx,
        cy,
        det.box.width,
        det.box.height,
    ]


class NetworkTablesResultSink:
    """Publishes every result atomically (all topics share the capture timestamp) and flushes."""

    def __init__(self, instance: ntcore.NetworkTableInstance, root: str) -> None:
        self._instance = instance
        table = instance.getTable(f"{root.rstrip('/')}/results")
        self._timestamp = table.getIntegerTopic("timestamp_us").publish()
        self._latency = table.getDoubleTopic("latency_ms").publish()
        self._frame = table.getIntegerTopic("frame").publish()
        self._count = table.getIntegerTopic("count").publish()
        self._has_target = table.getBooleanTopic("has_target").publish()
        self._json = table.getStringTopic("json").publish()
        self._flat = table.getDoubleArrayTopic("targets_flat").publish()
        self._flat_fields = table.getStringArrayTopic("targets_flat_fields").publish()
        self._pipeline = table.getStringTopic("pipeline").publish()
        best = table.getSubTable("best")
        self._best_x = best.getDoubleTopic("x").publish()
        self._best_y = best.getDoubleTopic("y").publish()
        self._best_z = best.getDoubleTopic("z").publish()
        self._best_distance = best.getDoubleTopic("distance").publish()
        self._best_confidence = best.getDoubleTopic("confidence").publish()
        self._best_class_id = best.getIntegerTopic("class_id").publish()
        self._best_class_name = best.getStringTopic("class_name").publish()
        self._flat_fields.set(list(FLAT_FIELDS))

    def publish(self, result: PipelineResult) -> None:
        stamp = monotonic_to_nt_us(result.capture_time_s)
        self._timestamp.set(to_server_time_us(self._instance, stamp), stamp)
        self._latency.set(result.latency_ms, stamp)
        self._frame.set(result.frame_number, stamp)
        self._count.set(len(result.targets), stamp)
        self._has_target.set(bool(result.targets), stamp)
        self._pipeline.set(result.pipeline, stamp)
        self._json.set(json.dumps(result.to_json(), allow_nan=False, default=str), stamp)
        flat: list[SupportsFloat | SupportsIndex] = []
        for target in result.targets:
            flat.extend(flatten_target(target))
        self._flat.set(flat, stamp)

        best = result.best
        if best is not None:
            pos = best.position_robot or (math.nan, math.nan, math.nan)
            self._best_x.set(pos[0], stamp)
            self._best_y.set(pos[1], stamp)
            self._best_z.set(pos[2], stamp)
            dist = best.distance_m
            self._best_distance.set(dist if dist is not None else math.nan, stamp)
            self._best_confidence.set(best.detection.confidence, stamp)
            self._best_class_id.set(best.detection.class_id, stamp)
            self._best_class_name.set(best.detection.class_name, stamp)
        self._instance.flush()

    def close(self) -> None:
        for publisher in (
            self._timestamp,
            self._latency,
            self._frame,
            self._count,
            self._has_target,
            self._json,
            self._flat,
            self._flat_fields,
            self._pipeline,
            self._best_x,
            self._best_y,
            self._best_z,
            self._best_distance,
            self._best_confidence,
            self._best_class_id,
            self._best_class_name,
        ):
            publisher.close()
