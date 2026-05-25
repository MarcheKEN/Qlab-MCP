"""Safety gates and readiness checks for QLab write mode."""

from __future__ import annotations

from typing import Any

from ..errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from ..osc.addressing import _clean_workspace_id
from .allowlist import planned_write_capabilities


EDIT_PERMISSION_NOTE = (
    "QLab edit permission cannot be proven without sending a mutating OSC command. "
    "This readiness check only verifies local write configuration, passcode presence, "
    "and workspace resolution through non-mutating reads."
)


def check_write_readiness(reader: Any, workspace_id: str) -> dict[str, Any]:
    workspace = _clean_workspace_id(workspace_id)
    config = reader.client.config
    write_enabled = bool(getattr(config, "enable_write", False))
    dry_run_default = bool(getattr(config, "write_dry_run_default", True))
    passcode_configured = bool(getattr(config, "passcode", None))
    capabilities = planned_write_capabilities(dry_run_default)
    blockers: list[str] = []
    warnings = [EDIT_PERMISSION_NOTE]
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
            "safe_to_probe": False,
            "reason": EDIT_PERMISSION_NOTE,
        },
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
            message="QLab write mode is not ready; resolve blockers before attempting cue creation.",
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
    return _readiness_result(
        ok=True,
        status="ready",
        message=(
            "QLab write mode is enabled and locally ready. Real edit permission is still only proven "
            "by the first mutating command, so prefer dry_run before creating cues."
        ),
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
        "message": message,
    }
