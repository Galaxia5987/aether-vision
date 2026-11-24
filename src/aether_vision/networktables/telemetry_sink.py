"""Publishes telemetry deltas to NetworkTables with typed topics."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import ntcore

from aether_vision.telemetry.bus import TelemetryDelta, TelemetryValue

_log = logging.getLogger(__name__)


_Instance = ntcore.NetworkTableInstance
#: NT type string -> topic getter.
_TOPIC_GETTERS: dict[str, Callable[[_Instance, str], Any]] = {
    "boolean": _Instance.getBooleanTopic,
    "integer": _Instance.getIntegerTopic,
    "double": _Instance.getDoubleTopic,
    "string": _Instance.getStringTopic,
    "boolean[]": _Instance.getBooleanArrayTopic,
    "integer[]": _Instance.getIntegerArrayTopic,
    "double[]": _Instance.getDoubleArrayTopic,
    "string[]": _Instance.getStringArrayTopic,
}


def _topic_kind(value: TelemetryValue) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if not value:
        return "double[]"
    first = value[0]
    if isinstance(first, bool):
        return "boolean[]"
    if isinstance(first, int):
        return "integer[]"
    if isinstance(first, float):
        return "double[]"
    return "string[]"


class NetworkTablesTelemetrySink:
    """Lazily creates one publisher per key. Used only from the dispatcher thread."""

    def __init__(self, instance: ntcore.NetworkTableInstance, root: str) -> None:
        self._instance = instance
        self._root = root.rstrip("/")
        self._publishers: dict[str, tuple[str, Any]] = {}

    def _publisher(self, key: str, kind: str) -> Any:
        existing = self._publishers.get(key)
        if existing is not None:
            if existing[0] == kind:
                return existing[1]
            _log.warning("Telemetry key %s changed type %s -> %s", key, existing[0], kind)
            existing[1].close()
        name = f"{self._root}/{key}"
        publisher = _TOPIC_GETTERS[kind](self._instance, name).publish()
        self._publishers[key] = (kind, publisher)
        return publisher

    def apply(self, delta: TelemetryDelta) -> None:
        for key in delta.removed:
            entry = self._publishers.pop(key, None)
            if entry is not None:
                entry[1].close()
        for key, value in delta.values.items():
            kind = _topic_kind(value)
            payload: object = list(value) if isinstance(value, tuple) else value
            try:
                self._publisher(key, kind).set(payload)
            except (TypeError, ValueError):
                _log.exception("Failed to publish telemetry %s", key)

    def close(self) -> None:
        for _, publisher in self._publishers.values():
            publisher.close()
        self._publishers.clear()
