"""Hardware-independent inference backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


class InferenceError(RuntimeError):
    """The model could not be loaded or executed."""


@dataclass(frozen=True, slots=True)
class Quantization:
    """Affine quantization: ``real = (quantized - zero_point) * scale``."""

    scale: float
    zero_point: int

    def quantize(self, values: npt.NDArray[np.float32], dtype: np.dtype[np.generic]) -> np.ndarray:
        info = np.iinfo(dtype)  # type: ignore[type-var]
        q = np.round(values / self.scale + self.zero_point)
        return np.clip(q, info.min, info.max).astype(dtype)

    def dequantize(self, values: np.ndarray) -> npt.NDArray[np.float32]:
        return ((values.astype(np.float32) - self.zero_point) * self.scale).astype(np.float32)


@dataclass(frozen=True, slots=True)
class TensorSpec:
    name: str
    shape: tuple[int, ...]  # -1 for dynamic dimensions
    dtype: np.dtype[np.generic]
    quantization: Quantization | None = None


class InferenceBackend(ABC):
    """Runs a model graph. Not thread-safe: use one instance per thread."""

    @abstractmethod
    def load(self) -> None:
        """Load the model. Raises :class:`InferenceError`."""

    @property
    @abstractmethod
    def inputs(self) -> tuple[TensorSpec, ...]: ...

    @property
    @abstractmethod
    def outputs(self) -> tuple[TensorSpec, ...]: ...

    @property
    def metadata(self) -> dict[str, str]:
        """Model metadata (e.g. Ultralytics embeds ``names`` and ``imgsz``)."""
        return {}

    @abstractmethod
    def run(self, inputs: list[np.ndarray]) -> list[np.ndarray]:
        """Execute the graph. Inputs and outputs are in model order and dtype."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources."""

    @property
    @abstractmethod
    def description(self) -> str: ...
