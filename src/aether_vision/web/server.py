"""Runs uvicorn on its own thread."""

from __future__ import annotations

import threading

import uvicorn
from fastapi import FastAPI

from aether_vision.core.concurrency import ServiceThread


class WebServer(ServiceThread):
    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        super().__init__("web")
        self._app = app
        self._host = host
        self._port = port
        self._server: uvicorn.Server | None = None
        self._server_lock = threading.Lock()

    def run_loop(self, stop_event: threading.Event) -> None:
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_config=None,  # use the application's logging configuration
            access_log=False,
            timeout_graceful_shutdown=2,
            ws_ping_interval=10.0,
        )
        server = uvicorn.Server(config)
        with self._server_lock:
            self._server = server
        if stop_event.is_set():
            return
        self._log.info("Web server listening on http://%s:%d", self._host, self._port)
        server.run()  # uvicorn skips signal handling off the main thread

    def on_stop_requested(self) -> None:
        self._app.state.stopping = True
        with self._server_lock:
            if self._server is not None:
                self._server.should_exit = True
