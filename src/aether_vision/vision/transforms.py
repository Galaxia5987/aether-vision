"""Rigid transforms between the camera optical frame and the robot frame.

Robot frame follows WPILib: x forward, y left, z up.
Camera optical frame (RealSense): x right, y down, z forward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt
from pydantic import Field

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import FloatArray

#: Rotation taking optical-frame vectors to a camera "body" frame aligned with WPILib axes.
OPTICAL_TO_BODY: Final[npt.NDArray[np.float64]] = np.array(
    [
        [0.0, 0.0, 1.0],  # body x (forward) = optical z
        [-1.0, 0.0, 0.0],  # body y (left)   = -optical x
        [0.0, -1.0, 0.0],  # body z (up)     = -optical y
    ]
)


class CameraExtrinsics(ConfigModel):
    """Camera pose on the robot (WPILib convention, robot-center origin)."""

    x_m: float = Field(0.0, description="Forward offset from robot center")
    y_m: float = Field(0.0, description="Left offset from robot center")
    z_m: float = Field(0.5, description="Height above the floor")
    roll_deg: float = 0.0
    pitch_deg: float = Field(0.0, description="Positive pitches the camera down (WPILib)")
    yaw_deg: float = 0.0


def rotation_from_rpy(roll: float, pitch: float, yaw: float) -> npt.NDArray[np.float64]:
    """Z-Y-X (yaw, pitch, roll) rotation matrix, radians."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    rotation: npt.NDArray[np.float64] = rz @ ry @ rx
    return rotation


@dataclass(frozen=True, slots=True)
class RigidTransform:
    rotation: npt.NDArray[np.float64]  # 3x3
    translation: npt.NDArray[np.float64]  # 3

    def apply(self, points: FloatArray) -> FloatArray:
        """Transform ``(N, 3)`` or ``(3,)`` points."""
        transformed = points.astype(np.float64) @ self.rotation.T + self.translation
        return transformed.astype(np.float32)

    @staticmethod
    def camera_to_robot(extrinsics: CameraExtrinsics) -> RigidTransform:
        mount = rotation_from_rpy(
            math.radians(extrinsics.roll_deg),
            math.radians(extrinsics.pitch_deg),
            math.radians(extrinsics.yaw_deg),
        )
        return RigidTransform(
            rotation=mount @ OPTICAL_TO_BODY,
            translation=np.array([extrinsics.x_m, extrinsics.y_m, extrinsics.z_m]),
        )
