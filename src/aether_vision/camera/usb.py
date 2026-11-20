"""Plain UVC camera via OpenCV (color only, synthesized intrinsics)."""

from __future__ import annotations

import math
import time

import cv2
import numpy as np

from aether_vision.camera.base import CameraError, CameraTimeoutError, FrameSource
from aether_vision.config.models import UsbCameraConfig
from aether_vision.core.types import CameraIntrinsics, FrameSet, StreamKind


class UsbCameraSource(FrameSource):
    def __init__(self, config: UsbCameraConfig) -> None:
        self._config = config
        self._capture: cv2.VideoCapture | None = None
        self._frame_number = 0
        self._intrinsics: CameraIntrinsics | None = None

    @property
    def streams(self) -> frozenset[StreamKind]:
        return frozenset({StreamKind.COLOR})

    def describe(self) -> str:
        cfg = self._config
        return f"USB[{cfg.device_index}] {cfg.width}x{cfg.height}@{cfg.fps}"

    def open(self) -> None:
        cfg = self._config
        capture = cv2.VideoCapture(cfg.device_index)
        if not capture.isOpened():
            capture.release()
            raise CameraError(f"Cannot open USB camera {cfg.device_index}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        capture.set(cv2.CAP_PROP_FPS, cfg.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._capture = capture
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or cfg.width
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or cfg.height
        focal = (width / 2.0) / math.tan(math.radians(cfg.horizontal_fov_deg) / 2.0)
        self._intrinsics = CameraIntrinsics(width, height, focal, focal, width / 2.0, height / 2.0)

    def read(self, timeout_s: float) -> FrameSet:
        del timeout_s  # OpenCV has no read timeout; the backend blocks
        if self._capture is None:
            raise CameraError("USB camera is not open")
        ok, image = self._capture.read()
        if not ok or image is None:
            if not self._capture.isOpened():
                raise CameraError("USB camera disconnected")
            raise CameraTimeoutError("USB camera returned no frame")
        self._frame_number += 1
        return FrameSet(
            frame_number=self._frame_number,
            capture_time_s=time.monotonic(),
            color=np.ascontiguousarray(image, dtype=np.uint8),
            intrinsics=self._intrinsics,
        )

    def close(self) -> None:
        capture, self._capture = self._capture, None
        if capture is not None:
            capture.release()
