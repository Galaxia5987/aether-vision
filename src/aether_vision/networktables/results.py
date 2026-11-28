"""Publishes pipeline results to NetworkTables."""

from __future__ import annotations

import json
import math
from typing import Final, Protocol, SupportsFloat, SupportsIndex, TypeVar

import ntcore
from wpimath.geometry import Pose3d, Rotation3d

from aether_vision.networktables.timebase import monotonic_to_nt_us, to_server_time_us
from aether_vision.pipeline.result import PipelineResult, Target

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


class _Closeable(Protocol):
    def close(self) -> None: ...


PublisherT = TypeVar("PublisherT", bound=_Closeable)

#: Values per target in ``results/targets_flat``.
FLAT_STRIDE: Final = len(FLAT_FIELDS)


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


def target_pose(target: Target) -> Pose3d | None:
    """Robot-relative ``Pose3d`` of a localized target, or ``None`` without a 3D position.

    Depth gives position only, so the rotation is always identity.
    """
    if target.position_robot is None:
        return None
    x, y, z = target.position_robot
    return Pose3d(x, y, z, Rotation3d())


class NetworkTablesResultSink:
    """Publishes every result atomically (all topics share the capture timestamp) and flushes."""

    def __init__(self, instance: ntcore.NetworkTableInstance, root: str) -> None:
        self._instance = instance
        self._publishers: list[_Closeable] = []
        table = instance.getTable(f"{root.rstrip('/')}/results")
        self._timestamp = self._own(table.getIntegerTopic("timestamp_us").publish())
        self._latency = self._own(table.getDoubleTopic("latency_ms").publish())
        self._frame = self._own(table.getIntegerTopic("frame").publish())
        self._count = self._own(table.getIntegerTopic("count").publish())
        self._has_target = self._own(table.getBooleanTopic("has_target").publish())
        self._json = self._own(table.getStringTopic("json").publish())
        self._flat = self._own(table.getDoubleArrayTopic("targets_flat").publish())
        self._flat_fields = self._own(table.getStringArrayTopic("targets_flat_fields").publish())
        self._pipeline = self._own(table.getStringTopic("pipeline").publish())
        self._poses = self._own(table.getStructArrayTopic("poses", Pose3d).publish())
        self._pose_class_ids = self._own(table.getIntegerArrayTopic("pose_class_ids").publish())
        best = table.getSubTable("best")
        self._best_x = self._own(best.getDoubleTopic("x").publish())
        self._best_y = self._own(best.getDoubleTopic("y").publish())
        self._best_z = self._own(best.getDoubleTopic("z").publish())
        self._best_distance = self._own(best.getDoubleTopic("distance").publish())
        self._best_confidence = self._own(best.getDoubleTopic("confidence").publish())
        self._best_class_id = self._own(best.getIntegerTopic("class_id").publish())
        self._best_class_name = self._own(best.getStringTopic("class_name").publish())
        self._best_pose = self._own(best.getStructTopic("pose", Pose3d).publish())
        self._best_has_pose = self._own(best.getBooleanTopic("has_pose").publish())
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

        localized = [(t, pose) for t in result.targets if (pose := target_pose(t)) is not None]
        self._poses.set([pose for _, pose in localized], stamp)
        self._pose_class_ids.set([t.detection.class_id for t, _ in localized], stamp)

        best = result.best
        best_pose = target_pose(best) if best is not None else None
        self._best_has_pose.set(best_pose is not None, stamp)
        if best_pose is not None:
            self._best_pose.set(best_pose, stamp)
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

    def _own(self, publisher: PublisherT) -> PublisherT:
        self._publishers.append(publisher)
        return publisher

    def close(self) -> None:
        for publisher in self._publishers:
            publisher.close()
