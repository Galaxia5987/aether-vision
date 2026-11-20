"""Fans pipeline results out to sinks on a dedicated thread."""

from __future__ import annotations

import threading
from typing import Protocol

from aether_vision.core.concurrency import LatestValue, ServiceThread
from aether_vision.pipeline.result import PipelineResult


class ResultSink(Protocol):
    """Receives results. Called only from the result-publisher thread."""

    def publish(self, result: PipelineResult) -> None: ...

    def close(self) -> None: ...


class ResultPublisher(ServiceThread):
    """Decouples slow sinks from the pipeline: the pipeline only does ``LatestValue.put``."""

    def __init__(self, results: LatestValue[PipelineResult], sinks: list[ResultSink]) -> None:
        super().__init__("results")
        self._results = results
        self._sinks = list(sinks)

    def run_loop(self, stop_event: threading.Event) -> None:
        last_seq = self._results.seq
        try:
            while not stop_event.is_set():
                latest = self._results.wait_newer(last_seq, 0.1)
                if latest is None:
                    continue
                last_seq = latest.seq
                for sink in self._sinks:
                    try:
                        sink.publish(latest.value)
                    except Exception:
                        self._log.exception("Result sink %r failed", sink)
        finally:
            for sink in self._sinks:
                try:
                    sink.close()
                except Exception:
                    self._log.exception("Failed to close result sink %r", sink)
