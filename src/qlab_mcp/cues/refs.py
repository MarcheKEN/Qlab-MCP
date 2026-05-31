"""Helpers for flattening nested QLab cue ID responses."""

from __future__ import annotations

from typing import Any


CONTAINER_CUE_TYPES = {"Cue List", "Cue Cart", "Group"}


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


def _cue_ref_from_shallow(
    cue: dict[str, Any],
    *,
    parent_id: str | None,
    cue_list_id: str | None,
    depth: int,
) -> dict[str, Any]:
    return {
        "uniqueID": cue.get("uniqueID"),
        "parent_id": parent_id,
        "cue_list_id": cue_list_id,
        "depth": depth,
        "cue": cue,
    }


def _is_container_cue(cue: dict[str, Any]) -> bool:
    return cue.get("type") in CONTAINER_CUE_TYPES


def _bounded_cue_refs_from_shallow(
    reader: Any,
    workspace_id: str,
    *,
    limit: int,
    max_depth: int | None = None,
    cacheable: bool = True,
) -> dict[str, Any]:
    """Walk cueLists/shallow + children/shallow without global uniqueIDs."""
    if limit < 1:
        raise ValueError("limit must be 1 or greater")

    refs: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    child_read_errors: list[dict[str, Any]] = []
    truncation_reasons: list[str] = []
    seen: set[str] = set()

    def mark_truncated(reason: str) -> None:
        if reason not in truncation_reasons:
            truncation_reasons.append(reason)

    def append_cue(cue: Any, *, parent_id: str | None, cue_list_id: str | None, depth: int) -> None:
        if len(refs) >= limit:
            mark_truncated("max_cues")
            return
        if not isinstance(cue, dict):
            errors[f"depth:{depth}:item:{len(refs)}"] = "QLab shallow cue entry must be an object"
            return

        cue_id_value = cue.get("uniqueID")
        cue_id = str(cue_id_value) if cue_id_value else None
        current_cue_list_id = (
            cue_id
            if parent_id is None and cue_id and cue.get("type") in {"Cue List", "Cue Cart"}
            else cue_list_id
        )
        if cue_id and cue_id in seen:
            return
        if cue_id:
            seen.add(cue_id)
        refs.append(
            _cue_ref_from_shallow(
                cue,
                parent_id=parent_id,
                cue_list_id=current_cue_list_id,
                depth=depth,
            )
        )

        if not cue_id or not _is_container_cue(cue):
            return
        if max_depth is not None and depth >= max_depth:
            mark_truncated("max_depth")
            return
        if len(refs) >= limit:
            mark_truncated("max_cues")
            return

        try:
            children = reader.get_cue_children(workspace_id, cue_id, shallow=True, ids_only=False)["children"]
        except Exception as exc:
            errors[cue_id] = str(exc)
            child_read_errors.append(
                {
                    "cue_ref": cue_id,
                    "parent_id": parent_id,
                    "cue_list_id": current_cue_list_id,
                    "depth": depth,
                    "message": str(exc),
                }
            )
            return
        if not isinstance(children, list):
            errors[cue_id] = "QLab children/shallow response must be a list"
            child_read_errors.append(
                {
                    "cue_ref": cue_id,
                    "parent_id": parent_id,
                    "cue_list_id": current_cue_list_id,
                    "depth": depth,
                    "message": "QLab children/shallow response must be a list",
                }
            )
            return
        for child in children:
            if len(refs) >= limit:
                mark_truncated("max_cues")
                break
            append_cue(child, parent_id=cue_id, cue_list_id=current_cue_list_id, depth=depth + 1)

    try:
        cue_lists = reader.get_cue_lists(workspace_id, include_children=False, cacheable=cacheable)["cue_lists"] or []
    except Exception as exc:
        return {
            "refs": [],
            "truncated": False,
            "truncation_reasons": [],
            "errors": {"cueLists/shallow": str(exc)},
            "child_read_errors": [],
        }
    if not isinstance(cue_lists, list):
        return {
            "refs": [],
            "truncated": False,
            "truncation_reasons": [],
            "errors": {"cueLists/shallow": "QLab cueLists/shallow response must be a list"},
            "child_read_errors": [],
        }

    for cue_list in cue_lists:
        if len(refs) >= limit:
            mark_truncated("max_cues")
            break
        append_cue(cue_list, parent_id=None, cue_list_id=None, depth=0)

    return {
        "refs": refs,
        "truncated": bool(truncation_reasons),
        "truncation_reasons": truncation_reasons,
        "errors": errors,
        "child_read_errors": child_read_errors,
    }
