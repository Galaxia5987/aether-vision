"""The pipeline thread: builds the selected pipeline and feeds it frames."""

from __future__ import annotations

import logging
import threading
import time
from enum import StrEnum
from typing import Any

from aether_vision.config.base import ConfigModel
from aether_vision.config.diff import requires_restart
from aether_vision.config.models import PipelineSelection
from aether_vision.core.concurrency import LatestValue, ServiceThread
from aether_vision.core.timing import RateMeter
from aether_vision.core.types import FrameSet
from aether_vision.pipeline.base import ConfigHandle, Pipeline, PipelineContext
from aether_vision.pipeline.registry import get_pipeline, validate_selection
from aether_vision.pipeline.result import PipelineResult
from aether_vision.streaming.hub import DebugStreams
from aether_vision.telemetry.bus import TelemetryBus
from aether_vision.telemetry.view import Telemetry

_FRAME_WAIT_S = 0.1
_BUILD_RETRY_S = 3.0


class PipelineState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class PipelineRunner(ServiceThread):
    """Runs one pipeline at a time on a dedicated thread.

    * Configuration changes are hot-applied, or trigger a soft restart when a
      restart-required field (or the pipeline itself) changed.
    * Exceptions are logged and counted; too many in a row rebuild the pipeline.
    * :attr:`heartbeat_s` advances every loop iteration so a watchdog can tell a
      stalled pipeline from an idle one.
    """

    def __init__(
        self,
        frames: LatestValue[FrameSet],
        results: LatestValue[PipelineResult],
        selection: PipelineSelection,
        bus: TelemetryBus,
        debug: DebugStreams,
        max_consecutive_errors: int,
    ) -> None:
        super().__init__("pipeline")
        self._frames = frames
        self._results = results
        self._bus = bus
        self._debug = debug
        self._telemetry = Telemetry(bus, "pipeline")
        self._max_errors = max_consecutive_errors
        self._lock = threading.Lock()
        self._selection = selection
        self._handle: ConfigHandle[Any] | None = None
        self._active_name = ""
        self._restart_event = threading.Event()
        self._state = PipelineState.STOPPED
        self._last_error = ""
        self._heartbeat_s = time.monotonic()
        self._restarts = 0
        self._rate = RateMeter()

    # ----------------------------------------------------------- public, any thread

    @property
    def state(self) -> PipelineState:
        with self._lock:
            return self._state

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    @property
    def pipeline_name(self) -> str:
        with self._lock:
            return self._active_name or self._selection.name

    @property
    def heartbeat_s(self) -> float:
        with self._lock:
            return self._heartbeat_s

    @property
    def fps(self) -> float:
        return self._rate.rate_hz

    def request_restart(self) -> None:
        """Soft restart: tear the pipeline down and build it again with the latest config."""
        self._log.info("Pipeline restart requested")
        self._restart_event.set()

    def apply_selection(self, selection: PipelineSelection) -> None:
        """Apply a new pipeline selection: hot-swap settings, or restart if needed."""
        validated = validate_selection(selection)
        with self._lock:
            self._selection = selection
            handle = self._handle
            same_pipeline = selection.name == self._active_name
        if handle is None or not same_pipeline:
            self.request_restart()
            return
        current: ConfigModel = handle.get()
        if requires_restart(current, validated):
            self._log.info("Restart-required pipeline setting changed")
            self.request_restart()
        else:
            handle.set(validated)
            self._log.info("Pipeline settings applied live")

    # ----------------------------------------------------------- pipeline thread

    def _set_state(self, state: PipelineState, error: str | None = None) -> None:
        with self._lock:
            self._state = state
            if error is not None:
                self._last_error = error
        self._telemetry.put("state", state.value)
        if error is not None:
            self._telemetry.put("last_error", error)

    def _beat(self) -> None:
        with self._lock:
            self._heartbeat_s = time.monotonic()

    def _build(self) -> Pipeline[Any] | None:
        with self._lock:
            selection = self._selection
        self._set_state(PipelineState.STARTING)
        self._telemetry.put("name", selection.name)
        try:
            cls = get_pipeline(selection.name)
            config = validate_selection(selection)
            handle: ConfigHandle[Any] = ConfigHandle(config)
            scope = self._telemetry.scope(selection.name)
            scope.clear()
            context = PipelineContext(
                telemetry=scope,
                debug=self._debug,
                logger=logging.getLogger(f"aether_vision.pipeline.{selection.name}"),
            )
            pipeline = cls(context, handle)
            try:
                pipeline.setup()
            except BaseException:
                pipeline.teardown()
                raise
        except Exception as error:
            self._log.exception("Failed to build pipeline %s", selection.name)
            self._set_state(PipelineState.ERROR, f"build failed: {error}")
            return None
        with self._lock:
            self._handle = handle
            self._active_name = selection.name
        self._log.info("Pipeline %s started", selection.name)
        self._set_state(PipelineState.RUNNING, "")
        return pipeline

    def run_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self._restart_event.clear()
            self._beat()
            pipeline = self._build()
            if pipeline is None:
                self._wait_for_retry(stop_event)
                continue
            try:
                self._process_frames(pipeline, stop_event)
            finally:
                self._teardown(pipeline)
            if not stop_event.is_set():
                self._restarts += 1
                self._telemetry.put("restarts", self._restarts)
        self._set_state(PipelineState.STOPPED)

    def _wait_for_retry(self, stop_event: threading.Event) -> None:
        deadline = time.monotonic() + _BUILD_RETRY_S
        while not stop_event.is_set() and not self._restart_event.is_set():
            self._beat()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            stop_event.wait(min(remaining, 0.25))

    def _teardown(self, pipeline: Pipeline[Any]) -> None:
        with self._lock:
            self._handle = None
            self._active_name = ""
        try:
            pipeline.teardown()
        except Exception:
            self._log.exception("Pipeline teardown failed")
        self._rate.reset()
        self._log.info("Pipeline %s stopped", pipeline.name)

    def _process_frames(self, pipeline: Pipeline[Any], stop_event: threading.Event) -> None:
        last_seq = 0
        consecutive_errors = 0
        processed = 0
        warned_streams = False
        while not stop_event.is_set() and not self._restart_event.is_set():
            self._beat()
            latest = self._frames.wait_newer(last_seq, _FRAME_WAIT_S)
            if latest is None:
                continue
            last_seq = latest.seq
            frames = latest.value

            missing = pipeline.required_streams - frames.streams
            if missing:
                if not warned_streams:
                    names = ", ".join(sorted(kind.value for kind in missing))
                    self._log.error("Camera does not provide required streams: %s", names)
                    self._set_state(PipelineState.ERROR, f"missing streams: {names}")
                    warned_streams = True
                continue
            if warned_streams:
                warned_streams = False
                self._set_state(PipelineState.RUNNING, "")

            try:
                result = pipeline.process(frames)
            except Exception as error:
                consecutive_errors += 1
                self._log.exception("Pipeline error %d/%d", consecutive_errors, self._max_errors)
                self._telemetry.put("consecutive_errors", consecutive_errors)
                self._set_state(PipelineState.ERROR, repr(error))
                if consecutive_errors >= self._max_errors:
                    self._log.error("Too many consecutive errors; rebuilding pipeline")
                    return
                continue

            if consecutive_errors:
                consecutive_errors = 0
                self._telemetry.put("consecutive_errors", 0)
                self._set_state(PipelineState.RUNNING, "")
            self._results.put(result)
            self._rate.tick()
            processed += 1
            if processed % 10 == 0:
                self._telemetry.put("fps", round(self._rate.rate_hz, 2))
            self._telemetry.put("latency_ms", round(result.latency_ms, 2))
