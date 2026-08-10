"""Shared response limits for sensitive cue reads."""

from __future__ import annotations

import json
from typing import Any


MAX_SENSITIVE_CUE_RESPONSE_BYTES = 1_048_576
SENSITIVE_CUE_PROFILES = frozenset({"full_sensitive", "exhaustive"})


def serialized_payload_bytes(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def sensitive_payload_size(payload: Any, profile: str) -> int | None:
    if profile.strip().lower() not in SENSITIVE_CUE_PROFILES:
        return None
    return serialized_payload_bytes(payload)
