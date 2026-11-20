"""The :class:`FrameSource` abstraction every camera implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from aether_vision.core.types import FrameSet, StreamKind


class CameraError(RuntimeError):
    """The device is unavailable or failed. The camera thread will reopen it."""


class CameraTimeoutError(CameraError):
    """No frame arrived within the timeout. Transient unless it keeps happening."""


class FrameSource(ABC):
    """A blocking, single-threaded camera driver.

    Implementations do not need to be thread-safe or handle reconnection:
    :class:`~aether_vision.camera.thread.CameraThread` calls them from one thread
    and owns the retry policy.
    """

    @property
    @abstractmethod
    def streams(self) -> frozenset[StreamKind]:
        """Streams contained in every :class:`FrameSet` this source produces."""

    @abstractmethod
    def open(self) -> None:
        """Connect and start streaming. Raises :class:`CameraError` on failure."""

    @abstractmethod
    def read(self, timeout_s: float) -> FrameSet:
        """Block for the next frame set.

        Raises :class:`CameraTimeoutError` or :class:`CameraError`.
        """

    @abstractmethod
    def close(self) -> None:
        """Release the device. Must be safe to call repeatedly and after a failed ``open``."""

    def recover(self, failed_attempts: int) -> None:  # noqa: B027 - optional hook
        """Called between failed reconnect attempts, e.g. to hardware-reset a device."""

    def describe(self) -> str:
        return type(self).__name__
