"""YOLO object detection with LiteRT, on the Qualcomm NPU (QNN delegate) when available.

Two output formats are understood:

* Qualcomm AI Hub exports: three outputs ``boxes [1, N, 4]`` (x1, y1, x2, y2),
  ``scores [1, N]`` and ``classes [1, N]``
* Ultralytics exports: one output ``[1, 4 + classes, N]`` (cx, cy, w, h, class scores)

Boxes may be in input pixels or normalized to 0..1; both are handled.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from aether_vision.config import DetectorConfig
from aether_vision.types import Box, ColorImage, Detection, FloatArray

_log = logging.getLogger(__name__)
_NPU_DELEGATE = "libQnnTFLiteDelegate.so"
_NPU_OPTIONS = {"backend_type": "htp", "htp_performance_mode": "2"}  # 2 = burst


class Detector:
    def __init__(self, config: DetectorConfig) -> None:
        from ai_edge_litert.interpreter import Interpreter, load_delegate

        delegates = []
        if config.use_npu:
            try:
                delegates.append(load_delegate(_NPU_DELEGATE, options=_NPU_OPTIONS))
            except (OSError, ValueError, RuntimeError) as error:
                _log.warning("NPU unavailable (%s); running on the CPU", error)
        self.backend = "npu" if delegates else "cpu"
        self._interpreter = Interpreter(
            model_path=config.model_path, experimental_delegates=delegates, num_threads=4
        )
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._outputs = self._interpreter.get_output_details()
        _, self._height, self._width, _ = self._input["shape"]
        if len(self._outputs) not in (1, 3):
            raise ValueError(f"Unsupported YOLO model with {len(self._outputs)} outputs")
        self._names = _read_labels(config.labels_path)
        _log.info("Loaded %s on the %s", config.model_path, self.backend)

    def detect(self, image: ColorImage, config: DetectorConfig) -> list[Detection]:
        tensor, scale, pad_x, pad_y = self._preprocess(image)
        self._interpreter.set_tensor(self._input["index"], tensor)
        self._interpreter.invoke()
        boxes, scores, classes = self._decode()

        keep = scores >= config.confidence_threshold
        if config.class_filter:
            keep &= np.isin(classes, config.class_filter)
        boxes, scores, classes = boxes[keep], scores[keep], classes[keep]
        if boxes.size and np.abs(boxes).max() <= 2.0:  # normalized 0..1 boxes
            boxes = boxes * np.array([self._width, self._height] * 2, dtype=np.float32)
        # Undo the letterbox: model-input pixels -> image pixels.
        boxes = (boxes - np.array([pad_x, pad_y] * 2, dtype=np.float32)) / scale
        xywh = np.column_stack((boxes[:, :2], boxes[:, 2:] - boxes[:, :2]))
        indices = cv2.dnn.NMSBoxesBatched(
            xywh.tolist(),
            scores.tolist(),
            classes.tolist(),
            config.confidence_threshold,
            config.iou_threshold,
            top_k=config.max_detections,
        )
        return [
            Detection(
                Box(*(float(v) for v in xywh[i])),
                float(scores[i]),
                int(classes[i]),
                self._names.get(int(classes[i]), f"class_{classes[i]}"),
            )
            for i in np.asarray(indices, dtype=np.int64).reshape(-1)[: config.max_detections]
        ]

    def _preprocess(self, image: ColorImage) -> tuple[np.ndarray, float, int, int]:
        """Letterbox to the model input (keep aspect, pad gray), BGR -> RGB, quantize."""
        h, w = image.shape[:2]
        scale = min(self._width / w, self._height / h)
        new_w, new_h = round(w * scale), round(h * scale)
        pad_x, pad_y = (self._width - new_w) // 2, (self._height - new_h) // 2
        resized = cv2.resize(image, (new_w, new_h)) if (new_w, new_h) != (w, h) else image
        padded = cv2.copyMakeBorder(
            resized,
            pad_y,
            self._height - new_h - pad_y,
            pad_x,
            self._width - new_w - pad_x,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        dtype = self._input["dtype"]
        in_scale, zero_point = self._input["quantization"]
        data: np.ndarray
        if dtype == np.float32:
            data = rgb.astype(np.float32) / 255.0
        elif dtype == np.uint8 and zero_point == 0 and abs(in_scale * 255 - 1) < 1e-4:
            data = rgb  # quantize(pixel / 255) == pixel
        else:
            info = np.iinfo(dtype)
            quantized = np.round(rgb / 255.0 / in_scale + zero_point)
            data = np.clip(quantized, info.min, info.max).astype(dtype)
        return data[np.newaxis], scale, pad_x, pad_y

    def _output(self, index: int) -> FloatArray:
        detail = self._outputs[index]
        raw = np.asarray(self._interpreter.get_tensor(detail["index"])[0], dtype=np.float32)
        scale, zero_point = detail["quantization"]
        return (raw - zero_point) * np.float32(scale) if scale > 0 else raw

    def _decode(self) -> tuple[FloatArray, FloatArray, np.ndarray]:
        """Return ``(boxes x1y1x2y2, scores, class_ids)`` in model-input units."""
        if len(self._outputs) == 1:  # Ultralytics [4 + classes, N]
            rows = self._output(0).T
            class_scores = rows[:, 4:]
            classes = class_scores.argmax(axis=1)
            scores = class_scores[np.arange(len(rows)), classes]
            half = rows[:, 2:4] / 2
            return np.hstack((rows[:, :2] - half, rows[:, :2] + half)), scores, classes
        shapes = [d["shape"] for d in self._outputs]
        box_index = next(i for i, s in enumerate(shapes) if len(s) == 3 and s[2] == 4)
        flat = [i for i in range(3) if i != box_index]
        names = {i: self._outputs[i]["name"].lower() for i in flat}
        class_index = next((i for i in flat if "class" in names[i]), flat[1])
        score_index = next(i for i in flat if i != class_index)
        # Class ids are plain integers even in quantized models.
        classes = self._interpreter.get_tensor(self._outputs[class_index]["index"])[0]
        return self._output(box_index), self._output(score_index), classes.astype(np.int64)


def _read_labels(path: str) -> dict[int, str]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        _log.warning("No labels file at %s; using class ids", path)
        return {}
    return {i: line.strip() for i, line in enumerate(lines) if line.strip()}
