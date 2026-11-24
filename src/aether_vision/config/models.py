"""Top-level application configuration schema."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from aether_vision.config.base import RESTART_REQUIRED, ConfigModel

# --------------------------------------------------------------------------- camera


class ReconnectConfig(ConfigModel):
    initial_delay_s: float = Field(0.5, gt=0.0, le=10.0)
    max_delay_s: float = Field(5.0, gt=0.0, le=60.0)
    frame_timeout_s: float = Field(1.0, gt=0.0, le=10.0, description="Read timeout per frame")
    max_consecutive_timeouts: int = Field(
        3, ge=1, le=100, description="Timeouts in a row before the camera is reopened"
    )


class DepthFiltersConfig(ConfigModel):
    spatial: bool = False
    temporal: bool = True
    hole_filling: bool = False


class RealSenseConfig(ConfigModel):
    kind: Literal["realsense"] = "realsense"
    serial: str = Field("", description="Device serial number; empty selects the first device")
    width: int = Field(640, ge=160, le=1920)
    height: int = Field(480, ge=120, le=1080)
    fps: int = Field(30, ge=6, le=90)
    enable_depth: bool = True
    emitter_enabled: bool = True
    laser_power: float | None = Field(None, ge=0.0, le=360.0)
    color_auto_exposure: bool = True
    color_exposure_us: float | None = Field(None, ge=1.0, le=10000.0)
    filters: DepthFiltersConfig = Field(default_factory=DepthFiltersConfig)
    hardware_reset_after_failures: int = Field(
        3, ge=0, le=100, description="Failed reconnects before a hardware reset; 0 disables"
    )


class UsbCameraConfig(ConfigModel):
    kind: Literal["usb"] = "usb"
    device_index: int = Field(0, ge=0, le=64)
    width: int = Field(640, ge=160, le=3840)
    height: int = Field(480, ge=120, le=2160)
    fps: int = Field(30, ge=1, le=240)
    horizontal_fov_deg: float = Field(
        69.0, gt=1.0, lt=179.0, description="Used to synthesize intrinsics"
    )


class MockCameraConfig(ConfigModel):
    kind: Literal["mock"] = "mock"
    width: int = Field(640, ge=64, le=3840)
    height: int = Field(480, ge=64, le=2160)
    fps: int = Field(30, ge=1, le=240)
    image_path: str = Field("", description="Optional image to use as the color stream")
    target_depth_m: float = Field(1.5, gt=0.1, le=20.0)
    background_depth_m: float = Field(4.0, gt=0.1, le=20.0)


CameraConfig = Annotated[
    RealSenseConfig | UsbCameraConfig | MockCameraConfig, Field(discriminator="kind")
]


class CameraSection(ConfigModel):
    source: CameraConfig = Field(default_factory=RealSenseConfig)
    reconnect: ReconnectConfig = Field(default_factory=ReconnectConfig)


# ---------------------------------------------------------------------- networking


class NetworkTablesConfig(ConfigModel):
    enabled: bool = Field(True, json_schema_extra=RESTART_REQUIRED)
    mode: Literal["client", "server"] = Field(
        "client",
        description="'server' is for bench testing without a robot",
        json_schema_extra=RESTART_REQUIRED,
    )
    team: int = Field(5987, ge=0, le=25599, json_schema_extra=RESTART_REQUIRED)
    server_address: str = Field(
        "",
        description="Overrides team-based discovery when set",
        json_schema_extra=RESTART_REQUIRED,
    )
    root_table: str = Field(
        "AetherVision",
        min_length=1,
        pattern=r"^[A-Za-z0-9_\-]+$",
        json_schema_extra=RESTART_REQUIRED,
    )
    identity: str = Field("aether-vision", min_length=1, json_schema_extra=RESTART_REQUIRED)
    telemetry_rate_hz: float = Field(50.0, gt=0.0, le=500.0, json_schema_extra=RESTART_REQUIRED)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        "INFO", json_schema_extra=RESTART_REQUIRED
    )


class WebConfig(ConfigModel):
    enabled: bool = Field(True, json_schema_extra=RESTART_REQUIRED)
    host: str = Field("0.0.0.0", json_schema_extra=RESTART_REQUIRED)
    port: int = Field(5803, ge=1, le=65535, json_schema_extra=RESTART_REQUIRED)
    stream_max_fps: float = Field(30.0, gt=0.0, le=120.0)
    jpeg_quality: int = Field(80, ge=10, le=100)
    frontend_dir: str = Field("frontend/dist", json_schema_extra=RESTART_REQUIRED)


# ------------------------------------------------------------------------- runtime


class LoggingConfig(ConfigModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        "INFO", json_schema_extra=RESTART_REQUIRED
    )
    directory: str = Field("logs", json_schema_extra=RESTART_REQUIRED)
    max_file_mb: float = Field(10.0, gt=0.0, json_schema_extra=RESTART_REQUIRED)
    backup_count: int = Field(5, ge=0, le=100, json_schema_extra=RESTART_REQUIRED)


class WatchdogConfig(ConfigModel):
    stall_timeout_s: float = Field(
        10.0, ge=0.0, description="Pipeline stall duration that triggers recovery; 0 disables"
    )
    hard_restart_on_stall: bool = Field(
        True, description="Restart the whole process (not just the pipeline) on a stall"
    )
    max_consecutive_errors: int = Field(
        10, ge=1, description="Pipeline exceptions in a row before it is rebuilt"
    )


class PipelineSelection(ConfigModel):
    name: str = "object_detection"
    settings: dict[str, JsonValue] = Field(
        default_factory=dict, description="Validated against the selected pipeline's config"
    )


class AppConfig(ConfigModel):
    camera: CameraSection = Field(default_factory=CameraSection)
    pipeline: PipelineSelection = Field(default_factory=PipelineSelection)
    network_tables: NetworkTablesConfig = Field(default_factory=NetworkTablesConfig)
    web: WebConfig = Field(default_factory=WebConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    watchdog: WatchdogConfig = Field(default_factory=WatchdogConfig)
