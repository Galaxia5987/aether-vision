"""Reusable stages: detection, 3D localization and annotation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import Field

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import ColorImage, Detection, FloatArray, FrameSet
from aether_vision.inference.yolo import YoloConfig, YoloDetector
from aether_vision.pipeline.base import Stage
from aether_vision.pipeline.result import Target, Vec3
from aether_vision.vision.clustering import ClusteringConfig, euclidean_clusters
from aether_vision.vision.deprojection import roi_point_cloud
from aether_vision.vision.drawing import class_color, draw_box, draw_text
from aether_vision.vision.transforms import CameraExtrinsics, CameraToRobot

# ----------------------------------------------------------------------- detect


class DetectStage(Stage[ColorImage, list[Detection]]):
    """Runs YOLO on the color image."""

    def __init__(self, config: Callable[[], YoloConfig], name: str | None = None) -> None:
        super().__init__(name)
        self._config = config
        self._detector: YoloDetector | None = None

    def setup(self) -> None:
        detector = YoloDetector(self._config())
        detector.load()
        self._detector = detector
        self.telemetry.put("backend", detector.backend_description)
        self.telemetry.put("classes", len(detector.class_names))

    def process(self, value: ColorImage) -> list[Detection]:
        if self._detector is None:
            raise RuntimeError("DetectStage used before setup()")
        detections = self._detector.detect(value, self._config())
        self.telemetry.put("count", len(detections))
        return detections

    def teardown(self) -> None:
        if self._detector is not None:
            self._detector.close()
            self._detector = None


# --------------------------------------------------------------------- localize


class LocalizationConfig(ConfigModel):
    enabled: bool = True
    roi_scale: float = Field(
        0.7, gt=0.05, le=1.0, description="Fraction of the box (about its center) sampled"
    )
    sample_stride: int = Field(2, ge=1, le=16, description="Use every Nth depth pixel")
    min_depth_m: float = Field(0.15, ge=0.0, le=20.0)
    max_depth_m: float = Field(8.0, gt=0.0, le=50.0)
    max_points: int = Field(
        3000, ge=50, le=200_000, description="Depth points per box are subsampled to this"
    )
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    cluster_selection: Literal["largest", "nearest"] = "largest"
    extrinsics: CameraExtrinsics = Field(default_factory=CameraExtrinsics)


@dataclass(frozen=True, slots=True)
class LocalizationInput:
    frames: FrameSet
    detections: list[Detection]


class LocalizeStage(Stage[LocalizationInput, list[Target]]):
    """Deprojects each detection's depth ROI, clusters it, and picks the object cluster."""

    def __init__(self, config: Callable[[], LocalizationConfig], name: str | None = None) -> None:
        super().__init__(name)
        self._config = config
        self._transform_for: CameraExtrinsics | None = None
        self._transform: CameraToRobot | None = None

    def _camera_to_robot(self, extrinsics: CameraExtrinsics) -> CameraToRobot:
        if self._transform is None or extrinsics != self._transform_for:
            self._transform = CameraToRobot(extrinsics)
            self._transform_for = extrinsics
        return self._transform

    def process(self, value: LocalizationInput) -> list[Target]:
        config = self._config()
        frames = value.frames
        if not config.enabled or frames.depth is None or frames.intrinsics is None:
            return [Target(detection) for detection in value.detections]
        transform = self._camera_to_robot(config.extrinsics)
        targets = [
            self._localize(detection, frames, config, transform) for detection in value.detections
        ]
        self.telemetry.put("localized", sum(t.position_camera is not None for t in targets))
        return targets

    @staticmethod
    def _localize(
        detection: Detection,
        frames: FrameSet,
        config: LocalizationConfig,
        transform: CameraToRobot,
    ) -> Target:
        points = roi_point_cloud(
            frames.require_depth(),
            frames.depth_scale_m,
            frames.require_intrinsics(),
            detection.box.shrunk(config.roi_scale),
            stride=config.sample_stride,
            min_depth_m=config.min_depth_m,
            max_depth_m=config.max_depth_m,
        )
        if points.shape[0] > config.max_points:
            keep = np.linspace(0, points.shape[0] - 1, config.max_points).astype(np.int64)
            points = points[keep]
        clusters = euclidean_clusters(points, config.clustering)
        if not clusters:
            return Target(detection, point_count=int(points.shape[0]))
        chosen = (
            min(clusters, key=lambda c: c.distance)
            if config.cluster_selection == "nearest"
            else clusters[0]
        )
        return Target(
            detection=detection,
            position_camera=_vec3(chosen.centroid),
            position_robot=_vec3(transform.apply(chosen.centroid)),
            extent_m=_vec3(chosen.extent),
            point_count=chosen.size,
        )


def _vec3(values: FloatArray) -> Vec3:
    x, y, z = (float(v) for v in values)
    return (x, y, z)


# --------------------------------------------------------------------- annotate


@dataclass(frozen=True, slots=True)
class AnnotationInput:
    image: ColorImage
    targets: list[Target]
    header: str


class AnnotateStage(Stage[AnnotationInput, ColorImage]):
    """Draws targets on a copy of the image."""

    def process(self, value: AnnotationInput) -> ColorImage:
        canvas = value.image.copy()
        for target in value.targets:
            det = target.detection
            lines = [f"{det.class_name} {det.confidence:.2f}"]
            if target.position_robot is not None and target.distance_m is not None:
                x, y, z = target.position_robot
                lines.append(f"{target.distance_m:.2f}m ({x:+.2f},{y:+.2f},{z:+.2f})")
            box = det.box
            draw_box(
                canvas, (box.x, box.y, box.width, box.height), class_color(det.class_id), lines
            )
        draw_text(canvas, value.header, (8, canvas.shape[0] - 10))
        return canvas
