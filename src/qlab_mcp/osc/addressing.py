"""Address and identifier helpers for QLab OSC paths."""

from __future__ import annotations

from typing import Any


def _clean_workspace_id(workspace_id: str) -> str:
    value = workspace_id.strip().strip("/")
    if not value:
        raise ValueError("workspace_id is required")
    if "/" in value:
        raise ValueError("workspace_id must be a workspace unique ID or OSC-compatible display name")
    return value


def _clean_cue_ref(cue_ref: str) -> str:
    value = str(cue_ref).strip().strip("/")
    if not value:
        raise ValueError("cue_ref is required")
    if "/" in value:
        raise ValueError("cue_ref must be a cue number, selected, playhead, playbackPosition, active, or cue ID")
    return value


def _workspace_address(workspace_id: str, command: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    return f"/workspace/{workspace}/{command.strip('/')}"


def _cue_address(workspace_id: str, cue_ref: str, command: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    cue = _clean_cue_ref(cue_ref)
    prefix = "cue_id" if _looks_like_unique_id(cue) else "cue"
    return f"/workspace/{workspace}/{prefix}/{cue}/{command.strip('/')}"


def _looks_like_unique_id(value: str) -> bool:
    # QLab unique IDs are UUID-like. Cue numbers can contain dashes, so require long UUID shape.
    return len(value) >= 32 and value.count("-") >= 4


def _normalize_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        cue_ids: list[str] = []
        unique_id = value.get("uniqueID")
        if unique_id is not None:
            cue_ids.append(str(unique_id))
        children = value.get("cues")
        if children is not None:
            cue_ids.extend(_normalize_id_list(children))
        return cue_ids
    if isinstance(value, list):
        cue_ids: list[str] = []
        for item in value:
            cue_ids.extend(_normalize_id_list(item))
        return cue_ids
    raise ValueError("QLab cue ID response must be a list, object, or string")
