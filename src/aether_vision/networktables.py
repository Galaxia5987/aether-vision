"""NetworkTables connection: telemetry and per-frame results for the robot.

Results, under ``/AetherVision/results``, all stamped with the frame's capture time:

* ``timestamp_us`` (int): capture time on the robot's clock
* ``latency_ms`` (double): capture to result
* ``poses`` (Pose3d[]) and ``pose_class_ids`` (int[]): every localized target, robot frame
* ``best/*``: the most confident target (``has_pose``, ``pose``, ``x``, ``y``, ``z``,
  ``distance``, ``confidence``, ``class_id``, ``class_name``); NaN where not localized
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import ntcore
from wpimath.geometry import Pose3d, Rotation3d

from aether_vision.config import NetworkTablesConfig
from aether_vision.telemetry import Value
from aether_vision.types import Result

_log = logging.getLogger(__name__)
ROOT = "AetherVision"


class NetworkTables:
    def __init__(self, config: NetworkTablesConfig) -> None:
        self._instance = ntcore.NetworkTableInstance.create()
        self._instance.startClient4("aether-vision")
        if config.server_address:
            self._instance.setServer(config.server_address)
        else:
            self._instance.setServerTeam(config.team)
        _log.info("NetworkTables connecting to %s", config.server_address or f"team {config.team}")
        table = self._instance.getTable(ROOT)
        self._table = table
        self._entries: dict[str, ntcore.NetworkTableEntry] = {}

        results = table.getSubTable("results")
        best = results.getSubTable("best")
        self._timestamp = results.getIntegerTopic("timestamp_us").publish()
        self._latency = results.getDoubleTopic("latency_ms").publish()
        self._poses = results.getStructArrayTopic("poses", Pose3d).publish()
        self._class_ids = results.getIntegerArrayTopic("pose_class_ids").publish()
        self._best_has_pose = best.getBooleanTopic("has_pose").publish()
        self._best_pose = best.getStructTopic("pose", Pose3d).publish()
        self._best: dict[str, Any] = {
            name: best.getDoubleTopic(name).publish()
            for name in ("x", "y", "z", "distance", "confidence")
        }
        self._best_class_id = best.getIntegerTopic("class_id").publish()
        self._best_class_name = best.getStringTopic("class_name").publish()

    @property
    def connected(self) -> bool:
        return bool(self._instance.isConnected())

    def put(self, key: str, value: Value) -> None:
        entry = self._entries.get(key)
        if entry is None:
            entry = self._entries[key] = self._table.getEntry(key)
        entry.setValue(value)

    def publish(self, result: Result) -> None:
        # Stamp every topic with the capture time, in the local NT time base.
        age_us = int((time.monotonic() - result.capture_time_s) * 1e6)
        stamp = max(1, ntcore._now() - age_us)
        offset = self._instance.getServerTimeOffset() or 0
        self._timestamp.set(stamp + offset, stamp)
        self._latency.set(result.latency_ms, stamp)

        localized = [t for t in result.targets if t.position is not None]
        self._poses.set([_pose(t.position) for t in localized if t.position], stamp)
        self._class_ids.set([t.detection.class_id for t in localized], stamp)

        if result.targets:
            best = max(result.targets, key=lambda t: t.detection.confidence)
            x, y, z = best.position or (math.nan, math.nan, math.nan)
            values = {
                "x": x,
                "y": y,
                "z": z,
                "distance": math.nan if best.distance_m is None else best.distance_m,
                "confidence": best.detection.confidence,
            }
            for name, value in values.items():
                self._best[name].set(value, stamp)
            self._best_class_id.set(best.detection.class_id, stamp)
            self._best_class_name.set(best.detection.class_name, stamp)
            if best.position is not None:
                self._best_pose.set(_pose(best.position), stamp)
            self._best_has_pose.set(best.position is not None, stamp)
        else:
            self._best_has_pose.set(False, stamp)
        self._instance.flush()

    def close(self) -> None:
        self._instance.flush()
        ntcore.NetworkTableInstance.destroy(self._instance)


def _pose(position: tuple[float, float, float]) -> Pose3d:
    # Depth gives position only, so the rotation is identity.
    return Pose3d(*position, Rotation3d())
