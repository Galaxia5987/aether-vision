"""Pixel + depth -> 3D points in the camera optical frame (x right, y down, z forward)."""

from __future__ import annotations

import numpy as np

from aether_vision.core.types import BoundingBox, CameraIntrinsics, DepthImage, FloatArray


def deproject_pixel(u: float, v: float, depth_m: float, intrinsics: CameraIntrinsics) -> FloatArray:
    """Deproject a single pixel. Returns ``[x, y, z]`` in meters."""
    return np.array(
        [
            (u - intrinsics.cx) / intrinsics.fx * depth_m,
            (v - intrinsics.cy) / intrinsics.fy * depth_m,
            depth_m,
        ],
        dtype=np.float32,
    )


def roi_point_cloud(
    depth: DepthImage,
    depth_scale_m: float,
    intrinsics: CameraIntrinsics,
    box: BoundingBox,
    stride: int = 1,
    min_depth_m: float = 0.1,
    max_depth_m: float = 10.0,
) -> FloatArray:
    """Deproject every ``stride``-th valid depth pixel inside ``box``.

    ``depth`` must be aligned to the image the box came from, with matching
    ``intrinsics``. Returns an ``(N, 3)`` float32 array (meters, optical frame).
    """
    if stride < 1:
        raise ValueError("stride must be >= 1")
    height, width = depth.shape
    clipped = box.clipped(width, height)
    x0, y0 = int(clipped.x), int(clipped.y)
    x1 = int(np.ceil(clipped.x + clipped.width))
    y1 = int(np.ceil(clipped.y + clipped.height))
    if x1 <= x0 or y1 <= y0:
        return np.empty((0, 3), dtype=np.float32)

    roi = depth[y0:y1:stride, x0:x1:stride].astype(np.float32) * np.float32(depth_scale_m)
    vs, us = np.nonzero((roi >= min_depth_m) & (roi <= max_depth_m))
    if us.size == 0:
        return np.empty((0, 3), dtype=np.float32)
    z = roi[vs, us]
    u = us.astype(np.float32) * stride + x0
    v = vs.astype(np.float32) * stride + y0
    x = (u - np.float32(intrinsics.cx)) / np.float32(intrinsics.fx) * z
    y = (v - np.float32(intrinsics.cy)) / np.float32(intrinsics.fy) * z
    return np.column_stack((x, y, z)).astype(np.float32, copy=False)
