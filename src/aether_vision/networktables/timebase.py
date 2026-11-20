"""Conversion between ``time.monotonic()`` and the NetworkTables time base."""

from __future__ import annotations

import time

import ntcore


def nt_local_now_us() -> int:
    """Current time in the local NT time base (microseconds)."""
    return int(ntcore._now())


def monotonic_to_nt_us(timestamp_s: float) -> int:
    """Map a ``time.monotonic()`` timestamp to the local NT time base."""
    age_us = max(0, int((time.monotonic() - timestamp_s) * 1_000_000))
    return max(1, nt_local_now_us() - age_us)  # 0 would mean "now" to ntcore


def to_server_time_us(instance: ntcore.NetworkTableInstance, local_us: int) -> int:
    """Map local NT time to the server's (robot's) clock; identity if not synchronized."""
    offset = instance.getServerTimeOffset()
    return local_us + int(offset) if offset is not None else local_us
