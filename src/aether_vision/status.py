"""Typed application status, served to the dashboard and summarized on NetworkTables."""

from __future__ import annotations

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    state: str
    fps: float = 0.0
    last_error: str = ""


class CameraStatus(ComponentStatus):
    source: str = ""


class PipelineStatus(ComponentStatus):
    name: str = ""


class NetworkTablesStatus(BaseModel):
    enabled: bool
    connected: bool


class AppStatus(BaseModel):
    version: str
    uptime_s: float
    supervised: bool
    restart_pending: bool
    camera: CameraStatus
    pipeline: PipelineStatus
    network_tables: NetworkTablesStatus
