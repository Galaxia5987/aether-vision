"""Synthetic color + depth source for development and tests without hardware."""

from __future__ import annotations

import math
import time

import cv2
import numpy as np

from aether_vision.camera.base import CameraError, FrameSource
from aether_vision.config.models import MockCameraConfig
from aether_vision.core.types import CameraIntrinsics, ColorImage, FrameSet, StreamKind

_DEPTH_SCALE_M = 0.001


class MockCameraSource(FrameSource):
    """Renders a ball moving over a background, with a matching depth image.

    If ``image_path`` is set, that image is used as the color stream instead
    (useful for trying a YOLO model on a still image).
    """

    def __init__(self, config: MockCameraConfig) -> None:
        self._config = config
        self._opened = False
        self._frame_number = 0
        self._next_frame_time = 0.0
        self._still: ColorImage | None = None
        width, height = config.width, config.height
        focal = (width / 2.0) / math.tan(math.radians(69.0) / 2.0)
        self._intrinsics = CameraIntrinsics(width, height, focal, focal, width / 2.0, height / 2.0)

    @property
    def streams(self) -> frozenset[StreamKind]:
        return frozenset({StreamKind.COLOR, StreamKind.DEPTH})

    def describe(self) -> str:
        cfg = self._config
        return f"Mock {cfg.width}x{cfg.height}@{cfg.fps}"

    def open(self) -> None:
        if self._config.image_path:
            image = cv2.imread(self._config.image_path, cv2.IMREAD_COLOR)
            if image is None:
                raise CameraError(f"Cannot read mock image {self._config.image_path}")
            resized = cv2.resize(image, (self._config.width, self._config.height))
            self._still = np.asarray(resized, dtype=np.uint8)
        self._opened = True
        self._next_frame_time = time.monotonic()

    def read(self, timeout_s: float) -> FrameSet:
        del timeout_s
        if not self._opened:
            raise CameraError("Mock source is not open")
        period = 1.0 / self._config.fps
        delay = self._next_frame_time - time.monotonic()
        if delay > 0.0:
            time.sleep(delay)
        self._next_frame_time = max(self._next_frame_time + period, time.monotonic())
        self._frame_number += 1
        color, depth = self._render(self._frame_number * period)
        return FrameSet(
            frame_number=self._frame_number,
            capture_time_s=time.monotonic(),
            color=color,
            depth=depth,
            depth_scale_m=_DEPTH_SCALE_M,
            intrinsics=self._intrinsics,
        )

    def _render(
        self, t: float
    ) -> tuple[ColorImage, np.ndarray[tuple[int, int], np.dtype[np.uint16]]]:
        cfg = self._config
        w, h = cfg.width, cfg.height
        depth = np.full((h, w), int(cfg.background_depth_m / _DEPTH_SCALE_M), dtype=np.uint16)
        cx = int(w / 2 + (w / 3) * math.sin(t * 0.8))
        cy = int(h / 2 + (h / 5) * math.sin(t * 1.3))
        radius = max(8, min(w, h) // 10)
        cv2.circle(depth, (cx, cy), radius, int(cfg.target_depth_m / _DEPTH_SCALE_M), -1)
        if self._still is not None:
            return self._still.copy(), depth
        color = np.zeros((h, w, 3), dtype=np.uint8)
        color[:, :, 0] = np.linspace(40, 90, w, dtype=np.uint8)[None, :]
        color[:, :, 1] = np.linspace(30, 60, h, dtype=np.uint8)[:, None]
        cv2.circle(color, (cx, cy), radius, (0, 140, 255), -1)
        return color, depth

    def close(self) -> None:
        self._opened = False
