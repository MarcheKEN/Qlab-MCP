"""Read-only QLab cue information operations."""

from __future__ import annotations

import json
from typing import Any

from .allowlist import properties_for_profile, validate_property_path, validate_value_keys
from .client import QLabOscClient
from .errors import OscTimeoutError, QLabReplyError


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
QLAB_VERSION_KEYS = ("qlabVersion", "QLabVersion", "applicationVersion", "version")
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
    "isBroken",
    "isWarning",
)

QUERY_FILTERS = {
    "type",
    "flagged",
    "armed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "colorName",
    "name_contains",
    "number_prefix",
    "cue_list_id",
    "parent_id",
}
QUERY_FILTER_PROPERTIES = {
    "type": ("type",),
    "flagged": ("flagged",),
    "armed": ("armed",),
    "isBroken": ("isBroken",),
    "isWarning": ("isWarning",),
    "isRunning": ("isRunning",),
    "isPaused": ("isPaused",),
    "colorName": ("colorName",),
    "name_contains": ("name", "displayName", "listName"),
    "number_prefix": ("number",),
    "cue_list_id": (),
    "parent_id": ("parent",),
}
QUERY_BASE_PROPERTIES = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "armed",
    "flagged",
    "colorName",
)


def _workspace_overview_metadata(workspace: Any) -> dict[str, Any]:
    if not isinstance(workspace, dict):
        return {"value": workspace}

    name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
    qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)

    return {
        "uniqueID": workspace.get("uniqueID"),
        "name": name,
        "displayName": workspace.get("displayName"),
        "qlab_version": qlab_version,
        "metadata": dict(workspace),
    }


def _known_child_count(cue: Any) -> int | None:
    if not isinstance(cue, dict):
        return None
    children = cue.get("cues")
    if isinstance(children, list):
        return len(children)
    return None


def _cue_overview_node(cue: Any) -> dict[str, Any]:
    if not isinstance(cue, dict):
        return {"value": cue, "child_count": 0, "children": []}
    node = {key: cue[key] for key in OVERVIEW_CUE_KEYS if key in cue}
    label = node.get("displayName") or node.get("name") or node.get("listName") or node.get("number") or node.get("uniqueID")
    if label is not None:
        node["label"] = str(label)
    node["child_count"] = _known_child_count(cue)
    node["children"] = []
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


def _connection_metadata(client: QLabOscClient) -> dict[str, Any]:
    return {
        "transport": "udp",
        "host": client.config.host,
        "osc_port": client.config.osc_port,
        "reply_port": client.config.reply_port,
        "timeout": client.config.timeout,
    }


def _workspace_candidate(workspace: Any) -> dict[str, Any]:
    if not isinstance(workspace, dict):
        return {"value": workspace}
    name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
    qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)
    return {
        "uniqueID": workspace.get("uniqueID"),
        "name": name,
        "displayName": workspace.get("displayName"),
        "qlab_version": qlab_version,
        "metadata": dict(workspace),
    }


def _base_permissions() -> dict[str, Any]:
    undetectable_reason = (
        "QLab does not expose passcode edit/control scopes through a read-only OSC query; "
        "proving this permission would require sending an edit or control command."
    )
    return {
        "probe_mode": "read_only",
        "view": {
            "ok": None,
            "status": "not_checked",
            "method": "cueLists/shallow",
            "safe_to_probe": True,
        },
        "edit": {
            "ok": None,
            "status": "not_checked",
            "method": None,
            "safe_to_probe": False,
            "reason": undetectable_reason,
        },
        "control": {
            "ok": None,
            "status": "not_checked",
            "method": None,
            "safe_to_probe": False,
            "reason": undetectable_reason,
        },
    }


def _base_capabilities() -> dict[str, Any]:
    return {
        "list_workspaces": False,
        "resolve_workspace": False,
        "read_workspace": False,
        "workspace_overview": False,
        "query_cues": False,
        "cue_details": False,
        "edit": None,
        "control": None,
    }


def _permission_warning() -> str:
    return (
        "Edit and control permissions are not checked by read-only diagnostics because QLab does not "
        "publish passcode scopes over OSC; confirming them would require an edit/control probe."
    )


def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(values))


def _normalize_query_filter(filter_name: str, value: Any) -> dict[str, Any]:
    normalized = filter_name.strip()
    if normalized not in QUERY_FILTERS:
        allowed = ", ".join(sorted(QUERY_FILTERS))
        raise ValueError(f"Unknown cue query filter {filter_name!r}; use one of: {allowed}")
    return {"filter": normalized, "value": value}


def _normalize_optional_filters(filters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_filters: list[dict[str, Any]] = []
    for item in filters or []:
        if not isinstance(item, dict):
            raise ValueError("optional_filters entries must be objects with filter and value")
        filter_name = item.get("filter") or item.get("name") or item.get("field")
        if not isinstance(filter_name, str):
            raise ValueError("optional_filters entries require a string filter")
        normalized_filters.append(_normalize_query_filter(filter_name, item.get("value")))
    return normalized_filters


def _parse_bool_filter(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0"}:
            return False
    raise ValueError(f"Boolean cue query filter value must be true or false: {value!r}")


def _string_equals(actual: Any, expected: Any) -> bool:
    return str(actual or "").casefold() == str(expected or "").casefold()


def _flatten_cue_refs(value: Any, parent_id: str | None = None, cue_list_id: str | None = None) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        return [{"uniqueID": value, "parent_id": parent_id, "cue_list_id": cue_list_id}]
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
                }
            )
        children = value.get("cues")
        if children is not None:
            cue_refs.extend(_flatten_cue_refs(children, parent_id=current_id, cue_list_id=current_cue_list_id))
        return cue_refs
    if isinstance(value, list):
        cue_refs: list[dict[str, Any]] = []
        for item in value:
            cue_refs.extend(_flatten_cue_refs(item, parent_id=parent_id, cue_list_id=cue_list_id))
        return cue_refs
    raise ValueError("QLab cue ID response must be a list, object, or string")


def _cue_matches_filter(cue: dict[str, Any], cue_ref: dict[str, Any], query_filter: dict[str, Any]) -> bool:
    filter_name = query_filter["filter"]
    expected = query_filter["value"]
    if filter_name in {"flagged", "armed", "isBroken", "isWarning", "isRunning", "isPaused"}:
        return cue.get(filter_name) is _parse_bool_filter(expected)
    if filter_name in {"type", "colorName"}:
        return _string_equals(cue.get(filter_name), expected)
    if filter_name == "name_contains":
        needle = str(expected or "").casefold()
        haystack = " ".join(str(cue.get(key) or "") for key in ("name", "displayName", "listName")).casefold()
        return needle in haystack
    if filter_name == "number_prefix":
        return str(cue.get("number") or "").startswith(str(expected or ""))
    if filter_name == "cue_list_id":
        return _string_equals(cue_ref.get("cue_list_id") or cue.get("parent"), expected)
    if filter_name == "parent_id":
        return _string_equals(cue_ref.get("parent_id") or cue.get("parent"), expected)
    raise ValueError(f"Unknown cue query filter {filter_name!r}")


class QLabReader:
    def __init__(self, client: QLabOscClient | None = None):
        self.client = client or QLabOscClient()

    def get_workspaces(self) -> dict[str, Any]:
        reply = self.client.request("/workspaces")
        return {"workspaces": reply.data, "status": reply.status}

    def check_connection(
        self,
        workspace_id: str | None = None,
        require_read_access: bool = True,
    ) -> dict[str, Any]:
        passcode_configured = bool(self.client.config.passcode)
        permissions = _base_permissions()
        capabilities = _base_capabilities()
        warnings: list[str] = [_permission_warning()]
        checks: dict[str, Any] = {
            "workspaces": None,
            "workspace_resolution": None,
            "read_access": None,
        }
        base_result: dict[str, Any] = {
            "ok": False,
            "status": "unknown",
            "qlab_reachable": False,
            "workspace_available": False,
            "workspace_readable": False,
            "workspace_id": None,
            "workspace_name": None,
            "qlab_version": None,
            "workspace_count": 0,
            "available_workspaces": [],
            "passcode_configured": passcode_configured,
            "passcode_status": None,
            "message": "",
            "connection": _connection_metadata(self.client),
            "permissions": permissions,
            "capabilities": capabilities,
            "checks": checks,
            "warnings": warnings,
        }

        try:
            workspaces_result = self.get_workspaces()
        except Exception as exc:
            checks["workspaces"] = {"ok": False, "error": str(exc)}
            return {
                **base_result,
                "status": "qlab_unreachable",
                "message": "QLab did not respond to /workspaces over OSC.",
            }

        workspaces = workspaces_result.get("workspaces") or []
        workspace_count = len(workspaces) if isinstance(workspaces, list) else 0
        checks["workspaces"] = {
            "ok": True,
            "reply_status": workspaces_result.get("status"),
            "workspace_count": workspace_count,
        }
        base_result.update(
            {
                "qlab_reachable": True,
                "workspace_count": workspace_count,
            }
        )
        capabilities["list_workspaces"] = True

        if not isinstance(workspaces, list):
            checks["workspace_resolution"] = {"ok": False, "error": "QLab workspaces response was not a list."}
            return {
                **base_result,
                "status": "invalid_workspaces_response",
                "message": "QLab responded, but /workspaces did not return the expected list shape.",
            }

        available_workspaces = [_workspace_candidate(item) for item in workspaces]
        base_result["available_workspaces"] = available_workspaces

        if workspace_count == 0:
            checks["workspace_resolution"] = {"ok": False, "error": "No open QLab workspaces were returned."}
            return {
                **base_result,
                "status": "no_workspace",
                "message": "QLab is reachable, but no open workspace was returned by /workspaces.",
            }

        if workspace_id is None and workspace_count > 1:
            checks["workspace_resolution"] = {
                "ok": False,
                "error": "Multiple workspaces are open; pass workspace_id to choose one.",
            }
            return {
                **base_result,
                "workspace_available": True,
                "status": "workspace_ambiguous",
                "message": "QLab is reachable, but multiple workspaces are open and no workspace_id was provided.",
            }

        try:
            if workspace_id is not None:
                requested = _clean_workspace_id(workspace_id)
                workspace = next(
                    (
                        item
                        for item in workspaces
                        if isinstance(item, dict)
                        and (item.get("uniqueID") == requested or item.get("displayName") == requested)
                    ),
                    None,
                )
                if workspace is None:
                    raise ValueError(f"Workspace not found: {requested}")
            else:
                workspace = self._resolve_workspace(workspaces, workspace_id)
            resolved_workspace_id = _clean_workspace_id(workspace.get("uniqueID") or workspace_id or "")
        except Exception as exc:
            checks["workspace_resolution"] = {"ok": False, "error": str(exc)}
            return {
                **base_result,
                "status": "workspace_not_found",
                "message": "QLab is reachable, but the requested workspace could not be resolved.",
            }

        workspace_name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
        qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)
        checks["workspace_resolution"] = {
            "ok": True,
            "workspace_id": resolved_workspace_id,
            "workspace_name": workspace_name,
        }
        capabilities["resolve_workspace"] = True
        base_result.update(
            {
                "workspace_available": True,
                "workspace_id": resolved_workspace_id,
                "workspace_name": workspace_name,
                "qlab_version": qlab_version,
            }
        )

        if not require_read_access:
            checks["read_access"] = {"ok": None, "skipped": True, "reason": "require_read_access is false"}
            permissions["view"] = {
                **permissions["view"],
                "ok": None,
                "status": "skipped",
                "reason": "require_read_access is false",
            }
            return {
                **base_result,
                "ok": True,
                "status": "ready",
                "message": "QLab is reachable and a workspace is available; read access was not checked.",
            }

        try:
            cue_lists = self.get_cue_lists(resolved_workspace_id, include_children=False)["cue_lists"]
        except QLabReplyError as exc:
            passcode_status = exc.status
            checks["read_access"] = {
                "ok": False,
                "status": exc.status,
                "address": exc.address,
                "data": exc.data,
                "error": str(exc),
            }
            permissions["view"] = {
                **permissions["view"],
                "ok": False,
                "status": exc.status,
                "address": exc.address,
                "error": str(exc),
            }
            return {
                **base_result,
                "passcode_status": passcode_status,
                "status": "workspace_denied" if exc.status == "denied" else "workspace_read_error",
                "message": "QLab is reachable, but the workspace denied the cue-list read check."
                if exc.status == "denied"
                else "QLab is reachable, but the workspace read check failed.",
            }
        except OscTimeoutError as exc:
            checks["read_access"] = {"ok": False, "status": "timeout", "error": str(exc)}
            permissions["view"] = {
                **permissions["view"],
                "ok": False,
                "status": "timeout",
                "error": str(exc),
            }
            return {
                **base_result,
                "status": "workspace_read_timeout",
                "message": "QLab is reachable, but the workspace read check timed out.",
            }
        except Exception as exc:
            checks["read_access"] = {"ok": False, "status": "error", "error": str(exc)}
            permissions["view"] = {
                **permissions["view"],
                "ok": False,
                "status": "error",
                "error": str(exc),
            }
            return {
                **base_result,
                "status": "workspace_read_error",
                "message": "QLab is reachable, but the workspace read check failed.",
            }

        checks["read_access"] = {
            "ok": True,
            "method": "cueLists/shallow",
            "cue_list_count": len(cue_lists) if isinstance(cue_lists, list) else None,
        }
        permissions["view"] = {
            "ok": True,
            "status": "confirmed",
            "method": "cueLists/shallow",
            "safe_to_probe": True,
            "cue_list_count": len(cue_lists) if isinstance(cue_lists, list) else None,
        }
        capabilities.update(
            {
                "read_workspace": True,
                "workspace_overview": True,
                "query_cues": True,
                "cue_details": True,
            }
        )
        return {
            **base_result,
            "ok": True,
            "status": "ready",
            "workspace_readable": True,
            "passcode_status": "accepted" if passcode_configured else None,
            "message": "QLab is reachable, a workspace is open, and the MCP can read cue lists.",
        }

    def get_workspace_overview(
        self,
        workspace_id: str | None = None,
        max_depth: int = 2,
        max_cues: int = 200,
        include_live_state: bool = False,
        include_selected_and_running: bool | None = None,
    ) -> dict[str, Any]:
        if include_selected_and_running is not None:
            include_live_state = include_selected_and_running
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

        summary: dict[str, Any] = {
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
            if summary["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                return None

            node = _cue_overview_node(cue)
            node["depth"] = depth
            summary["inspected_cues"] += 1
            summary["max_depth_returned"] = max(summary["max_depth_returned"], depth)
            _record_cue_stats(summary, node)

            cue_id = node.get("uniqueID")
            if not cue_id:
                node["child_count"] = node["child_count"] or 0
                return node
            if not _is_container_cue(node):
                node["child_count"] = node["child_count"] or 0
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
                if summary["inspected_cues"] >= max_cues:
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
            if summary["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                break

        live_state = None
        if include_live_state:
            live_state = {
                "selected_cues": self.get_selected_cues(
                    resolved_workspace_id,
                    include_children=False,
                )["selected_cues"],
                "running_cues": self.get_running_cues(
                    resolved_workspace_id,
                    include_paused=True,
                    include_children=False,
                )["running_cues"],
                "running_includes_paused": True,
            }

        warnings: list[str] = []
        if limits["truncated"]:
            warnings.append("Overview is partial; increase max_depth or max_cues for a deeper scan.")

        result = {
            "workspace_id": resolved_workspace_id,
            "workspace": _workspace_overview_metadata(workspace),
            "cue_count": id_result["cue_count"],
            "summary": summary,
            "cue_lists": overview_cue_lists,
            "limits": limits,
            "warnings": warnings,
            "errors": errors or None,
        }
        if live_state is not None:
            result["live_state"] = live_state
        return result

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

    def get_cue_lists(self, workspace_id: str, include_children: bool = False) -> dict[str, Any]:
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
        detail_profile: str = "basic_safe",
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

    def query_cues(
        self,
        workspace_id: str,
        primary_filter: str,
        primary_value: Any,
        optional_filters: list[dict[str, Any]] | None = None,
        profile: str = "basic_safe",
        max_results: int = 100,
        max_cues_scanned: int = 1000,
    ) -> dict[str, Any]:
        if max_results < 1:
            raise ValueError("max_results must be 1 or greater")
        if max_cues_scanned < 1:
            raise ValueError("max_cues_scanned must be 1 or greater")

        filters = [
            _normalize_query_filter(primary_filter, primary_value),
            *_normalize_optional_filters(optional_filters),
        ]

        response = self.client.request(_workspace_address(workspace_id, "cueLists/uniqueIDs"), workspace_id=workspace_id)
        cue_refs = _flatten_cue_refs(response.data)
        profile_keys = list(properties_for_profile(profile))
        filter_keys: list[str] = []
        for query_filter in filters:
            filter_keys.extend(QUERY_FILTER_PROPERTIES[query_filter["filter"]])
        keys = validate_value_keys(_dedupe_preserve_order([*QUERY_BASE_PROPERTIES, *profile_keys, *filter_keys]))

        scanned_count = 0
        matched_count = 0
        cues: list[dict[str, Any]] = []
        errors: dict[str, str] = {}

        for cue_ref in cue_refs[:max_cues_scanned]:
            cue_id = cue_ref.get("uniqueID")
            if not cue_id:
                continue
            scanned_count += 1
            try:
                values = self.read_cue_values(workspace_id, str(cue_id), keys)["values"]
                if not isinstance(values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
            except Exception as exc:
                errors[str(cue_id)] = str(exc)
                continue

            if not all(_cue_matches_filter(values, cue_ref, query_filter) for query_filter in filters):
                continue

            matched_count += 1
            if len(cues) < max_results:
                cue = {key: values[key] for key in keys if key in values}
                if cue_ref.get("parent_id") is not None:
                    cue["parent_id"] = cue_ref["parent_id"]
                if cue_ref.get("cue_list_id") is not None:
                    cue["cue_list_id"] = cue_ref["cue_list_id"]
                cues.append(cue)

        truncated = scanned_count < len(cue_refs) or matched_count > len(cues)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "filters": filters,
            "profile": profile,
            "scanned_count": scanned_count,
            "matched_count": matched_count,
            "returned_count": len(cues),
            "total_cue_ids": len(cue_refs),
            "truncated": truncated,
            "limits": {
                "max_results": max_results,
                "max_cues_scanned": max_cues_scanned,
            },
            "cues": cues,
            "errors": errors or None,
        }

    def get_selected_cues(self, workspace_id: str, include_children: bool = False) -> dict[str, Any]:
        command = "selectedCues" if include_children else "selectedCues/shallow"
        return self._workspace_data(workspace_id, command, "selected_cues")

    def get_running_cues(
        self,
        workspace_id: str,
        include_paused: bool = True,
        include_children: bool = False,
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

    def get_cue_details(self, workspace_id: str, cue_ref: str, profile: str = "basic_safe") -> dict[str, Any]:
        keys = list(properties_for_profile(profile))
        values: dict[str, Any]
        errors: dict[str, str] = {}

        try:
            batched_values = self.read_cue_values(workspace_id, cue_ref, keys)["values"]
            if not isinstance(batched_values, dict):
                raise ValueError("QLab valuesForKeys response must be an object")
            values = batched_values
        except Exception as exc:
            errors["valuesForKeys"] = str(exc)
            values = {}
            for property_path in keys:
                try:
                    values[property_path] = self.read_cue_property(workspace_id, cue_ref, property_path)["value"]
                except Exception as property_exc:
                    errors[property_path] = str(property_exc)

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
