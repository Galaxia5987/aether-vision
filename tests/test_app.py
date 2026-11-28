from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from aether_vision import pipeline
from aether_vision.camera import CameraThread
from aether_vision.config import CameraConfig, ConfigStore, DetectorConfig
from aether_vision.pipeline import PipelineThread
from aether_vision.telemetry import Telemetry
from aether_vision.types import Box, ColorImage, Detection, FrameSet, Latest, Result
from aether_vision.web import LogBuffer, create_app


class FakeDetector:
    """Detects the mock camera's orange ball by color."""

    backend = "fake"

    def __init__(self, config: DetectorConfig) -> None:
        pass

    def detect(self, image: ColorImage, config: DetectorConfig) -> list[Detection]:
        ys, xs = np.nonzero(image[:, :, 2] == 255)
        box = Box(float(xs.min()), float(ys.min()), float(np.ptp(xs)), float(np.ptp(ys)))
        return [Detection(box, 0.9, 0, "ball")]


@dataclass
class Running:
    store: ConfigStore
    telemetry: Telemetry
    frames: Latest[FrameSet]
    results: Latest[tuple[FrameSet, Result]]


@pytest.fixture
def running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Running]:
    """Mock camera + pipeline thread with a fake detector."""
    monkeypatch.setattr(pipeline, "Detector", FakeDetector)
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    telemetry = Telemetry()
    frames: Latest[FrameSet] = Latest()
    results: Latest[tuple[FrameSet, Result]] = Latest()
    camera = CameraThread(CameraConfig(kind="mock", fps=60), frames, telemetry)
    worker = PipelineThread(store, frames, results, telemetry, nt=None)
    camera.start()
    worker.start()
    yield Running(store, telemetry, frames, results)
    worker.stop()
    camera.stop()


def test_pipeline_localizes_mock_ball(running: Running, waiter: Callable[..., bool]) -> None:
    assert waiter(lambda: running.results.get()[1] is not None)
    _, latest = running.results.get()
    assert latest is not None
    result = latest[1]
    (target,) = result.targets
    # The mock ball is 1.5 m in front of the camera, which is 0.5 m above the floor.
    assert target.distance_m == pytest.approx(1.5, abs=0.05)
    assert target.position is not None
    assert target.position[2] == pytest.approx(0.5, abs=0.3)
    assert waiter(lambda: running.telemetry.snapshot().get("pipeline/state") == "running")


def test_web_api(running: Running, waiter: Callable[..., bool]) -> None:
    store = running.store
    restarts: list[bool] = []
    app = create_app(
        store,
        running.telemetry,
        running.frames,
        running.results,
        LogBuffer(),
        lambda: restarts.append(True),
    )
    client = TestClient(app)
    assert client.get("/api/config").json()["web"]["port"] == 5803
    assert "camera" in client.get("/api/schema").json()["properties"]
    assert client.put("/api/config", json={"web": {"port": 0}}).status_code == 422
    assert client.put("/api/config", json={"detector": {"iou_threshold": 0.3}}).status_code == 200
    assert store.current.detector.iou_threshold == 0.3
    assert waiter(lambda: client.get("/api/results").json() is not None)
    assert client.get("/api/results").json()["targets"][0]["class_name"] == "ball"
    assert client.get("/api/streams").json() == ["annotated", "color", "depth"]
    client.post("/api/restart")
    assert restarts == [True]
