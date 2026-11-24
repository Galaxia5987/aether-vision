"""ONNX Runtime backend (CPU, or any execution provider in the installed build)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from aether_vision.inference.backend import InferenceBackend, InferenceError, TensorSpec
from aether_vision.inference.config import OnnxRuntimeConfig

_log = logging.getLogger(__name__)

_ONNX_TYPES: dict[str, np.dtype[np.generic]] = {
    "tensor(float)": np.dtype(np.float32),
    "tensor(float16)": np.dtype(np.float16),
    "tensor(uint8)": np.dtype(np.uint8),
    "tensor(int8)": np.dtype(np.int8),
    "tensor(int32)": np.dtype(np.int32),
    "tensor(int64)": np.dtype(np.int64),
}


def _shape(raw: list[Any]) -> tuple[int, ...]:
    return tuple(dim if isinstance(dim, int) else -1 for dim in raw)


class OnnxRuntimeBackend(InferenceBackend):
    def __init__(self, model_path: Path, config: OnnxRuntimeConfig) -> None:
        self._model_path = model_path
        self._config = config
        self._session: ort.InferenceSession | None = None
        self._inputs: tuple[TensorSpec, ...] = ()
        self._outputs: tuple[TensorSpec, ...] = ()
        self._metadata: dict[str, str] = {}
        self._active_providers: list[str] = []

    def load(self) -> None:
        if not self._model_path.is_file():
            raise InferenceError(f"Model file not found: {self._model_path}")
        available = set(ort.get_available_providers())
        providers: list[str | tuple[str, dict[str, str]]] = []
        for provider in self._config.providers:
            if provider not in available:
                _log.warning("Execution provider %s is unavailable; skipping", provider)
                continue
            if provider == "QNNExecutionProvider":
                providers.append((provider, {"backend_path": self._config.qnn_backend_path}))
            else:
                providers.append(provider)
        if not providers:
            providers.append("CPUExecutionProvider")

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        if self._config.intra_op_threads > 0:
            options.intra_op_num_threads = self._config.intra_op_threads
        try:
            session = ort.InferenceSession(
                str(self._model_path), sess_options=options, providers=providers
            )
        except Exception as error:  # ORT raises several exception types
            raise InferenceError(f"Failed to load {self._model_path}: {error}") from error

        def spec(arg: Any) -> TensorSpec:
            dtype = _ONNX_TYPES.get(str(arg.type))
            if dtype is None:
                raise InferenceError(f"Unsupported tensor type {arg.type} for {arg.name}")
            return TensorSpec(str(arg.name), _shape(list(arg.shape)), dtype)

        self._inputs = tuple(spec(arg) for arg in session.get_inputs())
        self._outputs = tuple(spec(arg) for arg in session.get_outputs())
        self._metadata = {
            str(k): str(v) for k, v in session.get_modelmeta().custom_metadata_map.items()
        }
        self._active_providers = [str(p) for p in session.get_providers()]
        self._session = session
        _log.info("Loaded %s with providers %s", self._model_path, self._active_providers)

    @property
    def inputs(self) -> tuple[TensorSpec, ...]:
        return self._inputs

    @property
    def outputs(self) -> tuple[TensorSpec, ...]:
        return self._outputs

    @property
    def metadata(self) -> dict[str, str]:
        return dict(self._metadata)

    @property
    def description(self) -> str:
        return f"onnxruntime[{','.join(self._active_providers) or 'unloaded'}]"

    def run(self, inputs: list[np.ndarray]) -> list[np.ndarray]:
        if self._session is None:
            raise InferenceError("Backend is not loaded")
        feeds = {spec.name: tensor for spec, tensor in zip(self._inputs, inputs, strict=True)}
        try:
            results = self._session.run(None, feeds)
        except Exception as error:
            raise InferenceError(f"Inference failed: {error}") from error
        return [np.asarray(result) for result in results]

    def close(self) -> None:
        self._session = None
