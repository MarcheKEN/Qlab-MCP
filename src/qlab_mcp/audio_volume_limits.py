"""Guarded QLab 5.5.10 workspace Audio Volume Limits archive edits."""
from __future__ import annotations

import math
import struct
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, TypeAdapter, model_validator

from . import workspace_documents as docs
from .audio_effect_integrity import capture_effects, effects_match
from .light_patch.archive import Archive
from .osc.addressing import _workspace_address
from .sanitizer import sanitize_exception_message


_DB_VALUE = Annotated[StrictInt | StrictFloat, Field(allow_inf_nan=False)]
_MIN_VOLUME_RANGE = (-180.0, -40.0)
_MAX_VOLUME_RANGE = (-30.0, 60.0)
_RANGE_WARNING = (
    "Volume-limit endpoints were verified after saving and reopening a QLab 5.5.10/build 5510 "
    "copy; this does not verify audio playback or physical output."
)
__all__ = ["SetAudioVolumeLimits", "edit_audio_volume_limits"]


class SetAudioVolumeLimits(BaseModel):
    """Set one or both workspace Audio Volume Limits in dB."""

    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["set_volume_limits"]
    min_volume: _DB_VALUE | None = None
    max_volume: _DB_VALUE | None = None

    @model_validator(mode="after")
    def validate_values(self):
        if self.min_volume is None and self.max_volume is None:
            raise ValueError("At least one of min_volume or max_volume is required.")
        _validate_bound("min_volume", self.min_volume, _MIN_VOLUME_RANGE)
        _validate_bound("max_volume", self.max_volume, _MAX_VOLUME_RANGE)
        if (self.min_volume is not None and self.max_volume is not None
                and self.min_volume >= self.max_volume):
            raise ValueError("min_volume must be less than max_volume.")
        return self


def _validate_bound(name: str, value, bounds: tuple[float, float]) -> None:
    if value is None:
        return
    if (type(value) not in (int, float)
            or (type(value) is float and not math.isfinite(value))
            or value < bounds[0] or value > bounds[1]):
        raise ValueError(f"{name} must be between {bounds[0]:g} and {bounds[1]:g} dB.")


def _resolved(archive: Archive, value):
    value = archive.ref(value)
    if isinstance(value, dict) and "NS.string" in value:
        value = archive.ref(value["NS.string"])
    return value


def _finite_db(value, field: str) -> float:
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)):
        raise ValueError(f"Saved Audio {field} is missing or is not a finite number.")
    try:
        return float(value)
    except OverflowError as exc:
        raise ValueError(f"Saved Audio {field} is missing or is not a finite number.") from exc


def _osc_float32(value, field: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{field} is not a finite OSC number.")
    try:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{field} is not a finite OSC number.")
        encoded = struct.pack(">f", number)
        rounded = struct.unpack(">f", encoded)[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError(f"{field} is outside the finite OSC float32 range.") from exc
    if not math.isfinite(rounded):
        raise ValueError(f"{field} is outside the finite OSC float32 range.")
    return rounded


def _audio_data(source: bytes):
    outer = Archive(source)
    meta = outer.mapping(outer.root)
    build = _resolved(outer, meta.get("QLabBuildNumber"))
    version = _resolved(outer, meta.get("QLabShortVersionString"))
    if type(build) is not int or build != 5510 or version != "5.5.10":
        raise ValueError("Audio Volume Limits editing requires the QLab 5.5.10 archive format, build 5510.")
    try:
        workspace_id = str(UUID(str(_resolved(outer, meta["uniqueID"])))).upper()
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("Saved workspace UUID is invalid.") from exc

    settings = outer.mapping(meta["settings"])
    try:
        general = outer.mapping(settings["General"])
        audio_ref = settings["Audio"]
        audio = outer.mapping(audio_ref)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Saved General/Audio workspace settings are unavailable.") from exc
    if any(_resolved(outer, general.get(key)) is not False
           for key in ("doStartOnOpen", "doStartOnClose")):
        raise ValueError("Workspace automatic open/close cues must be known disabled.")
    if "minVolume" not in audio or "maxVolume" not in audio:
        raise ValueError("Saved Audio minVolume/maxVolume are unavailable.")

    minimum = _finite_db(_resolved(outer, audio["minVolume"]), "minVolume")
    maximum = _finite_db(_resolved(outer, audio["maxVolume"]), "maxVolume")
    audio_object = outer.ref(audio_ref)
    if (not isinstance(audio_object, dict) or not isinstance(audio_object.get("NS.keys"), list)
            or not isinstance(audio_object.get("NS.objects"), list)):
        raise ValueError("Saved Audio settings are not a supported keyed dictionary.")
    keys = [_resolved(outer, key) for key in audio_object["NS.keys"]]
    if (not all(type(key) is str for key in keys) or len(keys) != len(set(keys))
            or len(keys) != len(audio_object["NS.objects"])):
        raise ValueError("Saved Audio settings contain invalid or duplicate keys.")
    return outer, workspace_id, audio_object, keys, minimum, maximum


def _cue_archive(outer: Archive) -> Archive:
    try:
        meta = outer.mapping(outer.root)
        carrier = outer.ref(meta["cueLists"])
        data = carrier.get("NS.data") if isinstance(carrier, dict) else None
        if not isinstance(data, bytes):
            raise ValueError
        return Archive(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Saved cue archive is unavailable for Audio effect preservation checks.") from exc


def _summary(workspace_id: str, minimum: float, maximum: float) -> dict:
    return {"workspace_id": workspace_id, "min_volume": minimum, "max_volume": maximum}


def plan_audio_volume_limits(source: bytes, operations: list[dict]) -> dict:
    """Plan one typed min/max edit while preserving the rest of the workspace."""
    if not isinstance(operations, list) or len(operations) not in (0, 1):
        raise ValueError("Exactly one set_volume_limits operation is supported.")
    parsed = TypeAdapter(SetAudioVolumeLimits).validate_python(operations[0]) if operations else None
    outer, workspace_id, audio_object, keys, current_min, current_max = _audio_data(source)
    effects = capture_effects(outer, _cue_archive(outer))
    audio_other_fields = {
        key: audio_object["NS.objects"][index]
        for index, key in enumerate(keys)
        if key not in {"minVolume", "maxVolume"}
    }

    minimum = current_min if parsed is None or parsed.min_volume is None else float(parsed.min_volume)
    maximum = current_max if parsed is None or parsed.max_volume is None else float(parsed.max_volume)
    _validate_bound("min_volume", minimum, _MIN_VOLUME_RANGE)
    _validate_bound("max_volume", maximum, _MAX_VOLUME_RANGE)
    if minimum >= maximum:
        raise ValueError("min_volume must be less than max_volume.")

    requested = {}
    if parsed is not None:
        if parsed.min_volume is not None and minimum != current_min:
            requested["minVolume"] = minimum
        if parsed.max_volume is not None and maximum != current_max:
            requested["maxVolume"] = maximum
    if requested:
        for key, value in requested.items():
            index = keys.index(key)
            audio_object["NS.objects"][index] = outer.add(value)
        output = outer.dump()
    else:
        output = source

    changes = []
    if requested:
        changes.append({
            "action": "set_volume_limits",
            **({"min_volume": minimum} if "minVolume" in requested else {}),
            **({"max_volume": maximum} if "maxVolume" in requested else {}),
        })
    summary = _summary(workspace_id, minimum, maximum)
    return {
        "output_bytes": output,
        "workspace_id": workspace_id,
        "summary": summary,
        "changes": changes,
        "affected_cues": [],
        "warnings": [_RANGE_WARNING],
        "effect_snapshot": effects,
        "audio_other_fields": audio_other_fields,
    }


def _postcondition(source: bytes, plan: dict) -> bool:
    try:
        outer, workspace_id, audio_object, keys, minimum, maximum = _audio_data(source)
        if (workspace_id != plan["workspace_id"]
                or _summary(workspace_id, minimum, maximum) != plan["summary"]):
            return False
        other_fields = {
            key: audio_object["NS.objects"][index]
            for index, key in enumerate(keys)
            if key not in {"minVolume", "maxVolume"}
        }
        return (other_fields == plan["audio_other_fields"]
                and effects_match(source, plan["effect_snapshot"]))
    except (IndexError, KeyError, TypeError, ValueError, OverflowError):
        return False


def _verify_live(reader, workspace_id: str, summary: dict) -> dict:
    from .runtime.read_cache import shared_read_cache

    shared_read_cache().clear()
    values = {}
    for field, key in (("minimum", "minVolume"), ("maximum", "maxVolume")):
        address = _workspace_address(workspace_id, f"settings/audio/{key}")
        try:
            value = reader._request(address, workspace_id=workspace_id).data
        except Exception as exc:
            raise ValueError("Fresh OSC audio volume limits readback is unavailable.") from exc
        values[field] = _osc_float32(value, "Fresh OSC audio volume limits readback")
    if (summary.get("workspace_id") != workspace_id
            or values["minimum"] != _osc_float32(summary.get("min_volume"), "Planned minimum volume")
            or values["maximum"] != _osc_float32(summary.get("max_volume"), "Planned maximum volume")):
        raise ValueError("Fresh OSC volume limits do not match the saved archive plan.")
    return {"workspace_id": workspace_id, **values,
            "scope": "Fresh OSC reads of settings/audio/minVolume and settings/audio/maxVolume."}


def edit_audio_volume_limits(
    reader,
    workspace_id: str,
    operation: SetAudioVolumeLimits | dict,
    dry_run: bool = True,
    confirm_token: str | None = None,
) -> dict:
    """Run the guarded same-path archive transaction for workspace Audio limits."""
    from .workspace_archive import edit_archive

    try:
        workspace_id = docs._uuid(workspace_id)
        parsed = TypeAdapter(SetAudioVolumeLimits).validate_python(operation)
        operations = [parsed.model_dump(exclude_none=True)]
        result = edit_archive(
            reader,
            workspace_id,
            operations,
            dry_run,
            confirm_token,
            planner=plan_audio_volume_limits,
            token_family="audioVolumeLimits",
            postcondition=_postcondition,
            live_verifier=_verify_live,
        )
    except Exception as exc:
        result = {
            "ok": False,
            "status": "blocked",
            "planned_operations": [],
            "executed_operations": [],
            "error": sanitize_exception_message(exc),
        }
    result["volume_limit_bounds_scope"] = _RANGE_WARNING
    result["native_audio_volume_limits_verified"] = result.pop("native_patch_verified", False)
    result.pop("native_patch_verification_scope", None)
    if result["native_audio_volume_limits_verified"]:
        result["verification_scope"] = (
            "Saved Audio minVolume/maxVolume and unchanged Audio fields/effect graph after reopen; "
            "fresh OSC readback of both Volume Limits."
        )
    else:
        result["verification_scope"] = (
            "Dry-run archive plan and fresh OSC baseline readback; proposed Volume Limits are not "
            "verified as applied."
        )
    return result
