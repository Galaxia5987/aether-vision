"""Make values strictly JSON-serializable (browsers reject NaN/Infinity)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def json_safe(value: object) -> object:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str | int | bool) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, Sequence):
        return [json_safe(v) for v in value]
    return str(value)
