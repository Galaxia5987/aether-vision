"""Debug-image rendering helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import cv2
import numpy as np

from aether_vision.core.types import ColorImage, DepthImage

_PALETTE: Final = (
    (56, 56, 255),
    (151, 157, 255),
    (31, 112, 255),
    (29, 178, 255),
    (49, 210, 207),
    (10, 249, 72),
    (23, 204, 146),
    (134, 219, 61),
    (52, 147, 26),
    (187, 212, 0),
)


def class_color(class_id: int) -> tuple[int, int, int]:
    return _PALETTE[class_id % len(_PALETTE)]


def draw_box(
    image: ColorImage,
    xywh: tuple[float, float, float, float],
    color: tuple[int, int, int],
    lines: Sequence[str],
) -> None:
    """Draw a rectangle with stacked label lines above it (in place)."""
    x, y, w, h = (round(v) for v in xywh)
    cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.45
    line_height = 16
    top = max(y - line_height * len(lines), 0)
    for index, text in enumerate(lines):
        (tw, th), _ = cv2.getTextSize(text, font, scale, 1)
        ty = top + index * line_height
        cv2.rectangle(image, (x, ty), (x + tw + 4, ty + line_height), color, -1)
        cv2.putText(image, text, (x + 2, ty + th + 3), font, scale, (255, 255, 255), 1, cv2.LINE_AA)


def draw_text(image: ColorImage, text: str, origin: tuple[int, int]) -> None:
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(image, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)


def colorize_depth(depth: DepthImage, depth_scale_m: float, max_depth_m: float = 6.0) -> ColorImage:
    """Map depth to a color image; invalid (zero) depth is black."""
    meters = depth.astype(np.float32) * np.float32(depth_scale_m)
    normalized = np.clip(meters / max_depth_m, 0.0, 1.0)
    scaled = (255.0 - normalized * 255.0).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    colored[depth == 0] = 0
    return np.asarray(colored, dtype=np.uint8)
