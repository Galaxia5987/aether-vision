"""Model inference: hardware backends and the YOLO detector built on top of them."""

from aether_vision.inference.backend import InferenceBackend, InferenceError, TensorSpec
from aether_vision.inference.config import BackendConfig, LiteRtConfig, OnnxRuntimeConfig
from aether_vision.inference.factory import create_backend
from aether_vision.inference.yolo import YoloConfig, YoloDetector

__all__ = [
    "BackendConfig",
    "InferenceBackend",
    "InferenceError",
    "LiteRtConfig",
    "OnnxRuntimeConfig",
    "TensorSpec",
    "YoloConfig",
    "YoloDetector",
    "create_backend",
]
