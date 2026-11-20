"""What the web layer needs from the rest of the application (dependency inversion)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from aether_vision.config.store import ConfigStore
from aether_vision.core.concurrency import LatestValue
from aether_vision.logging_setup.buffer import LogBuffer
from aether_vision.pipeline.result import PipelineResult
from aether_vision.streaming.hub import StreamHub
from aether_vision.telemetry.bus import TelemetryBus


class Controls(Protocol):
    def restart_pipeline(self) -> None: ...

    def restart_camera(self) -> None: ...

    def restart_process(self) -> None: ...


@dataclass(frozen=True, slots=True)
class WebServices:
    config: ConfigStore
    telemetry: TelemetryBus
    logs: LogBuffer
    results: LatestValue[PipelineResult]
    streams: StreamHub
    status: Callable[[], dict[str, object]]
    controls: Controls
