# Aether Vision

Depth-camera vision for FRC robots. Aether Vision finds objects with YOLO,
measures where they are in 3D with an Intel RealSense depth camera, and
publishes the results to the robot over NetworkTables.

```
RealSense D435 ──► YOLO on color ──► depth points in each box ──► clustering ──► 3D position ──► NetworkTables
                                                                                        └──────► web dashboard
```

**Features**

- Intel RealSense D435/D4xx with color aligned to depth. USB webcams and a
  mock camera work for testing.
- YOLO inference on CPU (ONNX Runtime) or on the **Qualcomm QCS6490 NPU**
  (LiteRT + QNN delegate).
- Target positions in the WPILib robot frame, timestamped with the robot's
  clock for latency compensation.
- Web dashboard with live camera streams, results, telemetry, logs, and a
  settings editor. Most settings apply immediately.
- Recovers on its own from camera unplugs, pipeline errors, crashes, and stalls.
- Pipelines are plain Python classes, easy to change or add.

## Requirements

| | |
|---|---|
| OS | Linux (Ubuntu 22.04 or newer, x86-64 or ARM64). macOS works for development. |
| Python | Installed automatically (3.12) by [uv](https://docs.astral.sh/uv/) |
| Node.js | 20.19+ or 22.12+, only to build the dashboard |
| Camera | Intel RealSense D435 (or any D4xx). Optional for development. |

## Install

```bash
git clone https://github.com/Galaxia5987/aether-vision.git
cd aether-vision
scripts/install.sh
```

The script installs uv if needed, creates the Python environment in `.venv/`,
and builds the dashboard. Useful options:

| Option | What it does |
|---|---|
| `--udev` | Lets the RealSense camera work without root (installs udev rules, asks for sudo) |
| `--service` | Starts Aether Vision on boot with systemd (asks for sudo) |
| `--mock-config` | Uses a simulated camera, for machines without one |
| `--dev` / `--test` | Installs development tools / also runs the test suite |
| `--no-frontend`, `--no-realsense`, `--no-litert` | Skip a component |

A typical robot coprocessor install is `scripts/install.sh --udev --service`.
Run `scripts/install.sh --help` for all options.

<details>
<summary>Manual install</summary>

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # if uv is missing
uv sync --extra realsense --extra litert
(cd frontend && npm ci && npm run build)
```
</details>

## Usage

```bash
uv run aether-vision run
```

Open the dashboard at **http://\<coprocessor\>:5803**. On first start a
`config/config.json` with default settings is created: RealSense camera, the
`object_detection` pipeline, and a NetworkTables client for team 5987.

No camera? Start with the mock camera and a local NetworkTables server:

```bash
uv run aether-vision run --config examples/config.mock.json
```

| Command | Purpose |
|---|---|
| `aether-vision run` | Normal mode. A supervisor restarts the vision process after crashes and restart requests |
| `aether-vision run --reload` | Development: restart automatically when source files change |
| `aether-vision worker` | Run without the supervisor |
| `aether-vision pipelines` | List available pipelines |
| `aether-vision schema` | Print the full configuration schema (JSON) |

All commands take `--config PATH`, or the `AETHER_VISION_CONFIG` environment
variable.

### Dashboard

- **Status**: camera, pipeline and NetworkTables health, with buttons to
  restart the pipeline, the camera, or the whole process. A process restart
  also reloads code.
- **Streams**: `annotated` (detections drawn on the image), `color`, and
  `depth`. Add views with **+ view**.
- **Results / Telemetry / Logs**: live tabs at the bottom.
- **Configuration**: every setting. Click **Save** to apply. Settings marked
  ⟳ restart the pipeline or process; all others apply on the next frame.

### On the robot

The main topics, under `/AetherVision`:

| Topic | Type | Meaning |
|---|---|---|
| `results/has_target` | boolean | At least one target in the latest frame |
| `results/best/x`, `y`, `z` | double | Position of the best target, meters, robot frame (x forward, y left, z up) |
| `results/best/distance` | double | Distance from the camera, meters |
| `results/best/class_name` | string | What was detected |
| `results/timestamp_us` | int | Capture time on the robot's clock, for latency compensation |
| `results/targets_flat` | double[] | All targets, 10 numbers each (field names in `results/targets_flat_fields`) |
| `status/heartbeat` | int | Increments twice a second while running |

Set where the camera is mounted (`localization.extrinsics` in the pipeline
settings) so positions are relative to the robot center. Positions are NaN
when depth was unavailable.

## Documentation

| Document | Contents |
|---|---|
| [Configuration](docs/CONFIGURATION.md) | Every setting, including camera mounting and NetworkTables |
| [Deployment](docs/DEPLOYMENT.md) | Coprocessor setup, systemd, QCS6490 NPU, updating, troubleshooting |
| [Writing pipelines](docs/PIPELINES.md) | Adding your own processing, telemetry and settings |
| [Architecture](docs/ARCHITECTURE.md) | How the system is designed |
| [Contributing](CONTRIBUTING.md) | Development workflow and checks |

## Project layout

```
src/aether_vision/   Python package (camera, inference, vision, pipeline, web, ...)
frontend/            Svelte dashboard
tests/               pytest suite
models/              YOLO models (yolov8n.onnx, COCO classes)
examples/            Example configurations
scripts/install.sh   Installer
deploy/              systemd unit template
docs/                Documentation
```

## License note

The bundled `models/yolov8n.onnx` is an Ultralytics YOLOv8n model, licensed
under AGPL-3.0. Use your own trained model for competition objects (see
[Configuration](docs/CONFIGURATION.md#detector)).
