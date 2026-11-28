"""Dashboard backend: REST + WebSocket API, MJPEG streams and the built frontend."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections import deque
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from aether_vision import __version__
from aether_vision.config import AppConfig, ConfigStore
from aether_vision.telemetry import Telemetry
from aether_vision.types import ColorImage, FrameSet, Latest, Result

_FRONTEND = Path("frontend/dist")
_BOUNDARY = "frame"
_STREAMS = ("annotated", "color", "depth")


class LogBuffer(logging.Handler):
    """Keeps the last 1000 log lines for the dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self._lock_entries = threading.Lock()
        self._entries: deque[dict[str, Any]] = deque(maxlen=1000)
        self._seq = 0

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if record.exc_info:
            message += "\n" + logging.Formatter().formatException(record.exc_info)
        with self._lock_entries:
            self._seq += 1
            self._entries.append(
                {
                    "seq": self._seq,
                    "timestamp": record.created,
                    "level": record.levelname,
                    "logger": record.name,
                    "message": message,
                }
            )

    def since(self, seq: int) -> list[dict[str, Any]]:
        with self._lock_entries:
            return [entry for entry in self._entries if entry["seq"] > seq]


def annotate(image: ColorImage, result: Result) -> ColorImage:
    canvas = image.copy()
    for target in result.targets:
        det, box = target.detection, target.detection.box
        color = _PALETTE[det.class_id % len(_PALETTE)]
        x, y, w, h = round(box.x), round(box.y), round(box.width), round(box.height)
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        if target.position is not None and target.distance_m is not None:
            px, py, pz = target.position
            label += f" {target.distance_m:.2f}m ({px:+.2f},{py:+.2f},{pz:+.2f})"
        cv2.putText(canvas, label, (x + 2, max(y - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color)
    return canvas


def colorize_depth(depth: np.ndarray, depth_scale_m: float, max_m: float = 6.0) -> ColorImage:
    scaled = np.clip(depth * (depth_scale_m / max_m), 0.0, 1.0)
    colored = cv2.applyColorMap((255 - scaled * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    colored[depth == 0] = 0
    return np.asarray(colored, dtype=np.uint8)


_PALETTE = ((56, 56, 255), (31, 112, 255), (29, 178, 255), (49, 210, 207), (10, 249, 72))


def create_app(
    store: ConfigStore,
    telemetry: Telemetry,
    frames: Latest[FrameSet],
    results: Latest[tuple[FrameSet, Result]],
    logs: LogBuffer,
    restart: Callable[[], None],
) -> FastAPI:
    app = FastAPI(title="Aether Vision", version=__version__)

    @app.get("/api/config")
    def get_config() -> Any:
        return store.current.model_dump(mode="json")

    @app.put("/api/config")
    async def put_config(request: Request) -> Any:
        body = await request.body()
        try:
            # Listeners may restart the camera; keep that off the event loop.
            updated = await asyncio.to_thread(store.update, body)
        except ValidationError as error:
            raise HTTPException(422, str(error)) from error
        return updated.model_dump(mode="json")

    @app.get("/api/schema")
    def schema() -> Any:
        return AppConfig.model_json_schema()

    @app.get("/api/telemetry")
    def get_telemetry() -> Any:
        return telemetry.snapshot()

    @app.get("/api/results")
    def get_results() -> Any:
        _, latest = results.get()
        return None if latest is None else latest[1].to_json()

    @app.post("/api/restart")
    def post_restart() -> dict[str, str]:
        restart()
        return {"status": "restarting"}

    @app.get("/api/streams")
    def streams() -> list[str]:
        return list(_STREAMS)

    def render(name: str) -> tuple[int, ColorImage | None]:
        if name == "annotated":
            seq, latest = results.get()
            return seq, None if latest is None else annotate(latest[0].color, latest[1])
        seq, frame = frames.get()
        if frame is None:
            return seq, None
        if name == "color":
            return seq, frame.color
        depth = frame.load_depth()
        return seq, None if depth is None else colorize_depth(depth, frame.depth_scale_m)

    @app.get("/api/stream/{name}")
    def stream(name: str) -> StreamingResponse:
        if name not in _STREAMS:
            raise HTTPException(404, f"No stream named {name!r}")

        async def jpegs() -> AsyncIterator[bytes]:
            last = -1
            while True:
                seq = (results if name == "annotated" else frames).seq
                if seq != last:
                    last, image = await asyncio.to_thread(render, name)
                    if image is not None:
                        _, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        yield (
                            f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\n\r\n".encode()
                            + jpeg.tobytes()
                            + b"\r\n"
                        )
                await asyncio.sleep(1 / 30)

        return StreamingResponse(
            jpegs(), media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}"
        )

    @app.websocket("/api/ws")
    async def live(socket: WebSocket) -> None:
        """Pushes telemetry (whole snapshot on change), the newest result and new log lines."""
        await socket.accept()
        telemetry_version, result_seq, log_seq = -1, 0, 0
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            while True:
                if telemetry.version != telemetry_version:
                    telemetry_version = telemetry.version
                    await socket.send_json({"type": "telemetry", "values": telemetry.snapshot()})
                seq, latest = results.get()
                if latest is not None and seq != result_seq:
                    result_seq = seq
                    await socket.send_json({"type": "result", "data": latest[1].to_json()})
                entries = logs.since(log_seq)
                if entries:
                    log_seq = entries[-1]["seq"]
                    await socket.send_json({"type": "logs", "entries": entries})
                await asyncio.sleep(0.1)

    if (_FRONTEND / "index.html").is_file():
        app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
    return app


class WebServer:
    """Runs uvicorn on a background thread."""

    def __init__(self, app: FastAPI, port: int) -> None:
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_config=None,  # use the application's logging
            access_log=False,
            timeout_graceful_shutdown=2,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="web", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(5.0)
