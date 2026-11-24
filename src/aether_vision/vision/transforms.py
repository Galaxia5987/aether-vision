"""Rigid transforms between the camera optical frame and the robot frame.

Robot frame follows WPILib: x forward, y left, z up.
Camera optical frame (RealSense): x right, y down, z forward.
"""

from __future__ import annotations

from typing import Final

import numpy as np
from pydantic import Field
from scipy.spatial.transform import Rotation

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import FloatArray

#: Optical frame -> camera "body" frame aligned with WPILib axes
#: (body x = optical z, body y = -optical x, body z = -optical y).
OPTICAL_TO_BODY: Final = Rotation.from_matrix([[0, 0, 1], [-1, 0, 0], [0, -1, 0]])


class CameraExtrinsics(ConfigModel):
    """Camera pose on the robot (WPILib convention, robot-center origin)."""

    x_m: float = Field(0.0, description="Forward offset from robot center")
    y_m: float = Field(0.0, description="Left offset from robot center")
    z_m: float = Field(0.5, description="Height above the floor")
    roll_deg: float = 0.0
    pitch_deg: float = Field(0.0, description="Positive pitches the camera down (WPILib)")
    yaw_deg: float = 0.0


class CameraToRobot:
    """Maps optical-frame points to the robot frame for a given camera mounting."""

    def __init__(self, extrinsics: CameraExtrinsics) -> None:
        mount = Rotation.from_euler(
            "ZYX", [extrinsics.yaw_deg, extrinsics.pitch_deg, extrinsics.roll_deg], degrees=True
        )
        self._rotation = mount * OPTICAL_TO_BODY
        self._translation = np.array([extrinsics.x_m, extrinsics.y_m, extrinsics.z_m])

    def apply(self, points: FloatArray) -> FloatArray:
        """Transform ``(N, 3)`` or ``(3,)`` points."""
        rotated: FloatArray = np.asarray(self._rotation.apply(points), dtype=np.float32)
        return rotated + self._translation.astype(np.float32)
