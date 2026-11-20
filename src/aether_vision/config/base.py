"""Base class and field markers shared by every configuration model."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, JsonValue

RESTART_KEY: Final = "x-restart"

#: Pass as ``Field(json_schema_extra=RESTART_REQUIRED)`` on fields whose change
#: cannot be applied live (e.g. a model path). Changing such a field triggers a
#: soft restart of the owning component. The marker also appears in the JSON
#: schema so the frontend can flag the field.
RESTART_REQUIRED: Final[dict[str, JsonValue]] = {RESTART_KEY: True}


class ConfigModel(BaseModel):
    """Immutable, strict configuration model.

    Frozen instances can be shared between threads without locking: an update
    replaces the whole object instead of mutating it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)
