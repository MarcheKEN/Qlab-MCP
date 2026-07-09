"""Global QLab Inspector Basics edit metadata."""

from __future__ import annotations

from ..property_specs import _prop


COMMON_PROPERTIES = (
    _prop("name", "string", real_write_enabled=True),
    _prop("number", "string", real_write_enabled=True),
    _prop("notes", "string", real_write_enabled=True),
    _prop("armed", "boolean", real_write_enabled=True),
    _prop("flagged", "boolean", real_write_enabled=True),
    _prop("colorName", "color_name", real_write_enabled=True),
    _prop("preWait", "non_negative_number", real_write_enabled=True),
    _prop("postWait", "non_negative_number", real_write_enabled=True),
    _prop(
        "duration",
        "non_negative_number",
        real_write_enabled=True,
        contextual_requirements=("allows_editing_duration",),
    ),
    _prop(
        "tempDuration",
        "non_negative_number",
        real_write_enabled=True,
        contextual_requirements=("allows_editing_duration",),
    ),
    _prop("continueMode", "continue_mode", real_write_enabled=True),
    _prop("skipIfDisarmed", "boolean", real_write_enabled=True),
    _prop("autoLoad", "boolean", real_write_enabled=True),
    _prop("secondColorName", "color_name", modes=("saved", "live"), real_write_enabled=True),
    _prop("useSecondColor", "boolean", real_write_enabled=True),
)
