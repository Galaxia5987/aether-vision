"""Composition root: builds every component, wires them together and owns the lifecycle."""

from __future__ import annotations

import logging
import os
import threading
import time
from enum import StrEnum
from pathlib import Path
from typing import Final

from aether_vision import __version__
from aether_vision.camera.factory import create_frame_source
from aether_vision.camera.thread import CameraState, CameraThread
from aether_vision.config.diff import changed_fields
from aether_vision.config.models import AppConfig, LoggingConfig
from aether_vision.config.store import ConfigStore
from aether_vision.core.concurrency import LatestValue, PeriodicThread
from aether_vision.core.types import FrameSet
from aether_vision.logging_setup.buffer import LogBuffer
from aether_vision.logging_setup.setup import add_handler, configure_logging, remove_handler
from aether_vision.networktables.client import NetworkTablesClient
from aether_vision.networktables.log_handler import NetworkTablesLogHandler
from aether_vision.networktables.results import NetworkTablesResultSink
from aether_vision.networktables.telemetry_sink import NetworkTablesTelemetrySink
from aether_vision.pipeline.publisher import ResultPublisher, ResultSink
from aether_vision.pipeline.registry import validate_app_config
from aether_vision.pipeline.result import PipelineResult
from aether_vision.pipeline.runner import PipelineRunner, PipelineState
from aether_vision.streaming.hub import DebugStreams, StreamHub
from aether_vision.telemetry.bus import TelemetryBus
from aether_vision.telemetry.dispatcher import TelemetryDispatcher, TelemetrySink
from aether_vision.telemetry.view import Telemetry
from aether_vision.vision.drawing import colorize_depth
from aether_vision.web.app import create_app
from aether_vision.web.server import WebServer
from aether_vision.web.services import WebServices

_log = logging.getLogger(__name__)

#: Set by the supervisor so the worker knows to exit (not exec) on restart.
SUPERVISED_ENV: Final = "AETHER_VISION_SUPERVISED"
_STOP_TIMEOUT_S: Final = 5.0
_PROCESS_RESTART_SECTIONS: Final = ("network_tables", "web", "logging")


class ExitReason(StrEnum):
    STOP = "stop"
    RESTART = "restart"


class _StatusThread(PeriodicThread):
    """Publishes application status to telemetry (and thus NT) at a low rate."""

    def __init__(self, app: Application) -> None:
        super().__init__("status", rate_hz=2.0)
        self._app = app
        self._heartbeat = 0

    def tick(self) -> None:
        self._heartbeat += 1
        status = self._app.status()
        telemetry = self._app.status_telemetry
        telemetry.put("heartbeat", self._heartbeat)
        telemetry.put("uptime_s", round(float(str(status["uptime_s"])), 1))
        telemetry.put("version", __version__)
        telemetry.put("restart_pending", bool(status["restart_pending"]))


class Application:
    """Owns all threads. Public methods are thread-safe."""

    def __init__(self, config_path: Path) -> None:
        self._logs = LogBuffer()
        configure_logging(LoggingConfig(), self._logs)
        self._store = ConfigStore(config_path)
        self._store.add_validator(validate_app_config)

        self._shutdown = threading.Event()
        self._exit_reason = ExitReason.STOP
        self._reason_lock = threading.Lock()
        self._camera_lock = threading.Lock()
        self._started_s = time.monotonic()
        self._restart_pending = False

        self._bus = TelemetryBus()
        self._hub = StreamHub()
        self._frames: LatestValue[FrameSet] = LatestValue()
        self._results: LatestValue[PipelineResult] = LatestValue()
        self.status_telemetry = Telemetry(self._bus, "status")

        self._nt: NetworkTablesClient | None = None
        self._nt_log_handler: NetworkTablesLogHandler | None = None
        self._camera: CameraThread | None = None
        self._runner: PipelineRunner | None = None
        self._dispatcher: TelemetryDispatcher | None = None
        self._publisher: ResultPublisher | None = None
        self._status_thread: _StatusThread | None = None
        self._web: WebServer | None = None

    # ------------------------------------------------------------------ control

    def request_shutdown(self, reason: ExitReason = ExitReason.STOP) -> None:
        with self._reason_lock:
            if not self._shutdown.is_set():
                self._exit_reason = reason
                _log.info("Shutdown requested (%s)", reason.value)
        self._shutdown.set()

    def restart_pipeline(self) -> None:
        if self._runner is not None:
            self._runner.request_restart()

    def restart_process(self) -> None:
        self.request_shutdown(ExitReason.RESTART)

    def restart_camera(self) -> None:
        with self._camera_lock:
            if self._camera is not None:
                self._camera.stop(_STOP_TIMEOUT_S)
            self._camera = self._create_camera(self._store.current)
            self._camera.start()

    def status(self) -> dict[str, object]:
        camera = self._camera
        runner = self._runner
        nt = self._nt
        return {
            "version": __version__,
            "uptime_s": time.monotonic() - self._started_s,
            "supervised": os.environ.get(SUPERVISED_ENV) == "1",
            "restart_pending": self._restart_pending,
            "camera": {
                "state": camera.state.value if camera else CameraState.STOPPED.value,
                "source": camera.description if camera else "",
                "fps": round(camera.fps, 2) if camera else 0.0,
                "last_error": camera.last_error if camera else "",
            },
            "pipeline": {
                "name": runner.pipeline_name if runner else "",
                "state": runner.state.value if runner else PipelineState.STOPPED.value,
                "fps": round(runner.fps, 2) if runner else 0.0,
                "last_error": runner.last_error if runner else "",
            },
            "network_tables": {
                "enabled": nt is not None,
                "connected": nt.connected if nt else False,
            },
        }

    # ---------------------------------------------------------------- lifecycle

    def run(self) -> ExitReason:
        """Start everything, block until shutdown is requested, then stop everything."""
        config = self._store.load()
        configure_logging(config.logging, self._logs)
        _log.info("Aether Vision %s starting (config: %s)", __version__, self._store.path)
        try:
            validate_app_config(config)
        except ValueError as error:
            _log.error("Pipeline configuration is invalid: %s", error)
        try:
            self._start(config)
            self._store.subscribe(self._on_config_changed)
            while not self._shutdown.wait(1.0):
                self._supervise_threads()
        finally:
            self._stop()
        with self._reason_lock:
            return self._exit_reason

    def _create_camera(self, config: AppConfig) -> CameraThread:
        source_config = config.camera.source
        return CameraThread(
            source_factory=lambda: create_frame_source(source_config),
            output=self._frames,
            reconnect=config.camera.reconnect,
            telemetry=Telemetry(self._bus, "camera"),
        )

    def _start(self, config: AppConfig) -> None:
        telemetry_sinks: list[TelemetrySink] = []
        result_sinks: list[ResultSink] = []
        nt_config = config.network_tables
        if nt_config.enabled:
            nt = NetworkTablesClient(nt_config)
            nt.start()
            self._nt = nt
            telemetry_sinks.append(NetworkTablesTelemetrySink(nt.instance, nt.root))
            result_sinks.append(NetworkTablesResultSink(nt.instance, nt.root))
            self._nt_log_handler = NetworkTablesLogHandler(
                nt.instance, nt.root, logging.getLevelName(nt_config.log_level)
            )
            add_handler(self._nt_log_handler)

        self._hub.register_derived("color", self._frames, lambda frames: frames.color)
        self._hub.register_derived(
            "depth",
            self._frames,
            lambda frames: (
                None if frames.depth is None else colorize_depth(frames.depth, frames.depth_scale_m)
            ),
        )

        self._dispatcher = TelemetryDispatcher(
            self._bus, telemetry_sinks, nt_config.telemetry_rate_hz
        )
        self._publisher = ResultPublisher(self._results, result_sinks)
        self._runner = PipelineRunner(
            frames=self._frames,
            results=self._results,
            selection=config.pipeline,
            bus=self._bus,
            debug=DebugStreams(self._hub),
            max_consecutive_errors=config.watchdog.max_consecutive_errors,
        )
        self._camera = self._create_camera(config)
        self._status_thread = _StatusThread(self)

        self._dispatcher.start()
        self._publisher.start()
        self._runner.start()
        self._camera.start()
        self._status_thread.start()

        if config.web.enabled:
            services = WebServices(
                config=self._store,
                telemetry=self._bus,
                logs=self._logs,
                results=self._results,
                streams=self._hub,
                status=self.status,
                controls=self,
            )
            frontend = Path(config.web.frontend_dir)
            app = create_app(services, frontend if frontend.is_dir() else None)
            self._web = WebServer(app, config.web.host, config.web.port)
            self._web.start()

    def _stop(self) -> None:
        _log.info("Stopping")
        # Order: stop producers before consumers, network last so final values get out.
        for thread in (self._web, self._camera, self._runner, self._publisher, self._status_thread):
            if thread is not None:
                thread.stop(_STOP_TIMEOUT_S)
        if self._dispatcher is not None:
            self._dispatcher.stop(_STOP_TIMEOUT_S)
        if self._nt_log_handler is not None:
            remove_handler(self._nt_log_handler)
            self._nt_log_handler.close()
            self._nt_log_handler = None
        if self._nt is not None:
            self._nt.stop()
            self._nt = None
        _log.info("Stopped")

    # ---------------------------------------------------------------- monitoring

    def _supervise_threads(self) -> None:
        """Main-thread watchdog: restart crashed threads, detect pipeline stalls."""
        watchdog = self._store.current.watchdog
        with self._camera_lock:
            camera = self._camera
        if camera is not None and not camera.is_running and camera.failed is not None:
            _log.error("Camera thread crashed; restarting it")
            self.restart_camera()

        runner = self._runner
        if runner is None:
            return
        if not runner.is_running:
            _log.error("Pipeline thread exited unexpectedly; restarting it")
            runner.start()
            return
        if watchdog.stall_timeout_s <= 0.0 or runner.state == PipelineState.STARTING:
            return
        stalled_for = time.monotonic() - runner.heartbeat_s
        if stalled_for > watchdog.stall_timeout_s:
            _log.critical("Pipeline stalled for %.1fs", stalled_for)
            if watchdog.hard_restart_on_stall:
                self.request_shutdown(ExitReason.RESTART)
            else:
                runner.request_restart()

    def _on_config_changed(self, old: AppConfig, new: AppConfig) -> None:
        if old.camera != new.camera:
            _log.info("Camera configuration changed; restarting camera")
            self.restart_camera()
        if old.pipeline != new.pipeline and self._runner is not None:
            try:
                self._runner.apply_selection(new.pipeline)
            except (KeyError, ValueError):
                _log.exception("Rejected pipeline configuration")
        for section in _PROCESS_RESTART_SECTIONS:
            fields = changed_fields(getattr(old, section), getattr(new, section))
            if fields:
                self._restart_pending = True
                _log.warning(
                    "%s changed (%s); takes effect after a process restart",
                    section,
                    ", ".join(fields),
                )
