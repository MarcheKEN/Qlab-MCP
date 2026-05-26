"""Gated mutating OSC operations for QLab write mode."""

from __future__ import annotations

from typing import Any

from ..errors import UnsafeWriteOperationError
from ..osc.addressing import _clean_cue_ref, _clean_workspace_id, _cue_address, _workspace_address
from ..runtime.read_cache import shared_read_cache
from .allowlist import validate_writable_cue_type, validate_write_properties
from .safety import check_write_readiness, ensure_write_ready, resolve_dry_run


class QLabWriteMixin:
    def check_write_readiness(self, workspace_id: str) -> dict[str, Any]:
        return check_write_readiness(self, workspace_id)

    def create_cue(
        self,
        workspace_id: str,
        cue_type: str,
        properties: dict[str, Any] | None = None,
        dry_run: bool | None = None,
        after_cue_id: str | None = None,
    ) -> dict[str, Any]:
        workspace = _clean_workspace_id(workspace_id)
        qlab_cue_type = validate_writable_cue_type(cue_type)
        normalized_properties = validate_write_properties(properties)
        effective_dry_run = resolve_dry_run(self, dry_run)
        placement = _normalize_placement(after_cue_id)
        planned_operations = _planned_create_operations(workspace, qlab_cue_type, normalized_properties, placement)

        if placement is not None and not effective_dry_run:
            raise UnsafeWriteOperationError(
                "after_cue_id placement is only available in dry-run during this write-mode preface."
            )

        if effective_dry_run:
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace,
                "cue_type": qlab_cue_type,
                "dry_run": True,
                "created_cue_id": None,
                "placement": placement,
                "properties": normalized_properties,
                "planned_operations": planned_operations,
                "executed_operations": [],
                "verification": None,
                "warnings": [
                    "Dry run only: no mutating OSC commands were sent to QLab.",
                ],
                "message": "Dry run succeeded; review planned_operations before disabling dry_run.",
            }

        workspace = ensure_write_ready(self, workspace)

        read_cache = getattr(self, "_read_cache", shared_read_cache())
        read_cache.clear()

        executed_operations: list[dict[str, Any]] = []
        new_address = _workspace_address(workspace, "new")
        new_reply = self.client.request(new_address, qlab_cue_type, workspace_id=workspace)
        created_cue_id = _extract_created_cue_id(new_reply.data)
        executed_operations.append(
            {
                "operation": "new",
                "address": new_address,
                "args": [qlab_cue_type],
                "status": new_reply.status,
                "created_cue_id": created_cue_id,
            }
        )

        for key, value in normalized_properties.items():
            address = _cue_id_address(workspace, created_cue_id, key)
            reply = self.client.request(address, value, workspace_id=workspace)
            executed_operations.append(
                {
                    "operation": "set_property",
                    "property": key,
                    "address": address,
                    "args": [value],
                    "status": reply.status,
                }
            )

        read_cache.clear()
        verification = self.get_cue_details(workspace, created_cue_id, "auto")
        read_cache.clear()

        return {
            "ok": True,
            "status": "created",
            "workspace_id": workspace,
            "cue_type": qlab_cue_type,
            "dry_run": False,
            "created_cue_id": created_cue_id,
            "placement": placement,
            "properties": normalized_properties,
            "planned_operations": planned_operations,
            "executed_operations": executed_operations,
            "verification": verification,
            "warnings": [],
            "message": "Cue created, safe initial properties applied, and cue details read back fresh.",
        }

    def update_cue(
        self,
        workspace_id: str,
        cue_ref: str,
        properties: dict[str, Any],
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        workspace = _clean_workspace_id(workspace_id)
        cue = _clean_update_cue_ref(cue_ref)
        normalized_properties = validate_write_properties(properties)
        if not normalized_properties:
            raise UnsafeWriteOperationError("properties must include at least one allowlisted cue property")
        effective_dry_run = resolve_dry_run(self, dry_run)
        planned_operations = _planned_update_operations(workspace, cue, normalized_properties)

        if effective_dry_run:
            before, errors = _try_read_update_values(self, workspace, cue, normalized_properties)
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace,
                "cue_ref": cue,
                "dry_run": True,
                "properties": normalized_properties,
                "before": before,
                "after": None,
                "diff": _diff_properties(before, normalized_properties),
                "planned_operations": planned_operations,
                "executed_operations": [],
                "verification": None,
                "errors": errors or None,
                "warnings": ["Dry run only: no mutating OSC commands were sent to QLab."],
                "message": "Dry run succeeded; review planned_operations before disabling dry_run.",
            }

        workspace = ensure_write_ready(self, workspace)

        read_cache = getattr(self, "_read_cache", shared_read_cache())
        read_cache.clear()
        before, before_errors = _try_read_update_values(self, workspace, cue, normalized_properties)
        if before is None or not before.get("uniqueID"):
            read_cache.clear()
            return {
                "ok": False,
                "status": "cue_not_found",
                "workspace_id": workspace,
                "cue_ref": cue,
                "dry_run": False,
                "properties": normalized_properties,
                "before": before,
                "after": None,
                "diff": _diff_properties(before, normalized_properties),
                "planned_operations": planned_operations,
                "executed_operations": [],
                "verification": None,
                "errors": before_errors or {"cue": "Cue could not be read before update."},
                "warnings": [],
                "message": "Cue update was blocked because the target cue could not be read.",
            }

        executed_operations: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for key, value in normalized_properties.items():
            address = _cue_address(workspace, cue, key)
            try:
                reply = self.client.request(address, value, workspace_id=workspace)
            except Exception as exc:
                errors[key] = str(exc)
                break
            executed_operations.append(
                {
                    "operation": "set_property",
                    "property": key,
                    "address": address,
                    "args": [value],
                    "status": reply.status,
                }
            )

        read_cache.clear()
        after, after_errors = _try_read_update_values(self, workspace, cue, normalized_properties)
        verification = None
        try:
            verification = self.get_cue_details(workspace, cue, "auto")
        except Exception as exc:
            after_errors["verification"] = str(exc)
        read_cache.clear()

        all_errors = {**errors, **after_errors}
        failed = bool(errors)
        verification_failed = bool(after_errors) and not failed
        status = "partial_failed" if failed else "verification_failed" if verification_failed else "updated"
        if failed:
            message = "Cue update failed part-way; inspect executed_operations and errors."
        elif verification_failed:
            message = "Cue update commands completed, but fresh verification failed."
        else:
            message = "Cue updated, safe properties applied, and cue details read back fresh."
        return {
            "ok": not failed and not verification_failed,
            "status": status,
            "workspace_id": workspace,
            "cue_ref": cue,
            "dry_run": False,
            "properties": normalized_properties,
            "before": before,
            "after": after,
            "diff": _diff_properties(before, normalized_properties, after),
            "planned_operations": planned_operations,
            "executed_operations": executed_operations,
            "verification": verification,
            "errors": all_errors or None,
            "warnings": [],
            "message": message,
        }


def _normalize_placement(after_cue_id: str | None) -> dict[str, Any] | None:
    if after_cue_id is None:
        return None
    cue_id = _clean_cue_ref(after_cue_id)
    return {
        "after_cue_id": cue_id,
        "status": "planned_only",
        "message": "after_cue_id is accepted for dry-run planning only in this preface.",
    }


def _clean_update_cue_ref(cue_ref: str) -> str:
    cue = _clean_cue_ref(cue_ref)
    if cue.casefold() in {"selected", "playhead", "playbackposition", "active"}:
        raise UnsafeWriteOperationError("cue_ref for update must be a concrete cue number or unique ID")
    return cue


def _planned_create_operations(
    workspace_id: str,
    cue_type: str,
    properties: dict[str, Any],
    placement: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = [
        {
            "operation": "new",
            "address": _workspace_address(workspace_id, "new"),
            "args": [cue_type],
        }
    ]
    if placement is not None:
        operations.append(
            {
                "operation": "move_after",
                "after_cue_id": placement["after_cue_id"],
                "status": "planned_only",
            }
        )
    for key, value in properties.items():
        operations.append(
            {
                "operation": "set_property",
                "property": key,
                "address": f"/workspace/{workspace_id}/cue_id/{{created_cue_id}}/{key}",
                "args": [value],
            }
        )
    operations.append(
        {
            "operation": "verify",
            "profile": "auto",
            "cacheable": False,
        }
    )
    return operations


def _planned_update_operations(
    workspace_id: str,
    cue_ref: str,
    properties: dict[str, Any],
) -> list[dict[str, Any]]:
    operations = [
        {
            "operation": "read_before",
            "profile": "update_safe",
            "cacheable": False,
        }
    ]
    for key, value in properties.items():
        operations.append(
            {
                "operation": "set_property",
                "property": key,
                "address": _cue_address(workspace_id, cue_ref, key),
                "args": [value],
            }
        )
    operations.append(
        {
            "operation": "verify",
            "profile": "auto",
            "cacheable": False,
        }
    )
    return operations


def _update_read_keys(properties: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(["uniqueID", "type", *properties.keys()]))


def _try_read_update_values(
    reader: Any,
    workspace_id: str,
    cue_ref: str,
    properties: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    try:
        values = reader.read_cue_values(
            workspace_id,
            cue_ref,
            _update_read_keys(properties),
            cache_profile="basic_safe",
            cacheable=False,
        )["values"]
        if not isinstance(values, dict):
            raise ValueError("QLab valuesForKeys response must be an object")
        return values, {}
    except Exception as exc:
        return None, {"read_before": str(exc)}


def _diff_properties(
    before: dict[str, Any] | None,
    requested: dict[str, Any],
    after: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key, requested_value in requested.items():
        entry = {
            "before": before.get(key) if before else None,
            "requested": requested_value,
        }
        if after is not None:
            entry["after"] = after.get(key)
        diff[key] = entry
    return diff


def _extract_created_cue_id(data: Any) -> str:
    if isinstance(data, str):
        return _clean_cue_ref(data)
    if isinstance(data, dict):
        for key in ("uniqueID", "cueID", "cue_id", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return _clean_cue_ref(value)
        cue = data.get("cue")
        if isinstance(cue, dict):
            return _extract_created_cue_id(cue)
    if isinstance(data, list) and data:
        return _extract_created_cue_id(data[0])
    raise UnsafeWriteOperationError("QLab did not return a cue unique ID after /new.")


def _cue_id_address(workspace_id: str, cue_id: str, command: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    cue = _clean_cue_ref(cue_id)
    return f"/workspace/{workspace}/cue_id/{cue}/{command.strip('/')}"
