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
    "continueMode",
    "timecodeTrigger",
    "timecodeTrigger/hours",
    "timecodeTrigger/minutes",
    "timecodeTrigger/seconds",
    "timecodeTrigger/frames",
    "timecodeTrigger/bits",
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
    "duckLevel",
    "duckOthers",
    "duckTime",
    "fadeAndStopOthers",
    "fadeAndStopOthersTime",
}

TARGET_PROPERTIES = {
    "hasCueTargets",
    "hasFileTargets",
    "canHaveAudioMapTargets",
    "canHavePatchTargets",
    "fileTarget",
    "cueTargetID",
    "cueTargetNumber",
    "cueTargetName",
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
    "playlist/doLoop",
    "playlist/doShuffle",
    "playlist/doCrossfade",
    "playlist/crossfade/duration",
    "playlistLoop",
    "playlistShuffle",
    "timecodeFreewheelTime",
    "timecodeLookbackTime",
    "timecodeSMPTEFormat",
    "timecodeStartBehavior",
    "timecodeStopBehavior",
    "timecodeSyncMode",
}

TYPE_SPECIFIC_PROPERTIES = {
    "audioMap",
    "audioMapName",
    "audioMapNumber",
    "audioMapID",
    "audioMap/size",
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
    "audioInputPatchName",
    "audioInputPatchNumber",
    "audioInputPatchID",
    "audioOutputPatch/name",
    "videoOutputPatchName",
    "videoOutputPatchNumber",
    "videoOutputPatchID",
    "rate",
    "startTime",
    "endTime",
    "playCount",
    "infiniteLoop",
    "preservePitch",
    "doFade",
    "lockFadeToCue",
    "lastSlicePlayCount",
    "lastSliceInfiniteLoop",
    "channelOffset",
    "channels",
    "stage",
    "stageName",
    "stageNumber",
    "stageID",
    "stage/size",
    "stage/regions",
    "stage/uniqueID",
    "anchor/x",
    "anchor/y",
    "translation",
    "translation/x",
    "translation/y",
    "scale",
    "scale/x",
    "scale/y",
    "rotation",
    "opacity",
    "cropTop",
    "cropBottom",
    "cropLeft",
    "cropRight",
    "blendMode",
    "clockType",
    "videoEffects",
    "surfaceID",
    "surfaceName",
    "videoInputPatchName",
    "videoInputPatchNumber",
    "videoInputPatchID",
    "fixedWidth",
    "text",
    "text/fragments",
    "text/outputSize",
    "text/format/alignment",
    "text/format/fontName",
    "text/format/fontSize",
    "text/format/underlineStyle",
    "text/format/strikethroughStyle",
    "lightCommandText",
    "customString",
    "resend",
    "networkPatchName",
    "networkPatchNumber",
    "networkPatchID",
    "message",
    "messageError",
    "protocol",
    "parameterValues",
    "parameterFadesEnabled",
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
    "messageType",
    "channel",
    "command",
    "commandFormat",
    "status",
    "note",
    "velocity",
    "programChange",
    "pitchBend",
    "byte1",
    "byte2",
    "byteCombo",
    "controlNumber",
    "controlValue",
    "deviceID",
    "endValue",
    "macro",
    "rawString",
    "qList",
    "qNumber",
    "qPath",
    "timecodeString",
    "timecodeFormat",
    "timecodeMode",
    "outputType",
    "timecodeFrameRate",
    "framerate",
    "ltcChannel",
    "patch",
    "cameraPatch",
    "devampType",
    "startNextCueWhenSliceEnds",
    "stopTargetWhenDone",
    "levelsMode",
    "geoMode",
    "pathHeight",
    "pathWidth",
    "rotationType",
    "doOpacity",
    "doRate",
    "doRotation",
    "doScale",
    "doTranslation",
    "stopTargetWhenSliceEnds",
    "scriptSource",
    "scriptText",
    "alwaysCollate",
    "subcontroller",
}

EXHAUSTIVE_EXTRA_PROPERTIES = {
    "audioMap/filters",
    "audioMap/marks",
    "audioMap/objects",
    "audioMap/size/height",
    "audioMap/size/width",
    "audioMap/uniqueID",
    "audioOutputPatch",
    "audioOutputPatch/cueOutputChannels",
    "audioOutputPatch/muteChannels",
    "audioOutputPatch/routing",
    "levels",
    "muteChannels",
    "muteObjects",
    "numChannelsIn",
    "objectLevels",
    "objects",
    "sliderLevels",
    "sliceMarkers",
    "soloChannels",
    "soloObjects",
    "stage/name",
    "anchor",
    "cueSize",
    "cueSize/height",
    "cueSize/width",
    "fillStage",
    "fillStyle",
    "holdLastFrame",
    "layer",
    "origin",
    "origin/x",
    "origin/y",
    "preserveAspectRatio",
    "quaternion",
    "smooth",
    "text/format",
    "text/outputSize/height",
    "text/outputSize/width",
    "text/format/backgroundColor",
    "text/format/color",
    "text/format/fontFamily",
    "text/format/fontFamilyAndStyle",
    "text/format/fontStyle",
    "text/format/lineSpacing",
    "text/format/shadowBlurRadius",
    "text/format/shadowColor",
    "text/format/shadowOffset",
    "text/format/shadowOffset/height",
    "text/format/shadowOffset/width",
    "text/format/strikethroughColor",
    "text/format/underlineColor",
    "fadeNumberType",
    "fadeEntries",
    "fadeFrom",
    "fadeTo",
    "fadeType",
    "fps",
    "hours",
    "minutes",
    "seconds",
    "frames",
    "subframes",
    "devampType",
    "startNextCueWhenSliceEnds",
}

HEAVY_CUE_PROPERTIES = {
    "stage",
    "stage/regions",
}

READ_ONLY_CUE_PROPERTIES = (
    BASIC_PROPERTIES
    | TIMING_PROPERTIES
    | STATUS_PROPERTIES
    | TARGET_PROPERTIES
    | GROUP_PROPERTIES
    | TYPE_SPECIFIC_PROPERTIES
    | EXHAUSTIVE_EXTRA_PROPERTIES
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

AUTO_COMMON_PROFILE = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "colorName",
    "secondColorName",
    "useSecondColor",
    "parent",
    "cartPosition",
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
    "preWait",
    "duration",
    "postWait",
    "continueMode",
    "timecodeTrigger",
    "timecodeTrigger/text",
    "hasFileTargets",
    "hasCueTargets",
    "cueTargetID",
    "cueTargetNumber",
    "targetMode",
    "patchTargetID",
    "audioMapTargetID",
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
    "stage",
    "stageName",
    "stage/regions",
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
    "cueTargetNumber",
    "patchTargetID",
    "messageError",
)

INSPECTOR_SAFE_PROFILE = tuple(
    dict.fromkeys(
        (
            *AUTO_COMMON_PROFILE,
            "defaultName",
            "colorCondition",
            "cartPosition/row",
            "cartPosition/column",
            *tuple(sorted(TIMING_PROPERTIES)),
            *tuple(sorted(STATUS_PROPERTIES)),
            *tuple(sorted(TARGET_PROPERTIES - SENSITIVE_CUE_PROPERTIES)),
            *tuple(sorted(GROUP_PROPERTIES)),
            *tuple(sorted(TYPE_SPECIFIC_PROPERTIES - SENSITIVE_CUE_PROPERTIES - HEAVY_CUE_PROPERTIES)),
            "cueSize",
            "cueSize/width",
            "cueSize/height",
            "text/outputSize/width",
            "text/outputSize/height",
        )
    )
)

PROFILE_PROPERTIES = {
    "auto": AUTO_COMMON_PROFILE,
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
        "hasFileTargets",
        "hasCueTargets",
        "cueTargetID",
        "cueTargetNumber",
        "currentCueTargetID",
        "targetMode",
        "patchTargetID",
        "audioMapTargetID",
    ),
    "group": tuple(sorted(GROUP_PROPERTIES)),
    "type_specific": tuple(sorted(TYPE_SPECIFIC_PROPERTIES - SENSITIVE_CUE_PROPERTIES - HEAVY_CUE_PROPERTIES)),
    "inspector_safe": INSPECTOR_SAFE_PROFILE,
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
    if normalized == "exhaustive":
        return tuple(sorted(READ_ONLY_CUE_PROPERTIES))
    if normalized == "full_sensitive":
        merged: list[str] = []
        for key in ("basic", "timing", "status", "targets", "group", "type_specific"):
            merged.extend(PROFILE_PROPERTIES[key])
        merged.extend(sorted(SENSITIVE_CUE_PROPERTIES | HEAVY_CUE_PROPERTIES))
        return tuple(dict.fromkeys(merged))
    if normalized == "full":
        merged: list[str] = []
        for key in ("basic", "timing", "status", "targets", "group", "type_specific"):
            merged.extend(PROFILE_PROPERTIES[key])
        properties = tuple(dict.fromkeys(merged))
        return tuple(prop for prop in properties if prop not in SENSITIVE_CUE_PROPERTIES and prop not in HEAVY_CUE_PROPERTIES)
    if normalized not in PROFILE_PROPERTIES:
        allowed = ", ".join([*PROFILE_PROPERTIES.keys(), "full", "full_sensitive", "exhaustive"])
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

