"""Configuration schema and the JSON file that stores it."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_log = logging.getLogger(__name__)


class _Model(BaseModel):
    # Frozen so a config object can be shared between threads; updates replace it.
    model_config = ConfigDict(frozen=True, extra="forbid")


class CameraConfig(_Model):
    kind: Literal["realsense", "mock"] = "realsense"
    serial: str = Field("", description="RealSense serial number; empty uses the first device")
    width: int = Field(640, ge=160, le=1920)
    height: int = Field(480, ge=120, le=1080)
    fps: int = Field(30, ge=6, le=90)
    exposure_us: float | None = Field(
        None, ge=1.0, le=10000.0, description="Color exposure; empty for auto exposure"
    )


class DetectorConfig(_Model):
    model_path: str = Field(
        "models/yolox.tflite", description="TFLite model (int8 for the NPU); reloaded on change"
    )
    labels_path: str = Field("models/labels.txt", description="One class name per line")
    use_npu: bool = Field(True, description="Run on the Qualcomm NPU; falls back to the CPU")
    confidence_threshold: float = Field(0.4, ge=0.0, le=1.0)
    iou_threshold: float = Field(0.45, ge=0.0, le=1.0)
    max_detections: int = Field(20, ge=1, le=300)
    class_filter: tuple[int, ...] = Field((), description="Keep only these class ids; empty = all")


class CameraMount(_Model):
    """Camera pose on the robot (WPILib axes: x forward, y left, z up; robot-center origin)."""

    x_m: float = 0.0
    y_m: float = 0.0
    z_m: float = 0.5
    roll_deg: float = 0.0
    pitch_deg: float = Field(0.0, description="Positive pitches the camera down")
    yaw_deg: float = 0.0


class NetworkTablesConfig(_Model):
    team: int = Field(5987, ge=0, le=25599)
    server_address: str = Field("", description="Overrides team-based discovery when set")


class WebConfig(_Model):
    port: int = Field(5803, ge=1, le=65535)


class AppConfig(_Model):
    camera: CameraConfig = CameraConfig()
    detector: DetectorConfig = DetectorConfig()
    camera_mount: CameraMount = CameraMount()
    network_tables: NetworkTablesConfig = NetworkTablesConfig()
    web: WebConfig = WebConfig()


Listener = Callable[[AppConfig, AppConfig], None]


class ConfigStore:
    """The current config, persisted atomically to a JSON file. Thread-safe."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._config = AppConfig()
        self._listeners: list[Listener] = []

    @property
    def current(self) -> AppConfig:
        return self._config

    def load(self) -> AppConfig:
        """Read the file; a missing or invalid one is replaced by defaults (invalid: backed up)."""
        with self._lock:
            try:
                self._config = AppConfig.model_validate_json(self.path.read_bytes())
            except FileNotFoundError:
                _log.info("No config at %s; writing defaults", self.path)
                self._write(self._config)
            except ValueError as error:
                backup = self.path.with_suffix(f".invalid-{int(time.time())}.json")
                _log.error("Invalid config %s (%s); moved to %s", self.path, error, backup)
                self.path.replace(backup)
                self._write(self._config)
            return self._config

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def update(self, payload: str | bytes) -> AppConfig:
        """Validate a JSON config, save it and notify listeners. Raises ``ValueError``."""
        new = AppConfig.model_validate_json(payload)
        with self._lock:
            old = self._config
            if new == old:
                return old
            self._write(new)
            self._config = new
        _log.info("Configuration updated")
        for listener in self._listeners:
            listener(old, new)
        return new

    def _write(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(config.model_dump_json(indent=2) + "\n")
        os.replace(tmp, self.path)
