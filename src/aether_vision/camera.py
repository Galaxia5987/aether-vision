"""Camera sources (RealSense, mock) and the thread that keeps one streaming."""

from __future__ import annotations

import contextlib
import logging
import math
import threading
import time
from typing import Any, Protocol

import cv2
import numpy as np

from aether_vision.config import CameraConfig
from aether_vision.telemetry import Telemetry
from aether_vision.types import DepthGeometry, DepthImage, FrameSet, Intrinsics, Latest

_log = logging.getLogger(__name__)
_TIMEOUT_MS = 1000
_RESET_AFTER_FAILURES = 3


class Source(Protocol):
    def read(self) -> FrameSet: ...

    def close(self) -> None: ...


class RealSense:
    """Color + depth from an Intel RealSense.

    Depth is not aligned to color here: ``rs.align`` remaps the whole image every
    frame (~15 ms). Localization projects only the depth points it needs instead,
    using :class:`DepthGeometry`.
    """

    def __init__(self, config: CameraConfig) -> None:
        import pyrealsense2 as rs

        rs_config = rs.config()
        if config.serial:
            rs_config.enable_device(config.serial)
        size = (config.width, config.height)
        rs_config.enable_stream(rs.stream.color, *size, rs.format.bgr8, config.fps)
        rs_config.enable_stream(rs.stream.depth, *size, rs.format.z16, config.fps)
        self._pipeline = rs.pipeline()
        profile = self._pipeline.start(rs_config)
        device = profile.get_device()
        self._depth_scale = float(device.first_depth_sensor().get_depth_scale())
        color_sensor = device.first_color_sensor()
        color_sensor.set_option(rs.option.enable_auto_exposure, float(config.exposure_us is None))
        if config.exposure_us is not None:
            color_sensor.set_option(rs.option.exposure, config.exposure_us)
        color_stream = profile.get_stream(rs.stream.color).as_video_stream_profile()
        depth_stream = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        extrinsics = depth_stream.get_extrinsics_to(color_stream)
        self._geometry = DepthGeometry(
            depth=_intrinsics(depth_stream.get_intrinsics()),
            color=_intrinsics(color_stream.get_intrinsics()),
            # librealsense stores the rotation column-major.
            rotation=np.array(extrinsics.rotation, dtype=np.float32).reshape(3, 3).T,
            translation=np.array(extrinsics.translation, dtype=np.float32),
        )
        self._temporal = rs.temporal_filter()
        self._lock = threading.Lock()  # the temporal filter is stateful
        _log.info("RealSense %s started", device.get_info(rs.camera_info.serial_number))

    def read(self) -> FrameSet:
        frames = self._pipeline.wait_for_frames(_TIMEOUT_MS)
        color = np.asanyarray(frames.get_color_frame().get_data()).copy()
        return FrameSet(color, _DeferredDepth(self, frames), self._depth_scale, self._geometry)

    def process_depth(self, frames: Any) -> DepthImage:
        # Filtering holds the GIL, so it runs only for frames that are used, on the
        # thread that uses them (see _DeferredDepth).
        with self._lock:
            depth = self._temporal.process(frames.get_depth_frame())
            return np.array(depth.get_data(), dtype=np.uint16)

    def close(self) -> None:
        with contextlib.suppress(RuntimeError):
            self._pipeline.stop()


def _intrinsics(intr: Any) -> Intrinsics:
    return Intrinsics(intr.fx, intr.fy, intr.ppx, intr.ppy)


class _DeferredDepth:
    """Computes a frame's depth on first call, then returns the cached image."""

    def __init__(self, camera: RealSense, frames: Any) -> None:
        self._camera = camera
        self._frames: Any = frames
        self._depth: DepthImage | None = None
        self._lock = threading.Lock()

    def __call__(self) -> DepthImage | None:
        with self._lock:
            if self._frames is not None:
                frames, self._frames = self._frames, None
                try:
                    self._depth = self._camera.process_depth(frames)
                except RuntimeError as error:
                    _log.warning("Depth processing failed: %s", error)
            return self._depth


class Mock:
    """A ball moving in front of a wall, for development and tests without hardware."""

    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._start = time.monotonic()
        self._next = self._start
        focal = (config.width / 2) / math.tan(math.radians(69.0) / 2)
        intrinsics = Intrinsics(focal, focal, config.width / 2, config.height / 2)
        self._geometry = DepthGeometry(
            intrinsics, intrinsics, np.eye(3, dtype=np.float32), np.zeros(3, dtype=np.float32)
        )

    def read(self) -> FrameSet:
        self._next = max(self._next + 1.0 / self._config.fps, time.monotonic())
        time.sleep(max(0.0, self._next - time.monotonic()))
        t = time.monotonic() - self._start
        w, h = self._config.width, self._config.height
        center = (int(w / 2 + w / 3 * math.sin(t * 0.8)), int(h / 2 + h / 5 * math.sin(t * 1.3)))
        radius = min(w, h) // 10
        color = np.full((h, w, 3), 60, dtype=np.uint8)
        cv2.circle(color, center, radius, (0, 140, 255), -1)
        depth = np.full((h, w), 4000, dtype=np.uint16)
        cv2.circle(depth, center, radius, 1500, -1)
        return FrameSet(color, lambda: depth, 0.001, self._geometry)

    def close(self) -> None:
        pass


def _hardware_reset(serial: str) -> None:
    import pyrealsense2 as rs

    for device in rs.context().query_devices():
        if not serial or device.get_info(rs.camera_info.serial_number) == serial:
            _log.warning("Hardware-resetting RealSense")
            device.hardware_reset()
            return


class CameraThread:
    """Reads frames into ``frames``; reopens the camera with backoff when it fails."""

    def __init__(
        self, config: CameraConfig, frames: Latest[FrameSet], telemetry: Telemetry
    ) -> None:
        self._config = config
        self._frames = frames
        self._telemetry = telemetry
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(5.0)

    def _run(self) -> None:
        failures = 0
        while not self._stop.is_set():
            source: Source | None = None
            try:
                source = (
                    RealSense(self._config)
                    if self._config.kind == "realsense"
                    else Mock(self._config)
                )
                self._telemetry.put("camera/state", "streaming")
                failures = 0
                count, since = 0, time.monotonic()
                while not self._stop.is_set():
                    self._frames.put(source.read())
                    count += 1
                    if count == 30:
                        now = time.monotonic()
                        self._telemetry.put("camera/fps", round(count / (now - since), 1))
                        count, since = 0, now
            except Exception as error:  # driver errors are RuntimeError; anything else too
                failures += 1
                _log.error("Camera failed (attempt %d): %s", failures, error)
                self._telemetry.put("camera/state", f"error: {error}")
                self._telemetry.put("camera/fps", 0.0)
                if self._config.kind == "realsense" and failures % _RESET_AFTER_FAILURES == 0:
                    try:
                        _hardware_reset(self._config.serial)
                    except Exception as reset_error:
                        _log.warning("Hardware reset failed: %s", reset_error)
            finally:
                if source is not None:
                    source.close()
            self._stop.wait(min(0.5 * 2**failures, 5.0))
        self._telemetry.put("camera/state", "stopped")
