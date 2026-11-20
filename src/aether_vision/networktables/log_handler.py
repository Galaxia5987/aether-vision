"""Forwards text log records to NetworkTables."""

from __future__ import annotations

import logging

import ntcore


class NetworkTablesLogHandler(logging.Handler):
    """Publishes formatted records to ``log/messages`` (every value sent) and ``log/last_error``.

    ntcore publishers are thread-safe, so records are published directly from
    the logging thread without extra queues.
    """

    def __init__(self, instance: ntcore.NetworkTableInstance, root: str, level: int) -> None:
        super().__init__(level)
        table = instance.getTable(f"{root.rstrip('/')}/log")
        options = ntcore.PubSubOptions(sendAll=True, keepDuplicates=True)
        self._messages = table.getStringTopic("messages").publish(options)
        self._last_error = table.getStringTopic("last_error").publish()
        self.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("nt"):  # ntcore's own logging; avoid feedback loops
            return
        try:
            message = self.format(record)
            self._messages.set(message)
            if record.levelno >= logging.ERROR:
                self._last_error.set(message)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self._messages.close()
        self._last_error.close()
        super().close()
