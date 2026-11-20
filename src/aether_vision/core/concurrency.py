"""Thread-safety primitives.

Every cross-thread hand-off in the application goes through one of these classes,
so the locking rules live in exactly one place.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Versioned(Generic[T]):
    """A value tagged with a monotonically increasing sequence number."""

    seq: int
    value: T
    timestamp: float  # time.monotonic() at publish time


class LatestValue(Generic[T]):
    """A single-slot mailbox holding only the most recent value.

    Producers never block. Consumers either peek at the newest value or wait
    for one newer than the sequence number they last processed. Stale values are
    dropped, which is the behaviour real-time vision wants.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.Lock())
        self._latest: Versioned[T] | None = None
        self._seq = 0

    def put(self, value: T) -> int:
        """Publish a value and return its sequence number."""
        with self._condition:
            self._seq += 1
            self._latest = Versioned(self._seq, value, time.monotonic())
            self._condition.notify_all()
            return self._seq

    def get(self) -> Versioned[T] | None:
        """Return the newest value without waiting."""
        with self._condition:
            return self._latest

    def wait_newer(self, after_seq: int, timeout: float) -> Versioned[T] | None:
        """Wait up to ``timeout`` seconds for a value with ``seq > after_seq``."""
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._latest is None or self._latest.seq <= after_seq:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    return None
                self._condition.wait(remaining)
            return self._latest

    def clear(self) -> None:
        """Drop the stored value. The sequence counter keeps increasing."""
        with self._condition:
            self._latest = None
            self._condition.notify_all()

    @property
    def seq(self) -> int:
        with self._condition:
            return self._seq


class ServiceThread(ABC):
    """A restartable background thread with cooperative shutdown.

    Subclasses implement :meth:`run_loop`, which must return promptly once
    ``stop_event`` is set. Exceptions escaping ``run_loop`` are logged instead of
    silently killing the thread, and :attr:`failed` reports them.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._log = logging.getLogger(f"aether_vision.thread.{name}")
        self._lifecycle_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._failure: BaseException | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def failed(self) -> BaseException | None:
        return self._failure

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event = threading.Event()
            self._failure = None
            self._thread = threading.Thread(
                target=self._entrypoint, args=(self._stop_event,), name=self._name, daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> bool:
        """Request shutdown and wait. Returns ``False`` if the thread did not exit in time."""
        with self._lifecycle_lock:
            thread = self._thread
            self._stop_event.set()
            self.on_stop_requested()
            if thread is None:
                return True
            if thread is not threading.current_thread():
                thread.join(timeout)
            stopped = not thread.is_alive()
            if stopped:
                self._thread = None
            else:
                self._log.error("Thread %s did not stop within %.1fs", self._name, timeout)
            return stopped

    def restart(self, timeout: float = 5.0) -> bool:
        if not self.stop(timeout):
            return False
        self.start()
        return True

    def on_stop_requested(self) -> None:  # noqa: B027 - optional hook
        """Hook to unblock ``run_loop`` (e.g. close a socket). Called with the stop event set."""

    @abstractmethod
    def run_loop(self, stop_event: threading.Event) -> None:
        """Thread body. Must return soon after ``stop_event`` is set."""

    def _entrypoint(self, stop_event: threading.Event) -> None:
        self._log.debug("Thread started")
        try:
            self.run_loop(stop_event)
        except BaseException as error:
            self._failure = error
            self._log.exception("Thread %s crashed", self._name)
        finally:
            self._log.debug("Thread exited")


class PeriodicThread(ServiceThread):
    """A :class:`ServiceThread` that calls :meth:`tick` at a fixed rate."""

    def __init__(self, name: str, rate_hz: float) -> None:
        super().__init__(name)
        if rate_hz <= 0.0:
            raise ValueError("rate_hz must be positive")
        self._period = 1.0 / rate_hz

    @abstractmethod
    def tick(self) -> None:
        """Called once per period on the worker thread."""

    def run_loop(self, stop_event: threading.Event) -> None:
        next_tick = time.monotonic()
        while not stop_event.is_set():
            try:
                self.tick()
            except Exception:
                self._log.exception("Periodic task %s raised", self.name)
            next_tick += self._period
            delay = next_tick - time.monotonic()
            if delay < 0.0:
                next_tick = time.monotonic()  # fell behind; do not try to catch up
                delay = 0.0
            stop_event.wait(delay)
        self.on_exit()

    def on_exit(self) -> None:
        """Called on the worker thread after the loop finishes."""
