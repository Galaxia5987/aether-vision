# Aether Vision

Depth-camera vision for FRC robots. Aether Vision finds objects with YOLO,
measures where they are in 3D with an Intel RealSense depth camera, and
publishes the results to the robot over NetworkTables.

```
RealSense ──► YOLO on color ──► depth points in each box ──► main cluster ──► 3D position ──► NetworkTables
                (NPU)                                                                  └────► web dashboard
```

- YOLO with LiteRT, on the **Qualcomm QCS6490 NPU** (QNN delegate) when it is
  available, otherwise on the CPU.
- Target positions in the WPILib robot frame, timestamped with the robot's
  clock for latency compensation.
- Web dashboard: live streams, results, telemetry, logs and a settings editor.
  Settings apply immediately.
- Reconnects the camera by itself when it is unplugged.

## Install

On Linux (Ubuntu 22.04+, x86-64 or ARM64):

```bash
git clone https://github.com/Galaxia5987/aether-vision.git
cd aether-vision
scripts/install.sh            # add --service to start on boot
```

The installer sets up uv, Python, the packages from `uv.lock`, Node.js (to
build the dashboard), the RealSense udev rules, and on a QCS6490 Qualcomm's
NPU runtime. Run `scripts/install.sh --help` for options. Manual install:

```bash
uv sync --extra realsense            # QCS6490: also --extra qcs6490
(cd frontend && npm ci && npm run build)
```

## Usage

```bash
uv run aether-vision                                    # config/config.json
uv run aether-vision --config examples/config.mock.json # no camera: simulated one
```

Open the dashboard at **http://\<coprocessor\>:5803**. The first start writes
`config/config.json` with defaults. Every setting is editable in the
dashboard. The main ones:

| Setting | Meaning |
|---|---|
| `camera` | `realsense` or `mock`, resolution, fps, color exposure (empty = auto) |
| `detector.model_path` / `labels_path` | TFLite model (int8 for the NPU) and its class names, one per line |
| `detector.use_npu` | Use the QNN delegate; falls back to the CPU if it can't load |
| `detector.confidence_threshold`, `iou_threshold`, `max_detections`, `class_filter` | Detection filtering |
| `camera_mount` | Where the camera is on the robot (WPILib axes, meters/degrees; pitch is positive **down**) |
| `network_tables.team` / `server_address` | Where the robot is |
| `web.port` | Dashboard port |

Changing the model reloads it; changing NetworkTables or web settings restarts
the process. The dashboard's **Restart** button restarts the process, which
also reloads code from disk.

Supported models: Qualcomm AI Hub exports (separate `boxes`, `scores`,
`classes` outputs) and Ultralytics TFLite exports
(`yolo export model=best.pt format=tflite int8=True`).

## On the robot

Topics under `/AetherVision/results`, stamped with the capture time:

| Topic | Type | Meaning |
|---|---|---|
| `poses` | `Pose3d[]` struct | Every target with a 3D position, robot-relative |
| `pose_class_ids` | int[] | Class id of each entry in `poses` |
| `best/has_pose` | boolean | `best/pose` is valid for this frame |
| `best/pose` | `Pose3d` struct | The most confident target |
| `best/x`, `y`, `z`, `distance` | double | Same as `best/pose` as numbers, and distance from the camera (NaN without depth) |
| `best/confidence`, `class_id`, `class_name` | | What was detected |
| `timestamp_us` | int | Capture time on the robot's clock |
| `latency_ms` | double | Capture to result |

Positions are in meters in the WPILib robot frame (x forward, y left, z up)
from the robot center. Depth gives position only, so pose rotations are zero.
Telemetry (camera and pipeline state, fps, timings) is under `/AetherVision`
too. In Java:

```java
NetworkTable vision = NetworkTableInstance.getDefault().getTable("AetherVision/results");
StructSubscriber<Pose3d> bestPose =
    vision.getStructTopic("best/pose", Pose3d.struct).subscribe(new Pose3d());
BooleanSubscriber hasPose = vision.getSubTable("best").getBooleanTopic("has_pose").subscribe(false);
IntegerSubscriber captureTime = vision.getIntegerTopic("timestamp_us").subscribe(0);

if (hasPose.get()) {
  Pose3d robotRelative = bestPose.get();
  double captureSeconds = captureTime.get() / 1e6;  // same clock as Timer.getFPGATimestamp()
  poseEstimator.sampleAt(captureSeconds).ifPresent(robotPose -> {
    Pose3d onField = new Pose3d(robotPose).transformBy(new Transform3d(new Pose3d(), robotRelative));
  });
}
```

## Code

```
src/aether_vision/
  app.py            wires everything together, applies config changes
  camera.py         RealSense and mock sources, reconnecting camera thread
  detector.py       YOLO on LiteRT (NPU or CPU)
  localization.py   depth -> points -> main cluster -> robot-frame position
  pipeline.py       the vision loop
  networktables.py  results and telemetry to the robot
  web.py            dashboard API and streams
  config.py         settings schema and config file
frontend/           Svelte dashboard
```

See [Deployment](docs/DEPLOYMENT.md) for coprocessor setup and troubleshooting,
and [Contributing](CONTRIBUTING.md) for the development workflow.
