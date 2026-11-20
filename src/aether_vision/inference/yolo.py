"""YOLO object detector, independent of the inference backend.

Supports Ultralytics-style detection heads:

* ``channels_first`` — ``[1, 4 + num_classes, num_anchors]`` (YOLOv8/v11 ONNX/TFLite)
* ``anchors_first``  — ``[1, num_anchors, 4 + num_classes]`` (transposed exports)
* ``end2end``        — ``[1, max_det, 6]`` with ``x1, y1, x2, y2, score, class`` (NMS in graph)
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import cv2
import numpy as np
import numpy.typing as npt
from pydantic import Field

from aether_vision.config.base import RESTART_REQUIRED, ConfigModel
from aether_vision.core.types import BoundingBox, ColorImage, Detection
from aether_vision.inference.backend import InferenceBackend, InferenceError, TensorSpec
from aether_vision.inference.config import BackendConfig, OnnxRuntimeConfig
from aether_vision.inference.factory import create_backend

_log = logging.getLogger(__name__)

_PAD_VALUE: Final = 114
_DEFAULT_INPUT_SIZE: Final = 640
_CLASS_OFFSET: Final = 8192.0  # per-class NMS via coordinate offsets

OutputLayout = Literal["auto", "channels_first", "anchors_first", "end2end"]


class YoloConfig(ConfigModel):
    model_path: str = Field("models/yolov8n.onnx", json_schema_extra=RESTART_REQUIRED)
    backend: BackendConfig = Field(
        default_factory=OnnxRuntimeConfig, json_schema_extra=RESTART_REQUIRED
    )
    output_layout: OutputLayout = Field("auto", json_schema_extra=RESTART_REQUIRED)
    box_units: Literal["auto", "pixels", "normalized"] = Field(
        "auto", description="'normalized' for exports that output 0..1 boxes (e.g. TFLite)"
    )
    class_names: tuple[str, ...] = Field(
        (), description="Overrides names embedded in the model", json_schema_extra=RESTART_REQUIRED
    )
    confidence_threshold: float = Field(0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    class_agnostic_nms: bool = False
    max_detections: int = Field(50, ge=1, le=1000)
    class_filter: tuple[int, ...] = Field((), description="Keep only these class ids; empty = all")


@dataclass(frozen=True, slots=True)
class Letterbox:
    """Mapping from model-input coordinates back to the original image."""

    scale: float
    pad_x: float
    pad_y: float

    def to_image(self, boxes_xyxy: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        out = boxes_xyxy.copy()
        out[:, [0, 2]] = (out[:, [0, 2]] - self.pad_x) / self.scale
        out[:, [1, 3]] = (out[:, [1, 3]] - self.pad_y) / self.scale
        return out


def letterbox(image: ColorImage, width: int, height: int) -> tuple[ColorImage, Letterbox]:
    """Resize preserving aspect ratio and pad to ``width`` x ``height``."""
    src_h, src_w = image.shape[:2]
    scale = min(width / src_w, height / src_h)
    new_w = round(src_w * scale)
    new_h = round(src_h * scale)
    pad_x = (width - new_w) // 2
    pad_y = (height - new_h) // 2
    resized = (
        image
        if (new_w, new_h) == (src_w, src_h)
        else cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    )
    padded = cv2.copyMakeBorder(
        resized,
        pad_y,
        height - new_h - pad_y,
        pad_x,
        width - new_w - pad_x,
        cv2.BORDER_CONSTANT,
        value=(_PAD_VALUE, _PAD_VALUE, _PAD_VALUE),
    )
    return np.asarray(padded, dtype=np.uint8), Letterbox(scale, float(pad_x), float(pad_y))


def parse_class_names(metadata: dict[str, str]) -> dict[int, str]:
    """Parse the Ultralytics ``names`` metadata (a Python dict literal)."""
    raw = metadata.get("names")
    if not raw:
        return {}
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        _log.warning("Could not parse model class names metadata")
        return {}
    if isinstance(parsed, dict):
        return {int(k): str(v) for k, v in parsed.items()}
    if isinstance(parsed, list):
        return {i: str(v) for i, v in enumerate(parsed)}
    return {}


@dataclass(frozen=True, slots=True)
class _InputGeometry:
    spec: TensorSpec
    width: int
    height: int
    nchw: bool


def _input_geometry(spec: TensorSpec, metadata: dict[str, str]) -> _InputGeometry:
    if len(spec.shape) != 4:
        raise InferenceError(f"Expected a 4D image input, got shape {spec.shape}")
    nchw = spec.shape[1] == 3
    if not nchw and spec.shape[3] != 3:
        raise InferenceError(f"Cannot tell channel axis of input shape {spec.shape}")
    height, width = (spec.shape[2], spec.shape[3]) if nchw else (spec.shape[1], spec.shape[2])
    if height <= 0 or width <= 0:
        size = _DEFAULT_INPUT_SIZE
        imgsz = metadata.get("imgsz")
        if imgsz:
            try:
                parsed = ast.literal_eval(imgsz)
                size = int(parsed[0]) if isinstance(parsed, list | tuple) else int(parsed)
            except (ValueError, SyntaxError, TypeError):
                pass
        height = height if height > 0 else size
        width = width if width > 0 else size
    return _InputGeometry(spec, width, height, nchw)


class YoloDetector:
    """Loads a YOLO model on a backend and turns BGR images into :class:`Detection` lists.

    Model-structure settings are fixed at construction; thresholds are read from
    the config passed to :meth:`detect`, so they can change between frames.
    """

    def __init__(self, config: YoloConfig, backend: InferenceBackend | None = None) -> None:
        self._config = config
        self._backend = backend or create_backend(Path(config.model_path), config.backend)
        self._geometry: _InputGeometry | None = None
        self._class_names: dict[int, str] = {}
        self._layout: OutputLayout = config.output_layout

    @property
    def backend_description(self) -> str:
        return self._backend.description

    @property
    def class_names(self) -> dict[int, str]:
        return dict(self._class_names)

    def load(self) -> None:
        self._backend.load()
        if len(self._backend.inputs) != 1 or not self._backend.outputs:
            raise InferenceError("YOLO models must have one input and at least one output")
        metadata = self._backend.metadata
        self._geometry = _input_geometry(self._backend.inputs[0], metadata)
        if self._config.class_names:
            self._class_names = dict(enumerate(self._config.class_names))
        else:
            self._class_names = parse_class_names(metadata)
        if self._layout == "auto" and metadata.get("end2end", "").lower() == "true":
            self._layout = "end2end"
        _log.info(
            "YOLO ready: input %dx%d (%s), %d classes, backend %s",
            self._geometry.width,
            self._geometry.height,
            "NCHW" if self._geometry.nchw else "NHWC",
            len(self._class_names),
            self._backend.description,
        )

    def close(self) -> None:
        self._backend.close()

    # ------------------------------------------------------------------ pipeline

    def detect(self, image: ColorImage, settings: YoloConfig | None = None) -> list[Detection]:
        geometry = self._geometry
        if geometry is None:
            raise InferenceError("YoloDetector.load() was not called")
        cfg = settings or self._config
        tensor, box_map = self._preprocess(image, geometry)
        outputs = self._backend.run([tensor])
        raw = self._dequantize(outputs[0], self._backend.outputs[0])
        return self._postprocess(raw, box_map, geometry, cfg, image.shape[1], image.shape[0])

    def _preprocess(
        self, image: ColorImage, geometry: _InputGeometry
    ) -> tuple[np.ndarray, Letterbox]:
        padded, box_map = letterbox(image, geometry.width, geometry.height)
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        spec = geometry.spec
        if spec.dtype == np.float32 or spec.dtype == np.float16:
            data: np.ndarray = rgb.astype(np.float32) * np.float32(1.0 / 255.0)
            data = data.astype(spec.dtype)
        elif spec.quantization is not None:
            normalized = rgb.astype(np.float32) * np.float32(1.0 / 255.0)
            data = spec.quantization.quantize(normalized, spec.dtype)
        else:  # raw uint8 input without quantization params
            data = rgb.astype(spec.dtype)
        if geometry.nchw:
            data = np.transpose(data, (2, 0, 1))
        return np.ascontiguousarray(data[np.newaxis, ...]), box_map

    @staticmethod
    def _dequantize(tensor: np.ndarray, spec: TensorSpec) -> npt.NDArray[np.float32]:
        if spec.quantization is not None and not np.issubdtype(tensor.dtype, np.floating):
            return spec.quantization.dequantize(tensor)
        return tensor.astype(np.float32, copy=False)

    def _resolve_layout(self, raw: npt.NDArray[np.float32]) -> OutputLayout:
        """Infer the head layout of a 2D output.

        With known class names the channel count (4 + classes) identifies the
        layout exactly; otherwise fall back to "anchors outnumber channels".
        """
        if self._layout != "auto":
            return self._layout
        rows, cols = raw.shape
        if self._class_names:
            channels = 4 + len(self._class_names)
            if rows == channels and cols != channels:
                return "channels_first"
            if cols == channels:
                return "anchors_first"
        if cols == 6 and rows <= 1000:
            return "end2end"
        return "channels_first" if rows < cols else "anchors_first"

    def _postprocess(
        self,
        raw: npt.NDArray[np.float32],
        box_map: Letterbox,
        geometry: _InputGeometry,
        cfg: YoloConfig,
        image_width: int,
        image_height: int,
    ) -> list[Detection]:
        if raw.ndim == 3:
            raw = raw[0]
        if raw.ndim != 2:
            raise InferenceError(f"Unexpected YOLO output shape {raw.shape}")
        layout = self._resolve_layout(raw)

        if layout == "end2end":
            boxes_xyxy = raw[:, :4]
            confidences = raw[:, 4]
            class_ids = raw[:, 5].astype(np.int64)
        else:
            rows = raw.T if layout == "channels_first" else raw
            if rows.shape[1] < 5:
                raise InferenceError(f"YOLO output has too few channels: {rows.shape}")
            scores = rows[:, 4:]
            class_ids = np.argmax(scores, axis=1)
            confidences = scores[np.arange(scores.shape[0]), class_ids]
            cxcywh = rows[:, :4]
            boxes_xyxy = np.empty_like(cxcywh)
            boxes_xyxy[:, 0] = cxcywh[:, 0] - cxcywh[:, 2] / 2.0
            boxes_xyxy[:, 1] = cxcywh[:, 1] - cxcywh[:, 3] / 2.0
            boxes_xyxy[:, 2] = cxcywh[:, 0] + cxcywh[:, 2] / 2.0
            boxes_xyxy[:, 3] = cxcywh[:, 1] + cxcywh[:, 3] / 2.0

        keep = confidences >= cfg.confidence_threshold
        if cfg.class_filter:
            keep &= np.isin(class_ids, np.asarray(cfg.class_filter, dtype=np.int64))
        if not np.any(keep):
            return []
        boxes_xyxy = boxes_xyxy[keep].astype(np.float32)
        confidences = confidences[keep].astype(np.float32)
        class_ids = class_ids[keep]

        normalized = cfg.box_units == "normalized" or (
            cfg.box_units == "auto" and float(np.max(np.abs(boxes_xyxy))) <= 2.0
        )
        if normalized:
            boxes_xyxy[:, [0, 2]] *= geometry.width
            boxes_xyxy[:, [1, 3]] *= geometry.height
        boxes_xyxy = box_map.to_image(boxes_xyxy)

        order: list[int]
        if layout == "end2end":
            order = [int(i) for i in np.argsort(-confidences)[: cfg.max_detections]]
        else:
            order = self._nms(boxes_xyxy, confidences, class_ids, cfg)

        detections: list[Detection] = []
        for index in order:
            x0, y0, x1, y1 = (float(v) for v in boxes_xyxy[index])
            box = BoundingBox(x0, y0, x1 - x0, y1 - y0).clipped(image_width, image_height)
            if box.area <= 0.0:
                continue
            class_id = int(class_ids[index])
            detections.append(
                Detection(
                    box=box,
                    confidence=float(confidences[index]),
                    class_id=class_id,
                    class_name=self._class_names.get(class_id, f"class_{class_id}"),
                )
            )
        return detections

    @staticmethod
    def _nms(
        boxes_xyxy: npt.NDArray[np.float32],
        confidences: npt.NDArray[np.float32],
        class_ids: npt.NDArray[np.int64],
        cfg: YoloConfig,
    ) -> list[int]:
        offsets = (
            np.zeros((len(class_ids), 1), dtype=np.float32)
            if cfg.class_agnostic_nms
            else (class_ids.astype(np.float32) * _CLASS_OFFSET)[:, None]
        )
        shifted = boxes_xyxy + offsets
        xywh = np.column_stack(
            (
                shifted[:, 0],
                shifted[:, 1],
                shifted[:, 2] - shifted[:, 0],
                shifted[:, 3] - shifted[:, 1],
            )
        )
        indices = cv2.dnn.NMSBoxes(
            xywh.tolist(),
            confidences.tolist(),
            cfg.confidence_threshold,
            cfg.iou_threshold,
            top_k=cfg.max_detections,
        )
        flat = np.asarray(indices, dtype=np.int64).reshape(-1)
        return [int(i) for i in flat[: cfg.max_detections]]
