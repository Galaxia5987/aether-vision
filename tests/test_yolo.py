from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from aether_vision.inference.backend import Quantization, TensorSpec
from aether_vision.inference.yolo import YoloConfig, YoloDetector, letterbox, parse_class_names
from tests.fakes import MultiOutputBackend, StaticBackend

MODEL = Path(__file__).resolve().parents[1] / "models" / "yolov8n.onnx"


def _channels_first(rows: list[list[float]]) -> np.ndarray:
    """rows: [cx, cy, w, h, score_class0, score_class1] in model-input pixels."""
    return np.asarray(rows, dtype=np.float32).T[np.newaxis, ...]


def _detector(output: np.ndarray, **kwargs: object) -> YoloDetector:
    backend = StaticBackend(output, **kwargs)  # type: ignore[arg-type]
    detector = YoloDetector(YoloConfig(class_names=("ball", "robot")), backend)
    detector.load()
    return detector


def test_letterbox_maps_back_to_image() -> None:
    image = np.zeros((32, 64, 3), dtype=np.uint8)  # wide image -> vertical padding
    padded, box_map = letterbox(image, 64, 64)
    assert padded.shape == (64, 64, 3)
    assert box_map.scale == 1.0
    assert box_map.pad_y == 16
    mapped = box_map.to_image(np.array([[0, 16, 64, 48]], dtype=np.float32))
    np.testing.assert_allclose(mapped, [[0, 0, 64, 32]])


def test_decode_nms_and_class_names() -> None:
    output = _channels_first(
        [
            [32, 32, 20, 20, 0.9, 0.1],
            [33, 32, 20, 20, 0.8, 0.1],  # overlaps the first, same class -> suppressed
            [10, 10, 8, 8, 0.1, 0.7],
            [50, 50, 8, 8, 0.2, 0.1],  # below threshold
        ]
    )
    detector = _detector(output)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    detections = detector.detect(image, YoloConfig(confidence_threshold=0.5))
    assert [d.class_name for d in detections] == ["ball", "robot"]
    ball = detections[0]
    assert ball.box.x == pytest.approx(22)
    assert ball.box.width == pytest.approx(20)


def test_class_filter_and_live_threshold() -> None:
    output = _channels_first([[32, 32, 20, 20, 0.9, 0.1], [10, 10, 8, 8, 0.1, 0.7]])
    detector = _detector(output)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    assert [d.class_id for d in detector.detect(image, YoloConfig(class_filter=(1,)))] == [1]
    assert detector.detect(image, YoloConfig(confidence_threshold=0.95)) == []


def test_normalized_boxes_and_anchor_first_layout() -> None:
    rows = np.asarray([[0.5, 0.5, 0.25, 0.25, 0.9, 0.0]], dtype=np.float32)[np.newaxis, ...]
    rows = np.repeat(rows, 10, axis=1)  # anchors-first: [1, N, C] with N > C
    detector = _detector(rows)
    detections = detector.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert len(detections) == 1
    assert detections[0].box.width == pytest.approx(16)


def test_end2end_layout() -> None:
    output = np.asarray([[[4, 4, 20, 30, 0.9, 1], [0, 0, 1, 1, 0.1, 0]]], dtype=np.float32)
    # Ultralytics marks NMS-in-graph exports in metadata; with 2 classes the shape is ambiguous.
    detector = _detector(output, metadata={"end2end": "True"})
    detections = detector.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert len(detections) == 1
    assert detections[0].class_name == "robot"
    assert detections[0].box.height == pytest.approx(26)


def test_quantized_nhwc_model() -> None:
    quant = Quantization(scale=1.0 / 255.0, zero_point=0)
    real = _channels_first([[32, 32, 20, 20, 0.9, 0.1]])
    out_quant = Quantization(scale=0.5, zero_point=0)
    quantized = np.clip(np.round(real / 0.5), 0, 255).astype(np.uint8)
    backend = StaticBackend(
        quantized,
        input_shape=(1, 64, 64, 3),
        input_dtype=np.dtype(np.uint8),
        input_quant=quant,
        output_quant=out_quant,
    )
    config = YoloConfig(box_units="pixels", confidence_threshold=0.0, class_names=("a", "b"))
    detector = YoloDetector(config, backend)
    detector.load()
    image = np.full((64, 64, 3), 255, dtype=np.uint8)
    detections = detector.detect(image)
    assert backend.received[0].shape == (1, 64, 64, 3)
    assert backend.received[0].dtype == np.uint8
    assert int(backend.received[0].max()) == 255
    assert detections


def test_parse_class_names() -> None:
    assert parse_class_names({"names": "{0: 'person', 1: 'bike'}"}) == {0: "person", 1: "bike"}
    assert parse_class_names({"names": "['a', 'b']"}) == {0: "a", 1: "b"}
    assert parse_class_names({"names": "__import__('os')"}) == {}


@pytest.mark.skipif(not MODEL.is_file(), reason="bundled model not present")
def test_bundled_onnx_model_runs_on_cpu() -> None:
    detector = YoloDetector(YoloConfig(model_path=str(MODEL)))
    detector.load()
    assert detector.class_names[0] == "person"
    assert detector.detect(np.zeros((480, 640, 3), dtype=np.uint8)) == []
    detector.close()


def _split_model(
    names: tuple[str, str, str], order: tuple[int, int, int] = (0, 1, 2)
) -> tuple[list[np.ndarray], list[TensorSpec]]:
    """A quantized AI Hub-style model: boxes [1,N,4], scores [1,N], classes [1,N]."""
    box_q = Quantization(0.5, 10)
    score_q = Quantization(1 / 255, 0)
    boxes = np.asarray([[[4, 4, 24, 34], [5, 4, 25, 34], [40, 40, 50, 50]]], dtype=np.float32)
    tensors = [
        box_q.quantize(boxes, np.dtype(np.uint8)),
        score_q.quantize(np.asarray([[0.9, 0.8, 0.6]], dtype=np.float32), np.dtype(np.uint8)),
        np.asarray([[1, 1, 0]], dtype=np.uint8),
    ]
    specs = [
        TensorSpec(names[0], (1, 3, 4), np.dtype(np.uint8), box_q),
        TensorSpec(names[1], (1, 3), np.dtype(np.uint8), score_q),
        TensorSpec(names[2], (1, 3), np.dtype(np.uint8), None),
    ]
    return [tensors[i] for i in order], [specs[i] for i in order]


@pytest.mark.parametrize(
    ("names", "order"),
    [
        (("boxes", "scores", "class_idx"), (0, 1, 2)),
        (("boxes", "scores", "class_idx"), (2, 0, 1)),  # found by name
        (("out0", "out1", "out2"), (0, 1, 2)),  # unnamed: boxes, scores, classes order
    ],
)
def test_split_outputs_layout(names: tuple[str, str, str], order: tuple[int, int, int]) -> None:
    outputs, specs = _split_model(names, order)
    backend = MultiOutputBackend(outputs, specs, input_shape=(1, 64, 64, 3))
    detector = YoloDetector(YoloConfig(class_names=("ball", "robot")), backend)
    detector.load()
    detections = detector.detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert [d.class_name for d in detections] == ["robot", "ball"]  # duplicate removed by NMS
    assert detections[0].box.x == pytest.approx(4)
    assert detections[0].box.height == pytest.approx(30)
    assert detections[0].confidence == pytest.approx(0.9, abs=0.01)


def test_labels_file(tmp_path: Path) -> None:
    labels = tmp_path / "labels.txt"
    labels.write_text("ball\nrobot\n")
    backend = StaticBackend(_channels_first([[10, 10, 8, 8, 0.1, 0.7]]))
    detector = YoloDetector(YoloConfig(labels_path=str(labels)), backend)
    detector.load()
    assert detector.class_names == {0: "ball", 1: "robot"}
