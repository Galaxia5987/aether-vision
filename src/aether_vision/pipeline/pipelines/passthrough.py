"""Camera check pipeline: publishes an annotated color stream, produces no targets."""

from __future__ import annotations

from pydantic import Field

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import FrameSet, StreamKind
from aether_vision.pipeline.base import Pipeline
from aether_vision.pipeline.registry import register_pipeline
from aether_vision.pipeline.result import PipelineResult
from aether_vision.vision.drawing import draw_text


class PassthroughConfig(ConfigModel):
    overlay: bool = Field(True, description="Draw frame info on the debug stream")


@register_pipeline
class PassthroughPipeline(Pipeline[PassthroughConfig]):
    name = "passthrough"
    config_type = PassthroughConfig
    required_streams = frozenset({StreamKind.COLOR})
    description = "No processing; useful to verify the camera"

    def setup(self) -> None:
        pass

    def process(self, frames: FrameSet) -> PipelineResult:
        color = frames.require_color()
        self.telemetry.put("mean_brightness", round(float(color.mean()), 2))
        if self.config.overlay and self.debug.wants("annotated"):
            canvas = color.copy()
            draw_text(canvas, f"frame {frames.frame_number}", (8, 20))
            self.debug.publish("annotated", canvas)
        return self.empty_result(frames)
