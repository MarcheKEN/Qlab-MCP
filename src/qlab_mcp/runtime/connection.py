"""QLab workspace reachability and permission diagnostics."""

from __future__ import annotations

from typing import Any

from ..osc.addressing import _clean_workspace_id, _workspace_address
from ..osc.client import QLabOscClient
from ..errors import OscTimeoutError, QLabReplyError


QLAB_VERSION_KEYS = ("qlabVersion", "QLabVersion", "applicationVersion", "version")
CONNECT_SCOPE_ORDER = ("view", "edit", "control")


def parse_connect_scopes(data: Any) -> dict[str, Any]:
    """Normalize QLab /connect permission data such as ok:view|edit."""
    if not isinstance(data, str):
        return _connect_scope_result(
            ok=False,
            status="scope_unavailable",
            scopes=[],
            unknown_scopes=[],
            reason="/connect did not return a scope string.",
        )

    raw = data.strip()
    if not raw.casefold().startswith("ok:"):
        return _connect_scope_result(
            ok=False,
            status="scope_unavailable",
            scopes=[],
            unknown_scopes=[],
            reason="/connect did not return an ok:<scope> payload.",
        )

    known: list[str] = []
    unknown: list[str] = []
    for token in raw.split(":", 1)[1].replace(",", "|").split("|"):
        scope = token.strip().casefold()
        if not scope:
            continue
        if scope in CONNECT_SCOPE_ORDER:
            if scope not in known:
                known.append(scope)
        elif scope not in unknown:
            unknown.append(scope)

    ordered_known = [scope for scope in CONNECT_SCOPE_ORDER if scope in known]
    if not ordered_known:
        return _connect_scope_result(
            ok=False,
            status="scope_unavailable",
            scopes=[],
            unknown_scopes=unknown,
            reason="/connect returned no recognized permission scopes.",
        )

    return _connect_scope_result(
        ok=True,
        status="confirmed",
        scopes=ordered_known,
        unknown_scopes=unknown,
    )


def check_connect_scopes(client: QLabOscClient, workspace_id: str) -> dict[str, Any]:
    workspace = _clean_workspace_id(workspace_id)
    address = _workspace_address(workspace, "connect")
    passcode = getattr(client.config, "passcode", None)
    if not passcode:
        return _connect_scope_result(
            ok=None,
            status="not_checked",
            scopes=[],
            unknown_scopes=[],
            address=address,
            reason="QLAB_PASSCODE is not configured; /connect scopes were not checked.",
        )

    try:
        reply = client.request(address, passcode)
    except QLabReplyError as exc:
        return _connect_scope_result(
            ok=False,
            status=exc.status,
            scopes=[],
            unknown_scopes=[],
            address=address,
            error=str(exc),
        )
    except OscTimeoutError as exc:
        return _connect_scope_result(
            ok=False,
            status="timeout",
            scopes=[],
            unknown_scopes=[],
            address=address,
            error=str(exc),
        )
    except Exception as exc:
        return _connect_scope_result(
            ok=False,
            status="error",
            scopes=[],
            unknown_scopes=[],
            address=address,
            error=str(exc),
        )

    if reply.status != "ok":
        return _connect_scope_result(
            ok=False,
            status=reply.status,
            scopes=[],
            unknown_scopes=[],
            address=address,
        )

    parsed = parse_connect_scopes(reply.data)
    return {
        **parsed,
        "address": address,
        "reply_status": reply.status,
    }


def _connect_scope_result(
    *,
    ok: bool | None,
    status: str,
    scopes: list[str],
    unknown_scopes: list[str],
    address: str | None = None,
    reason: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": ok,
        "status": status,
        "scopes": scopes,
        "unknown_scopes": unknown_scopes,
        "source": "/connect",
    }
    if address is not None:
        result["address"] = address
    if reason:
        result["reason"] = reason
    if error:
        result["error"] = error
    return result


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
    not_checked_reason = "QLAB_PASSCODE is not configured; /connect permission scopes were not checked."
    return {
        "probe_mode": "connect",
        "view": {
            "ok": None,
            "status": "not_checked",
            "method": "cueLists/shallow",
            "safe_to_probe": True,
        },
        "edit": {
            "ok": None,
            "status": "not_checked",
            "source": "/connect",
            "safe_to_probe": True,
            "reason": not_checked_reason,
        },
        "control": {
            "ok": None,
            "status": "not_checked",
            "source": "/connect",
            "safe_to_probe": True,
            "reason": not_checked_reason,
        },
    }


def _base_capabilities() -> dict[str, Any]:
    return {
        "list_workspaces": False,
        "resolve_workspace": False,
        "read_workspace": False,
        "workspace_overview": False,
        "workspace_settings": False,
        "workspace_setting_details": False,
        "query_cues": False,
        "cue_details": False,
        "edit": None,
        "control": None,
    }


def _connect_warning(connect_scopes: dict[str, Any]) -> str | None:
    status = connect_scopes.get("status")
    if status == "not_checked":
        return "QLAB_PASSCODE is not configured; /connect permission scopes were not checked."
    if status == "scope_unavailable":
        return "QLab accepted /connect but did not return parseable permission scopes; edit/control are not granted."
    return None


def _apply_connect_permissions(
    permissions: dict[str, Any],
    capabilities: dict[str, Any],
    connect_scopes: dict[str, Any],
) -> None:
    status = connect_scopes.get("status")
    if status == "confirmed":
        scopes = set(connect_scopes.get("scopes") or [])
        for scope in CONNECT_SCOPE_ORDER:
            granted = scope in scopes
            permissions[scope] = {
                "ok": granted,
                "status": "confirmed" if granted else "not_granted",
                "source": "/connect",
                "safe_to_probe": True,
            }
        capabilities["edit"] = "edit" in scopes
        capabilities["control"] = "control" in scopes
        return

    if status == "not_checked":
        return

    for scope in CONNECT_SCOPE_ORDER:
        permissions[scope] = {
            "ok": False,
            "status": status,
            "source": "/connect",
            "safe_to_probe": True,
            "reason": connect_scopes.get("reason") or connect_scopes.get("error"),
        }
    capabilities["edit"] = False
    capabilities["control"] = False


class WorkspaceConnectionMixin:
    def check_connection(
        self,
        workspace_id: str | None = None,
        require_read_access: bool = True,
    ) -> dict[str, Any]:
        passcode_configured = bool(self.client.config.passcode)
        permissions = _base_permissions()
        capabilities = _base_capabilities()
        warnings: list[str] = []
        checks: dict[str, Any] = {
            "workspaces": None,
            "workspace_resolution": None,
            "connect": None,
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
            "connect_scopes": None,
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

        connect_scopes = check_connect_scopes(self.client, resolved_workspace_id)
        checks["connect"] = connect_scopes
        base_result["connect_scopes"] = connect_scopes
        _apply_connect_permissions(permissions, capabilities, connect_scopes)
        warning = _connect_warning(connect_scopes)
        if warning:
            warnings.append(warning)
        if connect_scopes["status"] in {"confirmed", "scope_unavailable"}:
            base_result["passcode_status"] = "accepted" if passcode_configured else None
        elif connect_scopes["status"] == "denied":
            return {
                **base_result,
                "passcode_status": "denied",
                "status": "workspace_denied",
                "message": "QLab is reachable, but the workspace denied /connect.",
            }
        elif connect_scopes["status"] in {"timeout", "error"}:
            return {
                **base_result,
                "passcode_status": connect_scopes["status"],
                "status": "workspace_connect_failed",
                "message": "QLab is reachable, but /connect failed for the requested workspace.",
            }

        if not require_read_access:
            checks["read_access"] = {"ok": None, "skipped": True, "reason": "require_read_access is false"}
            if permissions["view"]["status"] == "not_checked":
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
            "source": "cueLists/shallow",
            "safe_to_probe": True,
            "cue_list_count": len(cue_lists) if isinstance(cue_lists, list) else None,
        }
        capabilities.update(
            {
                "read_workspace": True,
                "workspace_overview": True,
                "workspace_settings": True,
                "workspace_setting_details": True,
                "query_cues": True,
                "cue_details": True,
            }
        )
        return {
            **base_result,
            "ok": True,
            "status": "ready",
            "workspace_readable": True,
            "message": "QLab is reachable, a workspace is open, and the MCP can read cue lists.",
        }
