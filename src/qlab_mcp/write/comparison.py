"""Shared numeric comparison policy for write readback verification."""

from __future__ import annotations

import math
from typing import Any


UPDATE_NUMERIC_MATCH_ABS_TOLERANCE = 1e-5
UPDATE_NUMERIC_MATCH_REL_TOLERANCE = 1e-6
SETTINGS_NUMERIC_MATCH_REL_TOLERANCE = 1e-5


def is_plain_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_plain_finite_number(value: Any) -> bool:
    return is_plain_number(value) and math.isfinite(float(value))


def numeric_values_match(
    actual: Any,
    requested: Any,
    *,
    rel_tol: float = UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
    abs_tol: float = UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
) -> bool:
    if not is_plain_finite_number(actual) or not is_plain_finite_number(requested):
        return False
    return math.isclose(
        float(actual),
        float(requested),
        rel_tol=rel_tol,
        abs_tol=abs_tol,
    )
