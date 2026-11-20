from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from aether_vision.config.store import ConfigStore
from aether_vision.core.concurrency import LatestValue
from aether_vision.logging_setup.buffer import LogBuffer
from aether_vision.pipeline.registry import validate_app_config
from aether_vision.pipeline.result import PipelineResult
from aether_vision.streaming.hub import StreamHub
from aether_vision.telemetry.bus import TelemetryBus
from aether_vision.web.app import create_app
from aether_vision.web.services import WebServices


class _Controls:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def restart_pipeline(self) -> None:
        self.calls.append("pipeline")

    def restart_camera(self) -> None:
        self.calls.append("camera")

    def restart_process(self) -> None:
        self.calls.append("process")


Setup = tuple[TestClient, WebServices, _Controls]


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    store.add_validator(validate_app_config)
    controls = _Controls()
    bus = TelemetryBus()
    bus.put("camera/fps", float("nan"))  # must not break JSON
    results: LatestValue[PipelineResult] = LatestValue()
    results.put(PipelineResult("p", 1, 0.0, 0.01))
    hub = StreamHub()
    hub.publish("annotated", np.zeros((8, 8, 3), dtype=np.uint8))
    services = WebServices(
        config=store,
        telemetry=bus,
        logs=LogBuffer(),
        results=results,
        streams=hub,
        status=lambda: {"state": "ok"},
        controls=controls,
    )
    return TestClient(create_app(services, None)), services, controls


def test_config_roundtrip_and_validation(setup: Setup) -> None:
    client, services, _ = setup
    config = client.get("/api/config").json()
    config["pipeline"]["settings"] = {"detector": {"confidence_threshold": 0.7}}
    response = client.put("/api/config", json=config)
    assert response.status_code == 200
    assert services.config.current.pipeline.settings["detector"] == {"confidence_threshold": 0.7}

    config["pipeline"]["settings"] = {"detector": {"confidence_threshold": 7}}
    response = client.put("/api/config", json=config)
    assert response.status_code == 422
    assert "confidence_threshold" in response.json()["detail"]


def test_schema_lists_pipelines(setup: Setup) -> None:
    client, _, _ = setup
    body = client.get("/api/schema").json()
    assert {"object_detection", "passthrough"} <= set(body["pipelines"])
    assert "properties" in body["app"]


def test_controls_and_streams(setup: Setup) -> None:
    client, _, controls = setup
    for action in ("restart-pipeline", "restart-camera", "restart-process"):
        assert client.post(f"/api/control/{action}").status_code == 200
    assert controls.calls == ["pipeline", "camera", "process"]
    assert client.post("/api/control/explode").status_code == 422
    assert client.get("/api/streams").json() == ["annotated"]
    assert client.get("/api/stream/missing").status_code == 404


def test_websocket_sends_initial_state(setup: Setup) -> None:
    client, _, _ = setup
    with client.websocket_connect("/api/ws") as socket:
        kinds = {socket.receive_json()["type"] for _ in range(3)}
    assert {"status", "telemetry", "result"} <= kinds


def test_telemetry_endpoint_is_strict_json(setup: Setup) -> None:
    client, _, _ = setup
    assert client.get("/api/telemetry").json() == {"camera/fps": None}
