"""Decide whether a configuration change can be applied without a restart."""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from aether_vision.config.base import RESTART_KEY


def _is_restart_field(info: FieldInfo) -> bool:
    extra = info.json_schema_extra
    return isinstance(extra, dict) and extra.get(RESTART_KEY) is True


def _diff(
    old: BaseModel, new: BaseModel, prefix: str = "", restart: bool = False
) -> Iterator[tuple[str, bool]]:
    """Yield ``(dotted path, needs restart)`` for every changed leaf.

    A field needs a restart if it, or any ancestor, is marked restart-required,
    or if a nested model changed type (e.g. a different union variant).
    """
    if type(old) is not type(new):
        yield prefix.rstrip(".") or "<root>", True
        return
    for name, info in type(old).model_fields.items():
        old_value: object = getattr(old, name)
        new_value: object = getattr(new, name)
        if old_value == new_value:
            continue
        field_restart = restart or _is_restart_field(info)
        if isinstance(old_value, BaseModel) and isinstance(new_value, BaseModel):
            yield from _diff(old_value, new_value, f"{prefix}{name}.", field_restart)
        else:
            yield f"{prefix}{name}", field_restart


def changed_fields(old: BaseModel, new: BaseModel) -> list[str]:
    """Dotted paths of leaf fields that differ between two models."""
    return [path for path, _ in _diff(old, new)]


def requires_restart(old: BaseModel, new: BaseModel) -> bool:
    """``True`` if any change cannot be applied live."""
    return any(restart for _, restart in _diff(old, new))
