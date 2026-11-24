"""LiteRT (TFLite) backend with optional Qualcomm QNN delegate for the QCS6490 NPU."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Final

import numpy as np

from aether_vision.inference.backend import (
    InferenceBackend,
    InferenceError,
    Quantization,
    TensorSpec,
)
from aether_vision.inference.config import LiteRtConfig

_log = logging.getLogger(__name__)

# Values understood by libQnnTFLiteDelegate's ``htp_performance_mode`` option.
_HTP_PERFORMANCE_MODES: Final[dict[str, str]] = {
    "default": "0",
    "sustained_high_performance": "1",
    "burst": "2",
    "high_performance": "3",
    "power_saver": "4",
}


def _import_interpreter() -> tuple[Any, Any]:
    """Return ``(Interpreter, load_delegate)`` from LiteRT or the legacy tflite_runtime."""
    try:
        from ai_edge_litert.interpreter import (
            Interpreter,
            load_delegate,
        )
    except ImportError:
        try:
            from tflite_runtime.interpreter import (
                Interpreter,
                load_delegate,
            )
        except ImportError as error:
            raise InferenceError("LiteRT is not installed; run `uv sync --extra litert`") from error
    return Interpreter, load_delegate


def _spec(detail: dict[str, Any]) -> TensorSpec:
    scale, zero_point = detail.get("quantization", (0.0, 0))
    quantization = Quantization(float(scale), int(zero_point)) if float(scale) > 0.0 else None
    return TensorSpec(
        name=str(detail["name"]),
        shape=tuple(int(d) for d in detail["shape"]),
        dtype=np.dtype(detail["dtype"]),
        quantization=quantization,
    )


class LiteRtBackend(InferenceBackend):
    def __init__(self, model_path: Path, config: LiteRtConfig) -> None:
        self._model_path = model_path
        self._config = config
        self._interpreter: Any = None
        self._input_indices: list[int] = []
        self._output_indices: list[int] = []
        self._inputs: tuple[TensorSpec, ...] = ()
        self._outputs: tuple[TensorSpec, ...] = ()
        self._delegated = False

    def _delegate_options(self) -> dict[str, str]:
        options = {
            "backend_type": self._config.qnn_backend,
            "htp_performance_mode": _HTP_PERFORMANCE_MODES[self._config.htp_performance_mode],
        }
        options.update(self._config.extra_delegate_options)
        return options

    def load(self) -> None:
        if not self._model_path.is_file():
            raise InferenceError(f"Model file not found: {self._model_path}")
        interpreter_cls, load_delegate = _import_interpreter()
        delegates: list[Any] = []
        if self._config.delegate == "qnn":
            try:
                delegates.append(
                    load_delegate(self._config.delegate_path, options=self._delegate_options())
                )
                self._delegated = True
            except (OSError, ValueError, RuntimeError) as error:
                raise InferenceError(
                    f"Cannot load QNN delegate {self._config.delegate_path}: {error}"
                ) from error
        try:
            interpreter = interpreter_cls(
                model_path=str(self._model_path),
                experimental_delegates=delegates or None,
                num_threads=self._config.num_threads,
            )
            interpreter.allocate_tensors()
        except (ValueError, RuntimeError) as error:
            raise InferenceError(f"Failed to load {self._model_path}: {error}") from error
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        self._input_indices = [int(d["index"]) for d in input_details]
        self._output_indices = [int(d["index"]) for d in output_details]
        self._inputs = tuple(_spec(d) for d in input_details)
        self._outputs = tuple(_spec(d) for d in output_details)
        self._interpreter = interpreter
        _log.info("Loaded %s (%s)", self._model_path, self.description)

    @property
    def inputs(self) -> tuple[TensorSpec, ...]:
        return self._inputs

    @property
    def outputs(self) -> tuple[TensorSpec, ...]:
        return self._outputs

    @property
    def description(self) -> str:
        if self._delegated:
            return f"litert[qnn:{self._config.qnn_backend}]"
        return "litert[cpu]"

    def run(self, inputs: list[np.ndarray]) -> list[np.ndarray]:
        interpreter = self._interpreter
        if interpreter is None:
            raise InferenceError("Backend is not loaded")
        try:
            for index, tensor in zip(self._input_indices, inputs, strict=True):
                interpreter.set_tensor(index, tensor)
            interpreter.invoke()
            return [np.array(interpreter.get_tensor(index)) for index in self._output_indices]
        except (ValueError, RuntimeError) as error:
            raise InferenceError(f"Inference failed: {error}") from error

    def close(self) -> None:
        self._interpreter = None
