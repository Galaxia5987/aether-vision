"""Builds every component, applies config changes, and shuts down cleanly."""

from __future__ import annotations

import logging
import logging.handlers
import threading
from pathlib import Path

from aether_vision import __version__
from aether_vision.camera import CameraThread
from aether_vision.config import AppConfig, ConfigStore
from aether_vision.networktables import NetworkTables
from aether_vision.pipeline import PipelineThread
from aether_vision.telemetry import Telemetry
from aether_vision.types import FrameSet, Latest, Result
from aether_vision.web import LogBuffer, WebServer, create_app

_log = logging.getLogger(__name__)


def configure_logging(buffer: logging.Handler) -> None:
    Path("logs").mkdir(exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            "logs/aether-vision.log", maxBytes=10_000_000, backupCount=3
        ),
        buffer,
    ]
    formatter = logging.Formatter(
        "%(asctime)s [%(threadName)s] %(levelname)-7s %(name)s - %(message)s"
    )
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)


class App:
    def __init__(self, config_path: Path) -> None:
        self.logs = LogBuffer()
        configure_logging(self.logs)
        self.store = ConfigStore(config_path)
        self.telemetry = Telemetry()
        self.frames: Latest[FrameSet] = Latest()
        self.results: Latest[tuple[FrameSet, Result]] = Latest()
        self.restart_requested = False
        self._shutdown = threading.Event()
        self._camera_lock = threading.Lock()
        self._camera: CameraThread | None = None

    def shutdown(self, restart: bool = False) -> None:
        self.restart_requested |= restart
        self._shutdown.set()

    def run(self) -> None:
        """Run until :meth:`shutdown`; then ``restart_requested`` says whether to re-exec."""
        config = self.store.load()
        _log.info("Aether Vision %s starting (config %s)", __version__, self.store.path)
        self.telemetry.put("version", __version__)
        nt = NetworkTables(config.network_tables)
        self.telemetry.nt = nt
        pipeline = PipelineThread(self.store, self.frames, self.results, self.telemetry, nt)
        app = create_app(
            self.store,
            self.telemetry,
            self.frames,
            self.results,
            self.logs,
            lambda: self.shutdown(restart=True),
        )
        web = WebServer(app, config.web.port)
        self.store.subscribe(self._on_config_changed)
        self._start_camera(config)
        pipeline.start()
        web.start()
        try:
            while not self._shutdown.wait(1.0):
                self.telemetry.put("networktables/connected", nt.connected)
        finally:
            _log.info("Stopping")
            web.stop()
            with self._camera_lock:
                if self._camera is not None:
                    self._camera.stop()
            pipeline.stop()
            self.telemetry.nt = None
            nt.close()

    def _start_camera(self, config: AppConfig) -> None:
        with self._camera_lock:
            if self._camera is not None:
                self._camera.stop()
            self._camera = CameraThread(config.camera, self.frames, self.telemetry)
            self._camera.start()

    def _on_config_changed(self, old: AppConfig, new: AppConfig) -> None:
        # Detector and mount settings are read every frame; the model reloads by itself.
        if old.camera != new.camera:
            _log.info("Camera settings changed; restarting the camera")
            self._start_camera(new)
        if old.network_tables != new.network_tables or old.web != new.web:
            _log.info("Network settings changed; restarting")
            self.shutdown(restart=True)
