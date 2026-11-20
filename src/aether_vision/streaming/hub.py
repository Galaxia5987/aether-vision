"""Named image streams with lazy rendering, viewer tracking and cached JPEG encoding."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

import cv2

from aether_vision.core.concurrency import LatestValue
from aether_vision.core.types import ColorImage

SourceT = TypeVar("SourceT")


@dataclass(frozen=True, slots=True)
class EncodedFrame:
    seq: int
    jpeg: bytes


class _Stream:
    """One stream: produces the latest image on demand and caches its JPEG."""

    def __init__(
        self,
        current_seq: Callable[[], int],
        produce: Callable[[], tuple[int, ColorImage] | None],
    ) -> None:
        self._current_seq = current_seq
        self._produce = produce
        self._lock = threading.Lock()
        self._cache: EncodedFrame | None = None
        self._cache_quality = -1
        self._viewers = 0

    def latest_seq(self) -> int:
        """Sequence number of the newest source value; cheap, never renders or encodes."""
        return self._current_seq()

    def encode(self, quality: int) -> EncodedFrame | None:
        """Encode the newest image, reusing the cached JPEG if nothing changed."""
        with self._lock:
            produced = self._produce()
            if produced is None:
                return None
            seq, image = produced
            if (
                self._cache is not None
                and self._cache.seq == seq
                and self._cache_quality == quality
            ):
                return self._cache
            ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                return None
            self._cache = EncodedFrame(seq, buffer.tobytes())
            self._cache_quality = quality
            return self._cache

    def add_viewer(self) -> None:
        with self._lock:
            self._viewers += 1

    def remove_viewer(self) -> None:
        with self._lock:
            self._viewers = max(0, self._viewers - 1)

    @property
    def viewers(self) -> int:
        with self._lock:
            return self._viewers


def _seq_of(value: LatestValue[SourceT]) -> int:
    latest = value.get()
    return 0 if latest is None else latest.seq


class _DerivedSource(Generic[SourceT]):
    """Renders an image from another :class:`LatestValue` only when requested."""

    def __init__(
        self, source: LatestValue[SourceT], render: Callable[[SourceT], ColorImage | None]
    ) -> None:
        self._source = source
        self._render = render
        self._lock = threading.Lock()
        self._rendered: tuple[int, ColorImage] | None = None

    def __call__(self) -> tuple[int, ColorImage] | None:
        latest = self._source.get()
        if latest is None:
            return None
        with self._lock:
            if self._rendered is not None and self._rendered[0] == latest.seq:
                return self._rendered
            image = self._render(latest.value)
            if image is None:
                return None
            self._rendered = (latest.seq, image)
            return self._rendered


class StreamHub:
    """Registry of debug streams. Thread-safe.

    Publishing a frame is a pointer swap. Encoding happens on the web server's
    threads, only while somebody is watching.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._streams: dict[str, _Stream] = {}
        self._direct: dict[str, LatestValue[ColorImage]] = {}

    def names(self) -> list[str]:
        with self._lock:
            return list(self._streams)

    def _get_or_create_direct(self, name: str) -> LatestValue[ColorImage]:
        with self._lock:
            slot = self._direct.get(name)
            if slot is None:
                slot = LatestValue[ColorImage]()
                self._direct[name] = slot
                bound = slot

                def produce() -> tuple[int, ColorImage] | None:
                    latest = bound.get()
                    return None if latest is None else (latest.seq, latest.value)

                self._streams[name] = _Stream(lambda: _seq_of(bound), produce)
            return slot

    def publish(self, name: str, image: ColorImage) -> None:
        self._get_or_create_direct(name).put(image)

    def register_derived(
        self,
        name: str,
        source: LatestValue[SourceT],
        render: Callable[[SourceT], ColorImage | None],
    ) -> None:
        """Register a stream rendered lazily from another value (e.g. colorized depth)."""
        with self._lock:
            self._streams[name] = _Stream(lambda: _seq_of(source), _DerivedSource(source, render))

    def has_viewers(self, name: str) -> bool:
        with self._lock:
            stream = self._streams.get(name)
        return stream is not None and stream.viewers > 0

    def stream(self, name: str) -> _Stream | None:
        with self._lock:
            return self._streams.get(name)


class DebugStreams:
    """Pipeline-facing facade: publish debug images, skip work when nobody watches."""

    def __init__(self, hub: StreamHub, always_render: bool = False) -> None:
        self._hub = hub
        self._always_render = always_render

    def wants(self, name: str) -> bool:
        """``True`` if a client is watching ``name`` (or the stream does not exist yet)."""
        if self._always_render:
            return True
        if self._hub.stream(name) is None:
            return True  # first publish registers the stream so the UI can list it
        return self._hub.has_viewers(name)

    def publish(self, name: str, image: ColorImage) -> None:
        self._hub.publish(name, image)
