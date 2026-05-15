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
    if not isinstance(value, list):
        raise ValueError("QLab cue ID response must be a list")
    return [str(item) for item in value]


class QLabReader:
    def __init__(self, client: QLabOscClient | None = None):
        self.client = client or QLabOscClient()

    def get_workspaces(self) -> dict[str, Any]:
        reply = self.client.request("/workspaces")
        return {"workspaces": reply.data, "status": reply.status}

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
