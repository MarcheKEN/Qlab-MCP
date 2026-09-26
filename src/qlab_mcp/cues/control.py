"""Read-only control/organization cue family; documented OSC properties only."""

from typing import Annotated, ClassVar, Literal, get_args

from pydantic import BaseModel, Field, JsonValue, StrictBool, StrictInt, StrictStr

from .audio import AudioCueSummary, AudioCuesResult
from .family import _fail
from .list_models import CueListReadResult, FiniteNumber
from .mic import MicBasics, MicTiming
from .limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES, serialized_payload_bytes

ControlCueType = Literal["Start", "Stop", "Pause", "Load", "Reset", "Devamp", "GoTo", "Target", "Arm", "Disarm", "Wait", "Memo"]
CONTROL_TYPES = get_args(ControlCueType)


class ControlCueSummary(AudioCueSummary):
    type: ControlCueType


class ControlCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Control"
    cues: list[ControlCueSummary] = Field(default_factory=list)
    type_filter: ControlCueType | None = None


class ControlBasics(MicBasics):
    defaultName: StrictStr | None = None
    listName: StrictStr | None = None
    secondColorName: StrictStr | None = None
    useSecondColor: StrictBool | None = None
    cartPosition: tuple[StrictInt, StrictInt] | None = None
    allowsEditingDuration: StrictBool | None = None
    hasCueTargets: StrictBool | None = None
    hasFileTargets: StrictBool | None = None
    canHavePatchTargets: StrictBool | None = None
    secondTriggerAction: StrictInt | None = None
    secondTriggerOnRelease: StrictBool | None = None
    duckOthers: StrictBool | None = None
    duckLevel: FiniteNumber | None = None
    duckTime: FiniteNumber | None = None
    # QLab 5.5.10 returns a boolean; the OSC dictionary documents modes 0..3.
    fadeAndStopOthers: StrictBool | Annotated[StrictInt, Field(ge=0, le=3)] | None = None
    fadeAndStopOthersTime: FiniteNumber | None = None


class ControlState(BaseModel):
    armed: StrictBool | None = None
    flagged: StrictBool | None = None
    isBroken: StrictBool | None = None
    isWarning: StrictBool | None = None
    isRunning: StrictBool | None = None
    isPaused: StrictBool | None = None
    isLoaded: StrictBool | None = None
    isActionRunning: StrictBool | None = None
    isAuditioning: StrictBool | None = None
    isOverridden: StrictBool | None = None
    isPanicking: StrictBool | None = None
    isTailingOut: StrictBool | None = None
    isCrossfadingOut: StrictBool | None = None
    isNextInPlaylist: StrictBool | None = None


class ControlTiming(MicTiming):
    model_config = {"populate_by_name": True}
    currentDuration: FiniteNumber | None = None
    tempDuration: FiniteNumber | None = None
    actionElapsed: FiniteNumber | None = None
    percentActionElapsed: FiniteNumber | None = None
    preWaitElapsed: FiniteNumber | None = None
    percentPreWaitElapsed: FiniteNumber | None = None
    postWaitElapsed: FiniteNumber | None = None
    percentPostWaitElapsed: FiniteNumber | None = None
    maxTimeInCueSequence: FiniteNumber | None = None
    timecodeTriggerText: StrictStr | None = Field(default=None, validation_alias="timecodeTrigger/text")


class ControlTarget(BaseModel):
    cueTargetID: StrictStr | None = None
    cueTargetNumber: StrictStr | None = None
    tempCueTargetID: StrictStr | None = None
    tempCueTargetNumber: StrictStr | None = None
    currentCueTargetID: StrictStr | None = None
    currentCueTargetNumber: StrictStr | None = None


class ResetSettings(BaseModel):
    targetMode: Annotated[StrictInt, Field(ge=0, le=1)] | None = None
    patchTargetID: StrictStr | None = None


class DevampSettings(BaseModel):
    devampType: Annotated[StrictInt, Field(ge=1, le=2)] | None = None
    startNextCueWhenSliceEnds: StrictBool | None = None
    stopTargetWhenSliceEnds: StrictBool | None = None


class ControlCueDetailsResult(CueListReadResult):
    cue_type: ClassVar[str] = "Control"
    cue_id: str
    profile: Literal["safe", "technical"] = "safe"
    identity: ControlCueSummary | None = None
    basics: ControlBasics | None = None
    state: ControlState | None = None
    timing: ControlTiming | None = None
    target: ControlTarget | None = None
    reset: ResetSettings | None = None
    devamp: DevampSettings | None = None
    technical_payload: JsonValue = None
    redactions: list[dict[str, str]] = Field(default_factory=list)


def _models(kind):
    models = {"basics": ControlBasics, "state": ControlState, "timing": ControlTiming}
    if kind not in {"Wait", "Memo"}:
        models["target"] = ControlTarget
    if kind == "Reset":
        models["reset"] = ResetSettings
    if kind == "Devamp":
        models["devamp"] = DevampSettings
    return models


class ControlCuesMixin:
    def get_control_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000, cue_type=None):
        if cue_type is not None and cue_type not in CONTROL_TYPES:
            return _fail(ControlCuesResult(workspace_id=str(workspace_id), cue_list_id=str(cue_list_id),
                                          limit=100, offset=0, max_cues_scanned=5000),
                         "validation_failed", "Unknown control cue type")
        result = self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                      ControlCuesResult, ControlCueSummary,
                                      accepted_types=(cue_type,) if cue_type else CONTROL_TYPES)
        result.type_filter = cue_type
        return result

    def get_control_cue_details(self, workspace_id, cue_id, profile="safe"):
        result = self._get_family_details(workspace_id, cue_id, profile, None, None,
                                         ControlCueDetailsResult, ControlCueSummary, _models,
                                         accepted_types=CONTROL_TYPES)
        if result.identity is not None:
            kind = result.identity.type
            if kind == "Load":
                result.coverage.unavailable_via_osc.append("Load cue load time")
            elif kind == "Target":
                result.coverage.unavailable_via_osc.append("Target cue assigned number")
            result.coverage.notes.extend([
                "Audio Maps are excluded. Patch references do not expand Workspace Settings.",
                "OSC coverage is not the entire inspector: Load load time and Target assigned number have no documented OSC read.",
                "Memo notes are included in safe; other notes require technical. No cue action is executed.",
            ])
        if serialized_payload_bytes(result.model_dump(mode="json")) > MAX_SENSITIVE_CUE_RESPONSE_BYTES:
            return _fail(ControlCueDetailsResult(workspace_id=result.workspace_id, cue_id=result.cue_id,
                                                 profile=result.profile),
                         "cue_payload_too_large", "Control detail exceeds the response byte budget")
        return result
