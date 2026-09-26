"""Cue List inventory and exact detail, sharing the existing OSC reader."""

from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from ..osc.addressing import _workspace_address
from ..sanitizer import sanitize_exception_message
from ..settings.redaction import _redact_payload
from .list_models import (
    CueCartCell, CueCartContents, CueCartDetailsResult, CueCartGrid, CueCartIdentity, CueContainerBasics,
    CueListChild, CueListContents, CueListDetailsResult, CueListIdentity,
    CueListInventoryItem, CueListPosition, CueListState, CueListTimecode, CueListsResult,
)
from .refs import _bounded_cue_refs_from_shallow, CONTAINER_CUE_TYPES


LIST_DETAILS_ACTION = "Use qlab_get_cue_list_details with the exact Cue List UUID."
ENUMS = {
    "timecodeSyncMode": {0: "MTC", 1: "LTC"},
    "timecodeSMPTEFormat": {0: "24 fps", 1: "25 fps", 2: "30 fps drop-frame", 3: "30 fps"},
    "timecodeStartBehavior": {
        0: "Ignore earlier triggers", 1: "Start triggers within the last minute",
        2: "Start triggers within the last hour", 3: "Start triggers within lookback time",
        4: "Start all earlier triggers",
    },
    "timecodeStopBehavior": {0: "Do nothing", 1: "Pause timecode-triggered cues", 2: "Stop timecode-triggered cues"},
}
TIMECODE_FIELDS = {
    "current": "currentTimecode", "text": "currentTimecode/text",
    "sync_mode": "timecodeSyncMode", "smpte_format": "timecodeSMPTEFormat",
    "start_behavior": "timecodeStartBehavior", "stop_behavior": "timecodeStopBehavior",
    "freewheel_seconds": "timecodeFreewheelTime", "lookback_seconds": "timecodeLookbackTime",
    "trigger": "timecodeTrigger", "trigger_text": "timecodeTrigger/text",
}
DETAIL_KEYS = list(dict.fromkeys([
    *CueListIdentity.model_fields, *CueListState.model_fields,
    *CueContainerBasics.model_fields,
    "playhead", "playheadID", "playbackPosition", "playbackPositionID",
    *TIMECODE_FIELDS.values(),
]))
CART_DETAIL_KEYS = [key for key in DETAIL_KEYS if key not in {
    "playhead", "playheadID", "playbackPosition", "playbackPositionID",
}] + ["cartRows", "cartColumns"]


def _error(result: Any, code: str, message: str, route: str, *, workspace: bool = False) -> Any:
    result.ok, result.status, result.partial = False, "error", False
    result.error_code, result.message = code, message
    result.errors[route] = message
    result.coverage.failed_routes = list(result.errors)
    result.suggested_action = (
        "Call qlab_check_connection and use an exact workspace UUID."
        if workspace else "Call qlab_get_cue_lists and use an exact cue_lists[].uniqueID with the matching type's detail tool."
    )
    return result


def _finish(result: Any) -> Any:
    if result.errors:
        result.status, result.partial = "partial", True
        result.coverage.failed_routes = list(result.errors)
    return result


def _inventory(reader: Any, workspace_id: str) -> list[dict[str, Any]]:
    roots = reader.get_cue_lists(
        workspace_id, cacheable=False, tcp_fallback_on_timeout=True,
    )["cue_lists"]
    if not isinstance(roots, list):
        raise ValueError("cueLists/shallow must return a list of cue objects")
    seen: set[str] = set()
    for root in roots:
        if not isinstance(root, dict) or not isinstance(root.get("uniqueID"), str) or not root["uniqueID"]:
            raise ValueError("cueLists/shallow entries must have a non-empty uniqueID")
        if root.get("type") not in {"Cue List", "Cue Cart", "Cart"}:
            raise ValueError("cueLists/shallow returned an invalid root type")
        if root["uniqueID"].casefold() in seen:
            raise ValueError("cueLists/shallow returned duplicate identities")
        seen.add(root["uniqueID"].casefold())
    return roots


def _section(model: Any, mapping: dict[str, str], values: dict[str, Any], result: CueListDetailsResult) -> Any:
    clean = {}
    for field, key in mapping.items():
        value = values.get(key)
        if value is None:
            result.coverage.unavailable_fields.append(key)
            continue
        try:
            if key in ENUMS:
                if type(value) is not int or value not in ENUMS[key]:
                    raise ValueError("Unknown or invalid timecode enumeration")
                value = {"value": value, "label": ENUMS[key][value]}
            clean[field] = TypeAdapter(model.model_fields[field].rebuild_annotation()).validate_python(value)
        except (ValueError, TypeError):
            result.errors[key] = "Invalid OSC value for this field"
    return model(**clean)


def _position(values: dict[str, Any], key: str, result: CueListDetailsResult) -> CueListPosition:
    position = _section(CueListPosition, {"number": key, "uniqueID": key + "ID"}, values, result)
    raw_id = position.uniqueID
    position.present = None if raw_id is None else raw_id != "none"
    if raw_id == "none":
        position.uniqueID = None
    if position.number == "none":
        position.number = None
    return position


def _contents(reader: Any, workspace_id: str, root: dict[str, Any], max_depth: int, max_cues: int,
              result: CueListDetailsResult) -> CueListContents:
    walk = _bounded_cue_refs_from_shallow(
        reader, workspace_id, limit=max_cues + 1, max_depth=max_depth,
        root_cues=[root], cacheable=False,
    )
    contents = CueListContents(max_depth=max_depth, max_cues=max_cues,
                              truncated=walk["truncated"], truncation_reasons=walk["truncation_reasons"])
    result.errors.update({f"contents/{key}": sanitize_exception_message(ValueError(value))
                          for key, value in walk["errors"].items()})
    nodes: dict[str, CueListChild] = {}
    for ref in walk["refs"]:
        if ref.get("uniqueID") == root["uniqueID"]:
            contents.direct_child_count = ref.get("child_count")
            continue
        try:
            cue = {key: value for key, value in ref["cue"].items()
                   if key in CueListChild.model_fields and key not in {"children", "children_complete", "child_count"}}
            node = CueListChild.model_validate(cue)
        except (ValueError, TypeError):
            result.errors[f"contents/{ref.get('uniqueID') or len(nodes)}"] = "Invalid shallow cue identity or payload"
            contents.truncated = True
            if "invalid_payload" not in contents.truncation_reasons:
                contents.truncation_reasons.append("invalid_payload")
            continue
        node.child_count = ref.get("child_count") if node.type in CONTAINER_CUE_TYPES else 0
        node.children_complete = True if node.type not in CONTAINER_CUE_TYPES else None
        nodes[node.uniqueID] = node
        parent_id = ref.get("parent_id")
        if parent_id == root["uniqueID"]:
            contents.children.append(node)
        elif parent_id in nodes:
            nodes[parent_id].children.append(node)
        else:
            result.errors[f"contents/{node.uniqueID}"] = "Parent unavailable; child omitted"
            del nodes[node.uniqueID]
    for node in nodes.values():
        if node.type in CONTAINER_CUE_TYPES and node.child_count is not None:
            node.children_complete = len(node.children) == node.child_count
    contents.returned_count = len(nodes)
    return contents


class CueListsMixin:
    def get_cue_list_inventory(self, workspace_id: str) -> CueListsResult:
        result = CueListsResult(workspace_id=workspace_id)
        try:
            result.workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _error(result, getattr(exc, "status", "workspace_unavailable"),
                          sanitize_exception_message(exc), "workspace", workspace=True)
        try:
            roots = _inventory(self, result.workspace_id)
            items = [CueListInventoryItem.model_validate({
                **root, "root_position": index, "is_current": None,
            }) for index, root in enumerate(roots)]
        except Exception as exc:
            return _error(result, "cue_list_payload_invalid", sanitize_exception_message(exc), "cueLists/shallow")
        result.cue_lists = items
        result.cue_list_count = sum(item.type == "Cue List" for item in items)
        result.cue_cart_count = len(items) - result.cue_list_count
        result.container_count = len(items)
        result.excluded_cue_cart_count = 0
        result.coverage.notes = ["Inventory fields absent from shallow OSC remain null; root_position is zero-based."]
        try:
            current = self._request_data(_workspace_address(result.workspace_id, "currentCueListID"),
                                         workspace_id=result.workspace_id, cacheable=False)
            if not isinstance(current, str) or not current:
                raise ValueError("currentCueListID must return a non-empty string")
            if current != "none":
                current_root = next((root for root in roots if root["uniqueID"].casefold() == current.casefold()), None)
                if current_root is None:
                    raise ValueError("Current container is absent from the inventory; workspace may have changed")
                result.current_container_id = current_root["uniqueID"]
                if current_root["type"] == "Cue List":
                    result.current_cue_list_id = current_root["uniqueID"]
            for item in items:
                item.is_current = item.uniqueID == result.current_container_id
        except Exception as exc:
            result.errors["currentCueListID"] = sanitize_exception_message(exc)
        return _finish(result)

    def get_cue_list_details(self, workspace_id: str, cue_list_id: str, profile: str = "safe",
                             max_depth: int = 2, max_cues: int = 1000) -> CueListDetailsResult:
        return self._get_container_details(workspace_id, cue_list_id, profile, max_depth, max_cues, cart=False)

    def get_cue_cart_details(self, workspace_id: str, cue_cart_id: str, profile: str = "safe",
                             max_cues: int = 1000) -> CueCartDetailsResult:
        return self._get_container_details(workspace_id, cue_cart_id, profile, 1, max_cues, cart=True)

    def _get_container_details(self, workspace_id: str, cue_list_id: str, profile: str,
                               max_depth: int, max_cues: int, *, cart: bool):
        prefix = "cue_cart" if cart else "cue_list"
        result = (CueCartDetailsResult(workspace_id=workspace_id, cue_cart_id=str(cue_list_id)) if cart
                  else CueListDetailsResult(workspace_id=workspace_id, cue_list_id=str(cue_list_id)))
        identity_model = CueCartIdentity if cart else CueListIdentity
        keys = [key for key in (CART_DETAIL_KEYS if cart else DETAIL_KEYS) if key != "notes" or profile == "technical"]
        expected_types = {"Cue Cart", "Cart"} if cart else {"Cue List"}
        try:
            target = str(UUID(str(cue_list_id)))
            if profile not in {"safe", "technical"}:
                raise ValueError("profile must be safe or technical")
            if type(max_depth) is not int or not 0 <= max_depth <= 5:
                raise ValueError("max_depth must be a strict integer in 0..5")
            if type(max_cues) is not int or not 1 <= max_cues <= 5000:
                raise ValueError("max_cues must be a strict integer in 1..5000")
        except (ValueError, TypeError) as exc:
            return _error(result, "validation_failed", str(exc), "validation")
        result.profile = profile
        try:
            result.workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _error(result, getattr(exc, "status", "workspace_unavailable"),
                          sanitize_exception_message(exc), "workspace", workspace=True)
        try:
            roots = _inventory(self, result.workspace_id)
        except Exception as exc:
            return _error(result, f"{prefix}_payload_invalid", sanitize_exception_message(exc), "cueLists/shallow")
        root = next((root for root in roots if root["uniqueID"].casefold() == target), None)
        if root is None:
            return _error(result, f"{prefix}_not_found", "No root container has this UUID", "cueLists/shallow")
        if root["type"] not in expected_types:
            return _error(result, f"{prefix}_type_mismatch", "The UUID identifies a different container type", "cueLists/shallow")
        setattr(result, f"{prefix}_id", root["uniqueID"])
        try:
            values = self.read_cue_values(result.workspace_id, root["uniqueID"], keys, cacheable=False)["values"]
            if not isinstance(values, dict) or not isinstance(values.get("uniqueID"), str):
                raise ValueError("valuesForKeys must return an object with uniqueID and type")
            if values["uniqueID"].casefold() != target:
                return _error(result, f"{prefix}_identity_mismatch", "OSC returned a different cue UUID", "valuesForKeys")
            if values.get("type") not in expected_types:
                return _error(result, f"{prefix}_type_mismatch", "OSC returned a different cue type", "valuesForKeys")
            identity = identity_model.model_validate(values)
        except Exception as exc:
            return _error(result, f"{prefix}_payload_invalid", sanitize_exception_message(exc), "valuesForKeys")
        result.identity = identity
        result.basics = _section(CueContainerBasics, {key: key for key in CueContainerBasics.model_fields if key in keys}, values, result)
        if result.basics.mode is not None and result.basics.mode != (5 if cart else 0):
            result.errors["mode"] = "OSC mode does not match the container type"
            result.basics.mode = None
        result.state = _section(CueListState, {key: key for key in CueListState.model_fields}, values, result)
        if not cart:
            result.playhead = _position(values, "playhead", result)
            result.playback_position = _position(values, "playbackPosition", result)
        result.incoming_timecode = _section(CueListTimecode, TIMECODE_FIELDS, values, result)
        result.coverage.unavailable_via_osc = ["sync_enabled", "mtc_source_name", "ltc_input_patch", "ltc_sync_channel"]
        result.coverage.notes = [
            "Timecode mode/configuration does not prove synchronization is enabled or a signal is present.",
            "Current timecode may be unavailable when the list is not receiving timecode.",
            "Depth 0 reads no children; max_cues counts descendants, excluding the list root.",
            "Reads are sequential observations, not an atomic snapshot.",
        ]
        contents = _contents(self, result.workspace_id, root, max_depth, max_cues, result)
        result.contents = CueCartContents.model_validate(contents.model_dump()) if cart else contents
        if cart:
            result.coverage.notes = [
                "Cue Carts have a grid, no playhead, and cannot contain Group cues.",
                "Cells contain bounded child identities, not deep child Inspector details.",
                "Timecode configuration does not prove synchronization is enabled or signal is present.",
                "Reads are sequential observations, not an atomic snapshot.",
            ]
            result.grid = _section(CueCartGrid, {"rows": "cartRows", "columns": "cartColumns"}, values, result)
            occupied = set()
            for child in contents.children:
                cell = CueCartCell.model_validate(child.model_dump())
                route = f"cells/{child.uniqueID}/cartPosition"
                try:
                    position = self.read_cue_values(result.workspace_id, child.uniqueID,
                        ["uniqueID", "type", "cartPosition"], cacheable=False)["values"]
                    if not isinstance(position, dict) or position.get("uniqueID") != child.uniqueID or position.get("type") != child.type:
                        raise ValueError("Cell identity mismatch")
                    coords = position.get("cartPosition")
                    if not isinstance(coords, list) or len(coords) != 2 or any(type(n) is not int or n < 0 for n in coords):
                        raise ValueError("cartPosition must contain two non-negative integers")
                    cell.row, cell.column = coords
                    if tuple(coords) in occupied:
                        raise ValueError("Duplicate cell position in sequential OSC observations")
                    occupied.add(tuple(coords))
                    if child.type in CONTAINER_CUE_TYPES:
                        raise ValueError("Cue Carts cannot contain container cues")
                except Exception as exc:
                    result.errors[route] = sanitize_exception_message(exc)
                result.grid.cells.append(cell)
            result.grid.complete = not result.contents.truncated and not result.errors and all(
                value is not None for value in (result.grid.rows, result.grid.columns))
        if profile == "technical":
            # Only requested allowlisted properties enter the technical payload.
            result.technical_payload = _redact_payload(
                {key: values[key] for key in keys if key in values and key not in result.errors},
                section=prefix, profile="technical", redactions=[],
            )
        return _finish(result)
