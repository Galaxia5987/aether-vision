from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aether_vision.inference import litert_backend
from aether_vision.inference.backend import InferenceError
from aether_vision.inference.config import LiteRtConfig


class _Interpreter:
    def __init__(self, model_path: str, experimental_delegates: Any, num_threads: int) -> None:
        self.delegates = experimental_delegates

    def allocate_tensors(self) -> None:
        pass

    def get_input_details(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "in",
                "index": 0,
                "shape": [1, 8, 8, 3],
                "dtype": np.uint8,
                "quantization": (1 / 255, 0),
            }
        ]

    def get_output_details(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "out",
                "index": 1,
                "shape": [1, 6, 4],
                "dtype": np.float32,
                "quantization": (0.0, 0),
            }
        ]


def _missing_delegate(path: str, options: dict[str, str]) -> Any:
    raise ValueError(f"Failed to load delegate from {path}")


@pytest.fixture
def model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(
        litert_backend, "_import_interpreter", lambda: (_Interpreter, _missing_delegate)
    )
    path = tmp_path / "model.tflite"
    path.write_bytes(b"")
    return path


def test_missing_delegate_falls_back_to_cpu(model: Path) -> None:
    backend = litert_backend.LiteRtBackend(model, LiteRtConfig())
    backend.load()
    assert backend.description == "litert[cpu]"
    assert backend.inputs[0].quantization is not None


def test_missing_delegate_without_fallback_fails(model: Path) -> None:
    backend = litert_backend.LiteRtBackend(model, LiteRtConfig(cpu_fallback=False))
    with pytest.raises(InferenceError, match="QNN delegate"):
        backend.load()
