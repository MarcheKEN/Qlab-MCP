"""Fail-closed classification of QLab Network patch display names."""

from __future__ import annotations

import shlex
from typing import Final


KNOWN_NETWORK_PATCH_PREFIXES: Final[tuple[str, ...]] = (
    "OSC Message",
    "Plain Text",
    "Hex Codes",
    "QLab 5",
    "Go Button 3",
    "d&b DS100",
)


def classify_network_patch_type(complete_name: str) -> str | None:
    """Return an exact observed prefix, or None for unknown/ambiguous names."""
    if not isinstance(complete_name, str):
        return None
    for prefix in KNOWN_NETWORK_PATCH_PREFIXES:
        marker = f"{prefix} - "
        if not complete_name.startswith(marker) or not complete_name[len(marker):].strip():
            continue
        suffix = complete_name[len(marker):]
        if any(suffix.startswith(f"{other} - ") for other in KNOWN_NETWORK_PATCH_PREFIXES):
            return None
        return prefix
    return None


def valid_osc_message_text(value: object) -> bool:
    """Accept a concrete OSC address plus optional QLab-parsed arguments."""
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    try:
        parts = shlex.split(stripped)
    except ValueError:
        return False
    if not parts:
        return False
    address = stripped.split(maxsplit=1)[0]
    forbidden = " #*,?[]{}"
    return (
        address.startswith("/")
        and address != "/"
        and "//" not in address
        and not any(char in forbidden or ord(char) < 32 for char in address)
    )
