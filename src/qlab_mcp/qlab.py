"""Read-only QLab cue information operations."""

from __future__ import annotations

import json
from typing import Any

from .allowlist import properties_for_profile, validate_property_path, validate_value_keys
from .client import QLabOscClient


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


CONTAINER_CUE_TYPES = {"Cue List", "Cue Cart", "Group"}
OVERVIEW_CUE_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "armed",
    "flagged",
    "colorName",
    "colorName/live",
)


def _cue_overview_node(cue: Any) -> dict[str, Any]:
    if not isinstance(cue, dict):
        return {"value": cue}
    node = {key: cue[key] for key in OVERVIEW_CUE_KEYS if key in cue}
    label = node.get("displayName") or node.get("name") or node.get("listName") or node.get("number") or node.get("uniqueID")
    if label is not None:
        node["label"] = str(label)
    return node


def _is_container_cue(cue: dict[str, Any]) -> bool:
    return cue.get("type") in CONTAINER_CUE_TYPES


def _count_stat(stats: dict[str, Any], bucket: str, key: Any) -> None:
    normalized = "unknown" if key in (None, "") else str(key)
    stats[bucket][normalized] = stats[bucket].get(normalized, 0) + 1


def _record_cue_stats(stats: dict[str, Any], cue: dict[str, Any]) -> None:
    _count_stat(stats, "types", cue.get("type"))
    _count_stat(stats, "colors", cue.get("colorName"))
    if cue.get("armed") is True:
        stats["armed"] += 1
    elif cue.get("armed") is False:
        stats["disarmed"] += 1
    if cue.get("flagged") is True:
        stats["flagged"] += 1


class QLabReader:
    def __init__(self, client: QLabOscClient | None = None):
        self.client = client or QLabOscClient()

    def get_workspaces(self) -> dict[str, Any]:
        reply = self.client.request("/workspaces")
        return {"workspaces": reply.data, "status": reply.status}

    def get_workspace_overview(
        self,
        workspace_id: str | None = None,
        max_depth: int = 2,
        max_cues: int = 200,
        include_selected_and_running: bool = True,
    ) -> dict[str, Any]:
        if max_depth < 0:
            raise ValueError("max_depth must be 0 or greater")
        if max_cues < 1:
            raise ValueError("max_cues must be 1 or greater")

        workspaces_result = self.get_workspaces()
        workspaces = workspaces_result.get("workspaces") or []
        workspace = self._resolve_workspace(workspaces, workspace_id)
        resolved_workspace_id = _clean_workspace_id(workspace.get("uniqueID") or workspace_id or "")

        cue_lists = self.get_cue_lists(resolved_workspace_id, include_children=False)["cue_lists"] or []
        id_result = self.get_workspace_cue_ids(resolved_workspace_id, include_children=True)

        stats: dict[str, Any] = {
            "total_cue_ids": id_result["cue_count"],
            "inspected_cues": 0,
            "cue_lists": len(cue_lists),
            "types": {},
            "colors": {},
            "armed": 0,
            "disarmed": 0,
            "flagged": 0,
            "max_depth_returned": 0,
        }
        limits: dict[str, Any] = {
            "max_depth": max_depth,
            "max_cues": max_cues,
            "truncated": False,
            "truncation_reasons": [],
        }
        errors: dict[str, str] = {}

        def mark_truncated(reason: str) -> None:
            limits["truncated"] = True
            if reason not in limits["truncation_reasons"]:
                limits["truncation_reasons"].append(reason)

        def build_node(cue: Any, depth: int) -> dict[str, Any] | None:
            if stats["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                return None

            node = _cue_overview_node(cue)
            node["depth"] = depth
            stats["inspected_cues"] += 1
            stats["max_depth_returned"] = max(stats["max_depth_returned"], depth)
            _record_cue_stats(stats, node)

            cue_id = node.get("uniqueID")
            if not cue_id or not _is_container_cue(node):
                return node
            if depth >= max_depth:
                node["children_truncated"] = True
                mark_truncated("max_depth")
                return node

            try:
                children = self.get_cue_children(
                    resolved_workspace_id,
                    str(cue_id),
                    shallow=True,
                    ids_only=False,
                )["children"]
            except Exception as exc:
                errors[str(cue_id)] = str(exc)
                return node

            if not isinstance(children, list):
                node["child_count"] = 0
                return node

            node["child_count"] = len(children)
            child_nodes: list[dict[str, Any]] = []
            for child in children:
                child_node = build_node(child, depth + 1)
                if child_node is not None:
                    child_nodes.append(child_node)
                if stats["inspected_cues"] >= max_cues:
                    mark_truncated("max_cues")
                    break
            node["children"] = child_nodes
            if len(child_nodes) < len(children):
                node["children_truncated"] = True
            return node

        overview_cue_lists: list[dict[str, Any]] = []
        for cue_list in cue_lists:
            node = build_node(cue_list, 0)
            if node is not None:
                overview_cue_lists.append(node)
            if stats["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                break

        selected_cues = None
        running_cues = None
        if include_selected_and_running:
            selected_cues = self.get_selected_cues(resolved_workspace_id, include_children=False)["selected_cues"]
            running_cues = self.get_running_cues(
                resolved_workspace_id,
                include_paused=True,
                include_children=False,
            )["running_cues"]

        warnings: list[str] = []
        if limits["truncated"]:
            warnings.append("Overview is partial; increase max_depth or max_cues for a deeper scan.")

        return {
            "workspace_id": resolved_workspace_id,
            "workspace": workspace,
            "cue_count": id_result["cue_count"],
            "cue_lists": overview_cue_lists,
            "selected_cues": selected_cues,
            "running_cues": running_cues,
            "stats": stats,
            "limits": limits,
            "warnings": warnings,
            "errors": errors or None,
        }

    def _resolve_workspace(self, workspaces: Any, workspace_id: str | None) -> dict[str, Any]:
        if not isinstance(workspaces, list):
            raise ValueError("QLab workspaces response must be a list")
        if workspace_id is None:
            if len(workspaces) != 1:
                raise ValueError("workspace_id is required when QLab has zero or multiple open workspaces")
            workspace = workspaces[0]
            if not isinstance(workspace, dict):
                raise ValueError("QLab workspace entry must be an object")
            return workspace

        requested = _clean_workspace_id(workspace_id)
        for workspace in workspaces:
            if not isinstance(workspace, dict):
                continue
            if workspace.get("uniqueID") == requested or workspace.get("displayName") == requested:
                return workspace
        return {"uniqueID": requested}

    def get_cue_lists(self, workspace_id: str, include_children: bool = True) -> dict[str, Any]:
        command = "cueLists" if include_children else "cueLists/shallow"
        return self._workspace_data(workspace_id, command, "cue_lists")

    def get_workspace_cue_ids(self, workspace_id: str, include_children: bool = True) -> dict[str, Any]:
        command = "cueLists/uniqueIDs" if include_children else "cueLists/uniqueIDs/shallow"
        reply = self.client.request(_workspace_address(workspace_id, command), workspace_id=workspace_id)
        cue_ids = _normalize_id_list(reply.data)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "include_children": include_children,
            "cue_count": len(cue_ids),
            "cue_ids": cue_ids,
        }

    def get_workspace_cue_inventory(
        self,
        workspace_id: str,
        include_details: bool = False,
        detail_profile: str = "basic",
    ) -> dict[str, Any]:
        id_result = self.get_workspace_cue_ids(workspace_id, include_children=True)
        result: dict[str, Any] = {
            "workspace_id": id_result["workspace_id"],
            "cue_count": id_result["cue_count"],
            "cue_ids": id_result["cue_ids"],
        }
        if not include_details:
            return result

        cues: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for cue_id in id_result["cue_ids"]:
            try:
                cues.append(self.get_cue_details(workspace_id, cue_id, detail_profile))
            except Exception as exc:
                errors[cue_id] = str(exc)
        result["detail_profile"] = detail_profile
        result["cues"] = cues
        if errors:
            result["errors"] = errors
        return result

    def get_selected_cues(self, workspace_id: str, include_children: bool = True) -> dict[str, Any]:
        command = "selectedCues" if include_children else "selectedCues/shallow"
        return self._workspace_data(workspace_id, command, "selected_cues")

    def get_running_cues(
        self,
        workspace_id: str,
        include_paused: bool = True,
        include_children: bool = True,
    ) -> dict[str, Any]:
        base = "runningOrPausedCues" if include_paused else "runningCues"
        command = base if include_children else f"{base}/shallow"
        return self._workspace_data(workspace_id, command, "running_cues")

    def get_cue_children(
        self,
        workspace_id: str,
        cue_ref: str,
        shallow: bool = False,
        ids_only: bool = False,
    ) -> dict[str, Any]:
        suffix = "children"
        if ids_only:
            suffix += "/uniqueIDs"
        if shallow:
            suffix += "/shallow"
        reply = self.client.request(_cue_address(workspace_id, cue_ref, suffix), workspace_id=workspace_id)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "children": reply.data,
            "ids_only": ids_only,
            "shallow": shallow,
        }

    def get_cue_details(self, workspace_id: str, cue_ref: str, profile: str = "basic") -> dict[str, Any]:
        values: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for property_path in properties_for_profile(profile):
            try:
                values[property_path] = self.read_cue_property(workspace_id, cue_ref, property_path)["value"]
            except Exception as exc:  # Non-applicable type-specific properties should not fail the whole profile.
                errors[property_path] = str(exc)
        result: dict[str, Any] = {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "profile": profile,
            "properties": values,
        }
        if errors:
            result["errors"] = errors
        return result

    def read_cue_property(self, workspace_id: str, cue_ref: str, property_path: str) -> dict[str, Any]:
        prop = validate_property_path(property_path)
        reply = self.client.request(_cue_address(workspace_id, cue_ref, prop), workspace_id=workspace_id)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "property": prop,
            "value": reply.data,
        }

    def read_cue_values(self, workspace_id: str, cue_ref: str, keys: list[str]) -> dict[str, Any]:
        normalized_keys = validate_value_keys(keys)
        reply = self.client.request(
            _cue_address(workspace_id, cue_ref, "valuesForKeys"),
            json.dumps(normalized_keys),
            workspace_id=workspace_id,
        )
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "keys": normalized_keys,
            "values": reply.data,
        }

    def _workspace_data(self, workspace_id: str, command: str, key: str) -> dict[str, Any]:
        reply = self.client.request(_workspace_address(workspace_id, command), workspace_id=workspace_id)
        return {"workspace_id": _clean_workspace_id(workspace_id), key: reply.data}
