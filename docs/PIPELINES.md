# Writing pipelines

A **pipeline** turns each camera frame into results. It is built from
**stages**: small, reusable steps that are timed automatically. Each pipeline
declares its own settings, and the dashboard shows them with no frontend work.

Built-in pipelines live in `src/aether_vision/pipeline/pipelines/`:

- `object_detection.py`: YOLO, then 3D localization from depth
- `passthrough.py`: the minimal example
- `stages.py`: reusable stages (`DetectStage`, `LocalizeStage`, `AnnotateStage`)

## A complete example

Create `src/aether_vision/pipeline/pipelines/closest_object.py`:

```python
"""Report only the closest detected object."""

from pydantic import Field

from aether_vision.config.base import RESTART_REQUIRED, ConfigModel
from aether_vision.core.types import FrameSet, StreamKind
from aether_vision.inference.yolo import YoloConfig
from aether_vision.pipeline.base import Pipeline
from aether_vision.pipeline.pipelines.stages import (
    DetectStage,
    LocalizationConfig,
    LocalizationInput,
    LocalizeStage,
)
from aether_vision.pipeline.registry import register_pipeline
from aether_vision.pipeline.result import PipelineResult


class ClosestObjectConfig(ConfigModel):
    detector: YoloConfig = Field(default_factory=YoloConfig)
    localization: LocalizationConfig = Field(default_factory=LocalizationConfig)
    max_distance_m: float = Field(3.0, gt=0.0, description="Ignore objects farther than this")
    label: str = Field("closest", json_schema_extra=RESTART_REQUIRED)


@register_pipeline
class ClosestObjectPipeline(Pipeline[ClosestObjectConfig]):
    name = "closest_object"
    config_type = ClosestObjectConfig
    required_streams = frozenset({StreamKind.COLOR, StreamKind.DEPTH})
    description = "Publishes only the nearest object within range"

    def setup(self) -> None:
        self.detect = self.add_stage(DetectStage(lambda: self.config.detector))
        self.localize = self.add_stage(LocalizeStage(lambda: self.config.localization))

    def process(self, frames: FrameSet) -> PipelineResult:
        detections = self.detect(frames.require_color())
        targets = self.localize(LocalizationInput(frames, detections))
        in_range = [
            t for t in targets
            if t.distance_m is not None and t.distance_m <= self.config.max_distance_m
        ]
        in_range.sort(key=lambda t: t.distance_m or 0.0)
        self.telemetry.put("in_range", len(in_range))
        return PipelineResult(
            self.name, frames.frame_number, frames.capture_time_s, targets=tuple(in_range[:1])
        )
```

Register it by adding the module to `pipeline/pipelines/__init__.py`:

```python
from aether_vision.pipeline.pipelines import closest_object, object_detection, passthrough
```

Restart the process. `closest_object` then appears in the dashboard's pipeline
list, with all its settings.

## The pieces

### Settings

Subclass `ConfigModel` (an immutable pydantic model) and use `Field` for
defaults, limits (`ge`, `le`, `gt`) and descriptions. All of these show up in
the dashboard.

- Read settings through `self.config` **every frame**. It always returns the
  latest saved values, so changes apply on the next frame.
- Mark a field with `json_schema_extra=RESTART_REQUIRED` when changing it needs
  a rebuild (e.g. a model path). Saving a change to it rebuilds the pipeline,
  and the dashboard shows ⟳ next to it.
- Settings are checked when saved. Invalid values are rejected with a message
  and never reach the pipeline.

### Lifecycle

| Method | When | Thread |
|---|---|---|
| `setup()` | Pipeline start or rebuild | pipeline thread |
| `process(frames)` | Every new frame | pipeline thread |
| `on_teardown()` | Before rebuild or shutdown | pipeline thread |

Everything runs on one thread, so pipeline code needs no locks. If `process`
raises, the error is logged and the frame skipped. After
`watchdog.max_consecutive_errors` errors in a row, the pipeline is rebuilt.

`FrameSet` gives you `color` (BGR), `depth` (aligned to color, raw units;
multiply by `depth_scale_m` for meters), `intrinsics`, `frame_number`, and
`capture_time_s`. Use `require_color()` / `require_depth()` to get them
without `None` checks. Declare `required_streams` so the pipeline only runs
with a suitable camera.

### Stages

```python
from aether_vision.core.types import ColorImage
from aether_vision.pipeline.base import Stage


class GrayscaleStage(Stage[ColorImage, ColorImage]):
    def setup(self) -> None: ...         # optional: load resources
    def process(self, value: ColorImage) -> ColorImage:
        ...
    def teardown(self) -> None: ...      # optional: release resources
```

Add stages with `self.add_stage(...)` in `setup()` and call them like
functions: `self.gray(image)`. Each call publishes
`pipeline/<pipeline>/stages/<stage>/latency_ms`. Stages are torn down
automatically. A stage's name comes from its class (`GrayscaleStage` →
`grayscale`) or the `name=` argument.

To let a stage follow live settings, pass it a function that returns them,
as in `DetectStage(lambda: self.config.detector)`.

### Telemetry

```python
self.telemetry.put("in_range", 3)                 # pipeline/<name>/in_range
self.telemetry.put("center", [1.0, 2.0])          # number arrays, numpy arrays work too
stage_scope = self.telemetry.scope("debug")       # pipeline/<name>/debug/...
with self.telemetry.timer("postprocess_ms"):      # time any block
    ...
```

Values can be bools, numbers, strings, lists of those, or numpy arrays.
`put` never blocks. Values are sent to NetworkTables (under `/AetherVision/`)
and the dashboard's Telemetry tab. Inside a stage, use `self.telemetry` the
same way; it is scoped to that stage.

### Debug images

```python
if self.debug.wants("mask"):            # skip the work when nobody watches
    self.debug.publish("mask", image)   # appears in the dashboard stream list
```

### Logging

`self.logger` (pipelines) and `self.logger` (stages) are standard Python
loggers. Messages go to the console, `logs/aether-vision.log`, the dashboard,
and NetworkTables `log/messages`.

### Results

Return a `PipelineResult`. Each `Target` has a `detection` (box, class,
confidence) and optionally `position_camera`, `position_robot`, `extent_m`, and
`point_count`. The first target is published as `results/best`. Use
`self.empty_result(frames)` when there is nothing to report.

## Testing a pipeline

Run it against the mock camera with a test image:

```json
{ "camera": { "source": { "kind": "mock", "image_path": "test.jpg" } },
  "pipeline": { "name": "closest_object" },
  "network_tables": { "mode": "server" } }
```

```bash
uv run aether-vision run --reload --config my-test-config.json
```

With `--reload`, saving a source file restarts the process with the new code.
For unit tests, `tests/test_pipeline_runner.py` shows how to drive a pipeline
with synthetic frames.
