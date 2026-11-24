"""Intel RealSense (D435 / D4xx) frame source: aligned color + depth."""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from aether_vision.camera.base import CameraError, CameraTimeoutError, FrameSource
from aether_vision.config.models import RealSenseConfig
from aether_vision.core.types import CameraIntrinsics, FrameSet, StreamKind

_log = logging.getLogger(__name__)


def _import_realsense() -> Any:
    try:
        import pyrealsense2 as rs
    except ImportError as error:
        raise CameraError(
            "pyrealsense2 is not installed; run `uv sync --extra realsense` "
            "or build librealsense with Python bindings"
        ) from error
    return rs


class RealSenseSource(FrameSource):
    """Streams BGR color and z16 depth, with depth aligned to the color frame.

    Since depth is aligned to color, the color intrinsics apply to both images,
    which is what deprojection of color-space detections needs.
    """

    def __init__(self, config: RealSenseConfig) -> None:
        self._config = config
        self._rs: Any = None
        self._pipeline: Any = None
        self._align: Any = None
        self._filters: list[Any] = []
        self._depth_scale = 0.001
        self._intrinsics: CameraIntrinsics | None = None
        self._serial = config.serial

    @property
    def streams(self) -> frozenset[StreamKind]:
        if self._config.enable_depth:
            return frozenset({StreamKind.COLOR, StreamKind.DEPTH})
        return frozenset({StreamKind.COLOR})

    def describe(self) -> str:
        serial = self._serial or "auto"
        cfg = self._config
        return f"RealSense[{serial}] {cfg.width}x{cfg.height}@{cfg.fps}"

    def _find_device(self, rs: Any) -> Any:
        devices = list(rs.context().query_devices())
        if not devices:
            raise CameraError("No RealSense device connected")
        for device in devices:
            serial = str(device.get_info(rs.camera_info.serial_number))
            if not self._config.serial or serial == self._config.serial:
                return device
        raise CameraError(f"RealSense device with serial {self._config.serial} not found")

    def open(self) -> None:
        rs = _import_realsense()
        self._rs = rs
        cfg = self._config
        try:
            device = self._find_device(rs)
            self._serial = str(device.get_info(rs.camera_info.serial_number))
            name = str(device.get_info(rs.camera_info.name))
            rs_config = rs.config()
            rs_config.enable_device(self._serial)
            rs_config.enable_stream(rs.stream.color, cfg.width, cfg.height, rs.format.bgr8, cfg.fps)
            if cfg.enable_depth:
                rs_config.enable_stream(
                    rs.stream.depth, cfg.width, cfg.height, rs.format.z16, cfg.fps
                )

            pipeline = rs.pipeline()
            profile = pipeline.start(rs_config)
            self._pipeline = pipeline
            self._configure_sensors(rs, profile)

            color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
            intr = color_profile.get_intrinsics()
            self._intrinsics = CameraIntrinsics(
                width=int(intr.width),
                height=int(intr.height),
                fx=float(intr.fx),
                fy=float(intr.fy),
                cx=float(intr.ppx),
                cy=float(intr.ppy),
            )
            self._align = rs.align(rs.stream.color) if cfg.enable_depth else None
            self._filters = self._build_filters(rs)
        except CameraError:
            self.close()
            raise
        except RuntimeError as error:
            self.close()
            raise CameraError(f"Failed to start RealSense: {error}") from error
        _log.info("Started %s (%s), depth scale %.6f m", name, self._serial, self._depth_scale)

    def _configure_sensors(self, rs: Any, profile: Any) -> None:
        cfg = self._config
        device = profile.get_device()
        if cfg.enable_depth:
            depth_sensor = device.first_depth_sensor()
            self._depth_scale = float(depth_sensor.get_depth_scale())
            if depth_sensor.supports(rs.option.emitter_enabled):
                depth_sensor.set_option(
                    rs.option.emitter_enabled, 1.0 if cfg.emitter_enabled else 0.0
                )
            if cfg.laser_power is not None and depth_sensor.supports(rs.option.laser_power):
                depth_sensor.set_option(rs.option.laser_power, cfg.laser_power)
        for sensor in device.query_sensors():
            if not sensor.supports(rs.option.enable_auto_exposure):
                continue
            if sensor.is_depth_sensor():
                continue
            sensor.set_option(
                rs.option.enable_auto_exposure, 1.0 if cfg.color_auto_exposure else 0.0
            )
            if not cfg.color_auto_exposure and cfg.color_exposure_us is not None:
                sensor.set_option(rs.option.exposure, cfg.color_exposure_us)

    def _build_filters(self, rs: Any) -> list[Any]:
        filters: list[Any] = []
        if not self._config.enable_depth:
            return filters
        if self._config.filters.spatial:
            filters.append(rs.spatial_filter())
        if self._config.filters.temporal:
            filters.append(rs.temporal_filter())
        if self._config.filters.hole_filling:
            filters.append(rs.hole_filling_filter())
        return filters

    def read(self, timeout_s: float) -> FrameSet:
        if self._pipeline is None:
            raise CameraError("RealSense source is not open")
        try:
            frames = self._pipeline.wait_for_frames(int(timeout_s * 1000))
        except RuntimeError as error:
            message = str(error)
            if "didn't arrive" in message or "timeout" in message.lower():
                raise CameraTimeoutError(message) from error
            raise CameraError(message) from error
        received = time.monotonic()

        if self._align is not None:
            frames = self._align.process(frames)
        color_frame = frames.get_color_frame()
        if not color_frame:
            raise CameraTimeoutError("Frame set without color frame")
        color = np.array(np.asanyarray(color_frame.get_data()), dtype=np.uint8, copy=True)

        depth: np.ndarray[Any, np.dtype[np.uint16]] | None = None
        if self._config.enable_depth:
            depth_frame = frames.get_depth_frame()
            if not depth_frame:
                raise CameraTimeoutError("Frame set without depth frame")
            for depth_filter in self._filters:
                depth_frame = depth_filter.process(depth_frame)
            depth = np.array(np.asanyarray(depth_frame.get_data()), dtype=np.uint16, copy=True)

        return FrameSet(
            frame_number=int(color_frame.get_frame_number()),
            capture_time_s=received,
            color=color,
            depth=depth,
            depth_scale_m=self._depth_scale,
            intrinsics=self._intrinsics,
            metadata={"device_timestamp_ms": float(color_frame.get_timestamp())},
        )

    def close(self) -> None:
        pipeline, self._pipeline = self._pipeline, None
        self._align = None
        self._filters = []
        if pipeline is not None:
            try:
                pipeline.stop()
            except RuntimeError as error:
                _log.debug("Ignoring error while stopping RealSense: %s", error)

    def recover(self, failed_attempts: int) -> None:
        threshold = self._config.hardware_reset_after_failures
        if threshold <= 0 or failed_attempts % threshold != 0 or self._rs is None:
            return
        rs = self._rs
        try:
            for device in rs.context().query_devices():
                serial = str(device.get_info(rs.camera_info.serial_number))
                if not self._config.serial or serial == self._config.serial:
                    _log.warning("Hardware-resetting RealSense %s", serial)
                    device.hardware_reset()
                    return
        except RuntimeError as error:
            _log.warning("Hardware reset failed: %s", error)
