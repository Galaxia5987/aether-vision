"""The telemetry store: latest value per key, with change tracking."""

from __future__ import annotations

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, TypeAlias

import numpy as np

TelemetryScalar: TypeAlias = bool | int | float | str
#: Normalized telemetry value. Arrays are stored as homogeneous tuples.
TelemetryValue: TypeAlias = (
    TelemetryScalar | tuple[bool, ...] | tuple[int, ...] | tuple[float, ...] | tuple[str, ...]
)
#: What callers may pass in; normalized by :func:`normalize_value`.
TelemetryInput: TypeAlias = (
    TelemetryScalar
    | np.generic
    | np.ndarray
    | Sequence[bool]
    | Sequence[int]
    | Sequence[float]
    | Sequence[str]
)

_KEY_PATTERN: Final = re.compile(r"^[A-Za-z0-9_\-.]+(/[A-Za-z0-9_\-.]+)*$")


def validate_key(key: str) -> str:
    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError(
            f"Invalid telemetry key {key!r}; use 'segment/segment' with [A-Za-z0-9_-.]"
        )
    return key


def normalize_value(value: TelemetryInput) -> TelemetryValue:
    """Convert numpy and sequence inputs into one of the canonical telemetry types."""
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, np.generic):
        item = value.item()
        if isinstance(item, bool | int | float | str):
            return item
        raise TypeError(f"Unsupported numpy scalar {value!r}")
    if isinstance(value, np.ndarray):
        flat = value.ravel()
        if flat.dtype == np.bool_:
            return tuple(bool(v) for v in flat)
        if np.issubdtype(flat.dtype, np.integer):
            return tuple(int(v) for v in flat)
        if np.issubdtype(flat.dtype, np.floating):
            return tuple(float(v) for v in flat)
        raise TypeError(f"Unsupported array dtype {flat.dtype}")
    items: list[object] = list(value)
    bools = [v for v in items if isinstance(v, bool)]
    if len(bools) == len(items):
        return tuple(bools)
    strings = [v for v in items if isinstance(v, str)]
    if len(strings) == len(items):
        return tuple(strings)
    if bools or strings:
        raise TypeError("Telemetry arrays must be homogeneous bool, int, float or str")
    ints = [v for v in items if isinstance(v, int)]
    if len(ints) == len(items):
        return tuple(ints)
    numbers = [float(v) for v in items if isinstance(v, int | float)]
    if len(numbers) == len(items):
        return tuple(numbers)
    raise TypeError("Telemetry arrays must be homogeneous bool, int, float or str")


@dataclass(frozen=True, slots=True)
class TelemetryDelta:
    """Changes since a cursor. ``cursor`` is passed back to get the next delta."""

    cursor: int
    values: dict[str, TelemetryValue]
    removed: tuple[str, ...]
    full: bool  # True if this delta is a complete snapshot (first call or after a reset)


class TelemetryBus:
    """Thread-safe latest-value store.

    Writers call :meth:`put` from any thread; it is O(1) and never blocks on I/O.
    Each consumer (NetworkTables sink, every web client) keeps its own cursor and
    asks for :meth:`delta_since`, so consumers never interfere with each other.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._values: dict[str, tuple[int, TelemetryValue]] = {}
        self._removed: dict[str, int] = {}  # key -> seq of removal
        self._epoch_floor = 0  # removals older than this were compacted

    def put(self, key: str, value: TelemetryInput) -> None:
        validate_key(key)
        normalized = normalize_value(value)
        with self._lock:
            current = self._values.get(key)
            if current is not None and current[1] == normalized:
                return
            self._seq += 1
            self._values[key] = (self._seq, normalized)
            self._removed.pop(key, None)

    def get(self, key: str) -> TelemetryValue | None:
        with self._lock:
            entry = self._values.get(key)
            return None if entry is None else entry[1]

    def remove_prefix(self, prefix: str) -> int:
        """Remove every key equal to ``prefix`` or below ``prefix/``. Returns the count."""
        with self._lock:
            doomed = [k for k in self._values if k == prefix or k.startswith(prefix + "/")]
            for key in doomed:
                self._seq += 1
                del self._values[key]
                self._removed[key] = self._seq
            if len(self._removed) > 10_000:
                self._compact_locked()
            return len(doomed)

    def snapshot(self) -> dict[str, TelemetryValue]:
        with self._lock:
            return {key: value for key, (_, value) in self._values.items()}

    def delta_since(self, cursor: int) -> TelemetryDelta:
        with self._lock:
            if cursor <= 0 or cursor < self._epoch_floor or cursor > self._seq:
                values = {key: value for key, (_, value) in self._values.items()}
                return TelemetryDelta(self._seq, values, (), full=True)
            values = {key: value for key, (seq, value) in self._values.items() if seq > cursor}
            removed = tuple(key for key, seq in self._removed.items() if seq > cursor)
            return TelemetryDelta(self._seq, values, removed, full=False)

    def _compact_locked(self) -> None:
        self._removed.clear()
        self._epoch_floor = self._seq
