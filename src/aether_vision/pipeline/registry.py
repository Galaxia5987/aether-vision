"""Pipeline registry: name -> pipeline class, plus settings validation."""

from __future__ import annotations

import threading
from typing import Any, TypeVar

from aether_vision.config.base import ConfigModel
from aether_vision.config.models import AppConfig, PipelineSelection
from aether_vision.pipeline.base import Pipeline

_lock = threading.Lock()
_registry: dict[str, type[Pipeline[Any]]] = {}

PipelineClass = TypeVar("PipelineClass", bound=type[Pipeline[Any]])


def register_pipeline(cls: PipelineClass) -> PipelineClass:
    """Class decorator registering a pipeline under ``cls.name``."""
    name = getattr(cls, "name", None)
    if not isinstance(name, str) or not name:
        raise TypeError(f"{cls.__name__} must define a non-empty 'name'")
    if not isinstance(getattr(cls, "config_type", None), type):
        raise TypeError(f"{cls.__name__} must define 'config_type'")
    with _lock:
        existing = _registry.get(name)
        if existing is not None and existing.__qualname__ != cls.__qualname__:
            raise ValueError(f"Pipeline name {name!r} is already used by {existing.__qualname__}")
        _registry[name] = cls
    return cls


def available_pipelines() -> list[str]:
    _ensure_builtin()
    with _lock:
        return sorted(_registry)


def get_pipeline(name: str) -> type[Pipeline[Any]]:
    _ensure_builtin()
    with _lock:
        cls = _registry.get(name)
    if cls is None:
        raise KeyError(f"Unknown pipeline {name!r}; available: {', '.join(sorted(_registry))}")
    return cls


def validate_selection(selection: PipelineSelection) -> ConfigModel:
    """Validate ``selection.settings`` against the selected pipeline's config model."""
    cls = get_pipeline(selection.name)
    return cls.config_type.model_validate(selection.settings)


def validate_app_config(config: AppConfig) -> None:
    """:class:`ConfigStore` validator hook."""
    try:
        validate_selection(config.pipeline)
    except KeyError as error:
        raise ValueError(str(error)) from error


def pipeline_schemas() -> dict[str, dict[str, Any]]:
    _ensure_builtin()
    with _lock:
        items = list(_registry.items())
    return {
        name: {
            "description": cls.description,
            "required_streams": sorted(kind.value for kind in cls.required_streams),
            "schema": cls.config_type.model_json_schema(),
            "defaults": cls.config_type().model_dump(mode="json"),
        }
        for name, cls in sorted(items)
    }


def _ensure_builtin() -> None:
    # Importing the package registers the built-in pipelines via decorators.
    import aether_vision.pipeline.pipelines  # noqa: F401
