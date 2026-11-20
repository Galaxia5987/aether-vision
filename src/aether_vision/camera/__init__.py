"""Frame acquisition: sources, factory and the recovering camera thread."""

from aether_vision.camera.base import CameraError, CameraTimeoutError, FrameSource
from aether_vision.camera.factory import create_frame_source
from aether_vision.camera.thread import CameraState, CameraThread

__all__ = [
    "CameraError",
    "CameraState",
    "CameraThread",
    "CameraTimeoutError",
    "FrameSource",
    "create_frame_source",
]
