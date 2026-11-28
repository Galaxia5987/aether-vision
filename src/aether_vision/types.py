"""Values passed between the camera, the pipeline and the publishers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

import numpy as np
import numpy.typing as npt

ColorImage = npt.NDArray[np.uint8]  # H x W x 3, BGR
DepthImage = npt.NDArray[np.uint16]  # H x W, raw units (multiply by depth_scale_m)
FloatArray = npt.NDArray[np.float32]
Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class Intrinsics:
    """Pinhole intrinsics in pixels."""

    fx: float
    fy: float
    cx: float
    cy: float


@dataclass(frozen=True, slots=True, eq=False)
class DepthGeometry:
    """How depth pixels map into the color image: both cameras' intrinsics and the
    depth -> color transform (``p_color = rotation @ p_depth + translation``, meters)."""

    depth: Intrinsics
    color: Intrinsics
    rotation: FloatArray  # 3 x 3
    translation: FloatArray  # 3


@dataclass(frozen=True, slots=True)
class FrameSet:
    """One capture: color, and depth in the depth camera's own pixel grid.

    Depth comes from ``load_depth`` so costly work (RealSense filtering) only runs
    for frames something actually reads.
    """

    color: ColorImage
    load_depth: Callable[[], DepthImage | None]
    depth_scale_m: float
    geometry: DepthGeometry
    capture_time_s: float = field(default_factory=time.monotonic)


@dataclass(frozen=True, slots=True)
class Box:
    """Axis-aligned box in pixels (top-left origin)."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class Detection:
    box: Box
    confidence: float
    class_id: int
    class_name: str


@dataclass(frozen=True, slots=True)
class Target:
    detection: Detection
    position: Vec3 | None = None  # robot frame (WPILib), meters
    distance_m: float | None = None  # from the camera

    def to_json(self) -> dict[str, object]:
        det, box = self.detection, self.detection.box
        return {
            "class_id": det.class_id,
            "class_name": det.class_name,
            "confidence": round(det.confidence, 3),
            "box": [round(v, 1) for v in (box.x, box.y, box.width, box.height)],
            "position": None if self.position is None else [round(v, 3) for v in self.position],
            "distance_m": None if self.distance_m is None else round(self.distance_m, 3),
        }


@dataclass(frozen=True, slots=True)
class Result:
    capture_time_s: float
    targets: tuple[Target, ...]
    completed_time_s: float = field(default_factory=time.monotonic)

    @property
    def latency_ms(self) -> float:
        return (self.completed_time_s - self.capture_time_s) * 1000.0

    def to_json(self) -> dict[str, object]:
        return {
            "latency_ms": round(self.latency_ms, 1),
            "targets": [t.to_json() for t in self.targets],
        }


T = TypeVar("T")


class Latest(Generic[T]):
    """Single-slot mailbox: producers overwrite, consumers wait for something newer."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._value: T | None = None
        self.seq = 0

    def put(self, value: T) -> None:
        with self._condition:
            self._value = value
            self.seq += 1
            self._condition.notify_all()

    def get(self) -> tuple[int, T | None]:
        with self._condition:
            return self.seq, self._value

    def wait_newer(self, seq: int, timeout: float) -> tuple[int, T | None]:
        with self._condition:
            self._condition.wait_for(lambda: self.seq > seq, timeout)
            return self.seq, self._value
