"""Validation for workspace-wide audio level limits."""
from __future__ import annotations

import math
from typing import Any


def validate_audio_level_limits(
    minimum: Any, maximum: Any, values: list[Any],
) -> tuple[int | float, int | float]:
    if (type(minimum) not in (int, float) or not math.isfinite(minimum)
            or type(maximum) not in (int, float) or not math.isfinite(maximum)
            or minimum > maximum):
        raise ValueError("Workspace audio volume limits cannot be verified")
    for value in values:
        if value == "-inf":
            continue
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Audio level must be a finite number or -inf")
        if value <= minimum:
            raise ValueError(f"Audio level must be greater than workspace minimum of {minimum} dB")
        if value > maximum:
            raise ValueError(f"Audio level exceeds workspace maximum of {maximum} dB")
    return minimum, maximum
