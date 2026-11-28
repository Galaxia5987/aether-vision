from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest
from ai_edge_litert import interpreter as litert

from aether_vision.config import DetectorConfig
from aether_vision.detector import Detector


class FakeInterpreter:
    """Stands in for LiteRT: a 64x64 uint8 model returning fixed outputs."""

    outputs: ClassVar[list[tuple[str, np.ndarray, tuple[float, int]]]] = []

    def __init__(self, model_path: str, experimental_delegates: Any, num_threads: int) -> None:
        self.delegates = experimental_delegates
        self.received: np.ndarray | None = None

    def allocate_tensors(self) -> None:
        pass

    def get_input_details(self) -> list[dict[str, Any]]:
        shape = [1, 64, 64, 3]
        return [{"index": 0, "shape": shape, "dtype": np.uint8, "quantization": (1 / 255, 0)}]

    def get_output_details(self) -> list[dict[str, Any]]:
        return [
            {"index": i + 1, "name": name, "shape": list(value.shape), "quantization": quant}
            for i, (name, value, quant) in enumerate(self.outputs)
        ]

    def set_tensor(self, index: int, value: np.ndarray) -> None:
        self.received = value

    def invoke(self) -> None:
        pass

    def get_tensor(self, index: int) -> np.ndarray:
        return self.outputs[index - 1][1]


def _no_npu(path: str, options: dict[str, str]) -> Any:
    raise ValueError("no delegate")


@pytest.fixture
def labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(litert, "Interpreter", FakeInterpreter)
    monkeypatch.setattr(litert, "load_delegate", _no_npu)
    path = tmp_path / "labels.txt"
    path.write_text("ball\nrobot\n")
    return str(path)


def test_split_outputs_nms_and_letterbox(labels: str) -> None:
    # AI Hub style: boxes x1y1x2y2 in input pixels, scores, class ids.
    boxes = np.array([[[10, 26, 30, 46], [11, 26, 31, 46], [40, 30, 50, 40]]], np.float32)
    FakeInterpreter.outputs = [
        ("boxes", boxes, (0.0, 0)),
        ("scores", np.array([[0.9, 0.8, 0.7]], np.float32), (0.0, 0)),
        ("class_idx", np.array([[0, 0, 1]], np.uint8), (0.0, 0)),
    ]
    detector = Detector(DetectorConfig(labels_path=labels))
    assert detector.backend == "cpu"
    # 128x64 image -> scale 0.5, 16 px of padding above and below.
    detections = detector.detect(np.zeros((64, 128, 3), np.uint8), DetectorConfig())
    assert [d.class_name for d in detections] == ["ball", "robot"]  # overlapping box suppressed
    ball = detections[0].box
    assert (ball.x, ball.y, ball.width, ball.height) == pytest.approx((20, 20, 40, 40))
    robots = detector.detect(np.zeros((64, 64, 3), np.uint8), DetectorConfig(class_filter=(1,)))
    assert [d.class_id for d in robots] == [1]


def test_ultralytics_output_with_normalized_boxes(labels: str) -> None:
    # [1, 4 + classes, N]: cx, cy, w, h normalized, then per-class scores.
    rows = np.array([[0.5, 0.5, 0.25, 0.25, 0.1, 0.9], [0.1, 0.1, 0.1, 0.1, 0.2, 0.1]], np.float32)
    FakeInterpreter.outputs = [("output0", rows.T[np.newaxis], (0.0, 0))]
    detector = Detector(DetectorConfig(labels_path=labels))
    detections = detector.detect(np.zeros((64, 64, 3), np.uint8), DetectorConfig())
    assert len(detections) == 1
    assert detections[0].class_name == "robot"
    assert detections[0].box.width == pytest.approx(16)
