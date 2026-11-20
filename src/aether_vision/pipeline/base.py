"""Core pipeline abstractions.

A *pipeline* turns a :class:`FrameSet` into a :class:`PipelineResult`. It is made
of *stages*: small reusable steps that are timed automatically and get their
own telemetry scope. Writing a new pipeline::

    class MyConfig(ConfigModel):
        threshold: float = 0.5

    @register_pipeline
    class MyPipeline(Pipeline[MyConfig]):
        name = "my_pipeline"
        config_type = MyConfig
        required_streams = frozenset({StreamKind.COLOR})

        def setup(self) -> None:
            self.blur = self.add_stage(BlurStage())

        def process(self, frames: FrameSet) -> PipelineResult:
            image = self.blur(frames.require_color())
            self.telemetry.put("mean", float(image.mean()))
            return self.empty_result(frames)
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from aether_vision.config.base import ConfigModel
from aether_vision.core.timing import Stopwatch
from aether_vision.core.types import FrameSet, StreamKind
from aether_vision.pipeline.result import PipelineResult
from aether_vision.streaming.hub import DebugStreams
from aether_vision.telemetry.view import Telemetry

InT = TypeVar("InT")
OutT = TypeVar("OutT")
ConfigT = TypeVar("ConfigT", bound=ConfigModel)


@dataclass(frozen=True, slots=True)
class PipelineContext:
    """Services available to a pipeline and its stages."""

    telemetry: Telemetry
    debug: DebugStreams
    logger: logging.Logger


class ConfigHandle(Generic[ConfigT]):
    """Thread-safe holder of a pipeline's current (immutable) configuration."""

    def __init__(self, config: ConfigT) -> None:
        self._lock = threading.Lock()
        self._config = config

    def get(self) -> ConfigT:
        with self._lock:
            return self._config

    def set(self, config: ConfigT) -> None:
        with self._lock:
            self._config = config


class Stage(ABC, Generic[InT, OutT]):
    """A single processing step. Call the stage (``stage(value)``) to run it timed."""

    def __init__(self, name: str | None = None) -> None:
        self._name = name or _snake_case(type(self).__name__.removesuffix("Stage"))
        self._telemetry: Telemetry | None = None
        self._logger = logging.getLogger(f"aether_vision.stage.{self._name}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def telemetry(self) -> Telemetry:
        if self._telemetry is None:
            raise RuntimeError(f"Stage {self._name} is not attached to a pipeline")
        return self._telemetry

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def attach(self, telemetry: Telemetry) -> None:
        self._telemetry = telemetry

    def setup(self) -> None:
        """Acquire resources (load models, ...). Called once, on the pipeline thread."""

    @abstractmethod
    def process(self, value: InT) -> OutT:
        """Do the work."""

    def teardown(self) -> None:
        """Release resources. Called once, on the pipeline thread."""

    def __call__(self, value: InT) -> OutT:
        watch = Stopwatch()
        with watch:
            result = self.process(value)
        self.telemetry.put("latency_ms", round(watch.elapsed_ms, 3))
        return result


class Pipeline(ABC, Generic[ConfigT]):
    """Base class for pipelines. Subclasses set the three class attributes below."""

    name: ClassVar[str]
    config_type: ClassVar[type[ConfigModel]]
    required_streams: ClassVar[frozenset[StreamKind]] = frozenset({StreamKind.COLOR})
    description: ClassVar[str] = ""

    def __init__(self, context: PipelineContext, config: ConfigHandle[ConfigT]) -> None:
        self._context = context
        self._config = config
        self._stages: list[Stage[object, object]] = []

    # ----------------------------------------------------------- for subclasses

    @property
    def config(self) -> ConfigT:
        """The latest configuration. Read it every frame to pick up live changes."""
        return self._config.get()

    @property
    def telemetry(self) -> Telemetry:
        return self._context.telemetry

    @property
    def debug(self) -> DebugStreams:
        return self._context.debug

    @property
    def logger(self) -> logging.Logger:
        return self._context.logger

    def add_stage(self, stage: Stage[InT, OutT]) -> Stage[InT, OutT]:
        """Attach and set up a stage; it is torn down automatically (in reverse order)."""
        if any(existing.name == stage.name for existing in self._stages):
            raise ValueError(f"Duplicate stage name {stage.name!r}")
        stage.attach(self.telemetry.scope(f"stages/{stage.name}"))
        stage.setup()
        self._stages.append(stage)  # type: ignore[arg-type]
        return stage

    def empty_result(self, frames: FrameSet) -> PipelineResult:
        return PipelineResult(self.name, frames.frame_number, frames.capture_time_s)

    @abstractmethod
    def setup(self) -> None:
        """Build stages with :meth:`add_stage`."""

    @abstractmethod
    def process(self, frames: FrameSet) -> PipelineResult:
        """Process one frame set."""

    def on_teardown(self) -> None:
        """Extra cleanup, called before stages are torn down."""

    # ----------------------------------------------------------- for the runner

    def teardown(self) -> None:
        try:
            self.on_teardown()
        finally:
            for stage in reversed(self._stages):
                try:
                    stage.teardown()
                except Exception:
                    self.logger.exception("Teardown of stage %s failed", stage.name)
            self._stages.clear()


def _snake_case(name: str) -> str:
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0 and not name[index - 1].isupper():
            out.append("_")
        out.append(char.lower())
    return "".join(out) or "stage"
