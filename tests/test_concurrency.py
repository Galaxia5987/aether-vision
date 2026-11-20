from __future__ import annotations

import threading
import time

from aether_vision.core.concurrency import LatestValue, PeriodicThread, ServiceThread
from aether_vision.core.timing import RateMeter


def test_latest_value_keeps_only_newest() -> None:
    slot: LatestValue[int] = LatestValue()
    assert slot.get() is None
    slot.put(1)
    seq = slot.put(2)
    latest = slot.get()
    assert latest is not None
    assert (latest.seq, latest.value) == (seq, 2)


def test_wait_newer_times_out_and_wakes() -> None:
    slot: LatestValue[str] = LatestValue()
    assert slot.wait_newer(0, timeout=0.05) is None

    def produce() -> None:
        time.sleep(0.05)
        slot.put("frame")

    threading.Thread(target=produce).start()
    got = slot.wait_newer(0, timeout=2.0)
    assert got is not None
    assert got.value == "frame"
    assert slot.wait_newer(got.seq, timeout=0.02) is None


class _Crashing(ServiceThread):
    def run_loop(self, stop_event: threading.Event) -> None:
        raise RuntimeError("boom")


class _Looping(ServiceThread):
    def __init__(self) -> None:
        super().__init__("looping")
        self.iterations = 0

    def run_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.iterations += 1
            stop_event.wait(0.005)


def test_service_thread_records_failure() -> None:
    thread = _Crashing("crashing")
    thread.start()
    thread.stop(1.0)
    assert isinstance(thread.failed, RuntimeError)


def test_service_thread_stop_and_restart() -> None:
    thread = _Looping()
    thread.start()
    time.sleep(0.03)
    assert thread.is_running
    assert thread.stop(1.0)
    assert not thread.is_running
    before = thread.iterations
    assert thread.restart(1.0)
    time.sleep(0.03)
    assert thread.iterations > before
    thread.stop(1.0)


class _Counter(PeriodicThread):
    def __init__(self) -> None:
        super().__init__("counter", rate_hz=200.0)
        self.ticks = 0
        self.exited = False

    def tick(self) -> None:
        self.ticks += 1
        if self.ticks == 2:
            raise ValueError("ticks may fail without killing the thread")

    def on_exit(self) -> None:
        self.exited = True


def test_periodic_thread_survives_tick_errors() -> None:
    thread = _Counter()
    thread.start()
    time.sleep(0.1)
    thread.stop(1.0)
    assert thread.ticks > 5
    assert thread.exited


def test_rate_meter() -> None:
    meter = RateMeter(smoothing=1.0)
    assert meter.rate_hz == 0.0
    meter.tick()
    time.sleep(0.02)
    meter.tick()
    assert 10.0 < meter.rate_hz < 60.0
