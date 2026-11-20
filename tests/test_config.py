from __future__ import annotations

import json
from pathlib import Path

import pytest

from aether_vision.config.diff import changed_fields, requires_restart
from aether_vision.config.models import AppConfig, MockCameraConfig, PipelineSelection
from aether_vision.config.store import ConfigError, ConfigStore
from aether_vision.pipeline.pipelines.object_detection import ObjectDetectionConfig
from aether_vision.pipeline.registry import validate_app_config


def test_load_writes_defaults(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    config = store.load()
    assert config == AppConfig()
    assert json.loads((tmp_path / "config.json").read_text())["web"]["port"] == 5803


def test_corrupt_config_is_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{ not json")
    store = ConfigStore(path)
    assert store.load() == AppConfig()
    backups = list(tmp_path.glob("config.invalid-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text() == "{ not json"


def test_update_persists_and_notifies(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    seen: list[tuple[AppConfig, AppConfig]] = []
    store.subscribe(lambda old, new: seen.append((old, new)))
    new = store.current.model_copy(
        update={"camera": store.current.camera.model_copy(update={"source": MockCameraConfig()})}
    )
    store.update(new)
    assert len(seen) == 1
    reloaded = ConfigStore(tmp_path / "config.json").load()
    assert isinstance(reloaded.camera.source, MockCameraConfig)


def test_validator_rejects_bad_pipeline_settings(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    store.add_validator(validate_app_config)
    bad = AppConfig(
        pipeline=PipelineSelection(
            name="object_detection", settings={"detector": {"confidence_threshold": 5}}
        )
    )
    with pytest.raises(ConfigError, match="confidence_threshold"):
        store.update(bad)
    with pytest.raises(ConfigError, match="Unknown pipeline"):
        store.update(AppConfig(pipeline=PipelineSelection(name="nope")))
    assert store.current == AppConfig()


def test_live_field_change_does_not_require_restart() -> None:
    old = ObjectDetectionConfig()
    new = ObjectDetectionConfig.model_validate({"detector": {"confidence_threshold": 0.8}})
    assert changed_fields(old, new) == ["detector.confidence_threshold"]
    assert not requires_restart(old, new)


def test_restart_field_change_requires_restart() -> None:
    old = ObjectDetectionConfig()
    assert requires_restart(
        old, ObjectDetectionConfig.model_validate({"detector": {"model_path": "other.onnx"}})
    )
    # Nested field inside a restart-required parent (backend).
    assert requires_restart(
        old,
        ObjectDetectionConfig.model_validate(
            {"detector": {"backend": {"kind": "onnxruntime", "intra_op_threads": 2}}}
        ),
    )
    # Switching a union variant always restarts.
    assert requires_restart(
        old, ObjectDetectionConfig.model_validate({"detector": {"backend": {"kind": "litert"}}})
    )


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValueError, match="extra"):
        ObjectDetectionConfig.model_validate({"detectr": {}})
