"""Helpers for flattening nested QLab cue ID responses."""

from __future__ import annotations

from typing import Any


CONTAINER_CUE_TYPES = {"Cue List", "Cue Cart", "Cart", "Group"}


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


def _child_read_error_context(
    cue: dict[str, Any],
    *,
    cue_id: str,
    parent_id: str | None,
    cue_list_id: str | None,
    depth: int,
    message: str,
    fallback_used: bool = False,
    child_count: int | None = None,
    child_count_source: str | None = None,
    child_metadata_status: str | None = None,
    fallback_error: str | None = None,
) -> dict[str, Any]:
    context = {
        "cue_ref": cue_id,
        "number": cue.get("number"),
        "name": cue.get("name"),
        "displayName": cue.get("displayName"),
        "type": cue.get("type"),
        "parent_id": parent_id,
        "cue_list_id": cue_list_id,
        "depth": depth,
        "colorName": cue.get("colorName"),
        "duration": cue.get("duration"),
        "isBroken": cue.get("isBroken"),
        "isWarning": cue.get("isWarning"),
        "message": message,
        "fallback_used": fallback_used,
        "child_count": child_count,
        "child_count_source": child_count_source,
        "child_metadata_status": child_metadata_status,
        "fallback_error": fallback_error,
    }
    required_keys = {
        "cue_ref",
        "number",
        "name",
        "displayName",
        "type",
        "parent_id",
        "cue_list_id",
        "depth",
        "message",
        "fallback_used",
    }
    return {key: value for key, value in context.items() if key in required_keys or value is not None}


def _bounded_cue_refs_from_shallow(
    reader: Any,
    workspace_id: str,
    *,
    limit: int,
    max_depth: int | None = None,
    cacheable: bool = True,
    fallback_child_ids: bool = False,
) -> dict[str, Any]:
    """Walk cueLists/shallow + children/shallow without global uniqueIDs."""
    if limit < 1:
        raise ValueError("limit must be 1 or greater")

    refs: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    child_read_errors: list[dict[str, Any]] = []
    truncation_reasons: list[str] = []
    seen: set[str] = set()
    known_ids: set[str] = set()

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
            if parent_id is None and cue_id and cue.get("type") in {"Cue List", "Cue Cart", "Cart"}
            else cue_list_id
        )
        if cue_id and cue_id in seen:
            return
        if cue_id:
            seen.add(cue_id)
        ref = _cue_ref_from_shallow(
            cue,
            parent_id=parent_id,
            cue_list_id=current_cue_list_id,
            depth=depth,
        )
        refs.append(ref)
        if cue_id:
            known_ids.add(cue_id)

        if not cue_id or not _is_container_cue(cue):
            return
        if max_depth is not None and depth >= max_depth:
            mark_truncated("max_depth")
            return
        if len(refs) >= limit:
            mark_truncated("max_cues")
            return

        def record_child_read_error(
            message: str,
            *,
            fallback_used: bool = False,
            child_count: int | None = None,
            child_count_source: str | None = None,
            child_metadata_status: str | None = None,
            fallback_error: str | None = None,
        ) -> None:
            child_read_errors.append(
                _child_read_error_context(
                    cue,
                    cue_id=cue_id,
                    parent_id=parent_id,
                    cue_list_id=current_cue_list_id,
                    depth=depth,
                    message=message,
                    fallback_used=fallback_used,
                    child_count=child_count,
                    child_count_source=child_count_source,
                    child_metadata_status=child_metadata_status,
                    fallback_error=fallback_error,
                )
            )

        def fallback_to_child_ids(message: str) -> None:
            errors[cue_id] = message
            ref["child_metadata_status"] = "timeout" if "Timed out" in message or "timed out" in message else "unavailable"
            try:
                id_children = reader.get_cue_children(workspace_id, cue_id, shallow=True, ids_only=True)["children"]
                id_refs = _flatten_cue_refs(
                    id_children,
                    parent_id=cue_id,
                    cue_list_id=current_cue_list_id,
                    depth=depth + 1,
                )
                child_ids = [str(item["uniqueID"]) for item in id_refs if item.get("uniqueID")]
                for child_id in child_ids:
                    known_ids.add(child_id)
                ref["child_count"] = len(child_ids)
                ref["child_count_source"] = "children/uniqueIDs/shallow"
                ref["child_metadata_status"] = "timeout" if "Timed out" in message or "timed out" in message else "unavailable"
                ref["fallback_used"] = True
                mark_truncated("child_metadata_unavailable")
                record_child_read_error(
                    message,
                    fallback_used=True,
                    child_count=len(child_ids),
                    child_count_source="children/uniqueIDs/shallow",
                    child_metadata_status=ref["child_metadata_status"],
                )
            except Exception as fallback_exc:
                ref["child_count"] = None
                ref["child_count_source"] = None
                ref["fallback_used"] = True
                mark_truncated("child_read_error")
                record_child_read_error(
                    message,
                    fallback_used=True,
                    child_metadata_status=ref["child_metadata_status"],
                    fallback_error=str(fallback_exc),
                )

        try:
            children = reader.get_cue_children(workspace_id, cue_id, shallow=True, ids_only=False)["children"]
        except Exception as exc:
            if not fallback_child_ids:
                errors[cue_id] = str(exc)
                mark_truncated("child_read_error")
                record_child_read_error(str(exc))
                return
            fallback_to_child_ids(str(exc))
            return
        if not isinstance(children, list):
            if not fallback_child_ids:
                message = "QLab children/shallow response must be a list"
                errors[cue_id] = message
                mark_truncated("child_read_error")
                record_child_read_error(message)
                return
            fallback_to_child_ids("QLab children/shallow response must be a list")
            return
        ref["child_count"] = len(children)
        ref["child_count_source"] = "children/shallow"
        ref["child_metadata_status"] = "available"
        ref["fallback_used"] = False
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
            "truncated": True,
            "truncation_reasons": ["root_read_error"],
            "errors": {"cueLists/shallow": str(exc)},
            "child_read_errors": [],
            "known_total_cues": None,
            "known_total_cues_status": "unknown",
            "known_total_cues_source": "bounded_shallow_traversal",
        }
    if not isinstance(cue_lists, list):
        return {
            "refs": [],
            "truncated": True,
            "truncation_reasons": ["root_read_error"],
            "errors": {"cueLists/shallow": "QLab cueLists/shallow response must be a list"},
            "child_read_errors": [],
            "known_total_cues": None,
            "known_total_cues_status": "unknown",
            "known_total_cues_source": "bounded_shallow_traversal",
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
        "known_total_cues": len(known_ids),
        "known_total_cues_status": "partial" if truncation_reasons or errors else "known",
        "known_total_cues_source": (
            "bounded_shallow_traversal+children/uniqueIDs/shallow"
            if any(item.get("fallback_used") for item in child_read_errors)
            else "bounded_shallow_traversal"
        ),
    }
