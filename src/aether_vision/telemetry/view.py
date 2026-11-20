"""Scoped, ergonomic telemetry API used by pipelines and stages."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from aether_vision.core.timing import Stopwatch
from aether_vision.telemetry.bus import TelemetryBus, TelemetryInput, validate_key


class Telemetry:
    """A view onto a :class:`TelemetryBus` under a key prefix.

    Example::

        telemetry = Telemetry(bus, "pipeline")
        telemetry.put("detections", 3)               # -> pipeline/detections
        stage = telemetry.scope("stages/detect")
        with stage.timer("latency_ms"):              # -> pipeline/stages/detect/latency_ms
            ...
    """

    __slots__ = ("_bus", "_prefix")

    def __init__(self, bus: TelemetryBus, prefix: str = "") -> None:
        self._bus = bus
        self._prefix = validate_key(prefix) if prefix else ""

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def bus(self) -> TelemetryBus:
        return self._bus

    def key(self, name: str) -> str:
        return f"{self._prefix}/{name}" if self._prefix else name

    def put(self, name: str, value: TelemetryInput) -> None:
        self._bus.put(self.key(name), value)

    def put_many(self, values: dict[str, TelemetryInput]) -> None:
        for name, value in values.items():
            self.put(name, value)

    def scope(self, name: str) -> Telemetry:
        return Telemetry(self._bus, self.key(name))

    def clear(self) -> None:
        """Remove every key under this scope."""
        if self._prefix:
            self._bus.remove_prefix(self._prefix)

    @contextmanager
    def timer(self, name: str = "latency_ms") -> Iterator[Stopwatch]:
        """Time a block and publish its duration in milliseconds."""
        watch = Stopwatch()
        with watch:
            yield watch
        self.put(name, watch.elapsed_ms)
