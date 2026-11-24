"""YOLO on color, depth deprojection + point-cloud clustering for 3D target positions."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import FrameSet, StreamKind
from aether_vision.inference.yolo import YoloConfig
from aether_vision.pipeline.base import Pipeline
from aether_vision.pipeline.pipelines.stages import (
    AnnotateStage,
    AnnotationInput,
    DetectStage,
    LocalizationConfig,
    LocalizationInput,
    LocalizeStage,
)
from aether_vision.pipeline.registry import register_pipeline
from aether_vision.pipeline.result import PipelineResult, Target

ANNOTATED_STREAM = "annotated"


class ObjectDetectionConfig(ConfigModel):
    detector: YoloConfig = Field(default_factory=YoloConfig)
    localization: LocalizationConfig = Field(default_factory=LocalizationConfig)
    sort_by: Literal["confidence", "distance", "area"] = "confidence"
    max_targets: int = Field(10, ge=1, le=100)
    require_position: bool = Field(
        False, description="Drop targets whose 3D position could not be computed"
    )


@register_pipeline
class ObjectDetectionPipeline(Pipeline[ObjectDetectionConfig]):
    name = "object_detection"
    config_type = ObjectDetectionConfig
    required_streams = frozenset({StreamKind.COLOR, StreamKind.DEPTH})
    description = "YOLO detection on color, 3D localization from aligned depth"

    def setup(self) -> None:
        self.detect = self.add_stage(DetectStage(lambda: self.config.detector))
        self.localize = self.add_stage(LocalizeStage(lambda: self.config.localization))
        self.annotate = self.add_stage(AnnotateStage())

    def process(self, frames: FrameSet) -> PipelineResult:
        config = self.config
        color = frames.require_color()
        detections = self.detect(color)
        targets = self.localize(LocalizationInput(frames, detections))
        if config.require_position:
            targets = [t for t in targets if t.position_camera is not None]
        targets = self._rank(targets, config.sort_by)[: config.max_targets]

        self.telemetry.put("targets", len(targets))
        if self.debug.wants(ANNOTATED_STREAM):
            header = f"#{frames.frame_number} targets: {len(targets)}"
            self.debug.publish(
                ANNOTATED_STREAM, self.annotate(AnnotationInput(color, targets, header))
            )
        return PipelineResult(
            self.name, frames.frame_number, frames.capture_time_s, targets=tuple(targets)
        )

    @staticmethod
    def _rank(targets: list[Target], sort_by: str) -> list[Target]:
        if sort_by == "distance":
            return sorted(
                targets,
                key=lambda t: (t.distance_m is None, t.distance_m or 0.0, -t.detection.confidence),
            )
        if sort_by == "area":
            return sorted(targets, key=lambda t: -t.detection.box.area)
        return sorted(targets, key=lambda t: -t.detection.confidence)
