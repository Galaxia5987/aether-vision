"""Thread-safe persistence of :class:`AppConfig` with change notification."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from aether_vision.config.models import AppConfig

_log = logging.getLogger(__name__)

ConfigListener = Callable[[AppConfig, AppConfig], None]
ConfigValidator = Callable[[AppConfig], None]


class ConfigError(ValueError):
    """Raised when a configuration is rejected."""


class ConfigStore:
    """Owns the current configuration.

    * Reads and writes are atomic (write to a temp file, then ``os.replace``).
    * ``current`` returns an immutable snapshot, safe to share between threads.
    * Validators (e.g. pipeline-settings validation) run before a config is accepted.
    * Listeners run on the caller's thread after the new config is committed.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._config = AppConfig()
        self._listeners: list[ConfigListener] = []
        self._validators: list[ConfigValidator] = []

    @property
    def path(self) -> Path:
        return self._path

    @property
    def current(self) -> AppConfig:
        with self._lock:
            return self._config

    def load(self) -> AppConfig:
        """Load from disk, falling back to defaults. A corrupt file is backed up, not lost."""
        with self._lock:
            if not self._path.exists():
                _log.info("No config at %s; writing defaults", self._path)
                self._config = AppConfig()
                self._write(self._config)
                return self._config
            try:
                raw = self._path.read_text(encoding="utf-8")
                self._config = AppConfig.model_validate_json(raw)
                _log.info("Loaded config from %s", self._path)
            except (ValidationError, OSError, ValueError) as error:
                backup = self._path.with_suffix(f".invalid-{int(time.time())}.json")
                _log.error("Config %s is invalid (%s); backing up to %s", self._path, error, backup)
                try:
                    self._path.replace(backup)
                except OSError:
                    _log.exception("Could not back up invalid config")
                self._config = AppConfig()
                self._write(self._config)
            return self._config

    def add_validator(self, validator: ConfigValidator) -> None:
        with self._lock:
            self._validators.append(validator)

    def subscribe(self, listener: ConfigListener) -> Callable[[], None]:
        """Register a listener; returns a function that unregisters it."""
        with self._lock:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def update(self, new_config: AppConfig) -> AppConfig:
        """Validate, persist and publish a new configuration."""
        with self._lock:
            for validator in self._validators:
                try:
                    validator(new_config)
                except (ValueError, ValidationError) as error:
                    raise ConfigError(str(error)) from error
            old = self._config
            if new_config == old:
                return old
            self._write(new_config)
            self._config = new_config
            listeners = list(self._listeners)
        _log.info("Configuration updated")
        for listener in listeners:
            try:
                listener(old, new_config)
            except Exception:
                _log.exception("Config listener %r failed", listener)
        return new_config

    def update_from_json(self, payload: str | bytes) -> AppConfig:
        try:
            config = AppConfig.model_validate_json(payload)
        except ValidationError as error:
            raise ConfigError(str(error)) from error
        return self.update(config)

    def _write(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(config.model_dump(mode="json"), indent=2) + "\n"
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=".config-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
