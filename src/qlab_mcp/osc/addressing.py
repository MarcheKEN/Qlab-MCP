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


def _normalize_id_list(value: Any, *, max_ids: int | None = None) -> list[str]:
    cue_ids: list[str] = []

    def append_id(raw_id: Any) -> None:
        if max_ids is None or len(cue_ids) < max_ids:
            cue_ids.append(str(raw_id))

    def walk(item: Any) -> None:
        if max_ids is not None and len(cue_ids) >= max_ids:
            return
        if item is None:
            return
        if isinstance(item, str):
            append_id(item)
            return
        if isinstance(item, dict):
            unique_id = item.get("uniqueID")
            if unique_id is not None:
                append_id(unique_id)
            children = item.get("cues")
            if children is not None:
                walk(children)
            return
        if isinstance(item, list):
            for child in item:
                walk(child)
                if max_ids is not None and len(cue_ids) >= max_ids:
                    break
            return
        raise ValueError("QLab cue ID response must be a list, object, or string")

    walk(value)
    return cue_ids


def _id_list_reached_limit(cue_ids: list[str], max_ids: int | None) -> bool:
    return max_ids is not None and len(cue_ids) >= max_ids
