# Configuration

Settings live in `config/config.json`. You can edit them in the dashboard
(recommended) or in the file. The file is validated on load. If it is invalid,
it is renamed to `config.invalid-<time>.json` and defaults are used, so a typo
never stops the robot's vision.

**When changes apply:**

- Most settings apply on the next frame.
- Settings marked **⟳** rebuild the pipeline (pipeline settings) or need a
  process restart (NetworkTables, web, logging). The dashboard shows a notice
  when a process restart is pending.
- Camera settings restart the camera.

Only the settings you want to change need to be in the file; everything else
uses the defaults below. See `examples/` for complete files. To print the
machine-readable schema, run `uv run aether-vision schema`.

## Camera — `camera`

### `camera.source`

Pick a camera with `kind`.

**`"kind": "realsense"`** (default)

| Setting | Default | Description |
|---|---|---|
| `serial` | `""` | Camera serial number; empty uses the first camera found |
| `width`, `height`, `fps` | `640`, `480`, `30` | Stream mode for both color and depth |
| `enable_depth` | `true` | Required by `object_detection` |
| `emitter_enabled` | `true` | IR pattern projector; improves depth on plain surfaces |
| `laser_power` | `null` | Projector power (0–360); `null` keeps the camera default |
| `color_auto_exposure` | `true` | Turn off and set `color_exposure_us` to reduce motion blur |
| `color_exposure_us` | `null` | Manual exposure, used when auto exposure is off |
| `filters.spatial` / `temporal` / `hole_filling` | `false` / `true` / `false` | RealSense depth filters |
| `hardware_reset_after_failures` | `3` | Reset the camera after this many failed reconnects; `0` disables |

**`"kind": "usb"`**: a webcam. It has no depth, so use it with `passthrough`
or a color-only pipeline. Settings: `device_index`, `width`, `height`, `fps`,
and `horizontal_fov_deg` (used to estimate the lens geometry).

**`"kind": "mock"`**: a simulated camera with a moving ball and matching
depth. Set `image_path` to a photo to test YOLO on real images.
`target_depth_m` and `background_depth_m` set the simulated distances.

### `camera.reconnect`

| Setting | Default | Description |
|---|---|---|
| `initial_delay_s` / `max_delay_s` | `0.5` / `5.0` | Wait between reconnect attempts (doubles each time) |
| `frame_timeout_s` | `1.0` | How long to wait for a frame |
| `max_consecutive_timeouts` | `3` | Missed frames in a row before reconnecting |

## Pipeline — `pipeline`

```json
"pipeline": { "name": "object_detection", "settings": { ... } }
```

`name` picks the pipeline (`uv run aether-vision pipelines` lists them).
`settings` holds that pipeline's settings, described below.

### `object_detection`

#### Detector

`settings.detector`:

| Setting | Default | Description |
|---|---|---|
| `model_path` ⟳ | `models/yolov8n.onnx` | `.onnx` for ONNX Runtime, `.tflite` for LiteRT |
| `backend` ⟳ | ONNX Runtime, CPU | See [Inference backends](#inference-backends) |
| `confidence_threshold` | `0.4` | Minimum detection confidence |
| `iou_threshold` | `0.45` | Overlap threshold for removing duplicate boxes |
| `class_agnostic_nms` | `false` | Remove overlapping boxes even across different classes |
| `max_detections` | `50` | Maximum detections per frame |
| `class_filter` | `[]` | Keep only these class ids; empty keeps all |
| `class_names` ⟳ | `[]` | Override the class names stored in the model |
| `box_units` | `auto` | `normalized` for models that output 0–1 boxes (some TFLite exports) |
| `output_layout` ⟳ | `auto` | Model output format; `auto` detects YOLOv8/v11 and end-to-end exports |

#### Localization (3D position)

`settings.localization`:

| Setting | Default | Description |
|---|---|---|
| `enabled` | `true` | Compute 3D positions from depth |
| `roi_scale` | `0.7` | Use the central 70% of each box, which avoids background at the edges |
| `sample_stride` | `2` | Use every 2nd depth pixel |
| `min_depth_m` / `max_depth_m` | `0.15` / `8.0` | Ignore depth outside this range |
| `max_points` | `3000` | Depth points per box are subsampled to this (speed) |
| `clustering.radius_m` | `0.04` | Points closer than this belong to the same object |
| `clustering.min_points` | `20` | Smaller groups are treated as noise |
| `cluster_selection` | `largest` | Which group is the object: `largest` or `nearest` |
| `extrinsics` | see below | Where the camera is mounted |

**Camera mounting** (`localization.extrinsics`): measured from the robot
center on the floor, in WPILib axes.

| Setting | Meaning |
|---|---|
| `x_m` | Forward distance from robot center (m) |
| `y_m` | Left distance from robot center (m) |
| `z_m` | Height of the camera lens above the floor (m) |
| `pitch_deg` | Tilt; **positive tilts the camera down** |
| `yaw_deg` | Rotation left (positive) / right |
| `roll_deg` | Rotation about the lens axis |

#### Output

| Setting | Default | Description |
|---|---|---|
| `sort_by` | `confidence` | Order of targets: `confidence`, `distance`, or `area`. The first target is published as `best` |
| `max_targets` | `10` | Maximum targets published |
| `require_position` | `false` | Drop targets without a 3D position |

### `passthrough`

Shows the camera image with no processing; useful for checking the camera.
Setting: `overlay` (draw the frame number).

## Inference backends

`settings.detector.backend`:

**`"kind": "onnxruntime"`** (default)

| Setting | Default | Description |
|---|---|---|
| `providers` | `["CPUExecutionProvider"]` | Use `["QNNExecutionProvider", "CPUExecutionProvider"]` with a QNN-enabled ONNX Runtime build |
| `intra_op_threads` | `0` | CPU threads; `0` lets ONNX Runtime decide |
| `qnn_backend_path` | `libQnnHtp.so` | QNN library, used only with `QNNExecutionProvider` |

**`"kind": "litert"`**: TFLite models, accelerated on the QCS6490 NPU.

| Setting | Default | Description |
|---|---|---|
| `delegate` | `qnn` | `qnn` for the NPU, `none` for CPU only |
| `delegate_path` | `libQnnTFLiteDelegate.so` | Full path if not on the library path |
| `qnn_backend` | `htp` | `htp` (NPU), `gpu`, or `dsp` |
| `htp_performance_mode` | `burst` | `burst`, `high_performance`, `sustained_high_performance`, `default`, `power_saver` |
| `num_threads` | `4` | CPU threads for operations the NPU can't run |
| `extra_delegate_options` | `{}` | Extra options passed straight to the QNN delegate |

See [Deployment → QCS6490](DEPLOYMENT.md#qualcomm-qcs6490).

## NetworkTables — `network_tables`

All settings here take effect after a process restart (⟳).

| Setting | Default | Description |
|---|---|---|
| `enabled` | `true` | Publish to NetworkTables |
| `mode` | `client` | `client` connects to the robot; `server` is for bench testing without a robot |
| `team` | `5987` | Finds the robot at `10.TE.AM.2` |
| `server_address` | `""` | Connect to this address instead of using `team` (e.g. `127.0.0.1` for simulation) |
| `root_table` | `AetherVision` | Top-level table name |
| `identity` | `aether-vision` | Client name shown on the robot |
| `telemetry_rate_hz` | `50` | How often telemetry is sent (results are always sent immediately) |
| `log_level` | `INFO` | Minimum level of log messages sent to `log/messages` |

## Web dashboard — `web`

| Setting | Default | Description |
|---|---|---|
| `enabled` ⟳ | `true` | Serve the dashboard and API |
| `host` ⟳, `port` ⟳ | `0.0.0.0`, `5803` | Listen address (FRC allows ports 5800–5810) |
| `stream_max_fps` | `30` | Frame rate limit for dashboard streams |
| `jpeg_quality` | `80` | Stream image quality (10–100); lower uses less bandwidth |
| `frontend_dir` ⟳ | `frontend/dist` | Built dashboard files |

## Logging — `logging`

All ⟳. `level` (`INFO`), `directory` (`logs`), `max_file_mb` (`10`),
`backup_count` (`5`). The log file is `logs/aether-vision.log`.

## Watchdog — `watchdog`

| Setting | Default | Description |
|---|---|---|
| `stall_timeout_s` | `10` | If the pipeline is stuck this long, recover; `0` disables |
| `hard_restart_on_stall` | `true` | Recover by restarting the process (otherwise only the pipeline) |
| `max_consecutive_errors` | `10` | Pipeline errors in a row before the pipeline is rebuilt |
