"""Gated mutating OSC operations for QLab write mode."""

from __future__ import annotations

import hashlib
import math
import secrets
import threading
import time
from typing import Any
from uuid import UUID

from ..errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from ..cues.refs import CONTAINER_CUE_TYPES
from ..osc.addressing import _clean_workspace_id, _workspace_address
from ..runtime.read_cache import shared_read_cache
from .allowlist import validate_writable_cue_type, writable_cue_type_label
from .comparison import is_plain_finite_number as _is_plain_finite_number
from .safety import check_write_readiness, ensure_write_ready, resolve_dry_run
from .tokens import decode_confirm_token, encode_confirm_token
from .moves import (
    _activity_snapshot as _structural_activity_snapshot,
    _fingerprint as _structural_fingerprint,
    _read_snapshot as _read_structural_snapshot,
    _qlab_bool,
    _uuid_key,
    move_cues as _move_cues,
    move_cue_lists as _move_cue_lists,
)
from .deletes import delete_cues as _delete_cues
from .cue_lists import create_cue_lists as _create_cue_lists, edit_cue_lists as _edit_cue_lists

CREATE_TOKEN_VERSION = 2
CREATE_TOKEN_TTL_SECONDS = 300
_CREATE_TOKEN_SECRET = secrets.token_bytes(32)
_CONSUMED_CREATE_TOKENS: dict[str, int] = {}
_CONSUMED_CREATE_TOKENS_LOCK = threading.Lock()
CREATE_CUES_TOKEN_VERSION = 2
CREATE_CUES_TOKEN_TTL_SECONDS = 300
CREATE_CUES_SOFT_BUDGET_SECONDS = 270.0


VIDEO_PHASE9D_AUDIO_MUTE_SOLO_PROPERTIES = frozenset({"mute/channel", "solo/channel"})
VIDEO_PHASE9E_AUDIO_LEVEL_BULK_PROPERTIES = frozenset({"mute/channel/clear", "solo/channel/clear"})
SLICE_MARKER_MIN_SPACING_SECONDS = 0.05


class QLabWriteMixin:
    def create_cue_lists(
        self, workspace_id: str, container_types: list[str],
        dry_run: bool | None = None, confirm_token: str | None = None,
    ) -> dict[str, Any]:
        return _create_cue_lists(
            self, workspace_id, container_types, dry_run=dry_run, confirm_token=confirm_token,
        )

    def edit_cue_lists(
        self, workspace_id: str, updates: list[dict[str, Any]], dry_run: bool | None = None,
    ) -> dict[str, Any]:
        return _edit_cue_lists(self, workspace_id, updates, dry_run=dry_run)

    def move_cue_lists(
        self, workspace_id: str, moves: list[dict[str, Any]],
        dry_run: bool | None = None, confirm_token: str | None = None,
    ) -> dict[str, Any]:
        return _move_cue_lists(self, workspace_id, moves, dry_run=dry_run, confirm_token=confirm_token)

    def check_write_readiness(self, workspace_id: str) -> dict[str, Any]:
        return check_write_readiness(self, workspace_id)

    def move_cues(
        self,
        workspace_id: str,
        moves: list[dict[str, Any]],
        dry_run: bool | None = None,
        confirm_token: str | None = None,
    ) -> dict[str, Any]:
        return _move_cues(self, workspace_id, moves, dry_run=dry_run, confirm_token=confirm_token)

    def delete_cues(
        self,
        workspace_id: str,
        cue_ids: list[str] | None = None,
        dry_run: bool | None = None,
        confirm_token: str | None = None,
        container_id: str | None = None,
        recursive: bool = False,
        delete_container: bool = False,
    ) -> dict[str, Any]:
        return _delete_cues(
            self,
            workspace_id,
            cue_ids,
            dry_run=dry_run,
            confirm_token=confirm_token,
            container_id=container_id,
            recursive=recursive,
            delete_container=delete_container,
        )

    def create_cue(
        self,
        workspace_id: str,
        cue_type: str,
        dry_run: bool | None = None,
        after_cue_id: str | None = None,
        confirm_token: str | None = None,
        parent_container_id: str | None = None,
    ) -> dict[str, Any]:
        workspace = _clean_workspace_id(workspace_id)
        effective_dry_run = resolve_dry_run(self, dry_run)
        osc_cue_type = validate_writable_cue_type(cue_type)
        # Keep the historical QLab display spelling in results.
        qlab_cue_type = writable_cue_type_label(cue_type)
        normalized_properties: dict[str, Any] = {}

        if effective_dry_run:
            try:
                workspace = _resolve_create_workspace(self, workspace, dry_run=True)
            except Exception as exc:
                return {
                    "ok": False,
                    "status": getattr(exc, "status", "workspace_not_found"),
                    "workspace_id": _clean_workspace_id(workspace_id),
                    "cue_type": qlab_cue_type,
                    "dry_run": True,
                    "created_cue_id": None,
                    "confirm_token": None,
                    "placement": None,
                    "properties": normalized_properties,
                    "planned_operations": [],
                    "executed_operations": [],
                    "verification": None,
                    "cleanup_required": False,
                    "cleanup": None,
                    "errors": {"workspace_resolution": str(exc)},
                    "warnings": ["Requested workspace could not be resolved."],
                    "error_code": getattr(exc, "status", "workspace_not_found"),
                    "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                    "message": "Requested workspace could not be resolved; no cue create operation was planned or sent.",
                }
            placement_mode, placement_target = _normalize_create_placement(
                after_cue_id,
                parent_container_id,
            )
            prepared = _prepare_create_request(
                self,
                workspace,
                osc_cue_type=osc_cue_type,
                qlab_cue_type=qlab_cue_type,
                placement_mode=placement_mode,
                placement_target=placement_target,
            )
            snapshot = prepared["snapshot"]
            activity = prepared["activity"]
            placement = prepared["placement"]
            preflight_error = prepared["preflight_error"]
            planned_operations = prepared["planned_operations"]
            if preflight_error:
                return _create_failure(
                    workspace,
                    qlab_cue_type,
                    normalized_properties,
                    dry_run=True,
                    placement=placement,
                    planned_operations=planned_operations,
                    error_code="preflight_failed",
                    errors={"preflight": preflight_error},
                    message="Create dry-run preflight failed; no mutating OSC commands were planned or sent.",
                )
            binding = _create_token_binding(workspace, qlab_cue_type, placement, snapshot, activity)
            token = _encode_create_token(binding)
            warnings = ["Dry run only: no mutating OSC commands were sent to QLab."]
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace,
                "cue_type": qlab_cue_type,
                "dry_run": True,
                "created_cue_id": None,
                "confirm_token": token,
                "placement": placement,
                "properties": normalized_properties,
                "planned_operations": planned_operations,
                "executed_operations": [],
                "verification": None,
                "warnings": warnings,
                "message": "Dry run succeeded; review planned_operations before disabling dry_run.",
            }

        try:
            workspace = _resolve_create_workspace(self, workspace, dry_run=False)
            placement_mode, placement_target = _normalize_create_placement(
                after_cue_id,
                parent_container_id,
            )
            prepared = _prepare_create_request(
                self,
                workspace,
                osc_cue_type=osc_cue_type,
                qlab_cue_type=qlab_cue_type,
                placement_mode=placement_mode,
                placement_target=placement_target,
            )
        except Exception as exc:
            return _create_failure(
                workspace, qlab_cue_type, normalized_properties, dry_run=False,
                placement=None, planned_operations=[], error_code="preflight_failed",
                errors={"preflight": str(exc)}, message="Create failed before mutating OSC commands.",
            )
        snapshot = prepared["snapshot"]
        activity = prepared["activity"]
        placement = prepared["placement"]
        preflight_error = prepared["preflight_error"]
        planned_operations = prepared["planned_operations"]
        if preflight_error:
            return _create_failure(
                workspace,
                qlab_cue_type,
                normalized_properties,
                dry_run=False,
                placement=placement,
                planned_operations=planned_operations,
                error_code="preflight_failed",
                errors={"preflight": preflight_error},
                message="Create preflight failed; no mutating OSC commands were sent.",
            )
        payload, token_error = _decode_create_token(confirm_token)
        if token_error or payload is None:
            return _create_failure(
                workspace,
                qlab_cue_type,
                normalized_properties,
                dry_run=False,
                placement=placement,
                planned_operations=planned_operations,
                error_code="preflight_failed",
                errors={"confirm_token": token_error or "create confirmation token is invalid."},
                message="Create real execution was rejected before any mutating OSC command.",
            )
        if _create_token_is_consumed(confirm_token):
            return _create_failure(
                workspace,
                qlab_cue_type,
                normalized_properties,
                dry_run=False,
                placement=placement,
                planned_operations=planned_operations,
                error_code="preflight_failed",
                errors={"confirm_token": "confirmation_already_consumed: create confirm_token has already been used."},
                message="Create real execution was rejected before any mutating OSC command.",
            )
        binding = _create_token_binding(
            workspace,
            qlab_cue_type,
            placement,
            snapshot,
            activity,
        )
        if payload.get("binding") != binding:
            return _create_failure(
                workspace,
                qlab_cue_type,
                normalized_properties,
                dry_run=False,
                placement=placement,
                planned_operations=planned_operations,
                error_code="preflight_failed",
                errors={"confirm_token": "create confirmation token does not match the fresh workspace structure."},
                message="Create real execution was rejected before any mutating OSC command.",
            )
        token_error = _consume_create_token(confirm_token, payload)
        if token_error:
            return _create_failure(
                workspace,
                qlab_cue_type,
                normalized_properties,
                dry_run=False,
                placement=placement,
                planned_operations=planned_operations,
                error_code="preflight_failed",
                errors={"confirm_token": token_error},
                message="Create real execution was rejected before any mutating OSC command.",
            )

        read_cache = getattr(self, "_read_cache", shared_read_cache())
        read_cache.clear()

        executed_operations: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: dict[str, str] = {}
        new_address = _workspace_address(workspace, "new")

        if placement["mode"] == "empty_cue_list":
            parent_osc_id = placement.get("parent_osc_id") or placement["parent_id"]
            current_list_address = _workspace_address(
                workspace,
                f"currentCueListID/{parent_osc_id}",
            )
            setter_timed_out = False
            setter_timeout_error: str | None = None
            executed_operations.append({"operation": "set_current_cue_list", "address": current_list_address, "args": [], "status": "attempted"})
            try:
                current_reply = getattr(self, "_request", self.client.request)(current_list_address)
            except OscTimeoutError as exc:
                executed_operations[-1]["status"] = "indeterminate"
                setter_timed_out = True
                setter_timeout_error = str(exc)
            except Exception as exc:
                executed_operations[-1]["status"] = "failed"
                errors["current_cue_list"] = str(exc)
                return _create_failure(
                    workspace,
                    qlab_cue_type,
                    normalized_properties,
                    dry_run=False,
                    placement=placement,
                    planned_operations=planned_operations,
                    executed_operations=executed_operations,
                    error_code="current_cue_list_failed",
                    errors=errors,
                    warnings=warnings,
                    message="Create was stopped because the target Cue List could not be selected and verified.",
                )
            else:
                executed_operations[-1].update(
                    {
                        "operation": "set_current_cue_list",
                        "address": current_list_address,
                        "args": [],
                        "status": current_reply.status,
                        "cue_list_id": placement["parent_id"],
                    }
                )
            try:
                current_id = _read_current_cue_list_id(self, workspace)
            except Exception as exc:
                errors["current_cue_list"] = (
                    f"{setter_timeout_error}; fresh readback failed: {exc}"
                    if setter_timed_out
                    else str(exc)
                )
                if setter_timed_out:
                    warnings.append("current_cue_list_may_have_changed")
                return _create_failure(
                    workspace,
                    qlab_cue_type,
                    normalized_properties,
                    dry_run=False,
                    placement=placement,
                    planned_operations=planned_operations,
                    executed_operations=executed_operations,
                    error_code="current_cue_list_failed",
                    errors=errors,
                    warnings=warnings,
                    message="Create was stopped because the target Cue List could not be selected and verified.",
                )
            if current_id != placement["parent_id"]:
                errors["current_cue_list"] = (
                    f"{setter_timeout_error}; fresh readback returned {current_id!r}, "
                    f"expected {placement['parent_id']!r}."
                    if setter_timed_out
                    else "QLab did not confirm the requested current Cue List."
                )
                if setter_timed_out:
                    warnings.append("current_cue_list_may_have_changed")
                return _create_failure(
                    workspace,
                    qlab_cue_type,
                    normalized_properties,
                    dry_run=False,
                    placement=placement,
                    planned_operations=planned_operations,
                    executed_operations=executed_operations,
                    error_code="current_cue_list_failed",
                    errors=errors,
                    warnings=warnings,
                    message="Create was stopped because the target Cue List could not be selected and verified.",
                )
            if setter_timed_out:
                warnings.append("setter_timeout_but_readback_matched")
            executed_operations.append(
                {
                    "operation": "verify_current_cue_list",
                    "address": _workspace_address(workspace, "currentCueListID"),
                    "args": [],
                    "status": "ok",
                    "cue_list_id": current_id,
                }
            )

        new_args = [osc_cue_type, *placement.get("new_args", [])]
        try:
            if callable(getattr(self, "_remaining_read_deadline", None)):
                self._remaining_read_deadline()
        except OscTimeoutError as exc:
            return _create_failure(workspace, qlab_cue_type, normalized_properties, dry_run=False,
                placement=placement, planned_operations=planned_operations, executed_operations=executed_operations,
                error_code="preflight_failed", errors={"budget": str(exc)}, message="Create budget exhausted before /new; no new cue command was sent.")
        new_operation = {"operation": "new", "address": new_address, "args": new_args, "status": "attempted", "created_cue_id": None}
        executed_operations.append(new_operation)
        try:
            new_reply = getattr(self, "_request", self.client.request)(new_address, *new_args)
            created_cue_id = _extract_created_cue_id(new_reply.data)
            new_status = new_reply.status
        except Exception as exc:
            candidate_cue_ids = []
            timeout_indeterminate = isinstance(exc, OscTimeoutError)
            new_operation["status"] = "error" if isinstance(exc, QLabReplyError) else "indeterminate"
            if isinstance(exc, QLabReplyError):
                return _create_failure(
                    workspace,
                    qlab_cue_type,
                    normalized_properties,
                    dry_run=False,
                    placement=placement,
                    planned_operations=planned_operations,
                    executed_operations=executed_operations,
                    error_code="create_new_failed",
                    errors={"new": str(exc)},
                    message="QLab rejected the container-specific /new command; no retry was sent.",
                )
            warnings.append(
                "QLab did not reply to /new; creation identity is indeterminate and no setter or retry was sent."
                if timeout_indeterminate
                else "QLab returned an invalid /new identity; no setter or retry was sent."
            )
            return {
                "ok": False,
                "status": "verification_failed",
                "workspace_id": workspace,
                "cue_type": qlab_cue_type,
                "dry_run": False,
                "created_cue_id": None,
                "confirm_token": None,
                "placement": placement,
                "properties": normalized_properties,
                "planned_operations": planned_operations,
                "executed_operations": executed_operations,
                "verification": None,
                "cleanup_required": True,
                "cleanup": {
                    "status": "manual_review_required",
                    "candidate_cue_ids": candidate_cue_ids or [],
                    "reason": str(exc),
                },
                "errors": {"new": str(exc)},
                "warnings": warnings,
                "error_code": "create_identity_indeterminate" if timeout_indeterminate else "create_identity_invalid",
                "suggested_action": "Inspect the workspace, then use a fresh dry-run/token before any cleanup or retry.",
                "message": "QLab may have created a cue, but its identity could not be proven safely.",
            }
        new_operation.update(status=new_status, created_cue_id=created_cue_id)

        if placement["mode"] == "empty_group":
            move_address = _workspace_address(workspace, f"move/{created_cue_id}")
            move_args = [
                placement["expected_index"],
                placement.get("parent_osc_id") or placement["parent_id"],
            ]
            move_operation = {"operation": "move_into_container", "address": move_address, "args": move_args, "status": "attempted", "created_cue_id": created_cue_id}
            executed_operations.append(move_operation)
            try:
                move_reply = getattr(self, "_request", self.client.request)(move_address, *move_args)
                move_operation.update(
                    {
                        "operation": "move_into_container",
                        "address": move_address,
                        "args": move_args,
                        "status": move_reply.status,
                        "created_cue_id": created_cue_id,
                        "parent_id": placement["parent_id"],
                    }
                )
            except Exception as exc:
                move_operation["status"] = "indeterminate" if isinstance(exc, OscTimeoutError) else "failed"
                return {
                    "ok": False,
                    "status": "verification_failed",
                    "workspace_id": workspace,
                    "cue_type": qlab_cue_type,
                    "dry_run": False,
                    "created_cue_id": created_cue_id,
                    "confirm_token": None,
                    "placement": placement,
                    "properties": normalized_properties,
                    "planned_operations": planned_operations,
                    "executed_operations": executed_operations,
                    "verification": None,
                    "cleanup_required": True,
                    "cleanup": {
                        "status": "manual_review_required",
                        "created_cue_id": created_cue_id,
                        "reason": str(exc),
                    },
                    "errors": {"move": str(exc)},
                    "warnings": [
                        "QLab may have created the cue, but the Group move did not complete safely; no move retry was sent."
                    ],
                    "error_code": "create_move_indeterminate" if isinstance(exc, OscTimeoutError) else "create_move_failed",
                    "suggested_action": "Inspect the workspace, then use a fresh dry-run/token before any cleanup or retry.",
                    "message": "Cue identity was known, but its move into the Group could not be proven safely.",
                }

        verification: dict[str, Any] | None = None
        verified = True
        try:
            read_cache.clear()
            verification = self.get_cue_details(
                workspace,
                created_cue_id,
                "auto",
            )
            read_cache.clear()
            verification_properties = verification.get("properties") if isinstance(verification, dict) else {}
            identity_matches = _created_cue_identity_matches(verification_properties, created_cue_id, qlab_cue_type)
            health = _read_create_health(verification_properties)
            verified = identity_matches and not health["active"]
            if not identity_matches:
                errors["verification"] = "Fresh readback did not identify the created cue and type."
            elif health["active"]:
                errors["verification"] = "Fresh readback found the created cue active; its result is ambiguous."
            if health["status"] == "broken":
                warnings.append("Cue was created and verified structurally, but QLab reports it broken.")
            elif health["status"] == "warning":
                warnings.append("Cue was created and verified structurally, but QLab reports a warning.")
            elif health["status"] == "unknown":
                warnings.append("Cue was created structurally, but QLab health flags were unavailable.")
            if placement["mode"] == "empty_cart" and not _cart_position_matches(
                verification_properties,
                placement.get("cart_readback_row", placement["cart_row"]),
                placement.get("cart_readback_column", placement["cart_column"]),
            ):
                errors["placement"] = "Fresh readback did not confirm the requested Cue Cart row and column."
        except Exception as exc:
            errors["verification"] = str(exc)
            verification = None
            verified = False
        structure = _verify_created_structure(self, workspace, created_cue_id, placement, snapshot)
        verification = _merge_create_verification(verification, structure)
        if verification is not None:
            verification["health"] = _read_create_health(verification.get("properties"))
        if structure.get("error"):
            errors.setdefault("placement", str(structure["error"]))
        verified = verified and bool(structure.get("ok"))
        if errors or not verified:
            status = "verification_failed"
            ok = False
            message = "Cue create command was sent, but fresh verification did not confirm the created cue."
            cleanup_required = True
            cleanup = {
                "status": "manual_review_required",
                "created_cue_id": created_cue_id,
                "reason": "Creation completed but fresh identity, inactive state, or structure verification failed.",
            }
        else:
            status = "created"
            ok = True
            message = "Cue created from QLab template/defaults and verified fresh."
            cleanup_required = False
            cleanup = None

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
            "confirm_token": None,
            "cleanup_required": cleanup_required,
            "cleanup": cleanup,
            "errors": errors or None,
            "warnings": warnings,
            "message": message,
        }

    def create_cues(
        self,
        workspace_id: str,
        cue_types: list[str],
        dry_run: bool | None = None,
        cue_list_id: str | None = None,
        group_id: str | None = None,
        cue_cart_id: str | None = None,
        after_cue_id: str | None = None,
        confirm_token: str | None = None,
    ) -> dict[str, Any]:
        """Create an ordered sequence, chaining each verified UUID to the next cue."""
        if not isinstance(cue_types, list) or not cue_types or len(cue_types) > 100:
            raise UnsafeWriteOperationError("cue_types must contain between 1 and 100 cue types.")
        wire_types: list[str] = []
        labels: list[str] = []
        for cue_type in cue_types:
            wire_types.append(validate_writable_cue_type(cue_type))
            labels.append(writable_cue_type_label(cue_type))
        workspace = _clean_workspace_id(workspace_id)
        effective_dry_run = resolve_dry_run(self, dry_run)
        deadline = time.monotonic() + CREATE_CUES_SOFT_BUDGET_SECONDS
        if not effective_dry_run and callable(getattr(self, "set_read_deadline", None)):
            self.set_read_deadline(CREATE_CUES_SOFT_BUDGET_SECONDS)
        destination = _normalize_create_destination(
            cue_list_id, group_id, cue_cart_id, after_cue_id, labels
        )
        placement_mode, placement_target = "destination", destination

        try:
            if effective_dry_run:
                workspace = _resolve_create_workspace(self, workspace, dry_run=True)
            else:
                workspace = _resolve_create_workspace(self, workspace, dry_run=False)
            prepared = _prepare_create_request(
                self,
                workspace,
                osc_cue_type=wire_types[0],
                qlab_cue_type=labels[0],
                placement_mode=placement_mode,
                placement_target=placement_target,
            )
        except Exception as exc:
            return _create_cues_failure(
                workspace, labels, effective_dry_run, {},
                {"preflight": str(exc)}, "preflight_failed",
                destination=destination,
            )
        snapshot = prepared["snapshot"]
        activity = prepared["activity"]
        placement = prepared["placement"]
        preflight_error = prepared["preflight_error"]
        if preflight_error or snapshot is None or placement is None:
            return _create_cues_failure(
                workspace, labels, effective_dry_run, placement or {},
                {"preflight": preflight_error or "Create batch preflight failed."}, "preflight_failed",
                destination=destination,
            )
        if placement.get("mode") == "empty_cart" and len(labels) > 1:
            return _create_cues_failure(
                workspace,
                labels,
                effective_dry_run,
                placement,
                {"placement": "A Cue Cart has no linear order; create one cue per Cart cell."},
                "preflight_failed",
                destination=destination,
            )

        binding = _create_cues_token_binding(workspace, wire_types, labels, destination, placement, snapshot, activity)
        planned_operations = _planned_create_cues_operations(workspace, wire_types, placement)
        if effective_dry_run:
            token = _encode_create_cues_token(binding)
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace,
                "dry_run": True,
                "requested_count": len(labels),
                "planned_count": len(planned_operations),
                "created_count": 0,
                "pending_indices": list(range(len(labels))),
                "uncertain_indices": [],
                "batch_verified": False,
                "destination": _create_cues_destination_result(destination, placement),
                "results": [
                    _create_cues_item_result(index, label, {"status": "planned"})
                    for index, label in enumerate(labels)
                ],
                "planned_operations": planned_operations,
                "executed_operations": [],
                "confirm_token": token,
                "error_code": None,
                "suggested_action": None,
                "warnings": ["Dry run only: no mutating OSC commands were sent to QLab."],
                "message": (
                    "Create sequence dry-run succeeded; planned_count counts generated plan operations "
                    "(including verification steps), while requested_count counts logical cues. "
                    "Review planned_operations before execution."
                ),
            }

        payload, token_error = _decode_create_cues_token(confirm_token)
        if token_error or payload is None:
            return _create_cues_failure(
                workspace, labels, False, placement,
                {"confirm_token": token_error or "Invalid confirmation token."},
                "preflight_failed", planned_operations, destination=destination,
            )
        if _create_token_is_consumed(confirm_token):
            return _create_cues_failure(
                workspace, labels, False, placement,
                {"confirm_token": "confirmation_already_consumed: create sequence token has already been used."},
                "preflight_failed", planned_operations, destination=destination,
            )
        try:
            fresh_prepared = _prepare_create_request(
                self,
                workspace,
                osc_cue_type=wire_types[0],
                qlab_cue_type=labels[0],
                placement_mode=placement_mode,
                placement_target=placement_target,
            )
        except Exception as exc:
            return _create_cues_failure(workspace, labels, False, placement, {"preflight": str(exc)}, "preflight_failed", planned_operations, destination=destination)
        fresh_snapshot = fresh_prepared["snapshot"]
        fresh_activity = fresh_prepared["activity"]
        fresh_placement = fresh_prepared["placement"]
        fresh_error = fresh_prepared["preflight_error"]
        if fresh_error or fresh_snapshot is None or fresh_placement is None:
            return _create_cues_failure(
                workspace, labels, False, placement,
                {"preflight": fresh_error or "Fresh create sequence preflight failed."},
                "preflight_failed", planned_operations, destination=destination,
            )
        fresh_binding = _create_cues_token_binding(
            workspace, wire_types, labels, destination, fresh_placement, fresh_snapshot, fresh_activity
        )
        if payload.get("binding") != fresh_binding:
            return _create_cues_failure(
                workspace, labels, False, fresh_placement,
                {"confirm_token": "Create sequence token does not match the fresh workspace structure."},
                "preflight_failed", planned_operations, destination=destination,
            )
        token_error = _consume_create_token(confirm_token, payload)
        if token_error:
            return _create_cues_failure(
                workspace, labels, False, fresh_placement,
                {"confirm_token": token_error}, "preflight_failed", planned_operations,
                destination=destination,
            )

        results: list[dict[str, Any]] = []
        executed_operations: list[dict[str, Any]] = []
        previous_id: str | None = None
        for index, (wire_type, label) in enumerate(zip(wire_types, labels)):
            if time.monotonic() >= deadline:
                return _create_cues_partial_result(workspace, labels, destination, placement, results, planned_operations, executed_operations, {"status": "preflight_failed", "error_code": "create_budget_exhausted", "errors": {"budget": "Create execution budget exhausted; no further /new was sent."}})
            item_after = previous_id if previous_id is not None else placement.get("after_cue_id")
            item_parent = placement["parent_id"] if index == 0 and not item_after else None
            executing = False
            try:
                item_plan = self.create_cue(workspace, wire_type, dry_run=True, after_cue_id=item_after, parent_container_id=item_parent)
                if not item_plan.get("ok"):
                    item_result = {**item_plan, "status": "preflight_failed"}
                elif time.monotonic() >= deadline:
                    return _create_cues_partial_result(workspace, labels, destination, placement, results, planned_operations, executed_operations, {"status": "preflight_failed", "error_code": "create_budget_exhausted", "errors": {"budget": "Create execution budget exhausted before /new."}})
                else:
                    executing = True
                    item_result = self.create_cue(workspace, wire_type, dry_run=False, after_cue_id=item_after, parent_container_id=item_parent, confirm_token=item_plan.get("confirm_token"))
            except Exception as exc:
                item_result = {"ok": False, "status": "verification_failed" if executing else "preflight_failed", "cleanup_required": executing, "errors": {"exception": str(exc)}, "message": "Create stopped after an unexpected error; inspect before retrying."}
            results.append(_create_cues_item_result(index, label, item_result))
            executed_operations.extend(item_result.get("executed_operations") or [])
            if not item_result.get("ok") or not item_result.get("created_cue_id"):
                return _create_cues_partial_result(workspace, labels, destination, placement, results, planned_operations, executed_operations, item_result)
            previous_id = item_result["created_cue_id"]
        try:
            _verify_created_batch(self, workspace, fresh_snapshot, fresh_placement, results)
        except Exception as exc:
            return _create_cues_partial_result(workspace, labels, destination, placement, results, planned_operations, executed_operations, {"status": "verification_failed", "error_code": "create_final_verification_failed", "errors": {"final_verification": str(exc)}})
        return {
            "ok": True,
            "status": "created",
            "workspace_id": workspace,
            "dry_run": False,
            "requested_count": len(labels),
            "planned_count": len(planned_operations),
            "created_count": len(results),
            "pending_indices": [],
            "uncertain_indices": [],
            "batch_verified": True,
            "destination": _create_cues_destination_result(destination, placement),
            "results": results,
            "planned_operations": planned_operations,
            "executed_operations": executed_operations,
            "confirm_token": None,
            "error_code": None,
            "suggested_action": None,
            "warnings": ["Sequence creation is sequential and has no automatic rollback."],
            "message": (
                "Cue sequence created; planned_count counts generated plan operations, "
                "created_count counts logical cues, and each item was verified before the next /new."
            ),
        }


def _normalize_create_uuid(value: str | None, field: str) -> str:
    try:
        return _uuid_key(value, field)
    except (TypeError, ValueError) as exc:
        raise UnsafeWriteOperationError(f"{field} must be an exact cue UUID.") from exc


def _normalize_create_placement(
    after_cue_id: str | None,
    parent_container_id: str | None,
) -> tuple[str, str]:
    has_anchor = isinstance(after_cue_id, str) and bool(after_cue_id.strip())
    has_container = isinstance(parent_container_id, str) and bool(parent_container_id.strip())
    if has_anchor == has_container:
        raise UnsafeWriteOperationError(
            "Create requires exactly one of after_cue_id or parent_container_id."
        )
    if has_anchor:
        return "anchored", _normalize_create_uuid(after_cue_id, "after_cue_id")
    return "empty_container", _normalize_create_uuid(parent_container_id, "parent_container_id")


def _normalize_create_destination(
    cue_list_id: str | None,
    group_id: str | None,
    cue_cart_id: str | None,
    after_cue_id: str | None,
    cue_types: list[str],
) -> dict[str, Any]:
    selectors = [(kind, field, value) for kind, field, value in (
        ("cue_list", "cue_list_id", cue_list_id),
        ("group", "group_id", group_id),
        ("cue_cart", "cue_cart_id", cue_cart_id),
    ) if value is not None]
    if len(selectors) != 1:
        raise UnsafeWriteOperationError("Create requires exactly one of cue_list_id, group_id, or cue_cart_id.")
    kind, field, value = selectors[0]
    destination_id = _normalize_create_uuid(value, field)
    anchor_id = _normalize_create_uuid(after_cue_id, "after_cue_id") if after_cue_id is not None else None
    if kind == "cue_cart":
        if anchor_id is not None or len(cue_types) != 1 or cue_types[0].casefold() == "group":
            raise UnsafeWriteOperationError("Cue Cart creation requires one non-Group cue and no after_cue_id.")
    return {"kind": kind, "id": destination_id, "after_cue_id": anchor_id}


def _create_tree_fingerprint(snapshot: dict[str, Any]) -> str:
    tree = snapshot.get("children_by_parent")
    if not isinstance(tree, dict):
        raise UnsafeWriteOperationError("Create structural snapshot is incomplete.")
    return _structural_fingerprint(
        [f"{parent}:{','.join(children)}" for parent, children in sorted(tree.items())]
    )


def _prepare_create_request(
    reader: Any,
    workspace_id: str,
    *,
    osc_cue_type: str,
    qlab_cue_type: str,
    placement_mode: str,
    placement_target: str | dict[str, Any],
) -> dict[str, Any]:
    snapshot, activity, placement, preflight_error = _create_preflight(
        reader,
        workspace_id,
        placement_mode,
        placement_target,
    )
    placement_error = _validate_create_placement_type(qlab_cue_type, placement)
    if placement_error and not preflight_error:
        preflight_error = placement_error
    planned_operations = (
        _planned_create_operations(workspace_id, osc_cue_type, placement)
        if placement is not None and preflight_error is None
        else []
    )
    return {
        "snapshot": snapshot,
        "activity": activity,
        "placement": placement,
        "preflight_error": preflight_error,
        "planned_operations": planned_operations,
    }


def _resolve_create_workspace(reader: Any, workspace_id: str, *, dry_run: bool) -> str:
    return (
        reader._resolve_workspace_id_strict(workspace_id)
        if dry_run
        else ensure_write_ready(reader, workspace_id)
    )


def _create_preflight(
    reader: Any,
    workspace_id: str,
    placement_mode: str,
    placement_target: str | dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any] | None, str | None]:
    try:
        snapshot = _read_structural_snapshot(reader, workspace_id)
        activity = _structural_activity_snapshot(reader, workspace_id)
    except Exception as exc:
        return None, {}, None, str(exc)
    if activity.get("active_count"):
        return snapshot, activity, None, "Workspace activity is not safely idle; create requires 0 running/paused cues."
    nodes = snapshot.get("nodes") or {}
    requested_destination: dict[str, Any] | None = None
    if placement_mode == "destination":
        requested_destination = placement_target
        destination_id = placement_target["id"]
        kind = placement_target["kind"]
        destination = nodes.get(destination_id)
        expected_types = {"cue_list": {"Cue List"}, "group": {"Group"}, "cue_cart": {"Cue Cart", "Cart"}}[kind]
        if not isinstance(destination, dict) or destination.get("type") not in expected_types:
            return snapshot, activity, None, f"{kind} does not identify the requested container type in this workspace."
        children = list(snapshot.get("children_by_parent", {}).get(destination_id, []))
        requested_anchor = placement_target.get("after_cue_id")
        if requested_anchor and requested_anchor not in children:
            return snapshot, activity, None, "after_cue_id must be a direct child of the selected destination."
        if kind == "cue_cart" and requested_anchor:
            return snapshot, activity, None, "after_cue_id is not supported for a Cue Cart."
        if requested_anchor or (kind != "cue_cart" and children):
            placement_mode = "anchored"
            placement_target = requested_anchor or children[-1]
        else:
            placement_mode = "empty_container"
            placement_target = destination_id
    if placement_mode == "anchored":
        anchor_id = placement_target
        anchor = nodes.get(anchor_id)
        if not isinstance(anchor, dict):
            return snapshot, activity, None, "after_cue_id does not resolve in the workspace."
        if _create_cue_is_active(anchor):
            return snapshot, activity, None, "after_cue_id must identify an inactive cue."
        parent_id = snapshot.get("parent_by_child", {}).get(anchor_id)
        if not parent_id:
            return snapshot, activity, None, "after_cue_id must identify a cue inside a Cue List or Group."
        parent = nodes.get(parent_id) or {}
        if parent.get("type") not in {"Cue List", "Group"}:
            return snapshot, activity, None, "after_cue_id must be inside a linear Cue List or Group."
        if _create_cue_is_active(parent):
            return snapshot, activity, None, "The anchor's parent container must be inactive."
        children = list(snapshot.get("children_by_parent", {}).get(parent_id, []))
        try:
            anchor_index = children.index(anchor_id)
        except ValueError:
            return snapshot, activity, None, "Structural snapshot does not contain the requested anchor order."
        placement = {
            "mode": "anchored",
            "after_cue_id": anchor_id,
            "anchor_osc_id": anchor.get("uniqueID", anchor_id),
            "new_args": [anchor.get("uniqueID", anchor_id)],
            "parent_id": parent_id,
            "parent_type": parent.get("type"),
            "anchor_index": anchor_index,
            "expected_index": anchor_index + 1,
            "parent_children": children,
            "parent_fingerprint": _structural_fingerprint(children),
            "tree_fingerprint": _create_tree_fingerprint(snapshot),
            "status": "anchored",
        }
        if requested_destination is not None:
            placement["destination"] = requested_destination
        return snapshot, activity, placement, None

    container_id = placement_target
    container = nodes.get(container_id)
    if not isinstance(container, dict):
        return snapshot, activity, None, "parent_container_id does not resolve in the workspace."
    container_type = container.get("type")
    if container_type not in CONTAINER_CUE_TYPES:
        return snapshot, activity, None, "parent_container_id must identify a Cue List, Group, or Cue Cart."
    if _create_cue_is_active(container):
        return snapshot, activity, None, "parent_container_id must identify an inactive container."
    children = list(snapshot.get("children_by_parent", {}).get(container_id, []))
    if children:
        return snapshot, activity, None, "parent_container_id must identify an empty container."

    source_cue_list_id = _containing_cue_list_id(snapshot, container_id)
    source_cue_list = nodes.get(source_cue_list_id) if source_cue_list_id else None
    if isinstance(source_cue_list, dict) and _create_cue_is_active(source_cue_list):
        return snapshot, activity, None, "The containing Cue List must be inactive."
    if container_type == "Cue List":
        try:
            current_cue_list_id = _read_current_cue_list_id(reader, workspace_id)
        except Exception as exc:
            return snapshot, activity, None, str(exc)
        mode = "empty_cue_list"
        new_args: list[Any] = []
    elif container_type == "Group":
        current_cue_list_id = source_cue_list_id
        mode = "empty_group"
        new_args = [container.get("uniqueID", container_id)]
    else:
        current_cue_list_id = source_cue_list_id
        mode = "empty_cart"
        new_args = [container.get("uniqueID", container_id), 0, 0]
    placement = {
        "mode": mode,
        "status": mode,
        "parent_container_id": container_id,
        "parent_id": container_id,
        # QLab OSC cue IDs are case-sensitive; keep the exact wire spelling
        # separate from the lowercase canonical IDs used by snapshots/tokens.
        "parent_osc_id": str(container.get("uniqueID") or placement_target),
        "parent_type": container_type,
        "source_cue_list_id": source_cue_list_id,
        "current_cue_list_id": current_cue_list_id,
        "new_args": new_args,
        "expected_index": 0,
        "parent_children": children,
        "parent_fingerprint": _structural_fingerprint(children),
        "tree_fingerprint": _create_tree_fingerprint(snapshot),
    }
    if requested_destination is not None:
        placement["destination"] = requested_destination
    if mode == "empty_cart":
        # QLab 5.5.10 accepts the documented 0,0 request but reports the
        # first Cart cell as 1,1 on readback.
        placement.update(
            {
                "cart_row": 0,
                "cart_column": 0,
                "cart_readback_row": 1,
                "cart_readback_column": 1,
            }
        )
    return snapshot, activity, placement, None


def _create_cue_is_active(cue: Any) -> bool:
    if not isinstance(cue, dict):
        return False
    return any(
        _qlab_bool(cue.get(key))
        for key in ("isRunning", "isPaused", "isAuditioning", "isActionRunning")
    )


def _validate_create_placement_type(
    cue_type: str,
    placement: dict[str, Any] | None,
) -> str | None:
    if placement and placement.get("mode") == "empty_cart" and cue_type.casefold() == "group":
        return "Group cues cannot be created inside a Cue Cart."
    return None


def _containing_cue_list_id(snapshot: dict[str, Any], cue_id: str) -> str | None:
    nodes = snapshot.get("nodes") or {}
    parents = snapshot.get("parent_by_child") or {}
    if (nodes.get(cue_id) or {}).get("type") == "Cue List":
        return cue_id
    current = parents.get(cue_id)
    while current:
        node = nodes.get(current) or {}
        if node.get("type") == "Cue List":
            return current
        current = parents.get(current)
    return None


def _read_current_cue_list_id(reader: Any, workspace_id: str) -> str:
    address = _workspace_address(workspace_id, "currentCueListID")
    reply = reader.client.request(address)
    data = reply.data
    if isinstance(data, dict):
        data = data.get("uniqueID") or data.get("currentCueListID") or data.get("id")
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, str):
        raise UnsafeWriteOperationError("QLab currentCueListID reply did not contain a cue list UUID.")
    try:
        return str(UUID(data.strip()))
    except (TypeError, ValueError) as exc:
        raise UnsafeWriteOperationError("QLab currentCueListID reply did not contain a cue list UUID.") from exc


def _create_token_binding(
    workspace_id: str,
    cue_type: str,
    placement: dict[str, Any],
    snapshot: dict[str, Any] | None,
    activity: dict[str, Any],
) -> dict[str, Any]:
    if snapshot is None:
        raise UnsafeWriteOperationError("Create structural snapshot is required for confirmation.")
    return {
        "version": CREATE_TOKEN_VERSION,
        "workspace_id": workspace_id,
        "cue_type": cue_type,
        "mode": placement["mode"],
        "after_cue_id": placement.get("after_cue_id"),
        "parent_container_id": placement.get("parent_container_id"),
        "parent_id": placement["parent_id"],
        "parent_osc_id": placement.get("parent_osc_id"),
        "parent_type": placement.get("parent_type"),
        "source_cue_list_id": placement.get("source_cue_list_id"),
        "current_cue_list_id": placement.get("current_cue_list_id"),
        "anchor_index": placement.get("anchor_index"),
        "expected_index": placement["expected_index"],
        "new_args": placement.get("new_args", []),
        "cart_row": placement.get("cart_row"),
        "cart_column": placement.get("cart_column"),
        "cart_readback_row": placement.get("cart_readback_row"),
        "cart_readback_column": placement.get("cart_readback_column"),
        "parent_children": list(placement["parent_children"]),
        "parent_fingerprint": placement["parent_fingerprint"],
        "tree_fingerprint": _create_tree_fingerprint(snapshot),
        "activity_snapshot": activity,
    }


def _encode_create_token(binding: dict[str, Any]) -> str:
    return encode_confirm_token(
        "createCue",
        CREATE_TOKEN_VERSION,
        {
            "binding": binding,
            "expires_at": int(time.time()) + CREATE_TOKEN_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(12),
        },
        _CREATE_TOKEN_SECRET,
    )


def _create_cues_token_binding(
    workspace_id: str,
    wire_types: list[str],
    labels: list[str],
    destination: dict[str, Any],
    placement: dict[str, Any],
    snapshot: dict[str, Any],
    activity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "version": CREATE_CUES_TOKEN_VERSION,
        "workspace_id": workspace_id,
        "wire_types": wire_types,
        "cue_types": labels,
        "destination": destination,
        "placement": placement,
        "tree_fingerprint": _create_tree_fingerprint(snapshot),
        "activity_snapshot": activity,
    }


def _encode_create_cues_token(binding: dict[str, Any]) -> str:
    return encode_confirm_token(
        "createCues",
        CREATE_CUES_TOKEN_VERSION,
        {
            "binding": binding,
            "expires_at": int(time.time()) + CREATE_CUES_TOKEN_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(12),
        },
        _CREATE_TOKEN_SECRET,
    )


def _decode_create_cues_token(token: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, "create sequence confirmation token is required."
    payload, error = decode_confirm_token(
        token,
        "createCues",
        CREATE_CUES_TOKEN_VERSION,
        _CREATE_TOKEN_SECRET,
    )
    if error == "malformed":
        return None, "create sequence confirmation token is malformed or has an unsupported family."
    if error == "signature":
        return None, "create sequence confirmation token signature is invalid."
    if error == "payload" or payload is None:
        return None, "create sequence confirmation token payload is invalid."
    if not isinstance(payload.get("expires_at"), int) or payload["expires_at"] < int(time.time()):
        return None, "create sequence confirmation token has expired."
    if not isinstance(payload.get("binding"), dict):
        return None, "create sequence confirmation token payload is invalid."
    return payload, None


def _planned_create_cues_operations(
    workspace_id: str,
    wire_types: list[str],
    placement: dict[str, Any],
) -> list[dict[str, Any]]:
    operations = _planned_create_operations(workspace_id, wire_types[0], placement)
    for index, wire_type in enumerate(wire_types[1:], start=1):
        operations.append(
            {
                "operation": "new",
                "address": _workspace_address(workspace_id, "new"),
                "args": [wire_type, "<previous_created_cue_id>"],
                "status": "planned",
                "sequence_index": index,
                "anchor_from_previous": True,
            }
        )
        operations.extend(
            [
                {
                    "operation": "verify",
                    "cue_id": "{created_cue_id}",
                    "expected_type": wire_type,
                    "sequence_index": index,
                    "cacheable": False,
                },
                {
                    "operation": "verify_structure",
                    "mode": "anchored",
                    "after_cue_id": "{previous_created_cue_id}",
                    "sequence_index": index,
                    "cacheable": False,
                },
            ]
        )
    return operations


def _create_cues_failure(
    workspace_id: str,
    labels: list[str],
    dry_run: bool,
    placement: dict[str, Any],
    errors: dict[str, str],
    status: str,
    planned_operations: list[dict[str, Any]] | None = None,
    *,
    destination: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "requested_count": len(labels),
        "planned_count": len(planned_operations or []),
        "created_count": 0,
        "pending_indices": list(range(len(labels))),
        "uncertain_indices": [],
        "batch_verified": False,
        "destination": _create_cues_destination_result(destination, placement),
        "results": [],
        "planned_operations": list(planned_operations or []),
        "executed_operations": [],
        "confirm_token": None,
        "error_code": status,
        "suggested_action": "Inspect the destination and run a new dry-run before creating cues.",
        "errors": errors,
        "warnings": [],
        "message": "Create sequence stopped before mutating OSC commands.",
    }


def _create_cues_partial_result(
    workspace_id: str,
    labels: list[str],
    destination: dict[str, Any],
    placement: dict[str, Any],
    results: list[dict[str, Any]],
    planned_operations: list[dict[str, Any]],
    executed_operations: list[dict[str, Any]],
    failed_result: dict[str, Any],
) -> dict[str, Any]:
    created_count = sum(1 for result in results if result.get("status") == "created")
    status = (
        "partial_failed" if created_count
        else "preflight_failed" if failed_result.get("status") == "preflight_failed"
        else "verification_failed"
    )
    return {
        "ok": False,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": False,
        "requested_count": len(labels),
        "planned_count": len(planned_operations),
        "created_count": created_count,
        "pending_indices": list(range(len(results), len(labels))),
        "uncertain_indices": [item["index"] for item in results if item.get("cleanup_required") and not item.get("verified")],
        "batch_verified": False,
        "destination": _create_cues_destination_result(destination, placement),
        "results": results,
        "planned_operations": planned_operations,
        "executed_operations": executed_operations,
        "confirm_token": None,
        "error_code": failed_result.get("error_code") or failed_result.get("status") or "create_failed",
        "suggested_action": failed_result.get("suggested_action") or "Inspect the workspace and created UUIDs before a new dry-run; do not retry an ambiguous create.",
        "errors": failed_result.get("errors") or {"sequence": failed_result.get("message", "Create sequence stopped.")},
        "warnings": ["No automatic rollback was sent; earlier successful cues remain."] if created_count else [],
        "message": (
            "Create sequence stopped before mutating OSC commands."
            if status == "preflight_failed" and not executed_operations
            else "Create sequence stopped at the first failed or ambiguous cue; no retry was sent."
        ),
    }


def _create_cues_destination_result(
    destination: dict[str, Any] | None,
    placement: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if destination is None:
        return None
    placement = placement or {}
    return {
        **destination,
        "resolved_after_cue_id": placement.get("after_cue_id"),
        "insertion_index": placement.get("expected_index"),
        "placement_mode": placement.get("mode"),
    }


def _create_cues_item_result(index: int, cue_type: str, result: dict[str, Any]) -> dict[str, Any]:
    verification = result.get("verification") or {}
    structure = verification.get("structure") or {}
    health = verification.get("health") or {}
    return {
        "index": index,
        "cue_type": cue_type,
        "status": result.get("status", "preflight_failed"),
        "created_cue_id": result.get("created_cue_id"),
        "verified": result.get("ok") if result.get("status") != "planned" else None,
        "parent_id": structure.get("parent_id"),
        "position_index": structure.get("index"),
        "health_status": health.get("status"),
        "cleanup_required": bool(result.get("cleanup_required")),
        "cleanup": result.get("cleanup"),
        "errors": result.get("errors"),
        "warnings": list(result.get("warnings") or []),
        "error_code": result.get("error_code"),
        "suggested_action": result.get("suggested_action"),
    }


def _decode_create_token(token: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, "create confirmation token is required."
    payload, error = decode_confirm_token(
        token,
        "createCue",
        CREATE_TOKEN_VERSION,
        _CREATE_TOKEN_SECRET,
    )
    if error == "malformed":
        return None, "create confirmation token is malformed or has an unsupported family."
    if error == "signature":
        return None, "create confirmation token signature is invalid."
    if error == "payload" or payload is None:
        return None, "create confirmation token payload is invalid."
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, int):
        return None, "create confirmation token payload is invalid."
    if expires_at < int(time.time()):
        return None, "create confirmation token has expired."
    if not isinstance(payload.get("binding"), dict):
        return None, "create confirmation token payload is invalid."
    return payload, None


def _consume_create_token(token: str | None, payload: dict[str, Any]) -> str | None:
    if not isinstance(token, str):
        return "create confirmation token is required."
    digest = hashlib.sha256(token.encode()).hexdigest()
    expires_at = int(payload.get("expires_at", 0))
    now = int(time.time())
    with _CONSUMED_CREATE_TOKENS_LOCK:
        for consumed, expiry in list(_CONSUMED_CREATE_TOKENS.items()):
            if expiry < now:
                del _CONSUMED_CREATE_TOKENS[consumed]
        if digest in _CONSUMED_CREATE_TOKENS:
            return "confirmation_already_consumed: create confirm_token has already been used."
        _CONSUMED_CREATE_TOKENS[digest] = expires_at
    return None


def _create_token_is_consumed(token: str | None) -> bool:
    if not isinstance(token, str):
        return False
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())
    with _CONSUMED_CREATE_TOKENS_LOCK:
        for consumed, expiry in list(_CONSUMED_CREATE_TOKENS.items()):
            if expiry < now:
                del _CONSUMED_CREATE_TOKENS[consumed]
        return digest in _CONSUMED_CREATE_TOKENS


def _create_failure(
    workspace_id: str,
    cue_type: str,
    properties: dict[str, Any],
    *,
    dry_run: bool,
    placement: dict[str, Any] | None,
    planned_operations: list[dict[str, Any]],
    executed_operations: list[dict[str, Any]] | None = None,
    error_code: str,
    errors: dict[str, str],
    warnings: list[str] | None = None,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "preflight_failed" if dry_run or error_code == "preflight_failed" else "verification_failed",
        "workspace_id": workspace_id,
        "cue_type": cue_type,
        "dry_run": dry_run,
        "created_cue_id": None,
        "confirm_token": None,
        "placement": placement,
        "properties": properties,
        "planned_operations": planned_operations,
        "executed_operations": list(executed_operations or []),
        "verification": None,
        "cleanup_required": False,
        "cleanup": None,
        "errors": errors,
        "warnings": list(warnings or []),
        "error_code": error_code,
        "suggested_action": "Review the fresh workspace snapshot and run a new dry-run before retrying.",
        "message": message,
    }


def _verify_created_batch(reader: Any, workspace: str, before: dict[str, Any], placement: dict[str, Any], results: list[dict[str, Any]]) -> None:
    expected = {parent: list(children) for parent, children in before["children_by_parent"].items()}
    parent = placement["parent_id"]
    ids = [_uuid_key(item["created_cue_id"], "created_cue_id") for item in results]
    index = placement["expected_index"]
    expected[parent][index:index] = ids
    for cue_id, item in zip(ids, results):
        if item["cue_type"] == "Group":
            expected[cue_id] = []
    after = _read_structural_snapshot(reader, workspace)
    roots_before = [cue_id for cue_id, parent_id in before.get("parent_by_child", {}).items() if parent_id is None]
    roots_after = [cue_id for cue_id, parent_id in after.get("parent_by_child", {}).items() if parent_id is None]
    if roots_before != roots_after:
        raise UnsafeWriteOperationError("Root order changed during Create.")
    if _create_tree_fingerprint({"children_by_parent": expected}) != _create_tree_fingerprint(after):
        raise UnsafeWriteOperationError("Final Create structure differs from the complete simulated batch.")
    if _structural_activity_snapshot(reader, workspace).get("active_count"):
        raise UnsafeWriteOperationError("Workspace became active during final Create verification.")


def _verify_created_structure(
    reader: Any,
    workspace_id: str,
    created_cue_id: str,
    placement: dict[str, Any],
    before_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        after = _read_structural_snapshot(reader, workspace_id)
        created_id = str(UUID(created_cue_id))
        parent_id = placement["parent_id"]
        children = list(after.get("children_by_parent", {}).get(parent_id, []))
        actual_index = children.index(created_id)
        expected_children = list(placement["parent_children"])
        expected_children.insert(placement["expected_index"], created_id)
        expected_tree = {
            parent: list(values)
            for parent, values in (before_snapshot or {}).get("children_by_parent", {}).items()
        }
        expected_tree[parent_id] = expected_children
        created_node = after.get("nodes", {}).get(created_id, {})
        if created_node.get("type") in {"Group", "Cue List", "Cue Cart", "Cart"}:
            expected_tree.setdefault(created_id, [])
        expected_fingerprint = _structural_fingerprint(
            [f"{parent}:{','.join(values)}" for parent, values in sorted(expected_tree.items())]
        )
        actual_fingerprint = _create_tree_fingerprint(after)
        if children != expected_children:
            raise UnsafeWriteOperationError(
                "Fresh structural readback did not confirm the created cue immediately after the anchor."
            )
        if actual_fingerprint != expected_fingerprint:
            raise UnsafeWriteOperationError("Fresh structural readback detected workspace drift during creation.")
        return {
            "ok": True,
            "parent_id": parent_id,
            "index": actual_index,
            "after_cue_id": placement.get("after_cue_id"),
            "mode": placement.get("mode"),
            "cart_row": placement.get("cart_row"),
            "cart_column": placement.get("cart_column"),
            "cart_readback_row": placement.get("cart_readback_row"),
            "cart_readback_column": placement.get("cart_readback_column"),
            "tree_fingerprint": actual_fingerprint,
            "expected_tree_fingerprint": expected_fingerprint,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _merge_create_verification(
    verification: dict[str, Any] | None,
    structure: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(verification or {})
    merged["structure"] = structure
    return merged


def _create_health_flag(properties: Any, key: str) -> bool | None:
    if not isinstance(properties, dict) or key not in properties:
        return None
    value = properties[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _read_create_health(properties: Any) -> dict[str, Any]:
    keys = (
        "isBroken",
        "isWarning",
        "isRunning",
        "isPaused",
        "isAuditioning",
        "isActionRunning",
    )
    flags = {key: _create_health_flag(properties, key) for key in keys}
    if flags["isBroken"] is True:
        status = "broken"
    elif flags["isWarning"] is True:
        status = "warning"
    elif flags["isBroken"] is None or flags["isWarning"] is None:
        status = "unknown"
    else:
        status = "healthy"
    active = any(flags[key] is True for key in keys[2:])
    return {"status": status, "active": active, **flags}


def _cart_position_matches(properties: Any, row: int, column: int) -> bool:
    if not isinstance(properties, dict):
        return False
    actual_row = properties.get("cartPosition/row")
    actual_column = properties.get("cartPosition/column")
    cart_position = properties.get("cartPosition")
    if isinstance(cart_position, dict):
        actual_row = cart_position.get("row", actual_row)
        actual_column = cart_position.get("column", actual_column)
    elif isinstance(cart_position, (list, tuple)) and len(cart_position) >= 2:
        actual_row, actual_column = cart_position[0], cart_position[1]
    return _cart_coordinate_matches(actual_row, row) and _cart_coordinate_matches(actual_column, column)


def _cart_coordinate_matches(value: Any, expected: int) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == expected
    if isinstance(value, str):
        try:
            return int(value.strip()) == expected
        except ValueError:
            return False
    return False


def _fade_matrix_cell(matrix: Any, row: Any, column: Any) -> Any:
    if (
        not isinstance(matrix, list)
        or not isinstance(row, int)
        or isinstance(row, bool)
        or not isinstance(column, int)
        or isinstance(column, bool)
        or row < 0
        or column < 0
        or row >= len(matrix)
        or not isinstance(matrix[row], list)
        or column >= len(matrix[row])
    ):
        return None
    return matrix[row][column]


def _fade_operation_coordinates(operation: dict[str, Any]) -> tuple[Any, Any]:
    values = operation.get("arg_values") or {}
    if operation.get("property") == "doLevel":
        return values.get("row"), values.get("column")
    if operation.get("property") == "level":
        return values.get("inChannel"), values.get("outChannel")
    if operation.get("property") == "sliderLevel":
        return 0, values.get("channel")
    if operation.get("property") == "inputChannelName":
        return values.get("number"), None
    if operation.get("property") == "gang":
        return values.get("inChannel"), values.get("outChannel")
    return None, None


def _fade_missing_parameter_state(before: dict[str, Any]) -> bool:
    visual_inactive = all(
        before.get(property_name) is False
        for property_name in ("doOpacity", "doRate", "doRotation", "doScale", "doTranslation")
    )
    do_level = before.get("doLevel")
    audio_inactive = not isinstance(do_level, list) or not any(
        value is True or value == 1
        for row in do_level
        if isinstance(row, list)
        for value in row
    )
    return visual_inactive and audio_inactive


def _phase9_video_audio_operation(item: dict[str, Any], properties: frozenset[str]) -> dict[str, Any] | None:
    if item.get("profile") != "video_basic":
        return None
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in properties
        ),
        None,
    )


def _phase9d_video_audio_mute_solo_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return _phase9_video_audio_operation(item, VIDEO_PHASE9D_AUDIO_MUTE_SOLO_PROPERTIES)


def _phase9e_video_audio_level_bulk_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return _phase9_video_audio_operation(item, VIDEO_PHASE9E_AUDIO_LEVEL_BULK_PROPERTIES)


def _phase9_channel_set(value: Any) -> set[int] | None:
    if not isinstance(value, list):
        return None
    channels: set[int] = set()
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            return None
        channels.add(item)
    return channels


def _phase9_mute_solo_warning_recovery_allowed(item: dict[str, Any], before: dict[str, Any]) -> bool:
    operation = _phase9d_video_audio_mute_solo_operation(item)
    if operation is not None:
        values = operation.get("arg_values") or {}
        output = values.get("output")
        requested = values.get("value")
        read_key = "muteChannels" if operation.get("property") == "mute/channel" else "soloChannels"
        channels = _phase9_channel_set(before.get(read_key))
        return requested is False and isinstance(output, int) and not isinstance(output, bool) and channels is not None and output in channels

    operation = _phase9e_video_audio_level_bulk_operation(item)
    if operation is not None:
        read_key = "muteChannels" if operation.get("property") == "mute/channel/clear" else "soloChannels"
        channels = _phase9_channel_set(before.get(read_key))
        return channels is not None and bool(channels)

    return False


def _canonical_slice_markers(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    markers: list[dict[str, Any]] = []
    for marker in value:
        if not isinstance(marker, dict):
            return None
        time_value = marker.get("time")
        play_count = marker.get("playCount")
        if not _is_plain_finite_number(time_value) or float(time_value) < 0:
            return None
        if not _slice_play_count_valid(play_count):
            return None
        markers.append({"time": float(time_value), "playCount": int(play_count)})
    return markers


def _phase8c_baseline_slice_markers(before: dict[str, Any]) -> list[dict[str, Any]] | None:
    if "sliceMarkers" not in before and before.get("type") in {"Audio", "Video"}:
        return []
    return _canonical_slice_markers(before.get("sliceMarkers"))


def _slice_play_count_valid(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and (value == -1 or value > 0)


def _slice_time_valid(value: Any) -> bool:
    return _is_plain_finite_number(value) and float(value) >= 0


def _phase8c_value_from_args(operation: dict[str, Any], key: str) -> Any:
    values = operation.get("arg_values")
    if isinstance(values, dict) and key in values:
        return values[key]
    args = operation.get("args") or []
    if operation.get("property") == "addSliceMarker":
        if key == "time" and len(args) >= 1:
            return args[0]
        if key == "playCount" and len(args) >= 2:
            return args[1]
    if operation.get("property") == "sliceMarker/time" and key == "time" and args:
        return args[0]
    if operation.get("property") == "sliceMarker/playCount" and key == "playCount" and args:
        return args[0]
    return None


def _phase8c_marker_index(operation: dict[str, Any]) -> int | None:
    values = operation.get("arg_values")
    index = values.get("index") if isinstance(values, dict) else None
    return index if isinstance(index, int) and not isinstance(index, bool) and index >= 0 else None


def _phase8c_time_window(before: dict[str, Any]) -> tuple[float, float | None]:
    start = before.get("startTime")
    lower = float(start) if _is_plain_finite_number(start) and float(start) >= 0 else 0.0
    for key in ("endTime", "duration"):
        value = before.get(key)
        if _is_plain_finite_number(value) and float(value) > lower:
            return lower, float(value)
    return lower, None


def _phase8c_spacing_ok(
    markers: list[dict[str, Any]],
    *,
    time_value: float,
    ignore_index: int | None,
    lower: float,
    upper: float | None,
) -> bool:
    if time_value < lower:
        return False
    if upper is not None and time_value > upper:
        return False
    if ignore_index is not None:
        if ignore_index > 0:
            previous_time = float(markers[ignore_index - 1]["time"])
            if time_value - previous_time < SLICE_MARKER_MIN_SPACING_SECONDS:
                return False
        if ignore_index + 1 < len(markers):
            next_time = float(markers[ignore_index + 1]["time"])
            if next_time - time_value < SLICE_MARKER_MIN_SPACING_SECONDS:
                return False
    for index, marker in enumerate(markers):
        if ignore_index is not None and index == ignore_index:
            continue
        if abs(float(marker["time"]) - time_value) < SLICE_MARKER_MIN_SPACING_SECONDS:
            return False
    return True


def _phase8c_expected_slice_markers(
    operation: dict[str, Any],
    before: dict[str, Any],
) -> tuple[list[dict[str, Any]] | None, str | None]:
    markers = _phase8c_baseline_slice_markers(before)
    if markers is None:
        return None, "Phase 8C requires readable sliceMarkers baseline with finite time and playCount."
    lower, upper = _phase8c_time_window(before)
    property_name = operation.get("property")
    expected = [dict(marker) for marker in markers]
    if property_name == "sliceMarker/time":
        index = _phase8c_marker_index(operation)
        time_value = _phase8c_value_from_args(operation, "time")
        if index is None or index >= len(expected):
            return None, "Phase 8C sliceMarker/time requires an existing marker index."
        if not _slice_time_valid(time_value):
            return None, "Phase 8C slice marker time must be a finite non-negative number."
        requested_time = float(time_value)
        if not _phase8c_spacing_ok(expected, time_value=requested_time, ignore_index=index, lower=lower, upper=upper):
            return None, "Phase 8C slice marker time violates cue bounds or 0.05s minimum spacing."
        expected[index]["time"] = requested_time
        return expected, None
    if property_name == "sliceMarker/playCount":
        index = _phase8c_marker_index(operation)
        play_count = _phase8c_value_from_args(operation, "playCount")
        if index is None or index >= len(expected):
            return None, "Phase 8C sliceMarker/playCount requires an existing marker index."
        if not _slice_play_count_valid(play_count):
            return None, "Phase 8C slice marker playCount must be positive int or -1; 0 is rejected."
        expected[index]["playCount"] = int(play_count)
        return expected, None
    if property_name == "addSliceMarker":
        time_value = _phase8c_value_from_args(operation, "time")
        play_count = _phase8c_value_from_args(operation, "playCount")
        if not _slice_time_valid(time_value):
            return None, "Phase 8C addSliceMarker requires finite non-negative time."
        requested_time = float(time_value)
        if not _slice_play_count_valid(play_count):
            return None, "Phase 8C addSliceMarker playCount must be positive int or -1; 0 is rejected."
        if not _phase8c_spacing_ok(expected, time_value=requested_time, ignore_index=None, lower=lower, upper=upper):
            return None, "Phase 8C addSliceMarker violates cue bounds or 0.05s minimum spacing."
        expected.append({"time": requested_time, "playCount": int(play_count)})
        expected.sort(key=lambda marker: marker["time"])
        return expected, None
    if property_name == "deleteSliceMarker":
        index = _phase8c_marker_index(operation)
        if index is None or index >= len(expected):
            return None, "Phase 8C deleteSliceMarker requires an existing marker index."
        del expected[index]
        return expected, None
    if property_name == "deleteSliceMarkers":
        if not expected:
            return None, "Phase 8C deleteSliceMarkers requires at least one existing marker; empty baseline is a no-op."
        return [], None
    if property_name == "lastSlicePlayCount":
        return None, None
    return None, "Phase 8C operation is blocked until readback and rollback semantics are proven."


def _try_read_safe_light_patch(
    reader: Any,
    workspace_id: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        result = reader._get_workspace_setting_details_single(
            workspace_id,
            section="light",
            kind="light_patch",
            profile="safe",
        )
    except Exception:
        return None, {
            "code": "light_patch_read_failed",
            "message": "Light Patch safe model could not be read.",
        }
    details = result.get("details") if isinstance(result, dict) else None
    if not isinstance(details, dict) or result.get("errors"):
        return None, {
            "code": "light_patch_read_failed",
            "message": "Light Patch safe model could not be read.",
        }
    return details, None


def _summarize_light_command_analysis(helper_result: dict[str, Any]) -> dict[str, Any]:
    results = helper_result.get("results") if isinstance(helper_result.get("results"), list) else []
    status_counts = {status: 0 for status in ("valid", "warning", "invalid", "unsupported")}
    affected_pairs: set[tuple[str, str]] = set()
    skipped_member_count = 0
    for result in results:
        status = result.get("status")
        if status in status_counts:
            status_counts[status] += 1
        for affected in result.get("affected", []):
            instrument = affected.get("instrument") if isinstance(affected, dict) else None
            parameter = affected.get("parameter") if isinstance(affected, dict) else None
            if isinstance(instrument, str) and isinstance(parameter, str):
                affected_pairs.add((instrument, parameter))
        skipped = result.get("skipped_members")
        if isinstance(skipped, list):
            skipped_member_count += len(skipped)

    if status_counts["invalid"]:
        overall_status = "invalid"
    elif status_counts["unsupported"]:
        overall_status = "unsupported"
    elif status_counts["warning"]:
        overall_status = "warning"
    else:
        overall_status = "valid"
    return {
        "availability": "available",
        "overall_status": overall_status,
        "line_count": helper_result.get("line_count", 0),
        "analyzed_count": helper_result.get("analyzed_count", len(results)),
        "status_counts": status_counts,
        "affected_instruments": sorted({instrument for instrument, _ in affected_pairs}),
        "affected_parameters": sorted({parameter for _, parameter in affected_pairs}),
        "affected_pair_count": len(affected_pairs),
        "skipped_member_count": skipped_member_count,
        "results": results,
    }


def _planned_create_operations(
    workspace_id: str,
    cue_type: str,
    placement: dict[str, Any],
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    parent_osc_id = placement.get("parent_osc_id") or placement["parent_id"]
    if placement["mode"] == "empty_cue_list":
        operations.extend(
            [
                {
                    "operation": "set_current_cue_list",
                    "address": _workspace_address(
                        workspace_id,
                        f"currentCueListID/{parent_osc_id}",
                    ),
                    "args": [],
                    "cue_list_id": placement["parent_id"],
                },
                {
                    "operation": "verify_current_cue_list",
                    "address": _workspace_address(workspace_id, "currentCueListID"),
                    "args": [],
                    "cue_list_id": placement["parent_id"],
                    "cacheable": False,
                },
            ]
        )
    operations.append(
        {
            "operation": "new",
            "address": _workspace_address(workspace_id, "new"),
            "args": [cue_type, *placement.get("new_args", [])],
            "after_cue_id": placement.get("after_cue_id"),
            "parent_container_id": placement.get("parent_container_id"),
            "mode": placement["mode"],
        }
    )
    if placement["mode"] == "empty_group":
        operations.append(
            {
                "operation": "move_into_container",
                "address": _workspace_address(workspace_id, "move/{created_cue_id}"),
                "args": [placement["expected_index"], parent_osc_id],
                "parent_id": placement["parent_id"],
                "expected_index": placement["expected_index"],
            }
        )
    operations.append(
        {
            "operation": "verify",
            "cue_id": "{created_cue_id}",
            "expected_type": cue_type,
            "cacheable": False,
        }
    )
    operations.append(
        {
            "operation": "verify_structure",
            "parent_id": placement["parent_id"],
            "after_cue_id": placement.get("after_cue_id"),
            "mode": placement["mode"],
            "expected_index": placement["expected_index"],
            "cart_row": placement.get("cart_row"),
            "cart_column": placement.get("cart_column"),
            "cacheable": False,
        }
    )
    return operations


def _try_read_update_values(
    reader: Any,
    workspace_id: str,
    cue_ref: str,
    read_keys: list[str],
    *,
    request_timeout: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    try:
        values = reader.read_cue_values(
            workspace_id,
            cue_ref,
            read_keys,
            cache_profile="basic_safe",
            cacheable=False,
            request_timeout=request_timeout,
        )["values"]
        if not isinstance(values, dict):
            raise ValueError("QLab valuesForKeys response must be an object")
        return values, {}
    except Exception as exc:
        return None, {"read_before": str(exc)}


def _created_cue_identity_matches(values: Any, created_cue_id: str, cue_type: str) -> bool:
    if not isinstance(values, dict):
        return False
    return values.get("uniqueID") == created_cue_id and str(values.get("type") or "").casefold() == cue_type.casefold()


def _extract_created_cue_id(data: Any) -> str:
    def validate(value: str) -> str:
        try:
            UUID(value)
        except (ValueError, TypeError, AttributeError) as exc:
            raise UnsafeWriteOperationError("QLab returned an invalid cue unique ID after /new.") from exc
        return value

    if isinstance(data, str):
        return validate(data.strip())
    if isinstance(data, dict):
        for key in ("uniqueID", "cueID", "cue_id", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return validate(value.strip())
        cue = data.get("cue")
        if isinstance(cue, dict):
            return _extract_created_cue_id(cue)
    if isinstance(data, list) and data:
        return _extract_created_cue_id(data[0])
    raise UnsafeWriteOperationError("QLab did not return a cue unique ID after /new.")
