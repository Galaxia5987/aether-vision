from __future__ import annotations

import time
from collections.abc import Callable

import pytest


def wait_until(predicate: Callable[[], bool], timeout: float = 5.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


@pytest.fixture
def waiter() -> Callable[..., bool]:
    return wait_until
