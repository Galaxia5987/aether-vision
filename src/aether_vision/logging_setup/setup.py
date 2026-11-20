"""Root logger configuration."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Final

from aether_vision.config.models import LoggingConfig
from aether_vision.logging_setup.buffer import LogBuffer

_FORMAT: Final = "%(asctime)s.%(msecs)03d [%(threadName)s] %(levelname)-7s %(name)s - %(message)s"
_DATE_FORMAT: Final = "%Y-%m-%d %H:%M:%S"
_MARKER: Final = "_aether_vision_handler"


def _tag(handler: logging.Handler) -> logging.Handler:
    setattr(handler, _MARKER, True)
    return handler


def configure_logging(config: LoggingConfig, buffer: LogBuffer) -> None:
    """Install console, rotating-file and buffer handlers on the root logger.

    Idempotent: handlers installed by a previous call are replaced.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _MARKER, False):
            root.removeHandler(handler)
            handler.close()

    root.setLevel(config.level)
    formatter = logging.Formatter(_FORMAT, _DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(_tag(console))

    directory = Path(config.directory)
    directory.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        directory / "aether-vision.log",
        maxBytes=int(config.max_file_mb * 1024 * 1024),
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(_tag(file_handler))

    buffer.setFormatter(formatter)
    root.addHandler(_tag(buffer))

    # Third-party libraries that are noisy at INFO.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)


def add_handler(handler: logging.Handler) -> None:
    """Attach an extra handler (e.g. NetworkTables) that ``configure_logging`` manages."""
    logging.getLogger().addHandler(_tag(handler))


def remove_handler(handler: logging.Handler) -> None:
    logging.getLogger().removeHandler(handler)
