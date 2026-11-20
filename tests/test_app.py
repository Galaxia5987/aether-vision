from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path

from aether_vision.app import Application, ExitReason


def _field(app: Application, section: str, key: str) -> object:
    value = app.status()[section]
    assert isinstance(value, dict)
    return value[key]


def test_application_end_to_end(tmp_path: Path, waiter: Callable[..., bool]) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "camera": {"source": {"kind": "mock", "width": 160, "height": 120, "fps": 60}},
                "pipeline": {"name": "passthrough"},
                "network_tables": {"enabled": False},
                "web": {"enabled": False},
                "logging": {"directory": str(tmp_path / "logs")},
            }
        )
    )
    app = Application(config_path)
    reason: list[ExitReason] = []
    thread = threading.Thread(target=lambda: reason.append(app.run()))
    thread.start()
    try:
        assert waiter(lambda: _field(app, "pipeline", "state") == "running", 10.0)
        assert waiter(lambda: float(str(_field(app, "camera", "fps"))) > 1.0, 10.0)
        app.restart_process()
        thread.join(15.0)
    finally:
        app.request_shutdown()
        thread.join(15.0)
    assert reason == [ExitReason.RESTART]
    assert (tmp_path / "logs" / "aether-vision.log").is_file()
