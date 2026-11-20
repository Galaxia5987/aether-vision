"""Decide whether a configuration change can be applied without a restart."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from aether_vision.config.base import RESTART_KEY


def _is_restart_field(info: FieldInfo) -> bool:
    extra = info.json_schema_extra
    return isinstance(extra, dict) and extra.get(RESTART_KEY) is True


def changed_fields(old: BaseModel, new: BaseModel, prefix: str = "") -> list[str]:
    """Return dotted paths of leaf fields that differ between two models."""
    if type(old) is not type(new):
        return [prefix.rstrip(".") or "<root>"]
    changes: list[str] = []
    for name in type(old).model_fields:
        old_value: object = getattr(old, name)
        new_value: object = getattr(new, name)
        if old_value == new_value:
            continue
        if isinstance(old_value, BaseModel) and isinstance(new_value, BaseModel):
            changes.extend(changed_fields(old_value, new_value, f"{prefix}{name}."))
        else:
            changes.append(f"{prefix}{name}")
    return changes


def requires_restart(old: BaseModel, new: BaseModel) -> bool:
    """``True`` if any changed field (or any ancestor of it) is marked restart-required.

    A change of model *type* (e.g. switching a discriminated union variant)
    always requires a restart.
    """
    if type(old) is not type(new):
        return True
    for name, info in type(old).model_fields.items():
        old_value: object = getattr(old, name)
        new_value: object = getattr(new, name)
        if old_value == new_value:
            continue
        if _is_restart_field(info):
            return True
        if isinstance(old_value, BaseModel) and isinstance(new_value, BaseModel):
            if requires_restart(old_value, new_value):
                return True
        elif isinstance(old_value, BaseModel) or isinstance(new_value, BaseModel):
            return True
    return False
