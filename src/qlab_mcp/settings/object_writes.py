"""One-property, token-gated Workspace Settings edits."""

from __future__ import annotations

import math
import secrets
import time
from typing import Any
from uuid import UUID

from ..audio_limits import validate_audio_level_limits
from ..errors import OscPreparationError, OscTimeoutError, QLabReplyError
from ..models import (
    AudioOutputPatchBatchOperation,
    WorkspaceSettingsEditResult,
)
from ..osc.addressing import _workspace_address
from ..write.safety import check_write_readiness, ensure_write_ready, resolve_dry_run
from ..write.timeouts import setter_reply_timeout
from ..write.tokens import decode_confirm_token, encode_confirm_token
from .workspace import _osc_geometry_values
from .write_operations import (
    SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_TTL_SECONDS, SETTINGS_TOKEN_VERSION,
    _SETTINGS_TOKEN_SECRET, _activity_snapshot, _consume_settings_token,
)


def _uuid(value: str) -> str:
    return str(UUID(str(value))).upper()


def _same(actual: Any, expected: Any, kind: str = "", floor: int | float | None = None) -> bool:
    if kind == "level" and expected == "-inf" and floor is not None:
        return actual == "-inf" or (isinstance(actual, (int, float)) and not isinstance(actual, bool)
                                    and math.isclose(actual, floor, abs_tol=1e-3))
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, int) and isinstance(expected, int):
        return actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-5, abs_tol=1e-3 if kind == "level" else 1e-5)
    if isinstance(actual, (tuple, list)) and isinstance(expected, (tuple, list)):
        return len(actual) == len(expected) and all(_same(a, b, kind, floor) for a, b in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def _value(value: Any, kind: str) -> Any:
    if kind in {"bounds", "origin", "size", "controlPoint"}:
        return _osc_geometry_values(value, kind)
    if kind in {"muteClear", "soloClear"}:
        if not isinstance(value, list) or any(not isinstance(x, int) or isinstance(x, bool) for x in value):
            raise ValueError("Expected list of muted or soloed output channels")
        return value
    if kind in {"general.selectionIsPlayhead", "enableGuides", "enableGrid", "enableGuide", "mute", "solo"}:
        if not isinstance(value, bool):
            raise ValueError("Expected boolean readback")
    if kind in {"cueOutputChannels", "x", "y", "width", "height"}:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("Expected integer readback")
    if kind == "name" and not isinstance(value, str):
        raise ValueError("Expected name readback")
    if kind in {"level", "general.minGoTime"} and not (
        (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))
        or (kind == "level" and value == "-inf")
    ):
        raise ValueError("Expected numeric or -inf readback")
    return value


def _operation(family: str, ids: dict[str, str], op: Any) -> tuple[str, str, list[Any], Any]:
    kind = op.kind
    if family == "general":
        path = "general/" + ("minGoTime" if kind == "general.minGoTime" else "selectionIsPlayhead")
        return kind, path, [op.value], op.value
    if family == "audio":
        base = f"audio/patchID/{ids['patch_id']}"
        if kind == "name":
            return kind, base + "/name", [op.value], op.value
        if kind == "cueOutputChannels":
            return kind, base + "/cueOutputChannels", [op.value], op.value
        if kind == "level":
            return kind, base + f"/level/{op.input_channel}/{op.output_channel}", [op.value], op.value
        if kind in {"mute", "solo"}:
            return kind, base + f"/{kind}/{op.output_channel}", [op.value], op.value
        if kind in {"muteClear", "soloClear"}:
            mode = kind[:-5]
            return kind, base + f"/{mode}/clear", [], []
    if family == "route":
        return kind, f"video/routeID/{ids['route_id']}/enableGuides", [op.value], op.value
    if family == "stage":
        return kind, f"video/stageID/{ids['stage_id']}/name", [op.value], op.value
    if family == "region":
        base = f"video/stageID/{ids['stage_id']}/regionID/{ids['region_id']}"
        if kind in {"bounds", "origin", "size", "controlPoint"}:
            keys = ("x", "y", "width", "height") if kind == "bounds" else (
                ("width", "height") if kind == "size" else ("x", "y")
            )
            if any(getattr(op, key) is None for key in keys):
                raise ValueError(f"{kind} requires {', '.join(keys)}")
            extra = "bounds" if kind == "bounds" else "bounds/origin" if kind == "origin" else "bounds/size" if kind == "size" else (
                f"subregionIndex/{op.subregion_index}/controlPointIndex/{op.control_point_index}"
            )
            if kind == "controlPoint" and (op.subregion_index is None or op.control_point_index is None):
                raise ValueError("controlPoint requires both indices")
            values = [getattr(op, key) for key in keys]
            return kind, base + "/" + extra, values, values
        if kind in {"x", "y", "width", "height"}:
            suffix = "origin/" if kind in {"x", "y"} else "size/"
            return kind, base + "/bounds/" + suffix + kind, [op.value], op.value
        if kind in {"enableGrid", "enableGuide"}:
            return kind, base + "/" + kind, [op.value], op.value
    raise ValueError("Unsupported Workspace Settings operation")


class ObjectSettingsWriteMixin:
    def _settings_raw(self, workspace: str, path: str) -> Any:
        address = _workspace_address(workspace, "settings/" + path)
        try:
            return self._request(address, workspace_id=workspace).data
        except OscTimeoutError:
            # Read-only retry; a timed-out setter is never resent.
            return self._request(address, workspace_id=workspace).data

    def _audio_level_limits(self, workspace: str, values: list[Any]) -> tuple[int | float, int | float]:
        minimum = self._settings_raw(workspace, "audio/minVolume")
        maximum = self._settings_raw(workspace, "audio/maxVolume")
        return validate_audio_level_limits(minimum, maximum, values)

    def _object_preflight(self, workspace: str, family: str, ids: dict[str, str], op: Any,
                          *, audio_cue_output_count: int | None = None) -> None:
        if family == "general":
            return
        path = (
            f"audio/patchID/{ids['patch_id']}" if family == "audio" else
            f"video/routeID/{ids['route_id']}" if family == "route" else
            f"video/stageID/{ids['stage_id']}" if family == "stage" else
            f"video/stageID/{ids['stage_id']}/regionID/{ids['region_id']}"
        )
        item = self._settings_raw(workspace, path)
        expected = ids["patch_id" if family == "audio" else "route_id" if family == "route" else "stage_id" if family == "stage" else "region_id"]
        if not isinstance(item, dict) or str(item.get("uniqueID", "")).casefold() != expected.casefold():
            raise ValueError("QLab object uniqueID does not match the requested UUID")
        if family == "audio":
            # Routing lists currently audible outputs; -inf can remove a valid output.
            # The exact crosspoint/mute/solo read validates that the output exists.
            if op.kind == "level":
                count = (audio_cue_output_count if audio_cue_output_count is not None
                         else self._settings_raw(workspace, path + "/cueOutputChannels"))
                if not isinstance(count, int) or isinstance(count, bool) or not (0 <= op.input_channel <= count and 1 <= count <= 128):
                    raise ValueError("Input channel is outside known cue outputs")
        if family == "region":
            stage = self._settings_raw(workspace, f"video/stageID/{ids['stage_id']}")
            if not isinstance(stage, dict) or str(stage.get("uniqueID", "")).casefold() != ids["stage_id"].casefold():
                raise ValueError("Stage identity mismatch")
            if op.kind in {"bounds", "origin", "size", "x", "y", "width", "height"}:
                size = self._settings_raw(workspace, f"video/stageID/{ids['stage_id']}/size")
                bounds = self._settings_raw(workspace, path + "/bounds")
                if not isinstance(size, dict) or not isinstance(bounds, dict):
                    raise ValueError("Stage size or region bounds unavailable")
                proposed = {key: bounds[key] for key in ("x", "y", "width", "height")}
                changes = op.model_dump(exclude_none=True)
                if op.kind in {"x", "y", "width", "height"}:
                    proposed[op.kind] = op.value
                else:
                    proposed.update({key: changes[key] for key in proposed if key in changes})
                if not all(isinstance(v, int) and not isinstance(v, bool) for v in proposed.values()):
                    raise ValueError("OSC bounds must use integers")
                if not (0 <= proposed["x"] and 0 <= proposed["y"] and proposed["width"] > 0 and proposed["height"] > 0
                        and proposed["x"] + proposed["width"] <= size["width"]
                        and proposed["y"] + proposed["height"] <= size["height"]):
                    raise ValueError("Region bounds must remain within the OSC stage area")
            if op.kind == "controlPoint":
                # The exact indexed OSC read below validates both indices; no matrix walk.
                point = self._settings_raw(workspace, path + f"/subregionIndex/{op.subregion_index}/controlPointIndex/{op.control_point_index}")
                _value(point, "controlPoint")
                route = item.get("route")
                if not isinstance(route, dict) or not route.get("uniqueID"):
                    raise ValueError("Control point output route is unknown")
                route_id = _uuid(route["uniqueID"])
                direct_route = self._settings_raw(workspace, f"video/routeID/{route_id}")
                size = direct_route.get("naturalSize") if isinstance(direct_route, dict) else None
                if (not isinstance(direct_route, dict) or str(direct_route.get("uniqueID", "")).casefold() != route_id.casefold()
                        or not isinstance(size, dict) or not isinstance(size.get("width"), int)
                        or not isinstance(size.get("height"), int)):
                    raise ValueError("Control point output area cannot be verified")
                if not (0 <= op.x <= size["width"] and 0 <= op.y <= size["height"]):
                    raise ValueError("Control point must stay inside the OSC output area")

    def edit_object_setting(
        self, workspace_id: str, family: str, ids: dict[str, str], op: Any,
        dry_run: bool | None, confirm_token: str | None,
    ) -> WorkspaceSettingsEditResult:
        workspace = str(workspace_id)
        ids = {key: _uuid(value) for key, value in ids.items()}
        dry = resolve_dry_run(self, dry_run)
        kind, path, args, wanted = _operation(family, ids, op)
        read_path = path.replace("/mute/clear", "/muteChannels").replace("/solo/clear", "/soloChannels")
        address = _workspace_address(workspace, "settings/" + path)
        planned = [{"operation": kind, "address": address, "args": args}]
        baseline: Any = None
        floor: int | float | None = None
        minimum: int | float | None = None
        maximum: int | float | None = None
        readiness: dict[str, Any] | None = None
        activity: dict[str, Any] | None = None

        def result(status: str, *, readback: Any = None, executed: list[dict[str, Any]] | None = None,
                   token: str | None = None, error: str | None = None, retry_unsafe: bool = False) -> WorkspaceSettingsEditResult:
            return WorkspaceSettingsEditResult(
                ok=status in {"dry_run", "unchanged", "updated", "updated_with_confirmed_timeouts"},
                status=status, workspace_id=workspace, operation=kind, dry_run=dry,
                requested_value=wanted, baseline=baseline, readback=readback,
                planned_operations=planned, executed_operations=executed or [], confirm_token=token,
                readiness=readiness, activity=activity,
                verification={"matched": _same(readback, wanted, kind, floor), "readback_available": readback is not None} if executed else None,
                retry_unsafe=retry_unsafe, errors={"write": error} if error else None,
                warnings=(["QLab reads -inf as the configured audio minimum; the OSC value cannot distinguish both states."]
                          if kind == "level" and wanted == "-inf" else []),
                message=status,
            )

        def read() -> Any:
            return _value(self._settings_raw(workspace, read_path), kind)

        try:
            workspace = self._resolve_settings_workspace_uuid(workspace)
            planned[0]["address"] = _workspace_address(workspace, "settings/" + path)
            readiness = check_write_readiness(self, workspace)
            if not readiness.get("ok"):
                return result("dry_run_preflight_failed" if dry else "preflight_failed", error=readiness.get("message"))
            self._object_preflight(workspace, family, ids, op)
            if family == "audio" and kind == "level":
                minimum, maximum = self._audio_level_limits(workspace, [wanted])
            if kind == "level" and wanted == "-inf":
                floor = minimum
            baseline = read()
            activity = _activity_snapshot(self, workspace)
            if activity["active_count"]:
                raise ValueError("Workspace has running or paused cues")
        except Exception as exc:
            return result("dry_run_preflight_failed" if dry else "preflight_failed", error=str(exc))

        # A numeric floor cannot prove -inf before its setter has been sent.
        if _same(baseline, wanted, kind):
            return result("unchanged", readback=baseline)
        binding = {"workspace_id": workspace, "family": family, "ids": ids, "operation": op.model_dump(),
                   "path": path, "baseline": baseline, "wanted": wanted, "audio_minimum": floor,
                   "audio_limit_minimum": minimum, "audio_maximum": maximum}
        if dry:
            binding.update(expires_at=int(time.time()) + SETTINGS_TOKEN_TTL_SECONDS, nonce=secrets.token_urlsafe(12))
            return result("dry_run", token=encode_confirm_token(
                SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_VERSION, binding, _SETTINGS_TOKEN_SECRET,
            ))
        payload, error = decode_confirm_token(
            confirm_token or "", SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_VERSION, _SETTINGS_TOKEN_SECRET,
        )
        if error or not isinstance(payload, dict) or payload.get("expires_at", 0) < int(time.time()) or any(
            payload.get(key) != value for key, value in binding.items()
        ):
            return result("preflight_failed", error="confirm_token invalid, expired, or bound to another value")
        try:
            ensure_write_ready(self, workspace)
            self._resolve_settings_workspace_uuid(workspace)
            self._object_preflight(workspace, family, ids, op)
            if minimum is not None and self._audio_level_limits(workspace, [wanted]) != (minimum, maximum):
                return result("preflight_failed", error="Audio volume limits changed before mutation")
            fresh = read()
            if not _same(fresh, baseline, kind):
                return result("preflight_failed", error="confirm_token baseline is stale")
            if _activity_snapshot(self, workspace)["active_count"]:
                return result("preflight_failed", error="Workspace activity changed before mutation")
            replay = _consume_settings_token(confirm_token or "", payload)
            if replay:
                return result("preflight_failed", error=replay)
        except Exception as exc:
            return result("preflight_failed", error=str(exc))

        executed = [{"operation": kind, "address": planned[0]["address"], "args": args}]
        setter_error = None
        timeout = False
        try:
            reply = self._request(planned[0]["address"], *args, workspace_id=workspace,
                                  request_timeout=setter_reply_timeout(self, 1),
                                  ensure_always_reply=True, allow_empty_data=True)
            if getattr(reply, "status", "ok") != "ok":
                raise QLabReplyError(reply.status, reply.data, planned[0]["address"])
            executed[0]["status"] = "ok"
        except OscPreparationError as exc:
            return result("preflight_failed", error=str(exc))
        except OscTimeoutError as exc:
            timeout = True
            setter_error = str(exc)
            executed[0]["status"] = "timeout_pending_verification"
        except Exception as exc:
            setter_error = str(exc)
            executed[0]["status"] = "error_pending_verification"
        if hasattr(self, "_read_cache"):
            self._read_cache.clear()
        try:
            observed = read()
        except Exception as exc:
            return result("verification_inconclusive", executed=executed,
                          error=f"Fresh readback unavailable: {exc}; setter: {setter_error}", retry_unsafe=True)
        if _same(observed, wanted, kind, floor):
            return result("updated_with_confirmed_timeouts" if timeout else "updated", readback=observed,
                          executed=executed, retry_unsafe=timeout)
        return result("verification_failed", readback=observed, executed=executed,
                      error=f"Fresh readback differs; setter: {setter_error}", retry_unsafe=True)

    def edit_audio_patch_batch(
        self, workspace_id: str, patch_id: str, batch: AudioOutputPatchBatchOperation,
        dry_run: bool | None, confirm_token: str | None,
    ) -> WorkspaceSettingsEditResult:
        workspace = str(workspace_id)
        ids = {"patch_id": _uuid(patch_id)}
        dry = resolve_dry_run(self, dry_run)
        operations = [op.model_dump(exclude_none=True) for op in batch.operations]
        entries = []
        for op in batch.operations:
            kind, path, args, wanted = _operation("audio", ids, op)
            if kind not in {"level", "mute", "solo"}:
                raise ValueError("Audio patch batches accept only level, mute, and solo operations.")
            entries.append({
                "op": op, "kind": kind, "path": path,
                "address": _workspace_address(workspace, "settings/" + path),
                "args": args, "wanted": wanted,
            })

        baseline = []
        patch_dimensions = None
        minimum = None
        maximum = None
        floor = None
        planned = [{"operation": entry["kind"], "address": entry["address"], "args": entry["args"]}
                   for entry in entries]
        readbacks = []
        executed = []
        readiness: dict[str, Any] | None = None
        activity: dict[str, Any] | None = None
        timed_out = False

        def result(status: str, *, token: str | None = None, error: str | None = None,
                   retry_unsafe: bool = False) -> WorkspaceSettingsEditResult:
            readback_complete = len(readbacks) == len(entries)
            observed_match = all(
                _same(value["value"], entries[index]["wanted"], entries[index]["kind"], entries[index].get("floor"))
                for index, value in enumerate(readbacks)
            )
            matched = False if not observed_match else True if readback_complete else None
            return WorkspaceSettingsEditResult(
                ok=status in {"dry_run", "unchanged", "updated", "updated_with_confirmed_timeouts"},
                status=status, workspace_id=workspace, operation="batch", dry_run=dry,
                requested_value=operations, baseline=baseline, readback=readbacks,
                planned_operations=planned, executed_operations=executed, confirm_token=token,
                readiness=readiness, activity=activity,
                verification={"matched": matched,
                              "readback_available": readback_complete} if readbacks else None,
                retry_unsafe=retry_unsafe, errors={"write": error} if error else None,
                warnings=(
                    ["QLab reads -inf as the configured audio minimum; the OSC value cannot distinguish both states."]
                    if any(entry["kind"] == "level" and entry["wanted"] == "-inf" for entry in entries) else []
                ),
                message=status,
            )

        def read(entry: dict[str, Any]) -> Any:
            return _value(self._settings_raw(workspace, entry["path"]), entry["kind"])

        def unchanged(value: Any, entry: dict[str, Any]) -> bool:
            if entry["kind"] == "level" and entry["wanted"] == "-inf":
                # A numeric floor readback cannot establish that QLab stored -inf.
                return value == "-inf"
            return _same(value, entry["wanted"], entry["kind"], entry.get("floor"))

        try:
            workspace = self._resolve_settings_workspace_uuid(workspace)
            for entry, planned_entry in zip(entries, planned, strict=True):
                entry["address"] = _workspace_address(workspace, "settings/" + entry["path"])
                planned_entry["address"] = entry["address"]
            readiness = check_write_readiness(self, workspace)
            if not readiness.get("ok"):
                return result("dry_run_preflight_failed" if dry else "preflight_failed", error=readiness.get("message"))
            if any(entry["kind"] == "level" for entry in entries):
                cue_output_count = self._settings_raw(
                    workspace, f"audio/patchID/{ids['patch_id']}/cueOutputChannels",
                )
                if (not isinstance(cue_output_count, int) or isinstance(cue_output_count, bool)
                        or not 1 <= cue_output_count <= 128):
                    raise ValueError("Audio patch cue-output count is unavailable or invalid")
                patch_dimensions = {"cue_output_channels": cue_output_count}
                minimum, maximum = self._audio_level_limits(
                    workspace, [entry["wanted"] for entry in entries if entry["kind"] == "level"]
                )
            self._object_preflight(workspace, "audio", ids, entries[0]["op"],
                                   audio_cue_output_count=(patch_dimensions or {}).get("cue_output_channels"))
            if any(entry["kind"] == "level" and entry["wanted"] == "-inf" for entry in entries):
                floor = minimum
            for entry in entries:
                if entry["kind"] == "level" and entry["op"].input_channel > patch_dimensions["cue_output_channels"]:
                    raise ValueError("Input channel is outside known cue outputs")
                if entry["kind"] == "level" and entry["wanted"] == "-inf":
                    entry["floor"] = floor
                value = read(entry)
                baseline.append({
                    "operation": entry["kind"], "address": entry["address"], "value": value,
                    **({"audio_minimum": entry["floor"]} if "floor" in entry else {}),
                })
            activity = _activity_snapshot(self, workspace)
            if activity["active_count"]:
                raise ValueError("Workspace has running or paused cues")
        except Exception as exc:
            return result("dry_run_preflight_failed" if dry else "preflight_failed", error=str(exc))

        if all(unchanged(base["value"], entry)
               for base, entry in zip(baseline, entries, strict=True)):
            readbacks.extend({"operation": base["operation"], "address": base["address"], "value": base["value"]}
                             for base in baseline)
            return result("unchanged")

        binding = {
            "workspace_id": workspace, "family": "audio", "ids": ids,
            "operation": {"kind": "batch", "operations": operations}, "baseline": baseline,
            "patch_dimensions": patch_dimensions, "audio_limit_minimum": minimum, "audio_maximum": maximum,
        }
        if dry:
            binding.update(expires_at=int(time.time()) + SETTINGS_TOKEN_TTL_SECONDS, nonce=secrets.token_urlsafe(12))
            return result("dry_run", token=encode_confirm_token(
                SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_VERSION, binding, _SETTINGS_TOKEN_SECRET,
            ))

        payload, error = decode_confirm_token(
            confirm_token or "", SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_VERSION, _SETTINGS_TOKEN_SECRET,
        )
        if error or not isinstance(payload, dict) or payload.get("expires_at", 0) < int(time.time()) or any(
            payload.get(key) != value for key, value in binding.items()
        ):
            return result("preflight_failed", error="confirm_token invalid, expired, or bound to another value")

        try:
            ensure_write_ready(self, workspace)
            self._resolve_settings_workspace_uuid(workspace)
            if patch_dimensions is not None:
                fresh_cue_output_count = self._settings_raw(
                    workspace, f"audio/patchID/{ids['patch_id']}/cueOutputChannels",
                )
                if fresh_cue_output_count != patch_dimensions["cue_output_channels"]:
                    return result("preflight_failed", error="Audio patch dimensions changed before mutation")
            if minimum is not None and self._audio_level_limits(
                workspace, [entry["wanted"] for entry in entries if entry["kind"] == "level"]
            ) != (minimum, maximum):
                return result("preflight_failed", error="Audio volume limits changed before mutation")
            self._object_preflight(workspace, "audio", ids, entries[0]["op"],
                                   audio_cue_output_count=(patch_dimensions or {}).get("cue_output_channels"))
            fresh_baseline = []
            for entry in entries:
                fresh_baseline.append({
                    "operation": entry["kind"], "address": entry["address"], "value": read(entry),
                    **({"audio_minimum": entry["floor"]} if "floor" in entry else {}),
                })
            if fresh_baseline != baseline:
                return result("preflight_failed", error="confirm_token baseline is stale")
            activity = _activity_snapshot(self, workspace)
            if activity["active_count"]:
                return result("preflight_failed", error="Workspace activity changed before mutation")
            replay = _consume_settings_token(confirm_token or "", payload)
            if replay:
                return result("preflight_failed", error=replay)
        except Exception as exc:
            return result("preflight_failed", error=str(exc))

        for entry, base in zip(entries, baseline, strict=True):
            if unchanged(base["value"], entry):
                executed.append({"operation": entry["kind"], "address": entry["address"], "args": entry["args"],
                                 "status": "unchanged"})
                readbacks.append({"operation": entry["kind"], "address": entry["address"], "value": base["value"]})
                continue
            item = {"operation": entry["kind"], "address": entry["address"], "args": entry["args"]}
            executed.append(item)
            setter_error = None
            timeout = False
            try:
                reply = self._request(entry["address"], *entry["args"], workspace_id=workspace,
                                      request_timeout=setter_reply_timeout(self, 1),
                                      ensure_always_reply=True, allow_empty_data=True)
                if getattr(reply, "status", "ok") != "ok":
                    raise QLabReplyError(reply.status, reply.data, entry["address"])
                item["status"] = "ok"
            except OscPreparationError as exc:
                item["status"] = "preparation_failed"
                partial = any(
                    item.get("status") in {"ok", "confirmed_after_timeout", "confirmed_after_error"}
                    for item in executed[:-1]
                )
                return result("verification_failed" if partial else "preflight_failed",
                              retry_unsafe=partial, error=str(exc))
            except OscTimeoutError as exc:
                timeout = timed_out = True
                setter_error = str(exc)
                item["status"] = "timeout_pending_verification"
            except Exception as exc:
                setter_error = str(exc)
                item["status"] = "error_pending_verification"
            if hasattr(self, "_read_cache"):
                self._read_cache.clear()
            try:
                observed = read(entry)
            except Exception as exc:
                return result("verification_inconclusive", retry_unsafe=True,
                              error=f"Fresh readback unavailable: {exc}; setter: {setter_error}")
            readbacks.append({"operation": entry["kind"], "address": entry["address"], "value": observed})
            if not _same(observed, entry["wanted"], entry["kind"], entry.get("floor")):
                item["status"] = "verification_failed"
                return result("verification_failed", retry_unsafe=True,
                              error=f"Fresh readback differs; setter: {setter_error}")
            if timeout:
                item["status"] = "confirmed_after_timeout"
            elif setter_error:
                item["status"] = "confirmed_after_error"

        status = "updated_with_confirmed_timeouts" if timed_out else "updated"
        return result(status, retry_unsafe=timed_out)
