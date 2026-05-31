"""Gated mutating OSC operations for QLab write mode."""

from __future__ import annotations

import os
import time
from typing import Any

from ..errors import OscTimeoutError, UnsafeWriteOperationError
from ..osc.addressing import (
    _clean_cue_ref,
    _clean_workspace_id,
    _cue_address,
    _normalize_id_list,
    _workspace_address,
)
from ..runtime.read_cache import shared_read_cache
from .allowlist import (
    COMMON_UPDATE_PROFILE,
    ensure_real_write_allowed,
    normalize_update_request,
    read_keys_for_operations,
    validate_update_profile,
    validate_update_profile_for_cue,
    validate_writable_cue_type,
    validate_write_properties,
)
from .safety import check_write_readiness, ensure_write_ready, resolve_dry_run


MAX_BATCH_UPDATES = 50
AFTER_READ_RETRY_DELAYS = (0.2, 0.5, 1.0)
UPDATE_STATUS_ACTIONS = {
    "preflight_failed": "Inspect per-cue errors; no setters were sent, so fix cue refs/profiles before retrying.",
    "partial_failed": "Inspect per-cue errors and verify the affected cues in QLab before retrying only failed items.",
    "verification_failed": "Read the cue fresh and compare requested versus after values before retrying.",
}
UPDATE_STATUS_CODES = {
    "preflight_failed": "QLAB_UPDATE_PREFLIGHT_FAILED",
    "partial_failed": "QLAB_UPDATE_PARTIAL_FAILED",
    "verification_failed": "QLAB_UPDATE_VERIFICATION_FAILED",
}
CONTINUE_MODE_VALUES = {
    0: 0,
    1: 1,
    2: 2,
    "0": 0,
    "1": 1,
    "2": 2,
    "do_not_continue": 0,
    "do-not-continue": 0,
    "manual": 0,
    "none": 0,
    "auto_continue": 1,
    "auto-continue": 1,
    "autocontinue": 1,
    "auto_follow": 2,
    "auto-follow": 2,
    "autofollow": 2,
}
CASEFOLD_COMPARISON_KEYS = {
    "blendMode",
    "clockType",
    "colorName",
    "text/format/alignment",
}


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
        warnings: list[str] = []
        errors: dict[str, str] = {}
        before_ids = _try_workspace_cue_ids(self, workspace)
        new_address = _workspace_address(workspace, "new")
        try:
            new_reply = self.client.request(new_address, qlab_cue_type)
            created_cue_id = _extract_created_cue_id(new_reply.data)
            new_status = new_reply.status
        except OscTimeoutError as exc:
            created_cue_id = _resolve_created_cue_after_timeout(self, workspace, before_ids)
            new_status = "timeout_confirmed_by_fresh_read"
            warnings.append(f"QLab did not reply to /new, but a fresh cue ID diff found created cue {created_cue_id}.")
            if created_cue_id is None:
                raise UnsafeWriteOperationError(f"QLab did not reply to /new and the created cue could not be identified: {exc}") from exc
        executed_operations.append(
            {
                "operation": "new",
                "address": new_address,
                "args": [qlab_cue_type],
                "status": new_status,
                "created_cue_id": created_cue_id,
            }
        )

        for key, value in normalized_properties.items():
            address = _cue_id_address(workspace, created_cue_id, key)
            try:
                reply = self.client.request(address, value)
                status = reply.status
                error = None
            except OscTimeoutError as exc:
                status = "timeout_pending_verification"
                error = str(exc)
                warnings.append(f"QLab did not reply to setter {key}; fresh verification is authoritative.")
            except Exception as exc:
                errors[key] = str(exc)
                break
            executed_operations.append(
                {
                    "operation": "set_property",
                    "property": key,
                    "address": address,
                    "args": [value],
                    "status": status,
                    **({"error": error} if error else {}),
                }
            )

        read_cache.clear()
        verification = self.get_cue_details(workspace, created_cue_id, "auto")
        read_cache.clear()
        verification_properties = verification.get("properties") if isinstance(verification, dict) else {}
        verified = _properties_match(verification_properties, normalized_properties)
        if errors or not verified:
            status = "verification_failed"
            ok = False
            message = "Cue create command was sent, but fresh verification did not confirm all requested properties."
        else:
            status = "created"
            ok = True
            message = "Cue created, safe initial properties applied, and cue details read back fresh."

        return {
            "ok": ok,
            "status": status,
            "workspace_id": workspace,
            "cue_type": qlab_cue_type,
            "dry_run": False,
            "created_cue_id": created_cue_id,
            "placement": placement,
            "properties": normalized_properties,
            "planned_operations": planned_operations,
            "executed_operations": executed_operations,
            "verification": verification,
            "errors": errors or None,
            "warnings": warnings,
            "message": message,
        }

    def update_cue(
        self,
        workspace_id: str,
        cue_ref: str,
        properties: dict[str, Any] | None = None,
        dry_run: bool | None = None,
        profile: str | None = None,
        operations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Compatibility wrapper for local Python callers; MCP exposes qlab_update_cues."""
        batch = self.update_cues(
            workspace_id,
            [
                {
                    "cue_ref": cue_ref,
                    "profile": profile or COMMON_UPDATE_PROFILE,
                    "properties": properties,
                    "operations": operations,
                }
            ],
            dry_run=dry_run,
        )
        item = dict(batch["results"][0])
        if not batch["ok"] and batch["status"] == "preflight_failed" and item.get("errors") and "profile" in item["errors"]:
            raise UnsafeWriteOperationError("; ".join(item["errors"].values()))
        status = item["status"]
        if item.get("errors") and "cue" in item["errors"]:
            status = "cue_not_found"
        if status == "updated_with_confirmed_timeouts":
            status = "updated"
        return {
            "ok": batch["ok"],
            "status": status,
            "workspace_id": batch["workspace_id"],
            "cue_ref": item["cue_ref"],
            "profile": item["profile"],
            "dry_run": batch["dry_run"],
            "properties": item["properties"],
            "operations": item["operations"],
            "before": item["before"],
            "after": item["after"],
            "diff": item["diff"],
            "planned_operations": item["planned_operations"],
            "executed_operations": item["executed_operations"],
            "verification": {"properties": item["after"]} if item.get("after") else None,
            "errors": item["errors"],
            "warnings": item["warnings"],
            "message": batch["message"],
        }

    def update_cues(
        self,
        workspace_id: str,
        updates: list[dict[str, Any]],
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        workspace = _clean_workspace_id(workspace_id)
        if not isinstance(updates, list):
            raise UnsafeWriteOperationError("updates must be a list")
        if not updates:
            raise UnsafeWriteOperationError("updates must include at least one cue update")
        if len(updates) > MAX_BATCH_UPDATES:
            raise UnsafeWriteOperationError(f"updates can include at most {MAX_BATCH_UPDATES} cue updates")
        effective_dry_run = resolve_dry_run(self, dry_run)
        items = [_normalize_batch_update_item(raw_update) for raw_update in updates]

        if effective_dry_run:
            results = []
            for item in items:
                before, errors = _try_read_update_values(self, workspace, item["cue_ref"], item["read_keys"])
                profile_errors = _validate_profile_for_before(item["profile"], before)
                errors.update(profile_errors)
                cue_id = _resolved_cue_id(before)
                results.append(
                    _batch_item_result(
                        workspace,
                        item,
                        cue_id=cue_id,
                        status="dry_run" if not errors else "dry_run_preflight_failed",
                        before=before,
                        after=None,
                        errors=errors or None,
                        warnings=["Dry run only: no mutating OSC commands were sent to QLab."],
                    )
                )
            failed_count = sum(1 for result in results if result["errors"])
            return _batch_update_result(
                workspace,
                dry_run=True,
                results=results,
                status="dry_run" if failed_count == 0 else "preflight_failed",
                requested_count=len(items),
                warnings=["Dry run only: no mutating OSC commands were sent to QLab."],
            )

        for item in items:
            ensure_real_write_allowed(item["profile"], item["operations"])
        workspace = ensure_write_ready(self, workspace)

        read_cache = getattr(self, "_read_cache", shared_read_cache())
        read_cache.clear()
        preflight_results: list[dict[str, Any]] = []
        preflight_ok = True
        for item in items:
            before, before_errors = _try_read_update_values(self, workspace, item["cue_ref"], item["read_keys"])
            resolved_cue_id = _resolved_cue_id(before)
            errors = dict(before_errors)
            if before is None or not resolved_cue_id:
                errors.setdefault("cue", "Cue could not be read before update.")
            errors.update(_validate_profile_for_before(item["profile"], before))
            if errors:
                preflight_ok = False
            preflight_results.append(
                _batch_item_result(
                    workspace,
                    item,
                    cue_id=resolved_cue_id,
                    status="planned" if not errors else "preflight_failed",
                    before=before,
                    after=None,
                    errors=errors or None,
                    warnings=[],
                )
            )

        if not preflight_ok:
            read_cache.clear()
            return _batch_update_result(
                workspace,
                dry_run=False,
                results=preflight_results,
                status="preflight_failed",
                requested_count=len(items),
                errors={"preflight": "One or more cue updates failed preflight; no setters were sent."},
            )

        executed_items: list[dict[str, Any]] = []
        for item, planned in zip(items, preflight_results, strict=True):
            cue_id = planned["cue_id"]
            executed_operations: list[dict[str, Any]] = []
            errors: dict[str, str] = {}
            setter_timeouts: dict[str, str] = {}
            for operation in item["operations"]:
                key = operation["property"]
                address = _cue_id_address(workspace, cue_id, operation["path"])
                try:
                    reply = self.client.request(address, *operation["args"])
                    status = reply.status
                    error = None
                except OscTimeoutError as exc:
                    setter_timeouts[key] = str(exc)
                    status = "timeout_pending_verification"
                    error = str(exc)
                except Exception as exc:
                    errors[key] = str(exc)
                    break
                executed_operations.append(
                    {
                        "operation": "set_property",
                        "property": key,
                        "address": address,
                        "args": operation["args"],
                        "mode": operation["mode"],
                        "status": status,
                        **({"error": error} if error else {}),
                    }
                )
            item_result = dict(planned)
            item_result["executed_operations"] = executed_operations
            item_result["_setter_timeouts"] = setter_timeouts
            item_result["_setter_errors"] = errors
            executed_items.append(item_result)

        read_cache.clear()
        final_results: list[dict[str, Any]] = []
        timeout_confirmed_count = 0
        for item, result in zip(items, executed_items, strict=True):
            after, after_errors = _try_read_update_values_with_retries(
                self,
                workspace,
                result["cue_id"],
                item["read_keys"],
                item["properties"],
                retry_on_mismatch=bool(result["_setter_timeouts"]),
            )
            confirmed_by_after = _properties_match(after, item["properties"])
            setter_timeouts = result.pop("_setter_timeouts")
            setter_errors = result.pop("_setter_errors")
            unconfirmed_timeouts = {} if confirmed_by_after else setter_timeouts
            value_mismatch = {}
            if not confirmed_by_after and not setter_errors and not unconfirmed_timeouts and not after_errors:
                value_mismatch["verification"] = _verification_mismatch_message(after, item["properties"])
            errors = {**setter_errors, **unconfirmed_timeouts, **after_errors, **value_mismatch}
            warnings = list(result["warnings"])
            if setter_timeouts and confirmed_by_after:
                timeout_confirmed_count += 1
                warnings.append("One or more setters did not reply, but fresh after-read confirmed requested values.")
            failed = bool(setter_errors) or bool(unconfirmed_timeouts)
            verification_failed = (bool(after_errors) or bool(value_mismatch)) and not failed
            if failed:
                status = "partial_failed"
            elif verification_failed:
                status = "verification_failed"
            elif setter_timeouts:
                status = "updated_with_confirmed_timeouts"
            else:
                status = "updated"
            result.update(
                {
                    "status": status,
                    "after": after,
                    "diff": _diff_properties(result["before"], item["properties"], after),
                    "errors": errors or None,
                    "warnings": warnings,
                }
            )
            if _update_debug_enabled(self):
                result["debug"] = {
                    "cue_ref": item["cue_ref"],
                    "cue_id": result["cue_id"],
                    "requested_properties": item["properties"],
                    "after_values": _after_values_for_requested(after, item["properties"]),
                    "properties_match": confirmed_by_after,
                    "setter_timeouts": setter_timeouts,
                    "confirmed_timeouts": bool(setter_timeouts and confirmed_by_after),
                    "setter_errors": setter_errors,
                    "final_status": status,
                }
            final_results.append(result)
        read_cache.clear()

        if any(result["status"] == "partial_failed" for result in final_results):
            status = "partial_failed"
        elif any(result["status"] == "verification_failed" for result in final_results):
            status = "verification_failed"
        elif any(result["status"] == "updated_with_confirmed_timeouts" for result in final_results):
            status = "updated_with_confirmed_timeouts"
        else:
            status = "updated"
        return _batch_update_result(
            workspace,
            dry_run=False,
            results=final_results,
            status=status,
            requested_count=len(items),
            timeout_confirmed_count=timeout_confirmed_count,
        )


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


def _normalize_batch_update_item(raw_update: Any) -> dict[str, Any]:
    if hasattr(raw_update, "model_dump"):
        raw_update = raw_update.model_dump()
    if not isinstance(raw_update, dict):
        raise UnsafeWriteOperationError("each update must be an object")
    cue = _clean_update_cue_ref(raw_update.get("cue_ref", ""))
    profile = validate_update_profile(raw_update.get("profile") or COMMON_UPDATE_PROFILE)
    properties, operations = normalize_update_request(
        profile,
        raw_update.get("properties"),
        raw_update.get("operations"),
    )
    return {
        "cue_ref": cue,
        "profile": profile,
        "properties": properties,
        "operations": operations,
        "read_keys": read_keys_for_operations(operations),
    }


def _validate_profile_for_before(profile: str, before: dict[str, Any] | None) -> dict[str, str]:
    if before is None:
        return {}
    try:
        validate_update_profile_for_cue(profile, before)
    except Exception as exc:
        return {"profile": str(exc)}
    return {}


def _batch_item_result(
    workspace_id: str,
    item: dict[str, Any],
    *,
    cue_id: str | None,
    status: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    errors: dict[str, str] | None,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "cue_ref": item["cue_ref"],
        "cue_id": cue_id,
        "profile": item["profile"],
        "status": status,
        "properties": item["properties"],
        "operations": item["operations"],
        "before": before,
        "after": after,
        "diff": _diff_properties(before, item["properties"], after),
        "planned_operations": _planned_update_operations(
            workspace_id,
            item["cue_ref"],
            item["operations"],
            resolved_cue_id=cue_id,
        ),
        "executed_operations": [],
        "errors": errors,
        "warnings": warnings,
    }


def _batch_update_result(
    workspace_id: str,
    *,
    dry_run: bool,
    results: list[dict[str, Any]],
    status: str,
    requested_count: int,
    timeout_confirmed_count: int = 0,
    errors: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    fixed_results = results
    failed_count = sum(1 for result in fixed_results if result.get("errors"))
    updated_count = sum(
        1
        for result in fixed_results
        if result.get("status") in {"updated", "updated_with_confirmed_timeouts"}
    )
    planned_count = sum(1 for result in fixed_results if result.get("status") != "preflight_failed")
    ok = failed_count == 0 and status not in {"preflight_failed", "partial_failed", "verification_failed"}
    if status == "dry_run":
        message = "Dry run succeeded; review planned_operations before disabling dry_run."
    elif status == "preflight_failed":
        message = "Batch cue update was blocked during preflight; no mutating OSC commands were sent."
    elif status == "partial_failed":
        message = "Batch cue update partially failed; inspect per-cue results and errors."
    elif status == "verification_failed":
        message = "Batch cue update commands completed, but fresh verification failed."
    elif status == "updated_with_confirmed_timeouts":
        message = "Batch cue update completed; some setters timed out but fresh after-reads confirmed requested values."
    else:
        message = "Batch cue update completed and fresh after-reads confirmed requested values."
    global_warnings = list(warnings or [])
    if status == "updated_with_confirmed_timeouts":
        global_warnings.append("One or more setters did not reply before timeout, but fresh after-reads confirmed the changes.")
    return {
        "ok": ok,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "requested_count": requested_count,
        "planned_count": planned_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "timeout_confirmed_count": timeout_confirmed_count,
        "results": fixed_results,
        "errors": errors,
        "warnings": global_warnings,
        "error_code": None if ok else UPDATE_STATUS_CODES.get(status, f"QLAB_UPDATE_{status.upper()}"),
        "suggested_action": None if ok else UPDATE_STATUS_ACTIONS.get(status, "Inspect per-cue results before retrying."),
        "message": message,
    }


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
    update_operations: list[dict[str, Any]],
    resolved_cue_id: str | None = None,
) -> list[dict[str, Any]]:
    operations = [
        {
            "operation": "read_before",
            "profile": "update_safe",
            "cacheable": False,
        }
    ]
    for update_operation in update_operations:
        address = (
            _cue_id_address(workspace_id, resolved_cue_id, update_operation["path"])
            if resolved_cue_id
            else _cue_address(workspace_id, cue_ref, update_operation["path"])
        )
        planned = {
            "operation": "set_property",
            "property": update_operation["property"],
            "address": address,
            "args": update_operation["args"],
            "mode": update_operation["mode"],
            "risk_tier": update_operation["risk_tier"],
            "real_write_enabled": update_operation["real_write_enabled"],
        }
        if update_operation.get("planned_only_reason"):
            planned["planned_only_reason"] = update_operation["planned_only_reason"]
        operations.append(planned)
    operations.append(
        {
            "operation": "verify",
            "profile": "auto",
            "cacheable": False,
        }
    )
    return operations


def _resolved_cue_id(values: dict[str, Any] | None) -> str | None:
    if not isinstance(values, dict):
        return None
    value = values.get("uniqueID")
    if isinstance(value, str) and value.strip():
        return _clean_cue_ref(value)
    return None


def _try_read_update_values(
    reader: Any,
    workspace_id: str,
    cue_ref: str,
    read_keys: list[str],
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    try:
        values = reader.read_cue_values(
            workspace_id,
            cue_ref,
            read_keys,
            cache_profile="basic_safe",
            cacheable=False,
        )["values"]
        if not isinstance(values, dict):
            raise ValueError("QLab valuesForKeys response must be an object")
        return values, {}
    except Exception as exc:
        return None, {"read_before": str(exc)}


def _try_read_update_values_with_retries(
    reader: Any,
    workspace_id: str,
    cue_ref: str,
    read_keys: list[str],
    requested: dict[str, Any],
    *,
    retry_on_mismatch: bool,
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    after, errors = _try_read_update_values(reader, workspace_id, cue_ref, read_keys)
    if not retry_on_mismatch or _properties_match(after, requested):
        return after, errors
    for delay in AFTER_READ_RETRY_DELAYS:
        time.sleep(delay)
        after, errors = _try_read_update_values(reader, workspace_id, cue_ref, read_keys)
        if _properties_match(after, requested):
            return after, errors
    return after, errors


def _try_workspace_cue_ids(reader: Any, workspace_id: str) -> list[str] | None:
    try:
        reply = reader.client.request(_workspace_address(workspace_id, "cueLists/uniqueIDs"))
        return _normalize_id_list(reply.data)
    except Exception:
        return None


def _resolve_created_cue_after_timeout(reader: Any, workspace_id: str, before_ids: list[str] | None) -> str | None:
    if before_ids is None:
        return None
    after_ids = _try_workspace_cue_ids(reader, workspace_id)
    if after_ids is None:
        return None
    created = [cue_id for cue_id in after_ids if cue_id not in set(before_ids)]
    return created[0] if len(created) == 1 else None


def _properties_match(values: Any, requested: dict[str, Any]) -> bool:
    if not isinstance(values, dict):
        return False
    return all(_property_values_match(key, values.get(key), value) for key, value in requested.items())


def _verification_mismatch_message(values: Any, requested: dict[str, Any]) -> str:
    if not isinstance(values, dict):
        return "Fresh after-read did not return cue values for verification."
    mismatches = [
        {"key": key, "requested": requested_value, "after": values.get(key)}
        for key, requested_value in requested.items()
        if not _property_values_match(key, values.get(key), requested_value)
    ]
    return f"Fresh after-read did not confirm requested values: {mismatches}"


def _property_values_match(key: str, actual: Any, requested: Any) -> bool:
    actual_value = _comparison_value(key, actual)
    requested_value = _comparison_value(key, requested)
    if _is_plain_number(actual_value) and _is_plain_number(requested_value):
        return float(actual_value) == float(requested_value)
    return actual_value == requested_value


def _comparison_value(key: str, value: Any) -> Any:
    if key == "continueMode":
        return _continue_mode_comparison_value(value)
    if key in CASEFOLD_COMPARISON_KEYS and isinstance(value, str):
        return value.strip().casefold()
    return value


def _continue_mode_comparison_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().casefold().replace(" ", "_")
        return CONTINUE_MODE_VALUES.get(normalized, value)
    return CONTINUE_MODE_VALUES.get(value, value)


def _is_plain_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _after_values_for_requested(values: Any, requested: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(values, dict):
        return None
    return {key: values.get(key) for key in requested}


def _update_debug_enabled(reader: Any) -> bool:
    config = getattr(getattr(reader, "client", None), "config", None)
    if config is not None and hasattr(config, "update_debug"):
        return bool(getattr(config, "update_debug"))
    return os.getenv("QLAB_UPDATE_DEBUG", "").strip().casefold() in {"1", "true", "yes", "on"}


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
