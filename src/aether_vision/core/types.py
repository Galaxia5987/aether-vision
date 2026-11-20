"""Value types passed between camera, pipeline and publishers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
import numpy.typing as npt

ColorImage = npt.NDArray[np.uint8]  # H x W x 3, BGR
DepthImage = npt.NDArray[np.uint16]  # H x W, raw depth units (multiply by depth_scale)
FloatArray = npt.NDArray[np.float32]


class StreamKind(StrEnum):
    COLOR = "color"
    DEPTH = "depth"


@dataclass(frozen=True, slots=True)
class CameraIntrinsics:
    """Pinhole intrinsics (pixels). Distortion is ignored for deprojection."""

    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

    def scaled(self, width: int, height: int) -> CameraIntrinsics:
        sx = width / self.width
        sy = height / self.height
        return CameraIntrinsics(
            width, height, self.fx * sx, self.fy * sy, self.cx * sx, self.cy * sy
        )


@dataclass(frozen=True, slots=True)
class FrameSet:
    """One synchronized capture. ``depth`` is aligned to ``color`` when both exist."""

    frame_number: int
    capture_time_s: float  # time.monotonic() when the host received the frame
    color: ColorImage | None = None
    depth: DepthImage | None = None
    depth_scale_m: float = 0.001
    intrinsics: CameraIntrinsics | None = None
    metadata: dict[str, float] = field(default_factory=dict)

    @property
    def streams(self) -> frozenset[StreamKind]:
        kinds: set[StreamKind] = set()
        if self.color is not None:
            kinds.add(StreamKind.COLOR)
        if self.depth is not None:
            kinds.add(StreamKind.DEPTH)
        return frozenset(kinds)

    def require_color(self) -> ColorImage:
        if self.color is None:
            raise ValueError("FrameSet has no color image")
        return self.color

    def require_depth(self) -> DepthImage:
        if self.depth is None:
            raise ValueError("FrameSet has no depth image")
        return self.depth

    def require_intrinsics(self) -> CameraIntrinsics:
        if self.intrinsics is None:
            raise ValueError("FrameSet has no intrinsics")
        return self.intrinsics


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned box in pixel coordinates (top-left origin)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    def clipped(self, width: int, height: int) -> BoundingBox:
        x0 = min(max(self.x, 0.0), float(width))
        y0 = min(max(self.y, 0.0), float(height))
        x1 = min(max(self.x + self.width, 0.0), float(width))
        y1 = min(max(self.y + self.height, 0.0), float(height))
        return BoundingBox(x0, y0, x1 - x0, y1 - y0)

    def shrunk(self, factor: float) -> BoundingBox:
        """Scale the box about its center (``factor`` < 1 shrinks)."""
        cx, cy = self.center
        w = self.width * factor
        h = self.height * factor
        return BoundingBox(cx - w / 2.0, cy - h / 2.0, w, h)


@dataclass(frozen=True, slots=True)
class Detection:
    box: BoundingBox
    confidence: float
    class_id: int
    class_name: str
