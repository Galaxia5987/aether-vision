"""Build a :class:`FrameSource` from configuration."""

from __future__ import annotations

from aether_vision.camera.base import FrameSource
from aether_vision.camera.mock import MockCameraSource
from aether_vision.camera.realsense import RealSenseSource
from aether_vision.camera.usb import UsbCameraSource
from aether_vision.config.models import (
    CameraConfig,
    MockCameraConfig,
    RealSenseConfig,
    UsbCameraConfig,
)


def create_frame_source(config: CameraConfig) -> FrameSource:
    if isinstance(config, RealSenseConfig):
        return RealSenseSource(config)
    if isinstance(config, UsbCameraConfig):
        return UsbCameraSource(config)
    if isinstance(config, MockCameraConfig):
        return MockCameraSource(config)
    raise TypeError(f"Unknown camera config {type(config).__name__}")
