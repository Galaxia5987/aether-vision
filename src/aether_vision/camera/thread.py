"""Camera acquisition thread with automatic disconnect recovery."""

from __future__ import annotations

import threading
from collections.abc import Callable
from enum import StrEnum

from aether_vision.camera.base import CameraError, CameraTimeoutError, FrameSource
from aether_vision.config.models import ReconnectConfig
from aether_vision.core.concurrency import LatestValue, ServiceThread
from aether_vision.core.timing import RateMeter
from aether_vision.core.types import FrameSet
from aether_vision.telemetry.view import Telemetry


class CameraState(StrEnum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"


class CameraThread(ServiceThread):
    """Reads frames from a :class:`FrameSource` into a :class:`LatestValue`.

    State machine::

        CONNECTING --open ok--> STREAMING --error / repeated timeouts--> RECONNECTING
            ^                                                                |
            +------------------- backoff (exponential, capped) --------------+
    """

    def __init__(
        self,
        source_factory: Callable[[], FrameSource],
        output: LatestValue[FrameSet],
        reconnect: ReconnectConfig,
        telemetry: Telemetry,
    ) -> None:
        super().__init__("camera")
        self._source_factory = source_factory
        self._output = output
        self._reconnect = reconnect
        self._telemetry = telemetry
        self._state_lock = threading.Lock()
        self._state = CameraState.STOPPED
        self._rate = RateMeter()
        self._reconnects = 0
        self._last_error = ""
        self._description = ""

    @property
    def state(self) -> CameraState:
        with self._state_lock:
            return self._state

    @property
    def fps(self) -> float:
        return self._rate.rate_hz

    @property
    def last_error(self) -> str:
        with self._state_lock:
            return self._last_error

    @property
    def description(self) -> str:
        with self._state_lock:
            return self._description

    def _set_state(self, state: CameraState, error: str | None = None) -> None:
        with self._state_lock:
            changed = state != self._state
            self._state = state
            if error is not None:
                self._last_error = error
        if changed:
            self._log.info("Camera state -> %s", state.value)
        self._telemetry.put("state", state.value)
        self._telemetry.put("connected", state == CameraState.STREAMING)
        if error is not None:
            self._telemetry.put("last_error", error)

    def run_loop(self, stop_event: threading.Event) -> None:
        source = self._source_factory()
        with self._state_lock:
            self._description = source.describe()
        self._telemetry.put("source", source.describe())
        delay = self._reconnect.initial_delay_s
        failed_attempts = 0
        self._set_state(CameraState.CONNECTING)
        try:
            while not stop_event.is_set():
                try:
                    source.open()
                except CameraError as error:
                    failed_attempts += 1
                    self._set_state(CameraState.RECONNECTING, str(error))
                    self._log.warning(
                        "Opening %s failed (attempt %d): %s",
                        source.describe(),
                        failed_attempts,
                        error,
                    )
                    source.close()
                    source.recover(failed_attempts)
                    stop_event.wait(delay)
                    delay = min(delay * 2.0, self._reconnect.max_delay_s)
                    continue

                failed_attempts = 0
                delay = self._reconnect.initial_delay_s
                self._set_state(CameraState.STREAMING)
                self._stream(source, stop_event)
                source.close()
                if not stop_event.is_set():
                    self._reconnects += 1
                    self._telemetry.put("reconnects", self._reconnects)
                    self._rate.reset()
                    self._telemetry.put("fps", 0.0)
                    stop_event.wait(delay)
        finally:
            source.close()
            self._rate.reset()
            self._set_state(CameraState.STOPPED)

    def _stream(self, source: FrameSource, stop_event: threading.Event) -> None:
        """Read until the stop event or a failure. Returns when the source must be reopened."""
        timeouts = 0
        frames = 0
        while not stop_event.is_set():
            try:
                frame_set = source.read(self._reconnect.frame_timeout_s)
            except CameraTimeoutError as error:
                timeouts += 1
                self._log.warning(
                    "Frame timeout %d/%d: %s",
                    timeouts,
                    self._reconnect.max_consecutive_timeouts,
                    error,
                )
                if timeouts >= self._reconnect.max_consecutive_timeouts:
                    self._set_state(CameraState.RECONNECTING, f"timed out: {error}")
                    return
                continue
            except CameraError as error:
                self._log.error("Camera failure, reconnecting: %s", error)
                self._set_state(CameraState.RECONNECTING, str(error))
                return
            except Exception as error:  # driver bugs must not kill acquisition
                self._log.exception("Unexpected camera error, reconnecting")
                self._set_state(CameraState.RECONNECTING, repr(error))
                return

            timeouts = 0
            frames += 1
            self._output.put(frame_set)
            self._rate.tick()
            if frames % 15 == 0:
                self._telemetry.put("fps", round(self._rate.rate_hz, 2))
                self._telemetry.put("frame_number", frame_set.frame_number)
