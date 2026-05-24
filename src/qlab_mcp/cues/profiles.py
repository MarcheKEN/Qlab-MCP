"""Cue detail profile helpers and safe derived fields."""

from __future__ import annotations

from typing import Any

from ..osc.addressing import _clean_cue_ref


AUTO_IDENTITY_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "colorName",
    "secondColorName",
    "useSecondColor",
)
AUTO_STRUCTURE_KEYS = (
    "parent",
    "cartPosition",
)
AUTO_STATUS_KEYS = (
    "armed",
    "flagged",
    "isRunning",
    "isPaused",
    "isLoaded",
    "isBroken",
    "isWarning",
    "isActionRunning",
    "isAuditioning",
    "isOverridden",
    "skipIfDisarmed",
    "autoLoad",
)
AUTO_TIMING_KEYS = (
    "preWait",
    "duration",
    "postWait",
    "continueMode",
    "continueModeLabel",
    "timecodeTrigger",
    "timecodeTrigger/text",
)
AUTO_TARGET_KEYS = (
    "hasFileTargets",
    "fileTargetPresent",
    "hasCueTargets",
    "cueTargetID",
    "cueTargetNumber",
    "targetMode",
    "patchTargetID",
    "audioMapTargetID",
)
AUTO_AUDIO_KEYS = (
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
    "audioMap",
    "audioMap/size",
)
AUTO_VIDEO_KEYS = (
    "stageName",
    "stageNumber",
    "stageID",
    "stage/size",
    "stage/uniqueID",
    "translation",
    "scale",
    "opacity",
    "videoEffects",
    "videoInputPatchName",
    "videoInputPatchNumber",
    "videoInputPatchID",
)
AUTO_TEXT_KEYS = (
    *AUTO_VIDEO_KEYS,
    "text",
    "text/fragments",
    "text/outputSize",
)
AUTO_LIGHT_KEYS = (
    "lightCommandText",
    "parameterValues",
    "parameterFadesEnabled",
    "alwaysCollate",
    "subcontroller",
)
AUTO_NETWORK_KEYS = (
    "networkPatchName",
    "networkPatchNumber",
    "networkPatchID",
    "message",
    "messageError",
)
AUTO_MIDI_KEYS = (
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
)
AUTO_TIMECODE_KEYS = (
    "timecodeString",
    "timecodeFormat",
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
)
AUTO_GROUP_KEYS = tuple(sorted(GROUP_KEY for GROUP_KEY in (
    "cartColumns",
    "cartRows",
    "currentTimecode",
    "currentTimecode/text",
    "isChildAuditioning",
    "isChildFlagged",
    "mode",
    "playbackPosition",
    "playbackPositionID",
    "playhead",
    "playheadID",
    "playlist/currentCue",
    "playlist/currentCueID",
    "playlistCrossfade",
    "playlistCrossfadeDuration",
    "playlistLoop",
    "playlistShuffle",
)))
AUTO_FADE_KEYS = (
    "cueTargetID",
    "cueTargetNumber",
    "currentCueTargetID",
    "targetMode",
    "patchTargetID",
    "audioMapTargetID",
    "audioOutputPatchName",
    "audioOutputPatchID",
)
AUTO_TRANSPORT_KEYS = (
    "cueTargetID",
    "cueTargetNumber",
    "currentCueTargetID",
    "currentCueTargetNumber",
    "targetMode",
)
AUTO_TYPE_SPECIFIC_KEYS = {
    "audio": (*AUTO_AUDIO_KEYS,),
    "mic": (*AUTO_AUDIO_KEYS,),
    "video": (*AUTO_VIDEO_KEYS, "audioOutputPatchName", "audioOutputPatchID"),
    "camera": (*AUTO_VIDEO_KEYS, "audioOutputPatchName", "audioOutputPatchID"),
    "text": AUTO_TEXT_KEYS,
    "light": AUTO_LIGHT_KEYS,
    "network": AUTO_NETWORK_KEYS,
    "midi": AUTO_MIDI_KEYS,
    "midi file": AUTO_MIDI_KEYS,
    "timecode": AUTO_TIMECODE_KEYS,
    "group": AUTO_GROUP_KEYS,
    "cue list": AUTO_GROUP_KEYS,
    "cue cart": AUTO_GROUP_KEYS,
    "fade": AUTO_FADE_KEYS,
    "start": AUTO_TRANSPORT_KEYS,
    "stop": AUTO_TRANSPORT_KEYS,
    "pause": AUTO_TRANSPORT_KEYS,
    "load": AUTO_TRANSPORT_KEYS,
    "reset": AUTO_TRANSPORT_KEYS,
    "devamp": AUTO_TRANSPORT_KEYS,
    "go to": AUTO_TRANSPORT_KEYS,
    "goto": AUTO_TRANSPORT_KEYS,
    "target": AUTO_TRANSPORT_KEYS,
    "arm": AUTO_TRANSPORT_KEYS,
    "disarm": AUTO_TRANSPORT_KEYS,
    "wait": (),
    "memo": (),
    "script": (),
}

def _coerce_qlab_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0"}:
            return False
    return None

def _is_positive_number(value: Any) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False

def _derive_profile_fields(profile: str, values: dict[str, Any]) -> dict[str, Any]:
    normalized = profile.strip().lower()
    derived = dict(values)
    if "hasFileTargets" in derived:
        derived["fileTargetPresent"] = bool(_coerce_qlab_bool(derived.get("hasFileTargets")))
    if "continueMode" in derived:
        derived["continueModeLabel"] = _continue_mode_label(derived.get("continueMode"))
    if normalized == "auto":
        for sensitive_key in ("notes", "fileTarget", "scriptSource"):
            derived.pop(sensitive_key, None)
        for heavy_key in ("stage", "stage/regions"):
            derived.pop(heavy_key, None)
    if normalized in {"health", "targets"}:
        derived.pop("fileTarget", None)
    if normalized == "type_specific":
        for sensitive_or_heavy_key in ("notes", "fileTarget", "scriptSource", "stage", "stage/regions"):
            derived.pop(sensitive_or_heavy_key, None)
    if normalized == "full":
        for sensitive_or_heavy_key in ("notes", "fileTarget", "scriptSource", "stage", "stage/regions"):
            derived.pop(sensitive_or_heavy_key, None)
    health_summary = _health_summary(derived)
    if health_summary is not None:
        derived["health_summary"] = health_summary
    return derived


def _continue_mode_label(value: Any) -> str:
    if isinstance(value, bool) or value in (None, ""):
        return "unknown"
    if isinstance(value, int):
        return {0: "do_not_continue", 1: "auto_continue", 2: "auto_follow"}.get(value, "unknown")
    if isinstance(value, float) and value.is_integer():
        return {0: "do_not_continue", 1: "auto_continue", 2: "auto_follow"}.get(int(value), "unknown")

    normalized = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"0", "do_not_continue", "manual", "none"}:
        return "do_not_continue"
    if normalized in {"1", "auto_continue", "autocontinue"}:
        return "auto_continue"
    if normalized in {"2", "auto_follow", "autofollow"}:
        return "auto_follow"
    return "unknown"


def _health_summary(values: dict[str, Any]) -> dict[str, Any] | None:
    has_broken = "isBroken" in values
    has_warning = "isWarning" in values
    if not has_broken and not has_warning and not values.get("messageError"):
        return None

    is_broken = _coerce_qlab_bool(values.get("isBroken")) is True
    is_warning = _coerce_qlab_bool(values.get("isWarning")) is True
    file_target_present = _coerce_qlab_bool(values.get("fileTargetPresent")) is True
    cue_type = str(values.get("type") or "").strip()
    normalized_type = cue_type.casefold()
    messages: list[str] = []
    evidence: list[str] = []
    probable_causes: list[str] = []
    diagnostic_hints: list[str] = []
    needs_human_check: list[str] = []

    if cue_type:
        evidence.append(f"type={cue_type}")
    if has_broken:
        evidence.append(f"isBroken={str(is_broken).lower()}")
    if has_warning:
        evidence.append(f"isWarning={str(is_warning).lower()}")
    if "fileTargetPresent" in values:
        evidence.append(f"fileTargetPresent={str(file_target_present).lower()}")

    if is_broken and normalized_type in {"cue list", "cue cart", "group"}:
        messages.append("Container reports a broken state, likely inherited from one or more broken child cues.")
        probable_causes.append("broken_child_cue_likely")
        diagnostic_hints.append("Query or expand child cues with isBroken=true before editing the container.")
        needs_human_check.append("Open QLab Workspace Status or expand the container to confirm which child cue is broken.")
    elif is_broken and file_target_present:
        messages.append("File target exists but the cue is broken; likely missing, unavailable, or incompatible media.")
        probable_causes.append("file_target_present_but_broken")
        diagnostic_hints.append("Inspect the cue with profile='technical' only if the exact media path is needed.")
        needs_human_check.append("Check that the media volume is mounted and the target file is reachable and supported by QLab.")
    elif is_broken and normalized_type == "light":
        messages.append("Light cue reports a broken state.")
        probable_causes.append("light_cue_reported_broken")
        diagnostic_hints.append("Inspect the light cue command and the workspace light patch before changing cues.")
        needs_human_check.append("Check QLab license, light patch, and physical DMX/Art-Net/sACN output in QLab.")
    elif is_broken:
        messages.append("Cue reports a broken state.")
        probable_causes.append("cue_reported_broken")
        diagnostic_hints.append("Inspect the cue with profile='auto' or 'technical' to gather type-specific context.")
        needs_human_check.append("Open QLab Workspace Status for the exact human-facing reason.")

    if is_warning:
        messages.append("Cue reports a warning state.")
        probable_causes.append("cue_reported_warning")
        diagnostic_hints.append("Review this cue in QLab before assuming the warning affects playback.")
        needs_human_check.append("Decide whether this warning is operationally relevant for the show.")

    message_error = values.get("messageError")
    if message_error not in (None, ""):
        evidence.append("messageError_present")
        messages.append(f"Network/message error reported: {message_error}")
        probable_causes.append("network_message_error")
        diagnostic_hints.append("Inspect the network patch and message payload before assuming the receiver is reachable.")
        needs_human_check.append("Confirm the target application or device receives the network message.")

    if is_broken and is_warning:
        status = "broken_warning"
    elif is_broken:
        status = "broken"
    elif is_warning:
        status = "warning"
    elif messages:
        status = "attention"
    else:
        status = "ok"

    return {
        "status": status,
        "messages": messages,
        "evidence": evidence,
        "probable_causes": probable_causes,
        "diagnostic_hints": diagnostic_hints,
        "needs_human_check": needs_human_check,
        "confidence": "derived",
    }


def _normalized_cue_type(cue_type: Any) -> str:
    return str(cue_type or "").strip().casefold()


def _auto_type_specific_keys(cue_type: Any) -> tuple[str, ...]:
    return tuple(AUTO_TYPE_SPECIFIC_KEYS.get(_normalized_cue_type(cue_type), ()))


def _section_values(values: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: values[key] for key in keys if key in values}


def _build_auto_sections(values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cue_type = values.get("type")
    type_specific_keys = _auto_type_specific_keys(cue_type)
    return {
        "identity": _section_values(values, AUTO_IDENTITY_KEYS),
        "structure": _section_values(values, AUTO_STRUCTURE_KEYS),
        "status": _section_values(values, AUTO_STATUS_KEYS),
        "timing": _section_values(values, AUTO_TIMING_KEYS),
        "targets": _section_values(values, AUTO_TARGET_KEYS),
        "type_specific": _section_values(values, type_specific_keys),
    }


def _empty_auto_sections() -> dict[str, dict[str, Any]]:
    return {
        "identity": {},
        "structure": {},
        "status": {},
        "timing": {},
        "targets": {},
        "type_specific": {},
    }


def _is_active_cue_ref(cue_ref: str) -> bool:
    return _clean_cue_ref(cue_ref).casefold() == "active"
