# Aether Vision — Python Rebuild Plan & Architecture

This document is the plan the Python rebuild was written against, and remains the
reference for how the system is put together.

## 1. Goals (from the requirements)

| Requirement | How it is met |
|---|---|
| D435: color → YOLO, depth → deprojection + point-cloud clustering | `camera/realsense.py` (aligned color+depth), `inference/yolo.py`, `vision/deprojection.py`, `vision/clustering.py`, wired in `pipeline/pipelines/object_detection.py` |
| QCS6490 inference + plain CPU inference | `inference/` backend abstraction: `onnxruntime` (CPU, or any ORT EP incl. QNN) and `litert` (TFLite + Qualcomm QNN delegate → Hexagon HTP NPU) |
| Clean code, abstractions, thread safety, maintainability | Small single-purpose modules, ABCs/Protocols at every seam, concurrency primitives in one place (`core/concurrency.py`), strict typing (`mypy --strict`) |
| Pipeline easy to modify | A pipeline is a plain class composed of `Stage`s; registered by decorator; declares its own pydantic config |
| Results/telemetry/logs → NetworkTables (ntcore) | `networktables/` sinks for telemetry (KV), results and text logs |
| Logging: KV to NT + text logging | `telemetry/` (KV bus) and `logging_setup/` (console, rotating file, ring buffer → web, NT log topic) |
| Telemetry/results → frontend | FastAPI WebSocket multiplexing telemetry, results, logs and status; MJPEG debug streams |
| Easy telemetry from inside the pipeline | `ctx.telemetry.put("key", value)` / `stage.telemetry` scoped views; stages are timed automatically |
| Clean restart, even after code changes | Two levels: *soft* (in-process pipeline restart) and *hard* (process re-exec / supervisor respawn — fresh interpreter = new code). Optional `--reload` file watching |
| uv, modular design | `pyproject.toml` + `uv.lock`, `src/` layout, optional extras per hardware target |
| Type hints everywhere, unambiguous code | `mypy --strict`, `ruff`, frozen dataclasses / pydantic models instead of loose dicts |
| Threads where appropriate | Camera acquisition, pipeline, result publishing, telemetry dispatch, web server each own a thread |
| Camera disconnect recovery | Camera thread state machine: `CONNECTING → STREAMING → RECONNECTING`, backoff, optional hardware reset |
| Configs definable from the pipeline | Each pipeline declares a pydantic `config_type`; the frontend renders it from its JSON schema; fields can be hot-applied or marked `restart` |

## 2. Process & thread model

```
 supervisor process (optional, `aether-vision run`)
   └── worker process (`aether-vision worker`)               ← fresh interpreter on hard restart
         main thread ........ lifecycle / shutdown / restart decisions (Application)
         camera thread ...... FrameSource acquire loop + reconnect   → LatestValue[FrameSet]
         pipeline thread .... PipelineRunner: wait frame → stages    → LatestValue[PipelineResult]
         result thread ...... ResultPublisher → NT results + web
         telemetry thread ... TelemetryDispatcher: bus snapshot → sinks (NT, web) @ N Hz
         web thread ......... uvicorn/FastAPI (REST, WebSocket, MJPEG)
         (ntcore runs its own native network threads)
```

Data flows only through thread-safe primitives:

* `LatestValue[T]` — single-slot, sequence-numbered, condition-variable mailbox.
  Producers never block; slow consumers simply skip stale frames (correct for
  real-time vision).
* `TelemetryBus` — lock-protected latest-value KV store with change tracking.
* `StreamHub` — named `LatestValue[np.ndarray]` slots for debug images; JPEG
  encoding happens lazily in the web thread, only while a client is watching.

## 3. Module layout

```
src/aether_vision/
  __main__.py / cli.py     CLI: run (supervised) | worker | schema
  app.py                   Application: composition root and lifecycle
  supervisor.py            child-process supervisor: respawn on restart/crash
  core/                    concurrency primitives, shared value types, timing
  config/                  pydantic models, ConfigStore (atomic load/save/subscribe), restart diff
  logging_setup/           logging configuration and handlers (ring buffer, NT)
  telemetry/               TelemetryBus, scoped Telemetry view, dispatcher, sink protocol
  networktables/           NT connection, telemetry sink, result publisher, log handler
  camera/                  FrameSource ABC, CameraThread (recovery), realsense / usb / mock
  inference/               InferenceBackend ABC, onnxruntime + litert(QNN) backends, YOLO
  vision/                  deprojection, clustering, rigid transforms, drawing
  pipeline/                Stage, Pipeline, PipelineContext, registry, runner, results
  pipeline/pipelines/      concrete pipelines (object_detection, passthrough)
  streaming/               StreamHub + JPEG encoding
  web/                     FastAPI app, WebSocket broadcaster, uvicorn thread
```

## 4. Key abstractions

* **`FrameSource`** (camera): `open() / read(timeout) -> FrameSet / close()` plus
  `streams`. `CameraThread` owns the loop, the reconnect policy and telemetry,
  so sources stay trivial. A `FrameSet` carries color (BGR), depth (uint16
  aligned to color), depth scale, intrinsics, timestamps and frame number.
* **`InferenceBackend`**: `load() / input_spec / run(tensor) -> list[np.ndarray]`.
  The YOLO detector does letterboxing, (de)quantization, decoding and NMS and
  does not care which backend runs the graph.
* **`Stage[In, Out]`**: `setup(ctx)`, `process(value) -> Out`, `teardown()`.
  Calling a stage times it and publishes `stages/<name>/latency_ms`
  automatically; each stage gets a scoped telemetry view.
* **`Pipeline[ConfigT]`**: declares `name`, `config_type`, `required_streams`,
  builds stages in `setup`, implements `process(frames) -> PipelineResult`.
  `self.config` always returns the latest validated snapshot (hot updates).
* **`PipelineRunner`**: the pipeline thread. Handles soft restarts, exceptions
  (logged, counted, pipeline torn down and rebuilt after repeated failures) and
  the stall watchdog.
* **Sinks**: `TelemetrySink` / `ResultSink` protocols, implemented by NT and web.

## 5. Configuration

* `config/config.json` holds `AppConfig` (camera union, NT, web, runtime,
  pipeline selection). Saving goes through `ConfigStore` (atomic write and
  validation, then notifies subscribers).
* The pipeline section is `{name, settings}`; `settings` is validated against the
  selected pipeline's `config_type` from the registry.
* Fields annotated `restart_required()` trigger a soft pipeline restart when they
  change. All other changes are applied live on the next frame. Camera changes
  restart the camera thread. NT/web changes need a hard restart.
* The frontend fetches the JSON schemas and renders the forms generically, so a
  new pipeline config field shows up in the UI with no frontend change.

## 6. Restarts

| Kind | Trigger | Effect |
|---|---|---|
| Hot config | config save, non-restart field | next frame uses new values |
| Soft pipeline restart | UI button / restart field / repeated pipeline errors | teardown → re-validate config → setup, in-process |
| Hard restart | UI button / `--reload` file change / stall watchdog | graceful shutdown (camera released, NT flushed), then supervisor respawns or the process `exec`s itself → **new code is loaded** |

## 7. NetworkTables layout (`/<root table>/…`)

The telemetry bus maps one-to-one onto NT: a bus key `camera/fps` is published
as `/<root>/camera/fps`. Components own top-level prefixes:

```
status/{heartbeat, uptime_s, version, restart_pending}
camera/{state, connected, fps, frame_number, reconnects, source, last_error}
pipeline/{state, name, fps, latency_ms, restarts, last_error}
pipeline/<pipeline name>/...                 pipeline telemetry (cleared on rebuild)
pipeline/<pipeline name>/stages/<stage>/...  per-stage telemetry incl. latency_ms
results/{timestamp_us, latency_ms, frame, count, has_target, pipeline, json,
         targets_flat, targets_flat_fields, best/{x,y,z,distance,confidence,class_id,class_name}}
log/{messages (sendAll string), last_error}
```

`targets_flat` is a fixed stride double array:
`[class_id, confidence, x, y, z, distance, cx_px, cy_px, w_px, h_px] * N`. The
positions are in the WPILib robot frame, using the camera extrinsics under
`localization.extrinsics` in the pipeline settings; unknown values are NaN.

## 8. Frontend

The Svelte + tweakpane frontend is kept. The Kotlin/JS `utils` client is
replaced by a typed TS client, plus:

* `SchemaForm` — generic JSON-schema → tweakpane form (config editing)
* Telemetry panel (live KV table with filter), results panel, status bar
* Log monitor over WebSocket; restart pipeline / restart process controls
* Vite dev proxy to the backend; production build served by FastAPI

## 9. Implementation order

1. uv project, tooling (ruff, mypy, pytest), core primitives
2. config, logging, telemetry
3. camera sources + recovery thread
4. inference backends + YOLO
5. vision (deprojection, clustering, transforms)
6. pipeline framework + object-detection pipeline
7. NT integration, streaming, web server
8. application lifecycle, supervisor, CLI
9. frontend rewrite of the API layer and new panels
10. tests, docs, removal of the Kotlin/C++ code
