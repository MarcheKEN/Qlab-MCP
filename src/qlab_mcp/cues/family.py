"""Shared bounded inventory and exact detail execution for specialized cue families."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, TypeAdapter

from .list_models import FiniteNumber
from .lists import _finish, _inventory
from .refs import _bounded_cue_refs_from_shallow
from .limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES, serialized_payload_bytes
from .profiles import _coerce_qlab_bool
from ..sanitizer import sanitize_exception_message
from ..settings.redaction import _redact_payload

Level = FiniteNumber | Literal["-inf"]


class AudioCrosspoint(BaseModel):
    input_channel: int
    output_channel: int
    value: Level


def _fail(result, code, message, route="selection"):
    result.ok, result.status, result.partial = False, "error", False
    result.error_code, result.message = code, message
    result.errors[route] = message
    result.coverage.failed_routes = list(result.errors)
    result.suggested_action = (
        "Call qlab_check_connection and use its exact workspace UUID."
        if code.startswith("workspace") else
        f"Call qlab_get_cue_lists, then qlab_get_{result.cue_type.lower()}_cues with an exact Cue List UUID."
    )
    return result


def _section(model, values, result, keys):
    clean = {}
    for name, field in model.model_fields.items():
        key = field.validation_alias or name
        if key not in keys:
            continue
        if values.get(key) is None:
            result.coverage.unavailable_fields.append(key)
            continue
        try:
            value = values[key]
            # QLab returns preservePitch as integer 0/1 in valuesForKeys.
            if key == "preservePitch" and type(value) is int and value in (0, 1):
                value = _coerce_qlab_bool(value)
            clean[name] = TypeAdapter(field.rebuild_annotation()).validate_python(value)
        except ValueError:
            result.errors[key] = "Invalid OSC value for this field"
    return model(**clean)


class CueFamilyReadsMixin:
    def _get_family_cues(self, workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                               result_model, summary_model, *, accepted_types=None):
        result = result_model(workspace_id=str(workspace_id), cue_list_id=str(cue_list_id),
                                limit=100, offset=0, max_cues_scanned=5000)
        try:
            UUID(str(workspace_id))
            target = str(UUID(str(cue_list_id)))
            if any(type(v) is not int for v in (limit, offset, max_cues_scanned)) or not (
                1 <= limit <= 500 and offset >= 0 and 1 <= max_cues_scanned <= 5000
            ):
                raise ValueError("Invalid inventory limits")
        except ValueError as exc:
            return _fail(result, "validation_failed", str(exc))
        result.limit, result.offset, result.max_cues_scanned = limit, offset, max_cues_scanned
        try:
            result.workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _fail(result, getattr(exc, "status", "workspace_not_found"), sanitize_exception_message(exc))
        try:
            roots = _inventory(self, result.workspace_id)
        except Exception as exc:
            return _fail(result, "cue_list_payload_invalid", sanitize_exception_message(exc), "cueLists/shallow")
        root = next((item for item in roots if item["uniqueID"].casefold() == target), None)
        if root is None:
            return _fail(result, "cue_list_not_found", "No root Cue List has this UUID")
        if root["type"] != "Cue List":
            return _fail(result, "cue_list_type_mismatch", "The UUID must identify a Cue List")
        result.cue_list_id = root["uniqueID"]
        bounded = _bounded_cue_refs_from_shallow(self, result.workspace_id, limit=max_cues_scanned + 1,
                                               root_cues=[root], cacheable=False)
        refs = bounded["refs"][1:]
        result.scanned_count = len(refs)
        accepted_types = accepted_types or (result.cue_type,)
        matches = [ref for ref in refs if ref["cue"].get("type") in accepted_types]
        result.matched_count = len(matches)
        result.errors.update({key: sanitize_exception_message(ValueError(value)) for key, value in bounded["errors"].items()})
        result.scan_complete = not bounded["truncated"] and not result.errors
        result.truncation_reasons = list(bounded["truncation_reasons"])
        page = matches[offset:offset + limit]
        for ref in page:
            uid = ref["uniqueID"]
            try:
                values = self.read_cue_values(result.workspace_id, uid, [key for key in summary_model.model_fields if key not in {"parent_id", "cue_list_id"}], cacheable=False)["values"]
                if not isinstance(values, dict) or str(values.get("uniqueID", "")).casefold() != uid.casefold():
                    raise ValueError(f"{result.cue_type} identity mismatch")
                if values.get("type") != ref["cue"].get("type"):
                    raise ValueError("Cue type changed during inventory read")
                result.cues.append(summary_model.model_validate({**values, "parent_id": ref["parent_id"],
                                                                   "cue_list_id": result.cue_list_id}))
            except Exception as exc:
                result.errors[uid] = sanitize_exception_message(exc)
        result.returned_count = len(result.cues)
        result.has_more = offset + len(page) < len(matches)
        result.next_offset = offset + len(page) if result.has_more else None
        if result.has_more:
            result.truncation_reasons.append("limit")
        result.truncated = bool(result.truncation_reasons)
        result.coverage.notes = ["Counts cover the scanned portion of this Cue List, including nested groups.",
                                 "Pages are fresh observations; edits between calls can shift offsets."]
        return _finish(result)

    def _get_family_details(self, workspace_id, cue_id, profile, input_channel, output_channel,
                                  result_model, summary_model, detail_models, *, max_bytes=MAX_SENSITIVE_CUE_RESPONSE_BYTES,
                                  accepted_types=None, conditional_models=None):
        result = result_model(workspace_id=str(workspace_id), cue_id=str(cue_id))
        cue_type = result.cue_type
        family = cue_type.lower()
        try:
            UUID(str(workspace_id))
            target = str(UUID(str(cue_id)))
            if profile not in {"safe", "technical"}:
                raise ValueError("Invalid profile")
            if (input_channel is None) != (output_channel is None):
                raise ValueError("Provide both channels together")
            if input_channel is not None and (type(input_channel) is not int or type(output_channel) is not int
                    or not 0 <= input_channel <= 24 or not 0 <= output_channel <= 128):
                raise ValueError("Channels must be integers in ranges 0..24 and 0..128")
        except ValueError as exc:
            return _fail(result, "validation_failed", str(exc))
        result.profile = profile
        try:
            result.workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _fail(result, getattr(exc, "status", "workspace_not_found"), sanitize_exception_message(exc))
        try:
            values = self.read_cue_values(result.workspace_id, target.upper(), [key for key in summary_model.model_fields if key not in {"parent_id", "cue_list_id"}], cacheable=False)["values"]
            if not isinstance(values, dict):
                raise ValueError("valuesForKeys must return an object")
            if not values.get("uniqueID"):
                return _fail(result, f"{family}_cue_not_found", f"No {cue_type} cue has this UUID")
            if str(values["uniqueID"]).casefold() != target:
                return _fail(result, f"{family}_cue_identity_mismatch", "OSC returned a different cue UUID")
            if values.get("type") not in (accepted_types or (cue_type,)):
                return _fail(result, f"{family}_cue_type_mismatch", f"The UUID does not identify a {cue_type} cue")
            result.identity = summary_model.model_validate(values)
            result.cue_id = result.identity.uniqueID
        except Exception as exc:
            return _fail(result, f"{family}_cue_payload_invalid", sanitize_exception_message(exc), "valuesForKeys")
        actual_type = values["type"]
        if callable(detail_models):
            detail_models = detail_models(actual_type)
        keys = list(dict.fromkeys(field.validation_alias or name
                                 for model in detail_models.values() for name, field in model.model_fields.items()
                                 if profile == "technical" or name not in {"notes", "fileTarget"}
                                 or (cue_type == "Control" and actual_type == "Memo" and name == "notes")))
        keys.append("parent")
        if profile == "technical" and cue_type in {"Audio", "Video"}:
            keys.append("audioTrackFormats")
        direct_keys = [key for key in keys if "/" in key]
        batch_keys = [key for key in keys if key not in direct_keys]
        try:
            extra = self.read_cue_values(result.workspace_id, result.cue_id, ["uniqueID", "type", *batch_keys], cacheable=False)["values"]
            if not isinstance(extra, dict):
                raise ValueError(f"{cue_type} detail must be an object")
            if str(extra.get("uniqueID", "")).casefold() != target or extra.get("type") != actual_type:
                result.identity = None
                return _fail(result, f"{family}_cue_identity_mismatch", f"{cue_type} identity changed during detail read")
            values.update({key: extra[key] for key in keys if key in extra})
        except Exception as exc:
            result.errors[f"valuesForKeys:{family}"] = sanitize_exception_message(exc)
        guards = {}
        if conditional_models is not None:
            try:
                additions, guards = conditional_models(self, result, values)
                detail_models = {**detail_models, **additions}
                extra_keys = list(dict.fromkeys(field.validation_alias or name
                    for model in additions.values() for name, field in model.model_fields.items()))
                keys.extend(extra_keys)
                direct_keys.extend(key for key in extra_keys if "/" in key)
                batch = [key for key in extra_keys if "/" not in key]
                if batch:
                    try:
                        extra = self.read_cue_values(result.workspace_id, result.cue_id,
                            ["uniqueID", "type", *batch], cacheable=False)["values"]
                    except Exception as exc:
                        result.errors[f"valuesForKeys:{family}:conditional"] = sanitize_exception_message(exc)
                    else:
                        if not isinstance(extra, dict) or str(extra.get("uniqueID", "")).casefold() != target or extra.get("type") != actual_type:
                            raise ValueError("Cue identity changed during conditional reads")
                        values.update({key: extra[key] for key in batch if key in extra})
            except Exception as exc:
                if (f"valuesForKeys:{family}" in result.errors
                        and isinstance(exc, ValueError)
                        and str(exc).startswith("Invalid or unavailable selector ")):
                    # The first secondary read failed: preserve confirmed identity.
                    additions, guards = {}, {}
                else:
                    return _fail(result_model(workspace_id=result.workspace_id, cue_id=result.cue_id, profile=profile),
                                 f"{family}_cue_payload_invalid", sanitize_exception_message(exc))
        for key in direct_keys:
            try:
                values[key] = self.read_cue_property(result.workspace_id, result.cue_id, key)["value"]
            except Exception as exc:
                result.errors[key] = sanitize_exception_message(exc)
        if direct_keys or conditional_models is not None:
            try:
                final = self.read_cue_values(result.workspace_id, result.cue_id, ["uniqueID", "type", *guards], cacheable=False)["values"]
                if not isinstance(final, dict) or str(final.get("uniqueID", "")).casefold() != target or final.get("type") != actual_type:
                    raise ValueError("Cue identity changed during property reads")
                if any(type(final.get(key)) is not type(value) or final.get(key) != value for key, value in guards.items()):
                    raise ValueError("Cue mode or target changed during conditional reads")
            except Exception as exc:
                result.identity = None
                return _fail(result, f"{family}_cue_identity_mismatch", sanitize_exception_message(exc))
        if cue_type in {"Video", "Camera", "Text", "Light", "Group", "Control", "Fade", "Network", "MIDI", "Timecode", "Script"}:
            values = _redact_payload(values, section=f"{family}_cue", profile=profile, redactions=result.redactions)
        for name, model in detail_models.items():
            setattr(result, name, _section(model, values, result, keys))
        parent = values.get("parent")
        if parent is None:
            result.coverage.unavailable_fields.append("parent")
        else:
            try:
                UUID(parent)
                result.identity.parent_id = parent
            except (ValueError, TypeError, AttributeError):
                result.errors["parent"] = "Invalid parent UUID"
        if input_channel is not None:
            try:
                matrix = result.audio.levels
                if matrix is None or input_channel >= len(matrix) or output_channel >= len(matrix[input_channel]):
                    raise ValueError("Requested crosspoint is unavailable in the returned levels matrix")
                result.level = AudioCrosspoint(input_channel=input_channel, output_channel=output_channel,
                                               value=matrix[input_channel][output_channel])
            except ValueError as exc:
                result.errors["level"] = str(exc)
        result.coverage.notes = ["Audio Maps, Audio Objects, live metrics and indexed effect reads are excluded.",
                                 "Levels are read as one aggregate; crosspoints are never scanned individually.",
                                 "Patch identity is a reference; use workspace Audio Settings for patch configuration.",
                                 f"Containing Cue List context comes from qlab_get_{family}_cues; detail reads only the immediate parent."]
        if cue_type in {"Video", "Camera", "Text"}:
            result.coverage.notes.append("Stage/input references do not expand patches, stages, regions or routes.")
        if cue_type == "Text":
            result.coverage.notes = [note for note in result.coverage.notes if not note.startswith(("Levels", "Patch"))]
        if cue_type in {"Light", "Group", "Control"}:
            result.coverage.notes = [
                f"Containing Cue List context comes from qlab_get_{family}_cues; detail reads the immediate parent.",
                "Read-only cue configuration; no live output is calculated or queried.",
            ]
            if cue_type == "Light":
                result.coverage.notes.append("Light command text is not executed; use workspace Light Settings for patch configuration.")
        if profile == "technical":
            normalized = {key: value for name in detail_models
                          for key, value in getattr(result, name).model_dump(mode="json", exclude_none=True).items()}
            if cue_type in {"Audio", "Video"}:
                formats = values.get("audioTrackFormats")
                if formats is None:
                    result.coverage.unavailable_fields.append("audioTrackFormats")
                elif isinstance(formats, dict):
                    normalized["audioTrackFormats"] = formats
                else:
                    result.errors["audioTrackFormats"] = "Expected a metadata dictionary"
            if cue_type in {"Video", "Camera", "Text"}:
                for key in ("videoEffects", "text/format"):
                    if key in values and key not in result.errors:
                        normalized[key] = values[key]
            result.technical_payload = _redact_payload(normalized,
                section=f"{family}_cue", profile=profile, redactions=result.redactions)
            result.warnings.append("Technical notes and paths may contain sensitive free text.")
        if serialized_payload_bytes(result.model_dump(mode="json")) > max_bytes:
            result.technical_payload = None
            for name in detail_models:
                setattr(result, name, None)
            if hasattr(result, "level"):
                result.level = None
            result.identity = None
            return _fail(result, "cue_payload_too_large", f"{cue_type} detail exceeds the response byte budget")
        return _finish(result)
