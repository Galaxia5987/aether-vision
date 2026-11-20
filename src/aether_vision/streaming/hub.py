"""Named image streams with lazy rendering, viewer tracking and cached JPEG encoding."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import cv2

from aether_vision.core.concurrency import LatestValue
from aether_vision.core.types import ColorImage

SourceT = TypeVar("SourceT")


@dataclass(frozen=True, slots=True)
class EncodedFrame:
    seq: int
    jpeg: bytes


class Stream(Generic[SourceT]):
    """An image rendered from a :class:`LatestValue`, rendered and encoded only on demand.

    The rendered image and JPEG are cached per source sequence number, so any
    number of viewers share one encode per frame.
    """

    def __init__(
        self, source: LatestValue[SourceT], render: Callable[[SourceT], ColorImage | None]
    ) -> None:
        self._source = source
        self._render = render
        self._lock = threading.Lock()
        self._cache: EncodedFrame | None = None
        self._cache_quality = -1
        self._viewers = 0

    def latest_seq(self) -> int:
        """Sequence number of the newest source value; cheap, never renders or encodes."""
        latest = self._source.get()
        return 0 if latest is None else latest.seq

    def encode(self, quality: int) -> EncodedFrame | None:
        with self._lock:
            latest = self._source.get()
            if latest is None:
                return None
            cache = self._cache
            if cache is not None and cache.seq == latest.seq and self._cache_quality == quality:
                return cache
            image = self._render(latest.value)
            if image is None:
                return None
            ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                return None
            self._cache = EncodedFrame(latest.seq, buffer.tobytes())
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


def _identity(image: ColorImage) -> ColorImage:
    return image


class StreamHub:
    """Registry of debug streams. Thread-safe.

    Publishing a frame is a pointer swap; rendering and encoding happen on the
    web server's threads, only while somebody is watching.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._streams: dict[str, Stream[Any]] = {}
        self._published: dict[str, LatestValue[ColorImage]] = {}

    def names(self) -> list[str]:
        with self._lock:
            return list(self._streams)

    def register(
        self,
        name: str,
        source: LatestValue[SourceT],
        render: Callable[[SourceT], ColorImage | None],
    ) -> None:
        """Register a stream rendered lazily from another value (e.g. colorized depth)."""
        with self._lock:
            self._streams[name] = Stream(source, render)

    def publish(self, name: str, image: ColorImage) -> None:
        """Publish a ready-made image, creating the stream on first use."""
        with self._lock:
            slot = self._published.get(name)
            if slot is None:
                slot = self._published[name] = LatestValue()
                self._streams[name] = Stream(slot, _identity)
        slot.put(image)

    def stream(self, name: str) -> Stream[Any] | None:
        with self._lock:
            return self._streams.get(name)


class DebugStreams:
    """Pipeline-facing facade: publish debug images, skip work when nobody watches."""

    def __init__(self, hub: StreamHub) -> None:
        self._hub = hub

    def wants(self, name: str) -> bool:
        """``True`` if a client is watching ``name``, or the stream does not exist yet
        (the first publish registers it so the UI can list it)."""
        stream = self._hub.stream(name)
        return stream is None or stream.viewers > 0

    def publish(self, name: str, image: ColorImage) -> None:
        self._hub.publish(name, image)
