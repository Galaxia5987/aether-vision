"""Pipeline output types."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from aether_vision.core.types import Detection

Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Target:
    """A detected object, optionally localized in 3D."""

    detection: Detection
    position_camera: Vec3 | None = None  # optical frame, meters
    position_robot: Vec3 | None = None  # WPILib robot frame, meters
    extent_m: Vec3 | None = None
    point_count: int = 0

    @property
    def distance_m(self) -> float | None:
        if self.position_camera is None:
            return None
        return math.sqrt(sum(c * c for c in self.position_camera))

    def to_json(self) -> dict[str, object]:
        box = self.detection.box
        return {
            "class_id": self.detection.class_id,
            "class_name": self.detection.class_name,
            "confidence": round(self.detection.confidence, 4),
            "box": [round(box.x, 1), round(box.y, 1), round(box.width, 1), round(box.height, 1)],
            "position_camera": _round3(self.position_camera),
            "position_robot": _round3(self.position_robot),
            "extent_m": _round3(self.extent_m),
            "distance_m": None if self.distance_m is None else round(self.distance_m, 4),
            "point_count": self.point_count,
        }


def _round3(vec: Vec3 | None) -> list[float] | None:
    return None if vec is None else [round(v, 4) for v in vec]


@dataclass(frozen=True, slots=True)
class PipelineResult:
    pipeline: str
    frame_number: int
    capture_time_s: float  # time.monotonic() of capture
    completed_time_s: float = field(default_factory=time.monotonic)
    targets: tuple[Target, ...] = ()

    @property
    def latency_ms(self) -> float:
        return (self.completed_time_s - self.capture_time_s) * 1000.0

    @property
    def best(self) -> Target | None:
        return self.targets[0] if self.targets else None

    def to_json(self) -> dict[str, object]:
        return {
            "pipeline": self.pipeline,
            "frame_number": self.frame_number,
            "latency_ms": round(self.latency_ms, 2),
            "targets": [target.to_json() for target in self.targets],
        }
