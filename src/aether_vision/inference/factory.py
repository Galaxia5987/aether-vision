"""Build an :class:`InferenceBackend` from configuration."""

from __future__ import annotations

from pathlib import Path

from aether_vision.inference.backend import InferenceBackend
from aether_vision.inference.config import BackendConfig, LiteRtConfig, OnnxRuntimeConfig


def create_backend(model_path: Path, config: BackendConfig) -> InferenceBackend:
    if isinstance(config, OnnxRuntimeConfig):
        from aether_vision.inference.onnx_backend import OnnxRuntimeBackend

        return OnnxRuntimeBackend(model_path, config)
    if isinstance(config, LiteRtConfig):
        from aether_vision.inference.litert_backend import LiteRtBackend

        return LiteRtBackend(model_path, config)
    raise TypeError(f"Unknown backend config {type(config).__name__}")
