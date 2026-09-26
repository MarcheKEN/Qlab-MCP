"""Light and Group reads over shared family and container readers."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field, JsonValue, StrictBool, StrictInt, StrictStr

from .audio import AudioCueSummary, AudioCuesResult
from .mic import MicBasics, MicTiming
from .list_models import CueListReadResult, CueListState, CueListContents, FiniteNumber
from .family import _fail, _section
from .lists import _contents, _finish
from .limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES, serialized_payload_bytes
from ..sanitizer import sanitize_exception_message


class LightCueSummary(AudioCueSummary):
    type: Literal["Light"]


class GroupCueSummary(AudioCueSummary):
    type: Literal["Group"]


class LightCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Light"
    cues: list[LightCueSummary] = Field(default_factory=list)


class GroupCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Group"
    cues: list[GroupCueSummary] = Field(default_factory=list)


class LightSettings(BaseModel):
    lightCommandText: StrictStr | None = None
    alwaysCollate: StrictBool | None = None
    subcontroller: StrictBool | None = None


class GroupSettings(BaseModel):
    mode: Annotated[StrictInt, Field(ge=1, le=6)] | None = None
    isChildAuditioning: StrictBool | None = None
    isChildFlagged: StrictBool | None = None


class PlaylistSettings(BaseModel):
    model_config = {"populate_by_name": True}
    currentCue: StrictStr | None = Field(default=None, validation_alias="playlist/currentCue")
    currentCueID: StrictStr | None = Field(default=None, validation_alias="playlist/currentCueID")
    doCrossfade: StrictBool | None = Field(default=None, validation_alias="playlist/doCrossfade")
    doLoop: StrictBool | None = Field(default=None, validation_alias="playlist/doLoop")
    doShuffle: StrictBool | None = Field(default=None, validation_alias="playlist/doShuffle")
    crossfadeDuration: Annotated[FiniteNumber, Field(ge=0)] | None = Field(default=None, validation_alias="playlist/crossfade/duration")


class LightCueDetailsResult(CueListReadResult):
    cue_type: ClassVar[str] = "Light"
    cue_id: str
    profile: Literal["safe", "technical"] = "safe"
    identity: LightCueSummary | None = None
    basics: MicBasics | None = None
    state: CueListState | None = None
    timing: MicTiming | None = None
    light: LightSettings | None = None
    technical_payload: JsonValue = None
    redactions: list[dict[str, str]] = Field(default_factory=list)


class GroupCueDetailsResult(CueListReadResult):
    cue_type: ClassVar[str] = "Group"
    cue_id: str
    profile: Literal["safe", "technical"] = "safe"
    identity: GroupCueSummary | None = None
    basics: MicBasics | None = None
    state: CueListState | None = None
    timing: MicTiming | None = None
    group: GroupSettings | None = None
    mode_label: str | None = None
    playlist: PlaylistSettings | None = None
    contents: CueListContents | None = None
    technical_payload: JsonValue = None
    redactions: list[dict[str, str]] = Field(default_factory=list)


COMMON_MODELS = {"basics": MicBasics, "state": CueListState, "timing": MicTiming}
MODES = {1: "Start first and enter", 2: "Start first", 3: "Timeline", 4: "Start random", 6: "Playlist"}


class LightGroupCuesMixin:
    def get_light_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                    LightCuesResult, LightCueSummary)

    def get_group_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                    GroupCuesResult, GroupCueSummary)

    def get_light_cue_details(self, workspace_id, cue_id, profile="safe"):
        return self._get_family_details(workspace_id, cue_id, profile, None, None,
                                       LightCueDetailsResult, LightCueSummary,
                                       {**COMMON_MODELS, "light": LightSettings})

    def get_group_cue_details(self, workspace_id, cue_id, profile="safe", max_depth=2, max_cues=1000):
        if type(max_depth) is not int or not 0 <= max_depth <= 5 or type(max_cues) is not int or not 1 <= max_cues <= 5000:
            return _fail(GroupCueDetailsResult(workspace_id=str(workspace_id), cue_id=str(cue_id)),
                         "validation_failed", "Invalid container limits")
        result = self._get_family_details(workspace_id, cue_id, profile, None, None,
                                         GroupCueDetailsResult, GroupCueSummary,
                                         {**COMMON_MODELS, "group": GroupSettings})
        if result.identity is None:
            return result
        mode = result.group.mode
        if mode not in MODES:
            return _fail(result, "group_cue_payload_invalid", "Invalid or unavailable Group mode")
        result.mode_label = MODES[mode]
        if mode == 6:
            values = {}
            keys = [field.validation_alias for field in PlaylistSettings.model_fields.values()]
            for key in keys:
                try:
                    values[key] = self.read_cue_property(result.workspace_id, result.cue_id, key)["value"]
                except Exception as exc:
                    result.errors[key] = sanitize_exception_message(exc)
            result.playlist = _section(PlaylistSettings, values, result, keys)
        result.contents = _contents(self, result.workspace_id, result.identity.model_dump(), max_depth, max_cues, result)
        try:
            final = self.read_cue_values(result.workspace_id, result.cue_id, ["uniqueID", "type", "mode"], cacheable=False)["values"]
            if not isinstance(final, dict) or str(final.get("uniqueID", "")).casefold() != result.cue_id.casefold() or final.get("type") != "Group" or type(final.get("mode")) is not int or final["mode"] != mode:
                raise ValueError("Group identity or mode changed during detail read")
        except Exception as exc:
            result.identity = result.group = result.playlist = result.contents = None
            result.technical_payload = None
            return _fail(result, "group_cue_identity_mismatch", sanitize_exception_message(exc))
        result.coverage.notes.append("Children are bounded summaries; depth zero reads no children.")
        if serialized_payload_bytes(result.model_dump(mode="json")) > MAX_SENSITIVE_CUE_RESPONSE_BYTES:
            result.identity = result.group = result.playlist = result.contents = None
            result.technical_payload = None
            return _fail(result, "cue_payload_too_large", "Group detail exceeds the response byte budget")
        return _finish(result)
