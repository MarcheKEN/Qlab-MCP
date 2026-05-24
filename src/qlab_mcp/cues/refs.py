"""Helpers for flattening nested QLab cue ID responses."""

from __future__ import annotations

from typing import Any


def _flatten_cue_refs(
    value: Any,
    parent_id: str | None = None,
    cue_list_id: str | None = None,
    depth: int = 0,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        return [{"uniqueID": value, "parent_id": parent_id, "cue_list_id": cue_list_id, "depth": depth}]
    if isinstance(value, dict):
        cue_refs: list[dict[str, Any]] = []
        unique_id_value = value.get("uniqueID")
        current_id = str(unique_id_value) if unique_id_value is not None else None
        current_cue_list_id = current_id if parent_id is None and current_id else cue_list_id
        if current_id:
            cue_refs.append(
                {
                    "uniqueID": current_id,
                    "parent_id": parent_id,
                    "cue_list_id": current_cue_list_id,
                    "depth": depth,
                }
            )
        children = value.get("cues")
        if children is not None:
            cue_refs.extend(
                _flatten_cue_refs(
                    children,
                    parent_id=current_id,
                    cue_list_id=current_cue_list_id,
                    depth=depth + 1,
                )
            )
        return cue_refs
    if isinstance(value, list):
        cue_refs: list[dict[str, Any]] = []
        for item in value:
            cue_refs.extend(
                _flatten_cue_refs(
                    item,
                    parent_id=parent_id,
                    cue_list_id=cue_list_id,
                    depth=depth,
                )
            )
        return cue_refs
    raise ValueError("QLab cue ID response must be a list, object, or string")
