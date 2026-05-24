"""Editorial health helpers for compact cue maps and query filters."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


EDITORIAL_EXAMPLE_LIMIT = 25
AMBIGUOUS_LABEL_VALUES = {
    "?",
    "??",
    "???",
    "????",
    "¿?",
    "-",
    "--",
    "0",
    "1",
    "new cue",
    "placeholder",
    "tbd",
    "todo",
    "untitled",
    "(untitled)",
    "(untitled cue)",
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalized_text(value: Any) -> str:
    return _clean_text(value).casefold()


def _is_empty_text(value: Any) -> bool:
    return _clean_text(value) == ""


def _first_label(cue: dict[str, Any]) -> str:
    for key in ("displayName", "name", "listName", "number"):
        text = _clean_text(cue.get(key))
        if text:
            return text
    return ""


def _is_ambiguous_label(cue: dict[str, Any]) -> bool:
    label = _first_label(cue)
    if not label:
        return False
    normalized = label.casefold()
    compact = "".join(ch for ch in normalized if not ch.isspace())
    if normalized in AMBIGUOUS_LABEL_VALUES or compact in AMBIGUOUS_LABEL_VALUES:
        return True
    if compact and all(ch in "?¿!" for ch in compact):
        return True
    return normalized.startswith("(untitled")


def _cue_identity(cue: dict[str, Any]) -> dict[str, Any]:
    return {
        key: cue.get(key)
        for key in ("uniqueID", "number", "name", "displayName", "type", "listName")
        if key in cue
    }


def _limited_category(items: list[dict[str, Any]], total_count: int | None = None) -> dict[str, Any]:
    count = len(items) if total_count is None else total_count
    return {
        "count": count,
        "examples": items[:EDITORIAL_EXAMPLE_LIMIT],
        "truncated": len(items) > EDITORIAL_EXAMPLE_LIMIT,
        "example_limit": EDITORIAL_EXAMPLE_LIMIT,
    }


def _duplicate_groups(cues_by_value: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    cue_count = 0
    for value, cues in sorted(cues_by_value.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(cues) < 2:
            continue
        cue_count += len(cues)
        groups.append(
            {
                "value": value,
                "count": len(cues),
                "cues": [_cue_identity(cue) for cue in cues[:EDITORIAL_EXAMPLE_LIMIT]],
                "truncated": len(cues) > EDITORIAL_EXAMPLE_LIMIT,
            }
        )
    return {
        "group_count": len(groups),
        "cue_count": cue_count,
        "examples": groups[:EDITORIAL_EXAMPLE_LIMIT],
        "truncated": len(groups) > EDITORIAL_EXAMPLE_LIMIT,
        "example_limit": EDITORIAL_EXAMPLE_LIMIT,
    }


def editorial_health_from_index(columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    cues: list[dict[str, Any]] = [dict(zip(columns, row, strict=False)) for row in rows]
    empty_names: list[dict[str, Any]] = []
    empty_display_names: list[dict[str, Any]] = []
    empty_numbers: list[dict[str, Any]] = []
    ambiguous_labels: list[dict[str, Any]] = []
    names: dict[str, list[dict[str, Any]]] = defaultdict(list)
    numbers: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for cue in cues:
        if _is_empty_text(cue.get("name")):
            empty_names.append(_cue_identity(cue))
        else:
            names[_normalized_text(cue.get("name"))].append(cue)
        if _is_empty_text(cue.get("displayName")):
            empty_display_names.append(_cue_identity(cue))
        if _is_empty_text(cue.get("number")):
            empty_numbers.append(_cue_identity(cue))
        else:
            numbers[_normalized_text(cue.get("number"))].append(cue)
        if _is_ambiguous_label(cue):
            ambiguous_labels.append(_cue_identity(cue))

    return {
        "source": "cue_index",
        "inspected_cues": len(cues),
        "name_empty": _limited_category(empty_names),
        "displayName_empty": _limited_category(empty_display_names),
        "number_empty": _limited_category(empty_numbers),
        "ambiguous_label": _limited_category(ambiguous_labels),
        "duplicate_names": _duplicate_groups(names),
        "duplicate_numbers": _duplicate_groups(numbers),
    }
