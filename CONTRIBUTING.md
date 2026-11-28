# Contributing

## Setup

```bash
scripts/install.sh --dev --mock-config
```

This installs the development tools (pytest, mypy, ruff) and a mock-camera
config, so no hardware is needed.

## Running

```bash
uv run aether-vision                   # backend; the dashboard's Restart reloads code
cd frontend && npm run dev             # dashboard with hot reload on :5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:5803`. Set
`AETHER_VISION_BACKEND=http://<host>:5803` to use a backend on another machine
(e.g. the robot's coprocessor).

## Checks

All of these must pass before merging:

```bash
uv run ruff format .        # format
uv run ruff check .         # lint
uv run mypy                 # strict type checking of src/ and tests/
uv run pytest               # tests
cd frontend && npm run check
```

## Conventions

- **Keep it small.** One module per concern (see the README). Add a setting
  only when it needs to change between robots; otherwise use a constant.
- **Types everywhere.** `mypy --strict` must pass.
- **Threads.** The camera, pipeline and web server each run on one thread.
  Data crosses threads through `Latest` (newest frame/result), `Telemetry`
  and `ConfigStore`, all thread-safe; config objects are immutable.
- **Prefer libraries** (numpy, scipy, OpenCV, wpimath, pydantic) over
  hand-written algorithms.
- **Dependencies:** add with `uv add <package>` (or `uv add --dev`) and commit
  `uv.lock`. Hardware-specific packages go in an optional extra in
  `pyproject.toml`.
