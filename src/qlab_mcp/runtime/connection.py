"""QLab workspace reachability and permission diagnostics."""

from __future__ import annotations

from typing import Any

from ..osc.addressing import _clean_workspace_id
from ..osc.client import QLabOscClient
from ..errors import OscTimeoutError, QLabReplyError


QLAB_VERSION_KEYS = ("qlabVersion", "QLabVersion", "applicationVersion", "version")

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
        "workspace_settings": False,
        "workspace_setting_details": False,
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


class WorkspaceConnectionMixin:
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
            "passcode_status": "accepted" if passcode_configured else None,
            "message": "QLab is reachable, a workspace is open, and the MCP can read cue lists.",
        }
