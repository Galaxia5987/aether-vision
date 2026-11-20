# Aether Vision

Depth-camera vision system for FRC robots, written in Python.

* **Intel RealSense D435**: aligned color + depth
* **YOLO** detection on the color stream, **depth deprojection** and
  **point-cloud clustering** for 3D target positions in the robot frame
* Inference on **CPU** (ONNX Runtime) or the **Qualcomm QCS6490 NPU**
  (LiteRT + QNN delegate, or ONNX Runtime's QNN execution provider)
* Results, telemetry and logs published to **NetworkTables** (ntcore)
* Web dashboard: live streams, telemetry, results, logs, configuration editor
* Automatic camera reconnection, pipeline error recovery, stall watchdog, and
  clean restarts, including after code changes

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design.

## Quick start

```bash
uv sync --all-extras          # or: uv sync --extra realsense
cd frontend && npm install && npm run build && cd ..
uv run aether-vision run      # supervised; dashboard on http://<host>:5803
```

On first start `config/config.json` is written with defaults (RealSense camera,
`object_detection` pipeline, NetworkTables client for team 5987).

No camera at hand? Select the `mock` camera in the dashboard, or put this in
`config/config.json`:

```json
{ "camera": { "source": { "kind": "mock", "image_path": "some_photo.jpg" } },
  "network_tables": { "mode": "server" } }
```

### Commands

| Command | Purpose |
|---|---|
| `aether-vision run [--reload]` | Supervisor + worker. Respawns the worker on restart requests and crashes; `--reload` restarts on code changes |
| `aether-vision worker` | Run the vision process directly (a restart re-execs the process) |
| `aether-vision schema` | Print the configuration JSON schemas |
| `aether-vision pipelines` | List registered pipelines |

`--config PATH` (or `AETHER_VISION_CONFIG`) selects the config file.

### Development

```bash
uv run pytest            # tests
uv run mypy              # strict type checking (src + tests)
uv run ruff check . && uv run ruff format .
cd frontend && npm run dev   # UI with hot reload, proxies /api to :5803
```

## Restarting

| Action | How | Reloads code |
|---|---|---|
| Hot config | Save a setting in the UI (fields without ⟳) | — |
| Pipeline restart | UI button, or saving a ⟳ pipeline field | no |
| Camera restart | UI button, or saving camera settings | no |
| Process restart | UI button, `--reload` file change, stall watchdog | **yes** |

A process restart shuts down gracefully: threads stop, the camera is released
and NT is flushed. Then the supervisor starts a fresh worker, or the
unsupervised worker `exec`s itself.

## Writing a pipeline

```python
# src/aether_vision/pipeline/pipelines/my_pipeline.py
from pydantic import Field

from aether_vision.config.base import RESTART_REQUIRED, ConfigModel
from aether_vision.core.types import FrameSet, StreamKind
from aether_vision.pipeline.base import Pipeline
from aether_vision.pipeline.pipelines.stages import DetectStage
from aether_vision.pipeline.registry import register_pipeline
from aether_vision.pipeline.result import PipelineResult, Target
from aether_vision.inference.yolo import YoloConfig


class MyConfig(ConfigModel):              # shown in the UI automatically
    detector: YoloConfig = Field(default_factory=YoloConfig)
    min_area_px: float = Field(400.0, ge=0.0)          # applied live
    mode: str = Field("fast", json_schema_extra=RESTART_REQUIRED)  # restarts pipeline


@register_pipeline
class MyPipeline(Pipeline[MyConfig]):
    name = "my_pipeline"
    config_type = MyConfig
    required_streams = frozenset({StreamKind.COLOR})

    def setup(self) -> None:              # runs on the pipeline thread
        self.detect = self.add_stage(DetectStage(lambda: self.config.detector))

    def process(self, frames: FrameSet) -> PipelineResult:
        detections = [
            d for d in self.detect(frames.require_color())   # stage call is timed
            if d.box.area >= self.config.min_area_px         # self.config is always current
        ]
        self.telemetry.put("kept", len(detections))          # -> NT + dashboard
        return PipelineResult(
            self.name, frames.frame_number, frames.capture_time_s,
            targets=tuple(Target(d) for d in detections),
        )
```

Then import the module in `pipeline/pipelines/__init__.py`.

* `self.telemetry.put(key, value)` takes bools, numbers, strings, sequences or
  numpy arrays. It never blocks, and it is published to NT at
  `/<root>/pipeline/<name>/<key>` and to the dashboard.
* `self.debug.wants("name")` / `self.debug.publish("name", image)` add a debug
  stream to the dashboard. Rendering is skipped when nobody is watching.
* `self.logger` is a normal `logging.Logger`. Records go to the console, the
  rotating file, the dashboard and NT (`/<root>/log/messages`).
* Stages (`Stage[In, Out]`) get `setup` / `process` / `teardown`, automatic
  `latency_ms` telemetry and their own telemetry scope.

## NetworkTables layout

```
/AetherVision/results/timestamp_us        int     capture time, robot (server) clock
/AetherVision/results/latency_ms          double  capture → result
/AetherVision/results/count, has_target, frame, pipeline, json
/AetherVision/results/targets_flat        double[] 10 per target, robot frame (see targets_flat_fields)
/AetherVision/results/best/{x,y,z,distance,confidence,class_id,class_name}
/AetherVision/status/{heartbeat,uptime_s,version,restart_pending}
/AetherVision/camera/{state,connected,fps,reconnects,last_error,...}
/AetherVision/pipeline/{state,fps,latency_ms,last_error,...}
/AetherVision/pipeline/<name>/...         pipeline + stage telemetry
/AetherVision/log/{messages,last_error}
```

All `results/*` values of one frame share the capture timestamp. Positions use
the WPILib robot frame (x forward, y left, z up). Set the camera pose under
`localization.extrinsics` in the pipeline settings.

## QCS6490

Two options:

1. **LiteRT + QNN delegate (recommended).** Export a quantized TFLite model, e.g.
   with Ultralytics `yolo export format=tflite int8=True` or from Qualcomm AI Hub.
   Install the extra (`uv sync --extra litert`), then set
   `detector.backend = {"kind": "litert", "delegate": "qnn", "qnn_backend": "htp"}`
   and `detector.model_path` to the `.tflite`. The delegate library
   (`libQnnTFLiteDelegate.so`) comes with the Qualcomm AI Engine Direct SDK /
   Qualcomm Linux image. Set `delegate_path` if it is not on the library path.
   If the model outputs normalized boxes, set `box_units` to `normalized`; the
   `auto` default usually detects this.
2. **ONNX Runtime with QNN EP.** With an ONNX Runtime build that includes
   `QNNExecutionProvider`, set
   `detector.backend.providers = ["QNNExecutionProvider", "CPUExecutionProvider"]`.

`pyrealsense2` has no PyPI wheels for some aarch64 platforms. If so, build
librealsense with `-DBUILD_PYTHON_BINDINGS=ON` and install it into the venv.
