# Contributing

## Setup

```bash
scripts/install.sh --dev --mock-config
```

This installs the development tools (pytest, mypy, ruff, watchfiles) and a
mock-camera config, so no hardware is needed.

## Running

```bash
uv run aether-vision run --reload      # backend; restarts on code changes
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

- **Types everywhere.** `mypy --strict` must pass; avoid `Any` and untyped dicts.
  Use frozen dataclasses or `ConfigModel` for data passed between components.
- **Threads.** Components that block or run continuously subclass
  `ServiceThread` / `PeriodicThread`. Data crosses threads only through
  `LatestValue`, `TelemetryBus`, `ConfigStore`, or `StreamHub`; don't share
  mutable state any other way.
- **Prefer libraries** (numpy, scipy, OpenCV, pydantic) over hand-written
  algorithms.
- **Settings** belong in a `ConfigModel` with defaults, limits and a
  description, so they show up in the dashboard.
- **New pipelines:** see [docs/PIPELINES.md](docs/PIPELINES.md).
- **Dependencies:** add with `uv add <package>` (or `uv add --dev`) and commit
  `uv.lock`. Hardware-specific packages go in an optional extra in
  `pyproject.toml`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the parts fit together.
