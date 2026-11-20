"""Moves telemetry from the bus to sinks on a dedicated thread."""

from __future__ import annotations

from typing import Protocol

from aether_vision.core.concurrency import PeriodicThread
from aether_vision.telemetry.bus import TelemetryBus, TelemetryDelta


class TelemetrySink(Protocol):
    """Receives telemetry deltas. Called only from the dispatcher thread."""

    def apply(self, delta: TelemetryDelta) -> None: ...

    def close(self) -> None: ...


class TelemetryDispatcher(PeriodicThread):
    """Periodically forwards bus changes to every registered sink.

    Batching at a fixed rate keeps pipeline code free of I/O: ``Telemetry.put``
    only touches an in-memory dict.
    """

    def __init__(self, bus: TelemetryBus, sinks: list[TelemetrySink], rate_hz: float) -> None:
        super().__init__("telemetry", rate_hz)
        self._bus = bus
        self._sinks = list(sinks)
        self._cursors = [0 for _ in self._sinks]

    def tick(self) -> None:
        for index, sink in enumerate(self._sinks):
            delta = self._bus.delta_since(self._cursors[index])
            self._cursors[index] = delta.cursor
            if delta.values or delta.removed or delta.full:
                sink.apply(delta)

    def on_exit(self) -> None:
        self.tick()  # flush the last values
        for sink in self._sinks:
            try:
                sink.close()
            except Exception:
                self._log.exception("Failed to close telemetry sink %r", sink)
