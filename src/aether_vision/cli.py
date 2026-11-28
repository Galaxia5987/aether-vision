"""Command-line entry point: ``aether-vision [--config PATH]``."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path

from aether_vision import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aether-vision", description="Aether Vision")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.environ.get("AETHER_VISION_CONFIG", "config/config.json")),
        help="Path to config.json (created with defaults if missing)",
    )
    args = parser.parse_args(argv)

    from aether_vision.app import App

    app = App(args.config)
    signal.signal(signal.SIGINT, lambda *_: app.shutdown())
    signal.signal(signal.SIGTERM, lambda *_: app.shutdown())
    app.run()
    if app.restart_requested:
        # A fresh interpreter, so a restart also picks up code changes.
        os.execv(sys.executable, [sys.executable, *sys.orig_argv[1:]])
    return 0
