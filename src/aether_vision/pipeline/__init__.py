"""Pipeline framework: stages, pipelines, registry and the runner thread."""

from aether_vision.pipeline.base import Pipeline, PipelineContext, Stage
from aether_vision.pipeline.registry import (
    available_pipelines,
    get_pipeline,
    pipeline_schemas,
    register_pipeline,
    validate_selection,
)
from aether_vision.pipeline.result import PipelineResult, Target

__all__ = [
    "Pipeline",
    "PipelineContext",
    "PipelineResult",
    "Stage",
    "Target",
    "available_pipelines",
    "get_pipeline",
    "pipeline_schemas",
    "register_pipeline",
    "validate_selection",
]
