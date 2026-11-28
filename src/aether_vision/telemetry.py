"""Latest-value telemetry, shown on the dashboard and mirrored to NetworkTables."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aether_vision.networktables import NetworkTables

Value = bool | int | float | str


class Telemetry:
    """Thread-safe ``key -> value`` store (keys like ``camera/fps``)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: dict[str, Value] = {}
        self.version = 0
        self.nt: NetworkTables | None = None

    def put(self, key: str, value: Value) -> None:
        with self._lock:
            if self._values.get(key) == value:
                return
            self._values[key] = value
            self.version += 1
        if self.nt is not None:
            self.nt.put(key, value)

    def snapshot(self) -> dict[str, Value]:
        with self._lock:
            return dict(self._values)
