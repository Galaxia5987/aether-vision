"""Test doubles shared by several test modules."""

from __future__ import annotations

import numpy as np

from aether_vision.camera.base import CameraError, CameraTimeoutError, FrameSource
from aether_vision.core.types import CameraIntrinsics, FrameSet, StreamKind
from aether_vision.inference.backend import InferenceBackend, Quantization, TensorSpec

INTRINSICS = CameraIntrinsics(width=64, height=48, fx=50.0, fy=50.0, cx=32.0, cy=24.0)


def make_frames(number: int = 1, depth_m: float = 2.0) -> FrameSet:
    color = np.zeros((48, 64, 3), dtype=np.uint8)
    depth = np.full((48, 64), int(depth_m * 1000), dtype=np.uint16)
    return FrameSet(
        frame_number=number,
        capture_time_s=0.0,
        color=color,
        depth=depth,
        depth_scale_m=0.001,
        intrinsics=INTRINSICS,
    )


class ScriptedSource(FrameSource):
    """Plays back actions ('frame', 'timeout', 'error'); ``open`` fails ``open_failures`` times."""

    def __init__(self, script: list[str], open_failures: int = 0) -> None:
        self.script = list(script)
        self.open_failures = open_failures
        self.opens = 0
        self.closes = 0
        self.recover_calls: list[int] = []
        self._number = 0

    @property
    def streams(self) -> frozenset[StreamKind]:
        return frozenset({StreamKind.COLOR, StreamKind.DEPTH})

    def open(self) -> None:
        self.opens += 1
        if self.open_failures > 0:
            self.open_failures -= 1
            raise CameraError("not plugged in")

    def read(self, timeout_s: float) -> FrameSet:
        action = self.script.pop(0) if self.script else "idle"
        if action == "timeout":
            raise CameraTimeoutError("late")
        if action == "error":
            raise CameraError("unplugged")
        if action == "idle":
            import time

            time.sleep(timeout_s)
            raise CameraTimeoutError("idle")
        self._number += 1
        return make_frames(self._number)

    def close(self) -> None:
        self.closes += 1

    def recover(self, failed_attempts: int) -> None:
        self.recover_calls.append(failed_attempts)


class StaticBackend(InferenceBackend):
    """Returns a fixed output tensor; records the inputs it received."""

    def __init__(
        self,
        output: np.ndarray,
        input_shape: tuple[int, ...] = (1, 3, 64, 64),
        input_dtype: np.dtype[np.generic] | None = None,
        input_quant: Quantization | None = None,
        output_quant: Quantization | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self._output = output
        self._input = TensorSpec(
            "images", input_shape, input_dtype or np.dtype(np.float32), input_quant
        )
        self._output_spec = TensorSpec("out", tuple(output.shape), output.dtype, output_quant)
        self._metadata = metadata or {}
        self.received: list[np.ndarray] = []

    def load(self) -> None:
        pass

    @property
    def inputs(self) -> tuple[TensorSpec, ...]:
        return (self._input,)

    @property
    def outputs(self) -> tuple[TensorSpec, ...]:
        return (self._output_spec,)

    @property
    def metadata(self) -> dict[str, str]:
        return self._metadata

    @property
    def description(self) -> str:
        return "static"

    def run(self, inputs: list[np.ndarray]) -> list[np.ndarray]:
        self.received.append(inputs[0])
        return [self._output]


class MultiOutputBackend(StaticBackend):
    """Returns several fixed output tensors, described by ``specs``."""

    def __init__(
        self, outputs: list[np.ndarray], specs: list[TensorSpec], **kwargs: object
    ) -> None:
        super().__init__(outputs[0], **kwargs)  # type: ignore[arg-type]
        self._outputs = outputs
        self._specs = tuple(specs)

    @property
    def outputs(self) -> tuple[TensorSpec, ...]:
        return self._specs

    def run(self, inputs: list[np.ndarray]) -> list[np.ndarray]:
        self.received.append(inputs[0])
        return list(self._outputs)
