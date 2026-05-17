"""Read-only cue property allowlist for QLab cue information tools."""

from __future__ import annotations

from .errors import UnsafeCuePropertyError


BASIC_PROPERTIES = {
    "uniqueID",
    "number",
    "name",
    "displayName",
    "defaultName",
    "listName",
    "type",
    "armed",
    "flagged",
    "colorName",
    "secondColorName",
    "useSecondColor",
    "colorCondition",
    "notes",
    "parent",
    "cartPosition",
    "cartPosition/row",
    "cartPosition/column",
}

TIMING_PROPERTIES = {
    "duration",
    "currentDuration",
    "tempDuration",
    "preWait",
    "postWait",
    "actionElapsed",
    "percentActionElapsed",
    "preWaitElapsed",
    "percentPreWaitElapsed",
    "postWaitElapsed",
    "percentPostWaitElapsed",
    "maxTimeInCueSequence",
    "timecodeTrigger",
    "timecodeTrigger/text",
}

STATUS_PROPERTIES = {
    "allowsEditingDuration",
    "autoLoad",
    "isActionRunning",
    "isAuditioning",
    "isBroken",
    "isLoaded",
    "isOverridden",
    "isPanicking",
    "isPaused",
    "isRunning",
    "isTailingOut",
    "isWarning",
    "skipIfDisarmed",
    "secondTriggerAction",
    "secondTriggerOnRelease",
}

TARGET_PROPERTIES = {
    "hasCueTargets",
    "hasFileTargets",
    "canHaveAudioMapTargets",
    "canHavePatchTargets",
    "fileTarget",
    "cueTargetID",
    "cueTargetNumber",
    "currentCueTarget",
    "currentCueTargetID",
    "currentCueTargetNumber",
    "tempCueTargetID",
    "tempCueTargetNumber",
    "targetMode",
    "patchTargetID",
    "audioMapTargetID",
}

GROUP_PROPERTIES = {
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
}

TYPE_SPECIFIC_PROPERTIES = {
    "audioMap",
    "audioMap/size",
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
    "stage",
    "stageName",
    "stageNumber",
    "stageID",
    "stage/size",
    "stage/regions",
    "stage/uniqueID",
    "translation",
    "scale",
    "opacity",
    "videoEffects",
    "videoInputPatchName",
    "videoInputPatchNumber",
    "videoInputPatchID",
    "text",
    "text/fragments",
    "text/outputSize",
    "lightCommandText",
    "networkPatchName",
    "networkPatchNumber",
    "networkPatchID",
    "message",
    "messageError",
    "parameterValues",
    "parameterFadesEnabled",
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
    "timecodeString",
    "timecodeFormat",
    "scriptSource",
}

READ_ONLY_CUE_PROPERTIES = (
    BASIC_PROPERTIES
    | TIMING_PROPERTIES
    | STATUS_PROPERTIES
    | TARGET_PROPERTIES
    | GROUP_PROPERTIES
    | TYPE_SPECIFIC_PROPERTIES
)

SENSITIVE_CUE_PROPERTIES = {
    "notes",
    "fileTarget",
    "scriptSource",
}

BASIC_SAFE_PROFILE = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "type",
    "armed",
    "flagged",
    "colorName",
)

TECHNICAL_PROFILE = (
    *BASIC_SAFE_PROFILE,
    "notes",
    "parent",
    "cartPosition",
    "duration",
    "preWait",
    "postWait",
    "isRunning",
    "isPaused",
    "isLoaded",
    "isBroken",
    "isWarning",
    "hasFileTargets",
    "hasCueTargets",
    "fileTarget",
    "cueTargetID",
    "cueTargetNumber",
    "targetMode",
    "patchTargetID",
    "audioOutputPatchName",
    "stageName",
    "networkPatchName",
    "message",
    "messageError",
    "lightCommandText",
)

HEALTH_PROFILE = (
    *BASIC_SAFE_PROFILE,
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "isLoaded",
    "hasFileTargets",
    "hasCueTargets",
    "fileTarget",
    "cueTargetNumber",
    "patchTargetID",
    "messageError",
)

PROFILE_PROPERTIES = {
    "basic_safe": BASIC_SAFE_PROFILE,
    "basic": (
        "uniqueID",
        "number",
        "name",
        "displayName",
        "type",
        "armed",
        "flagged",
        "colorName",
        "notes",
    ),
    "technical": tuple(dict.fromkeys(TECHNICAL_PROFILE)),
    "health": tuple(dict.fromkeys(HEALTH_PROFILE)),
    "timing": (
        "duration",
        "currentDuration",
        "preWait",
        "postWait",
        "actionElapsed",
        "percentActionElapsed",
        "preWaitElapsed",
        "percentPreWaitElapsed",
        "postWaitElapsed",
        "percentPostWaitElapsed",
    ),
    "status": (
        "isRunning",
        "isPaused",
        "isLoaded",
        "isBroken",
        "isWarning",
        "isActionRunning",
    ),
    "targets": (
        "fileTarget",
        "cueTargetID",
        "cueTargetNumber",
        "currentCueTargetID",
        "targetMode",
        "patchTargetID",
    ),
    "group": tuple(sorted(GROUP_PROPERTIES)),
    "type_specific": tuple(sorted(TYPE_SPECIFIC_PROPERTIES)),
}

BLOCKED_VALUE_KEYS = {
    "auditionGo",
    "auditionPreview",
    "captureTimecode",
    "collapse",
    "collateAndStart",
    "compileSource",
    "delete",
    "expand",
    "go",
    "hardPause",
    "hardStop",
    "load",
    "loadAndSetPlayhead",
    "panic",
    "pause",
    "preview",
    "reset",
    "resume",
    "start",
    "startAndAutoloadNext",
    "stop",
    "togglePause",
}


def validate_property_path(property_path: str) -> str:
    normalized = property_path.strip().strip("/")
    if not normalized:
        raise UnsafeCuePropertyError("Cue property path cannot be empty")
    if any(part in {"..", ""} for part in normalized.split("/")):
        raise UnsafeCuePropertyError(f"Unsafe cue property path: {property_path!r}")
    if normalized not in READ_ONLY_CUE_PROPERTIES:
        raise UnsafeCuePropertyError(f"Cue property is not allowlisted for read-only access: {normalized}")
    return normalized


def properties_for_profile(profile: str) -> tuple[str, ...]:
    normalized = profile.strip().lower()
    if normalized in {"full", "full_sensitive"}:
        merged: list[str] = []
        for key in ("basic", "timing", "status", "targets", "group", "type_specific"):
            merged.extend(PROFILE_PROPERTIES[key])
        properties = tuple(dict.fromkeys(merged))
        if normalized == "full":
            return tuple(prop for prop in properties if prop not in SENSITIVE_CUE_PROPERTIES)
        return properties
    if normalized not in PROFILE_PROPERTIES:
        allowed = ", ".join([*PROFILE_PROPERTIES.keys(), "full", "full_sensitive"])
        raise UnsafeCuePropertyError(f"Unknown cue detail profile {profile!r}; use one of: {allowed}")
    return PROFILE_PROPERTIES[normalized]


def validate_value_keys(keys: list[str] | tuple[str, ...]) -> list[str]:
    if not keys:
        raise UnsafeCuePropertyError("At least one cue value key is required")
    if len(keys) > 100:
        raise UnsafeCuePropertyError("At most 100 cue value keys can be read in one request")

    normalized: list[str] = []
    for key in keys:
        if not isinstance(key, str):
            raise UnsafeCuePropertyError("Cue value keys must be strings")
        value = key.strip().strip("/")
        if not value:
            raise UnsafeCuePropertyError("Cue value keys cannot be empty")
        if any(part in {"", ".."} for part in value.split("/")):
            raise UnsafeCuePropertyError(f"Unsafe cue value key: {key!r}")
        if value in BLOCKED_VALUE_KEYS or value.split("/", 1)[0] in BLOCKED_VALUE_KEYS:
            raise UnsafeCuePropertyError(f"Cue value key is not read-only: {value}")
        if value not in READ_ONLY_CUE_PROPERTIES:
            raise UnsafeCuePropertyError(f"Cue value key is not allowlisted for read-only access: {value}")
        normalized.append(value)
    return normalized

