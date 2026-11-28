from __future__ import annotations

import math
import time

import ntcore
from wpimath.geometry import Pose3d

from aether_vision.config import NetworkTablesConfig
from aether_vision.networktables import NetworkTables
from aether_vision.types import Box, Detection, Result, Target


def test_publishes_poses_and_best_target() -> None:
    nt = NetworkTables(NetworkTablesConfig(server_address="127.0.0.1"))
    instance: ntcore.NetworkTableInstance = nt._instance
    try:
        note = Detection(Box(10, 20, 30, 40), 0.9, 2, "note")
        robot = Detection(Box(0, 0, 5, 5), 0.5, 1, "robot")
        result = Result(
            time.monotonic() - 0.05, (Target(note, (2.0, 0.0, 0.5), 2.1), Target(robot))
        )
        nt.publish(result)
        nt.put("camera/fps", 30.0)

        poses = instance.getStructArrayTopic("/AetherVision/results/poses", Pose3d)
        assert [(p.x, p.z) for p in poses.subscribe([]).get()] == [(2.0, 0.5)]
        ids = instance.getIntegerArrayTopic("/AetherVision/results/pose_class_ids")
        assert list(ids.subscribe([]).get()) == [2]
        best = "/AetherVision/results/best/"
        assert instance.getStringTopic(best + "class_name").subscribe("").get() == "note"
        assert instance.getDoubleTopic(best + "distance").subscribe(0.0).get() == 2.1
        assert instance.getBooleanTopic(best + "has_pose").subscribe(False).get()
        fps = instance.getDoubleTopic("/AetherVision/camera/fps").subscribe(0.0).get()
        assert fps == 30.0

        nt.publish(Result(time.monotonic(), (Target(robot),)))
        assert not instance.getBooleanTopic(best + "has_pose").subscribe(True).get()
        assert math.isnan(instance.getDoubleTopic(best + "x").subscribe(0.0).get())
        # An empty struct array is zero bytes (subscribers then return their default).
        raw = instance.getTopic("/AetherVision/results/poses").genericSubscribe().get()
        assert raw.getRaw() == b""
    finally:
        nt.close()
