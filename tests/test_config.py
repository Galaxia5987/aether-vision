from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aether_vision.config import AppConfig, ConfigStore


def test_missing_file_writes_defaults(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    assert store.load() == AppConfig()
    assert AppConfig.model_validate_json((tmp_path / "config.json").read_text()) == AppConfig()


def test_invalid_file_is_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"camera": {"fps": "fast"}}')
    assert ConfigStore(path).load() == AppConfig()
    assert len(list(tmp_path.glob("config.invalid-*.json"))) == 1


def test_update_saves_and_notifies(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    seen: list[tuple[int, int]] = []
    store.subscribe(lambda old, new: seen.append((old.web.port, new.web.port)))
    store.update('{"web": {"port": 8080}}')
    assert seen == [(5803, 8080)]
    assert ConfigStore(tmp_path / "config.json").load().web.port == 8080
    with pytest.raises(ValidationError):
        store.update('{"unknown": 1}')
    assert store.current.web.port == 8080
