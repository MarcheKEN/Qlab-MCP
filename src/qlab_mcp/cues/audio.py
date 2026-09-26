"""Scoped Audio inventory and exact, bounded Audio details using shared readers."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field, JsonValue, StrictBool, StrictInt, StrictStr

from .list_models import CueListReadResult, CueListState, CueTimecodeComponents, FiniteNumber
from .limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES
from .family import AudioCrosspoint, Level


Channel = Annotated[StrictInt, Field(ge=0, le=128)]


class AudioCueSummary(BaseModel):
    uniqueID: StrictStr
    type: Literal["Audio"]
    number: StrictStr | None = None
    name: StrictStr | None = None
    displayName: StrictStr | None = None
    parent_id: StrictStr | None = None
    cue_list_id: StrictStr | None = None
    armed: StrictBool | None = None
    flagged: StrictBool | None = None
    isBroken: StrictBool | None = None
    isWarning: StrictBool | None = None


class AudioCuesResult(CueListReadResult):
    cue_type: ClassVar[str] = "Audio"
    cue_list_id: str
    cues: list[AudioCueSummary] = Field(default_factory=list)
    limit: int
    offset: int
    max_cues_scanned: int
    scanned_count: int = 0
    matched_count: int = 0
    returned_count: int = 0
    scan_complete: bool = False
    has_more: bool = False
    next_offset: int | None = None
    truncated: bool = False
    truncation_reasons: list[str] = Field(default_factory=list)


class AudioTiming(BaseModel):
    preWait: FiniteNumber | None = None
    duration: FiniteNumber | None = None
    postWait: FiniteNumber | None = None
    continueMode: StrictInt | None = None
    startTime: FiniteNumber | None = None
    endTime: FiniteNumber | None = None
    rate: FiniteNumber | None = None
    preservePitch: StrictBool | None = None
    playCount: StrictInt | None = None
    infiniteLoop: StrictBool | None = None
    lastSlicePlayCount: StrictInt | None = None
    lastSliceInfiniteLoop: StrictBool | None = None
    timecodeTrigger: CueTimecodeComponents | None = None


class AudioSlice(BaseModel):
    time: FiniteNumber
    playCount: StrictInt


class AudioSettings(BaseModel):
    audioOutputPatchID: StrictStr | None = None
    audioOutputPatchName: StrictStr | None = None
    audioOutputPatchNumber: StrictInt | None = None
    numChannelsIn: StrictInt | None = None
    levels: list[list[Level]] | None = None
    sliderLevels: list[Level] | None = None
    muteChannels: list[Channel] | None = None
    soloChannels: list[Channel] | None = None
    sliceMarkers: list[AudioSlice] | None = None


class AudioBasics(BaseModel):
    colorName: StrictStr | None = None
    autoLoad: StrictBool | None = None
    skipIfDisarmed: StrictBool | None = None
    hasFileTargets: StrictBool | None = None
    fileTarget: StrictStr | None = None
    notes: StrictStr | None = None


class AudioCueDetailsResult(CueListReadResult):
    cue_type: ClassVar[str] = "Audio"
    cue_id: str
    profile: Literal["safe", "technical"] = "safe"
    identity: AudioCueSummary | None = None
    basics: AudioBasics | None = None
    state: CueListState | None = None
    timing: AudioTiming | None = None
    audio: AudioSettings | None = None
    level: AudioCrosspoint | None = None
    technical_payload: JsonValue = None
    redactions: list[dict[str, str]] = Field(default_factory=list)


DETAIL_MODELS = {"basics": AudioBasics, "state": CueListState, "timing": AudioTiming, "audio": AudioSettings}


class AudioCuesMixin:
    def get_audio_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                     AudioCuesResult, AudioCueSummary)

    def get_audio_cue_details(self, workspace_id, cue_id, profile="safe", input_channel=None, output_channel=None):
        return self._get_family_details(workspace_id, cue_id, profile, input_channel, output_channel,
                                        AudioCueDetailsResult, AudioCueSummary, DETAIL_MODELS,
                                        max_bytes=MAX_SENSITIVE_CUE_RESPONSE_BYTES)
