"""In-memory log ring buffer read by the web frontend."""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LogEntry:
    seq: int
    timestamp: float  # UNIX epoch seconds
    level: str
    logger: str
    thread: str
    message: str

    def to_json(self) -> dict[str, str | float | int]:
        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "thread": self.thread,
            "message": self.message,
        }


class LogBuffer(logging.Handler):
    """A logging handler that keeps the last ``capacity`` records.

    Readers poll with a cursor (:meth:`since`) instead of registering callbacks,
    so logging from any thread never calls into a consumer's event loop.
    """

    def __init__(self, capacity: int = 1000, level: int = logging.DEBUG) -> None:
        super().__init__(level)
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._entries_lock = threading.Lock()
        self._seq = 0

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info is not None:
                formatter = self.formatter or logging.Formatter()
                message = f"{message}\n{formatter.formatException(record.exc_info)}"
            with self._entries_lock:
                self._seq += 1
                self._entries.append(
                    LogEntry(
                        seq=self._seq,
                        timestamp=record.created,
                        level=record.levelname,
                        logger=record.name,
                        thread=record.threadName or "",
                        message=message,
                    )
                )
        except Exception:
            self.handleError(record)

    def since(self, after_seq: int, limit: int = 500) -> list[LogEntry]:
        with self._entries_lock:
            newer = [entry for entry in self._entries if entry.seq > after_seq]
        return newer[-limit:]

    @property
    def last_seq(self) -> int:
        with self._entries_lock:
            return self._seq
