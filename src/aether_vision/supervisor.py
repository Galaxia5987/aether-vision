"""Parent process that runs the worker and respawns it on restart requests or crashes.

Restarting the *process* (not just threads) is what makes "restart after a code
change" reliable: the new worker imports the current code from disk.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from types import FrameType
from typing import Final

from aether_vision.app import SUPERVISED_ENV

_log = logging.getLogger("aether_vision.supervisor")

#: Exit code with which a worker asks to be restarted.
RESTART_EXIT_CODE: Final = 75
_TERMINATE_TIMEOUT_S: Final = 10.0
_STABLE_RUN_S: Final = 60.0
_MAX_BACKOFF_S: Final = 30.0


class Supervisor:
    def __init__(self, worker_args: Sequence[str], watch_dir: Path | None) -> None:
        self._worker_args = list(worker_args)
        self._watch_dir = watch_dir
        self._stopping = threading.Event()
        self._restart_requested = threading.Event()
        self._child: subprocess.Popen[bytes] | None = None
        self._child_lock = threading.Lock()

    def _spawn(self) -> subprocess.Popen[bytes]:
        env = dict(os.environ)
        env[SUPERVISED_ENV] = "1"
        command = [sys.executable, "-m", "aether_vision", "worker", *self._worker_args]
        _log.info("Starting worker: %s", " ".join(command))
        return subprocess.Popen(command, env=env)

    def _terminate_child(self) -> None:
        with self._child_lock:
            child = self._child
        if child is None or child.poll() is not None:
            return
        child.send_signal(signal.SIGTERM)
        try:
            child.wait(_TERMINATE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            _log.error("Worker did not exit within %.0fs; killing it", _TERMINATE_TIMEOUT_S)
            child.kill()

    def _on_signal(self, signum: int, frame: FrameType | None) -> None:
        del frame
        _log.info("Supervisor received signal %d; stopping", signum)
        self._stopping.set()
        threading.Thread(target=self._terminate_child, daemon=True).start()

    def request_restart(self) -> None:
        self._restart_requested.set()
        self._terminate_child()

    def _watch(self) -> None:
        try:
            from watchfiles import PythonFilter, watch
        except ImportError:
            _log.error("--reload needs watchfiles: uv sync --extra reload")
            return
        assert self._watch_dir is not None
        _log.info("Watching %s for code changes", self._watch_dir)
        for changes in watch(
            self._watch_dir, watch_filter=PythonFilter(), stop_event=self._stopping
        ):
            files = sorted({Path(path).name for _, path in changes})
            _log.info("Code changed (%s); restarting worker", ", ".join(files))
            self.request_restart()

    def run(self) -> int:
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)
        if self._watch_dir is not None:
            threading.Thread(target=self._watch, name="reload", daemon=True).start()

        backoff = 1.0
        while not self._stopping.is_set():
            self._restart_requested.clear()
            started = time.monotonic()
            child = self._spawn()
            with self._child_lock:
                self._child = child
            code = child.wait()
            with self._child_lock:
                self._child = None
            if self._stopping.is_set():
                break
            if code == RESTART_EXIT_CODE or self._restart_requested.is_set():
                _log.info("Worker requested restart")
                backoff = 1.0
                continue
            if code == 0:
                _log.info("Worker exited normally")
                return 0
            if time.monotonic() - started > _STABLE_RUN_S:
                backoff = 1.0
            _log.error("Worker crashed with code %d; restarting in %.0fs", code, backoff)
            if self._stopping.wait(backoff):
                break
            backoff = min(backoff * 2.0, _MAX_BACKOFF_S)
        return 0
