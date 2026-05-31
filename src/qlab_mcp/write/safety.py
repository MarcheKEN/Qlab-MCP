"""Safety gates and readiness checks for QLab write mode."""

from __future__ import annotations

from typing import Any

from ..errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from ..osc.addressing import _clean_workspace_id
from ..runtime.connection import check_connect_scopes, read_workspace_mode
from .allowlist import planned_write_capabilities


EDIT_PERMISSION_NOTE = (
    "QLab edit permission must be confirmed by /connect before real write commands can run."
)

READINESS_ACTIONS = {
    "write_disabled": "Set QLAB_ENABLE_WRITE=true only for a deliberate write session.",
    "passcode_missing": "Set QLAB_PASSCODE on the MCP server; do not pass the QLab passcode as a tool argument.",
    "workspace_unavailable": "Call qlab_check_connection and pass a workspace_id from available_workspaces.",
    "qlab_unreachable": "Start QLab, open the workspace, enable OSC, and verify host/port settings.",
    "edit_not_confirmed": "Confirm the QLab passcode grants edit scope via /connect.",
    "workspace_in_show_mode": "Switch the QLab workspace to Edit Mode before real writes.",
    "show_mode_unknown": "Verify /showMode can be read and confirms Edit Mode before real writes.",
}


def check_write_readiness(reader: Any, workspace_id: str) -> dict[str, Any]:
    workspace = _clean_workspace_id(workspace_id)
    config = reader.client.config
    write_enabled = bool(getattr(config, "enable_write", False))
    dry_run_default = bool(getattr(config, "write_dry_run_default", True))
    passcode_configured = bool(getattr(config, "passcode", None))
    capabilities = planned_write_capabilities(dry_run_default)
    blockers: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {
        "write_enabled": {"ok": write_enabled, "env": "QLAB_ENABLE_WRITE"},
        "workspace_id": {"ok": True, "required": True, "workspace_id": workspace},
        "passcode": {
            "ok": passcode_configured,
            "env": "QLAB_PASSCODE",
            "required_for_real_write": True,
        },
        "edit_permission": {
            "ok": None,
            "status": "not_checked",
            "source": "/connect",
            "safe_to_probe": True,
            "reason": EDIT_PERMISSION_NOTE,
        },
        "connect": None,
        "show_mode": None,
        "workspace_resolution": {"ok": None, "status": "not_checked"},
    }

    if not write_enabled:
        blockers.append("write_disabled")
    if not passcode_configured:
        blockers.append("passcode_missing")

    if blockers:
        return _readiness_result(
            ok=False,
            status=blockers[0],
            message="QLab write mode is not ready; resolve blockers before attempting gated writes.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    try:
        workspace_info = _resolve_workspace_for_write(reader, workspace)
    except QLabReplyError as exc:
        checks["workspace_resolution"] = {"ok": False, "status": exc.status}
        blockers.append("workspace_unavailable")
        return _readiness_result(
            ok=False,
            status="workspace_unavailable",
            message="QLab responded but the requested workspace could not be resolved for write mode.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )
    except OscTimeoutError:
        checks["workspace_resolution"] = {"ok": False, "status": "timeout"}
        blockers.append("qlab_unreachable")
        return _readiness_result(
            ok=False,
            status="qlab_unreachable",
            message="QLab did not reply while resolving the workspace for write mode.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )
    except Exception:
        checks["workspace_resolution"] = {"ok": False, "status": "error"}
        blockers.append("workspace_unavailable")
        return _readiness_result(
            ok=False,
            status="workspace_unavailable",
            message="The requested workspace could not be resolved for write mode.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    checks["workspace_resolution"] = {
        "ok": True,
        "status": "resolved",
        "workspace_id": workspace_info.get("uniqueID") or workspace,
        "workspace_name": workspace_info.get("displayName") or workspace_info.get("name"),
    }
    connect_scopes = check_connect_scopes(reader.client, workspace)
    checks["connect"] = connect_scopes
    edit_confirmed = connect_scopes.get("status") == "confirmed" and "edit" in (connect_scopes.get("scopes") or [])
    edit_status = "confirmed" if edit_confirmed else "not_granted"
    if not edit_confirmed and connect_scopes.get("status") not in {"confirmed", None}:
        edit_status = str(connect_scopes.get("status"))
    checks["edit_permission"] = {
        "ok": edit_confirmed,
        "status": edit_status,
        "source": "/connect",
        "safe_to_probe": True,
        "scopes": connect_scopes.get("scopes") or [],
        "connect_status": connect_scopes.get("status"),
    }
    if not edit_confirmed:
        blockers.append("edit_not_confirmed")
        return _readiness_result(
            ok=False,
            status="edit_not_confirmed",
            message="QLab write mode is not ready; /connect did not confirm edit permission.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    workspace_mode = read_workspace_mode(reader.client, workspace, authenticated=True)
    checks["show_mode"] = workspace_mode
    if workspace_mode.get("show_mode") is True:
        blockers.append("workspace_in_show_mode")
        return _readiness_result(
            ok=False,
            status="workspace_in_show_mode",
            message="QLab write mode is not ready; the workspace is currently in Show Mode.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )
    if workspace_mode.get("ok") is not True:
        blockers.append("show_mode_unknown")
        return _readiness_result(
            ok=False,
            status="show_mode_unknown",
            message="QLab write mode is not ready; /showMode could not confirm the workspace is in Edit Mode.",
            workspace_id=workspace,
            write_enabled=write_enabled,
            dry_run_default=dry_run_default,
            passcode_configured=passcode_configured,
            capabilities=capabilities,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    return _readiness_result(
        ok=True,
        status="ready",
        message="QLab write mode is enabled, /connect confirmed edit permission, and the workspace is in Edit Mode.",
        workspace_id=workspace,
        write_enabled=write_enabled,
        dry_run_default=dry_run_default,
        passcode_configured=passcode_configured,
        capabilities=capabilities,
        checks=checks,
        blockers=[],
        warnings=warnings,
    )


def ensure_write_ready(reader: Any, workspace_id: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    config = reader.client.config
    if not bool(getattr(config, "enable_write", False)):
        raise UnsafeWriteOperationError("Write mode is disabled. Set QLAB_ENABLE_WRITE=true to enable gated writes.")
    if not bool(getattr(config, "passcode", None)):
        raise UnsafeWriteOperationError("QLAB_PASSCODE must be configured on the server before write mode can run.")
    readiness = check_write_readiness(reader, workspace)
    if not readiness["ok"]:
        raise UnsafeWriteOperationError(readiness["message"])
    return workspace


def resolve_dry_run(reader: Any, dry_run: bool | None) -> bool:
    if dry_run is not None:
        return bool(dry_run)
    return bool(getattr(reader.client.config, "write_dry_run_default", True))


def _resolve_workspace_for_write(reader: Any, workspace_id: str) -> dict[str, Any]:
    workspaces = reader.get_workspaces().get("workspaces")
    workspace = reader._resolve_workspace(workspaces, workspace_id)
    if not isinstance(workspace, dict):
        raise ValueError("QLab workspace entry must be an object")
    return workspace


def _readiness_result(
    *,
    ok: bool,
    status: str,
    message: str,
    workspace_id: str,
    write_enabled: bool,
    dry_run_default: bool,
    passcode_configured: bool,
    capabilities: dict[str, Any],
    checks: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "workspace_id": workspace_id,
        "write_enabled": write_enabled,
        "dry_run_default": dry_run_default,
        "passcode_configured": passcode_configured,
        "capabilities": capabilities,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "error_code": None if ok else f"QLAB_WRITE_{status.upper()}",
        "suggested_action": None if ok else READINESS_ACTIONS.get(status, "Inspect checks and blockers before retrying."),
        "message": message,
    }
