"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import FrameType

from aether_vision import __version__

_DEFAULT_CONFIG = os.environ.get("AETHER_VISION_CONFIG", "config/config.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aether-vision", description="Aether Vision")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run under a supervisor (restarts, crash recovery)")
    run.add_argument("--config", default=_DEFAULT_CONFIG, help="Path to config.json")
    run.add_argument("--reload", action="store_true", help="Restart the worker on code changes")

    worker = sub.add_parser("worker", help="Run the vision process directly")
    worker.add_argument("--config", default=_DEFAULT_CONFIG, help="Path to config.json")

    sub.add_parser("schema", help="Print the configuration JSON schemas")
    sub.add_parser("pipelines", help="List registered pipelines")
    return parser


def _run_worker(config_path: Path) -> int:
    from aether_vision.app import SUPERVISED_ENV, Application, ExitReason
    from aether_vision.supervisor import RESTART_EXIT_CODE

    app = Application(config_path)
    interrupts = 0

    def on_signal(signum: int, frame: FrameType | None) -> None:
        nonlocal interrupts
        del frame
        interrupts += 1
        if interrupts > 1:
            os._exit(1)  # second Ctrl+C: give up on graceful shutdown
        app.request_shutdown(ExitReason.STOP)
        del signum

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    reason = app.run()
    if reason != ExitReason.RESTART:
        return 0
    if os.environ.get(SUPERVISED_ENV) == "1":
        return RESTART_EXIT_CODE
    # Unsupervised: replace this process with a fresh interpreter (picks up new code).
    logging.getLogger(__name__).info("Re-executing process")
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])
    return 0  # unreachable


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    command: str = args.command or "run"

    if command == "schema":
        from aether_vision.config.models import AppConfig
        from aether_vision.pipeline.registry import pipeline_schemas

        payload = {"app": AppConfig.model_json_schema(), "pipelines": pipeline_schemas()}
        print(json.dumps(payload, indent=2))
        return 0
    if command == "pipelines":
        from aether_vision.pipeline.registry import available_pipelines

        for name in available_pipelines():
            print(name)
        return 0

    config_path = Path(getattr(args, "config", _DEFAULT_CONFIG))
    if command == "worker":
        return _run_worker(config_path)

    from aether_vision.supervisor import Supervisor

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [supervisor] %(levelname)s %(message)s"
    )
    watch_dir = Path(__file__).resolve().parent if getattr(args, "reload", False) else None
    return Supervisor(["--config", str(config_path)], watch_dir).run()
