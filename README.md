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
| OS | Linux (Ubuntu 22.04 or newer / glibc 2.35+, x86-64 or ARM64). macOS works for development. |
| Camera | Intel RealSense D435 (or any D4xx). Optional for development. |
| Internet | Needed during install |

Nothing else needs to be installed first. The installer sets up Python,
Node.js and everything else itself.

## Install

```bash
git clone https://github.com/Galaxia5987/aether-vision.git
cd aether-vision
scripts/install.sh
```

The installer checks each item and installs only what's missing:

1. **System packages** with apt or dnf: `curl`, `tar`, `xz`, `libusb`, `udev`
2. **[uv](https://docs.astral.sh/uv/)** into `~/.local/bin`, checksum-verified
3. **Python 3.12** (managed by uv) and the exact package versions from `uv.lock`, in `.venv/`
4. **Node.js 22**, a private copy in `.tools/node`, only if the system Node.js is
   missing or too old (checksum-verified)
5. **The dashboard**, built into `frontend/dist`
6. **RealSense udev rules**, so the camera works without root
7. **On a Qualcomm QCS6490** (e.g. RUBIK Pi 3, detected automatically): Qualcomm's
   AI packages with the QNN delegate for the NPU, and the LiteRT version it is
   validated with

Steps 1, 6 and 7 change the system and use `sudo` (you may be asked for your
password). Running it again is safe and takes a few seconds.

| Option | What it does |
|---|---|
| `--service` | Starts Aether Vision on boot with systemd |
| `--mock-config` | Uses a simulated camera, for machines without one |
| `--dev` / `--test` | Installs development tools / also runs the test suite |
| `--no-frontend`, `--no-realsense`, `--no-litert`, `--no-udev` | Skip a component |
| `--no-system-packages` | Don't touch OS packages (install them yourself) |
| `--qcs6490` / `--no-qcs6490` | Force or skip the QCS6490 setup |

A typical robot coprocessor install is `scripts/install.sh --service`.
Run `scripts/install.sh --help` for all options.

<details>
<summary>Manual install</summary>

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # if uv is missing
uv sync --extra realsense --extra litert     # QCS6490: --extra qcs6490 instead of litert
(cd frontend && npm ci && npm run build)
```
</details>

## Usage

```bash
uv run aether-vision run
```

(If uv was just installed, open a new shell first, or use
`.venv/bin/aether-vision run`.)

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
