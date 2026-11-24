"""FastAPI application: REST, WebSocket live updates and MJPEG streams."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Final, Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic_core import to_jsonable_python

from aether_vision import __version__
from aether_vision.config.models import AppConfig
from aether_vision.config.store import ConfigError
from aether_vision.pipeline.registry import pipeline_schemas
from aether_vision.web.services import WebServices

_log = logging.getLogger(__name__)

_BOUNDARY: Final = "aether-frame"
_WS_PERIOD_S: Final = 0.05
_WS_STATUS_PERIOD_S: Final = 1.0


def json_safe(value: object) -> Any:
    """JSON-compatible form of ``value``; NaN/Infinity become null (browsers reject them)."""
    return to_jsonable_python(value, inf_nan_mode="null")


ControlAction = Literal["restart-pipeline", "restart-camera", "restart-process"]


def create_app(services: WebServices, frontend_dir: Path | None) -> FastAPI:
    app = FastAPI(title="Aether Vision", version=__version__)
    app.state.stopping = False

    # ------------------------------------------------------------------ REST

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/status")
    def status() -> Any:
        return json_safe(services.status())

    @app.get("/api/config")
    def get_config() -> Any:
        return services.config.current.model_dump(mode="json")

    @app.put("/api/config")
    async def put_config(request: Request) -> Any:
        body = await request.body()
        try:
            # Listeners may restart threads; keep that off the event loop.
            updated = await asyncio.to_thread(services.config.update_from_json, body)
        except ConfigError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return updated.model_dump(mode="json")

    @app.get("/api/schema")
    def schema() -> Any:
        return {"app": AppConfig.model_json_schema(), "pipelines": pipeline_schemas()}

    @app.get("/api/telemetry")
    def telemetry() -> Any:
        return json_safe(services.telemetry.snapshot())

    @app.get("/api/results")
    def results() -> Any:
        latest = services.results.get()
        return None if latest is None else json_safe(latest.value.to_json())

    @app.get("/api/logs")
    def logs(after: int = 0, limit: int = 500) -> Any:
        return [entry.to_json() for entry in services.logs.since(after, limit)]

    @app.post("/api/control/{action}")
    async def control(action: ControlAction) -> dict[str, str]:
        _log.info("Control action requested from web: %s", action)
        if action == "restart-pipeline":
            services.controls.restart_pipeline()
        elif action == "restart-camera":
            await asyncio.to_thread(services.controls.restart_camera)
        else:
            services.controls.restart_process()
        return {"status": "accepted", "action": action}

    # --------------------------------------------------------------- streams

    @app.get("/api/streams")
    def streams() -> list[str]:
        return sorted(services.streams.names())

    @app.get("/api/stream/{name}")
    def stream(name: str) -> StreamingResponse:
        source = services.streams.stream(name)
        if source is None:
            raise HTTPException(status_code=404, detail=f"No stream named {name!r}")

        async def frames() -> AsyncIterator[bytes]:
            source.add_viewer()
            last_seq = -1
            try:
                while not app.state.stopping:
                    web = services.config.current.web
                    seq = source.latest_seq()
                    if seq > 0 and seq != last_seq:
                        encoded = await asyncio.to_thread(source.encode, web.jpeg_quality)
                        if encoded is not None:
                            last_seq = encoded.seq
                            header = (
                                f"--{_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                                f"Content-Length: {len(encoded.jpeg)}\r\n\r\n"
                            ).encode()
                            yield header + encoded.jpeg + b"\r\n"
                    await asyncio.sleep(1.0 / web.stream_max_fps)
            finally:
                source.remove_viewer()

        return StreamingResponse(
            frames(),
            media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
            headers={"Cache-Control": "no-store"},
        )

    # ------------------------------------------------------------- websocket

    @app.websocket("/api/ws")
    async def live(socket: WebSocket) -> None:
        await socket.accept()
        closed = asyncio.Event()

        async def drain() -> None:
            try:
                while True:
                    await socket.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                closed.set()

        reader = asyncio.create_task(drain())
        telemetry_cursor = 0
        result_seq = services.results.seq - 1 if services.results.get() else 0
        log_seq = 0
        loop = asyncio.get_running_loop()
        next_status = 0.0
        try:
            while not closed.is_set() and not app.state.stopping:
                now = loop.time()
                if now >= next_status:
                    next_status = now + _WS_STATUS_PERIOD_S
                    await socket.send_json({"type": "status", "data": json_safe(services.status())})

                delta = services.telemetry.delta_since(telemetry_cursor)
                telemetry_cursor = delta.cursor
                if delta.values or delta.removed or delta.full:
                    await socket.send_json(
                        {
                            "type": "telemetry",
                            "full": delta.full,
                            "values": json_safe(delta.values),
                            "removed": list(delta.removed),
                        }
                    )

                latest = services.results.get()
                if latest is not None and latest.seq > result_seq:
                    result_seq = latest.seq
                    await socket.send_json(
                        {"type": "result", "data": json_safe(latest.value.to_json())}
                    )

                entries = services.logs.since(log_seq, 200)
                if entries:
                    log_seq = entries[-1].seq
                    await socket.send_json(
                        {"type": "logs", "entries": [entry.to_json() for entry in entries]}
                    )

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(closed.wait(), timeout=_WS_PERIOD_S)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            reader.cancel()

    # -------------------------------------------------------------- frontend

    if frontend_dir is not None and (frontend_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    else:

        @app.get("/")
        def no_frontend() -> JSONResponse:
            return JSONResponse(
                {"message": "Frontend not built; run `npm run build` in frontend/", "api": "/docs"}
            )

    return app
