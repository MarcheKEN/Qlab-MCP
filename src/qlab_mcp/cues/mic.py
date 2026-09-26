"""Mic-specific contracts over the shared scoped Audio/Mic reader."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr

from .audio import AudioCueSummary, AudioCuesResult, AudioCueDetailsResult, Channel, Level
from .list_models import CueListState, CueTimecodeComponents, FiniteNumber


class MicCueSummary(AudioCueSummary):
    type: Literal["Mic"]


class MicCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Mic"
    cues: list[MicCueSummary] = Field(default_factory=list)


class MicBasics(BaseModel):
    colorName: StrictStr | None = None
    autoLoad: StrictBool | None = None
    skipIfDisarmed: StrictBool | None = None
    notes: StrictStr | None = None


class MicTiming(BaseModel):
    preWait: FiniteNumber | None = None
    duration: FiniteNumber | None = None
    postWait: FiniteNumber | None = None
    continueMode: StrictInt | None = None
    timecodeTrigger: CueTimecodeComponents | None = None


class MicSettings(BaseModel):
    audioInputPatchID: StrictStr | None = None
    audioInputPatchName: StrictStr | None = None
    audioInputPatchNumber: StrictInt | None = None
    audioOutputPatchID: StrictStr | None = None
    audioOutputPatchName: StrictStr | None = None
    audioOutputPatchNumber: StrictInt | None = None
    channels: Annotated[StrictInt, Field(ge=1)] | None = None
    channelOffset: Annotated[StrictInt, Field(ge=0)] | None = None
    levels: list[list[Level]] | None = None
    sliderLevels: list[Level] | None = None
    muteChannels: list[Channel] | None = None
    soloChannels: list[Channel] | None = None


class MicCueDetailsResult(AudioCueDetailsResult):
    cue_type: ClassVar[str] = "Mic"
    identity: MicCueSummary | None = None
    basics: MicBasics | None = None
    timing: MicTiming | None = None
    audio: MicSettings | None = None


DETAIL_MODELS = {"basics": MicBasics, "state": CueListState, "timing": MicTiming, "audio": MicSettings}


class MicCuesMixin:
    def get_mic_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                          MicCuesResult, MicCueSummary)

    def get_mic_cue_details(self, workspace_id, cue_id, profile="safe", input_channel=None, output_channel=None):
        return self._get_family_details(workspace_id, cue_id, profile, input_channel, output_channel,
                                             MicCueDetailsResult, MicCueSummary, DETAIL_MODELS)
