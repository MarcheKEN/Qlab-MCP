"""Timeout budgeting helpers for gated write operations."""

from __future__ import annotations

import time
from typing import Any


AFTER_READ_RETRY_DELAYS = (0.2, 0.5, 1.0)
UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS = 90.0
UPDATE_SETTER_REPLY_TIMEOUT_CAP_SECONDS = 0.1
UPDATE_SETTER_REPLY_TOTAL_BUDGET_SECONDS = 8.0
UPDATE_AFTER_READ_TIMEOUT_CAP_SECONDS = 0.5
UPDATE_MIN_REPLY_TIMEOUT_SECONDS = 0.001


def client_config_timeout(
    reader: Any,
    fallback: float,
    *,
    min_reply_timeout_seconds: float = UPDATE_MIN_REPLY_TIMEOUT_SECONDS,
) -> float:
    value = getattr(getattr(getattr(reader, "client", None), "config", None), "timeout", fallback)
    try:
        return max(min_reply_timeout_seconds, float(value))
    except (TypeError, ValueError):
        return fallback


def budget_remaining(
    deadline: float | None,
    *,
    soft_budget_seconds: float = UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS,
) -> float:
    if deadline is None:
        return soft_budget_seconds
    return deadline - time.monotonic()


def bounded_reply_timeout(
    reader: Any,
    cap: float,
    deadline: float | None = None,
    *,
    min_reply_timeout_seconds: float = UPDATE_MIN_REPLY_TIMEOUT_SECONDS,
    soft_budget_seconds: float = UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS,
) -> float:
    timeout = min(
        client_config_timeout(
            reader,
            cap,
            min_reply_timeout_seconds=min_reply_timeout_seconds,
        ),
        cap,
    )
    if deadline is not None:
        remaining = budget_remaining(deadline, soft_budget_seconds=soft_budget_seconds)
        if remaining <= 0:
            return min_reply_timeout_seconds
        timeout = min(timeout, remaining)
    return max(min_reply_timeout_seconds, timeout)


def setter_reply_timeout(
    reader: Any,
    setter_count: int,
    deadline: float | None = None,
    *,
    min_reply_timeout_seconds: float = UPDATE_MIN_REPLY_TIMEOUT_SECONDS,
    soft_budget_seconds: float = UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS,
    setter_reply_timeout_cap_seconds: float = UPDATE_SETTER_REPLY_TIMEOUT_CAP_SECONDS,
    setter_reply_total_budget_seconds: float = UPDATE_SETTER_REPLY_TOTAL_BUDGET_SECONDS,
) -> float:
    if setter_count <= 0:
        return min_reply_timeout_seconds
    per_setter_budget = setter_reply_total_budget_seconds / setter_count
    cap = min(setter_reply_timeout_cap_seconds, per_setter_budget)
    return bounded_reply_timeout(
        reader,
        cap,
        deadline,
        min_reply_timeout_seconds=min_reply_timeout_seconds,
        soft_budget_seconds=soft_budget_seconds,
    )
