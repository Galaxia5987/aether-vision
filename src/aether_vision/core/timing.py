"""Time measurement helpers."""

from __future__ import annotations

import threading
import time
from types import TracebackType


def now_s() -> float:
    """Monotonic time in seconds."""
    return time.monotonic()


class Stopwatch:
    """Context manager measuring elapsed wall time in milliseconds."""

    __slots__ = ("_start", "elapsed_ms")

    def __init__(self) -> None:
        self._start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> Stopwatch:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0


class RateMeter:
    """Thread-safe event-rate estimator using an exponential moving average."""

    def __init__(self, smoothing: float = 0.1) -> None:
        if not 0.0 < smoothing <= 1.0:
            raise ValueError("smoothing must be in (0, 1]")
        self._smoothing = smoothing
        self._lock = threading.Lock()
        self._last: float | None = None
        self._period_s: float | None = None

    def tick(self) -> None:
        stamp = time.monotonic()
        with self._lock:
            if self._last is not None:
                period = stamp - self._last
                if self._period_s is None:
                    self._period_s = period
                else:
                    self._period_s += self._smoothing * (period - self._period_s)
            self._last = stamp

    @property
    def rate_hz(self) -> float:
        with self._lock:
            if self._period_s is None or self._period_s <= 0.0 or self._last is None:
                return 0.0
            # Decay towards zero if events stopped arriving.
            if time.monotonic() - self._last > 4.0 * max(self._period_s, 0.25):
                return 0.0
            return 1.0 / self._period_s

    def reset(self) -> None:
        with self._lock:
            self._last = None
            self._period_s = None
