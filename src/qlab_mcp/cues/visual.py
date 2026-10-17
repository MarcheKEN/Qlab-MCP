"""Typed Video, Text and Camera reads using the shared cue-family executor."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, StrictBool, StrictInt, StrictStr

from .audio import AudioBasics, AudioCueSummary, AudioCuesResult, AudioSettings, AudioTiming
from .family import AudioCrosspoint
from .list_models import CueListReadResult, CueListState, FiniteNumber
from .mic import MicBasics, MicSettings, MicTiming
from .profiles import _video_effects_summary
from .control import ControlTriggers

Pair = Annotated[list[FiniteNumber], Field(min_length=2, max_length=2)]
Quaternion = Annotated[list[FiniteNumber], Field(min_length=4, max_length=4)]
Color = Annotated[list[Annotated[FiniteNumber, Field(ge=0, le=1)]], Field(min_length=4, max_length=4)]
TextRange = Annotated[list[Annotated[StrictInt, Field(ge=0)]], Field(min_length=2, max_length=2)]


class FontsResult(BaseModel):
    """Application-wide font inventory returned by QLab, never inferred locally."""
    workspace_id: str
    scope: Literal["application"] = "application"
    font_names: list[Annotated[StrictStr, Field(min_length=1)]]
    families_and_styles: dict[Annotated[StrictStr, Field(min_length=1)],
                              list[Annotated[StrictStr, Field(min_length=1)]]]


class Point(BaseModel):
    x: FiniteNumber
    y: FiniteNumber


class Size(BaseModel):
    width: FiniteNumber
    height: FiniteNumber


class VideoEffect(BaseModel):
    index: StrictInt
    name: StrictStr | None = None
    type: StrictStr | None = None
    enabled: StrictBool | None = None
    keys: list[StrictStr] = Field(default_factory=list)


def _effects(value):
    if isinstance(value, list) and all(isinstance(item, VideoEffect) for item in value):
        return value
    if not isinstance(value, list) or any(not isinstance(item, (dict, str)) for item in value):
        raise ValueError("Expected a list of effect names or objects")
    return _video_effects_summary(value)["effects"]


Effects = Annotated[list[VideoEffect], BeforeValidator(_effects)]


class VisualGeometry(BaseModel):
    stageID: StrictStr | None = None
    stageName: StrictStr | None = None
    stageNumber: StrictInt | None = None
    cueSize: Size | None = None
    anchor: Point | None = None
    translation: Point | None = None
    scale: Point | None = None
    quaternion: Quaternion | None = None
    cropTop: FiniteNumber | None = None
    cropBottom: FiniteNumber | None = None
    cropLeft: FiniteNumber | None = None
    cropRight: FiniteNumber | None = None
    opacity: Annotated[FiniteNumber, Field(ge=0, le=1)] | None = None
    layer: Annotated[StrictInt, Field(ge=0, le=1000)] | None = None
    blendMode: StrictStr | None = None
    fillStage: StrictBool | None = None
    fillStyle: Annotated[StrictInt, Field(ge=0, le=2)] | None = None
    preserveAspectRatio: StrictBool | None = None
    smooth: StrictBool | None = None
    videoEffects: Effects | None = None


class VisualBasics(MicBasics):
    pass


class VisualMediaBasics(AudioBasics, VisualBasics):
    pass


class VideoTiming(AudioTiming):
    holdLastFrame: StrictBool | None = None
    clockType: Literal["audio", "video"] | None = None


class CameraGeometry(VisualGeometry):
    videoInputPatchID: StrictStr | None = None
    videoInputPatchName: StrictStr | None = None
    videoInputPatchNumber: StrictInt | None = None


class TextRun(BaseModel):
    # Preserve read-only native attributes for complete format snapshots.
    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)

    range: TextRange
    fontFamily: StrictStr | None = None
    fontStyle: StrictStr | None = None
    fontName: StrictStr | None = None
    fontSize: FiniteNumber | None = None
    lineSpacing: FiniteNumber | None = None
    color: Color | None = None
    alignment: Literal["left", "center", "right", "justify"] | None = None
    backgroundColor: Color | None = None
    shadowColor: Color | None = None
    shadowBlurRadius: FiniteNumber | None = None
    shadowOffset: Size | None = None
    strikethroughColor: Color | None = None
    underlineColor: Color | None = None
    strikethroughStyle: Literal["none", "single", "double"] | None = None
    underlineStyle: Literal["none", "single", "double"] | None = None


class FontFamilyAndStyle(BaseModel):
    fontFamily: StrictStr
    fontStyle: StrictStr


class TextContent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: StrictStr | None = None
    fixedWidth: Annotated[FiniteNumber, Field(ge=0)] | None = None
    outputSize: Size | None = Field(default=None, validation_alias="text/outputSize")
    fragments: list[TextRun] | None = Field(default=None, validation_alias="text/format")
    alignment: Literal["left", "center", "right", "justify"] | None = Field(default=None, validation_alias="text/format/alignment")
    fontFamily: StrictStr | None = Field(default=None, validation_alias="text/format/fontFamily")
    fontStyle: StrictStr | None = Field(default=None, validation_alias="text/format/fontStyle")
    fontFamilyAndStyle: FontFamilyAndStyle | None = Field(default=None, validation_alias="text/format/fontFamilyAndStyle")
    fontName: StrictStr | None = Field(default=None, validation_alias="text/format/fontName")
    fontSize: FiniteNumber | None = Field(default=None, validation_alias="text/format/fontSize")
    lineSpacing: FiniteNumber | None = Field(default=None, validation_alias="text/format/lineSpacing")
    color: Color | None = Field(default=None, validation_alias="text/format/color")
    backgroundColor: Color | None = Field(default=None, validation_alias="text/format/backgroundColor")
    shadowColor: Color | None = Field(default=None, validation_alias="text/format/shadowColor")
    shadowBlurRadius: FiniteNumber | None = Field(default=None, validation_alias="text/format/shadowBlurRadius")
    shadowOffset: Size | None = Field(default=None, validation_alias="text/format/shadowOffset")
    strikethroughColor: Color | None = Field(default=None, validation_alias="text/format/strikethroughColor")
    underlineColor: Color | None = Field(default=None, validation_alias="text/format/underlineColor")
    strikethroughStyle: Literal["none", "single", "double"] | None = Field(default=None, validation_alias="text/format/strikethroughStyle")
    underlineStyle: Literal["none", "single", "double"] | None = Field(default=None, validation_alias="text/format/underlineStyle")


class VideoCueSummary(AudioCueSummary):
    type: Literal["Video"]


class TextCueSummary(AudioCueSummary):
    type: Literal["Text"]


class CameraCueSummary(AudioCueSummary):
    type: Literal["Camera"]


class VideoCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Video"
    cues: list[VideoCueSummary] = Field(default_factory=list)


class TextCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Text"
    cues: list[TextCueSummary] = Field(default_factory=list)


class CameraCuesResult(AudioCuesResult):
    cue_type: ClassVar[str] = "Camera"
    cues: list[CameraCueSummary] = Field(default_factory=list)


class VisualDetailsResult(CueListReadResult):
    cue_id: str
    profile: Literal["safe", "technical"] = "safe"
    basics: VisualBasics | None = None
    state: CueListState | None = None
    timing: MicTiming | None = None
    video: VisualGeometry | None = None
    triggers: ControlTriggers | None = None
    edit_capabilities: dict[str, JsonValue] = Field(default_factory=dict)
    selected_video_effects: list[dict[str, JsonValue]] = Field(default_factory=list)
    technical_payload: JsonValue = None
    redactions: list[dict[str, str]] = Field(default_factory=list)


class VideoCueDetailsResult(VisualDetailsResult):
    cue_type: ClassVar[str] = "Video"
    identity: VideoCueSummary | None = None
    basics: VisualMediaBasics | None = None
    timing: VideoTiming | None = None
    audio: AudioSettings | None = None
    level: AudioCrosspoint | None = None


class CameraCueDetailsResult(VisualDetailsResult):
    cue_type: ClassVar[str] = "Camera"
    identity: CameraCueSummary | None = None
    video: CameraGeometry | None = None
    audio: MicSettings | None = None
    level: AudioCrosspoint | None = None


class TextCueDetailsResult(VisualDetailsResult):
    cue_type: ClassVar[str] = "Text"
    identity: TextCueSummary | None = None
    text: TextContent | None = None


VIDEO_MODELS = {"triggers": ControlTriggers, "basics": VisualMediaBasics, "state": CueListState, "timing": VideoTiming,
                "video": VisualGeometry, "audio": AudioSettings}
CAMERA_MODELS = {"triggers": ControlTriggers, "basics": VisualBasics, "state": CueListState, "timing": MicTiming,
                 "video": CameraGeometry, "audio": MicSettings}
TEXT_MODELS = {"triggers": ControlTriggers, "basics": VisualBasics, "state": CueListState, "timing": MicTiming,
               "video": VisualGeometry, "text": TextContent}


class VisualCuesMixin:
    def get_fonts(self, workspace_id):
        workspace_id = self._resolve_workspace_id_strict(workspace_id)
        # The complete installed-font list can exceed a UDP datagram.
        return FontsResult(workspace_id=workspace_id,
                           font_names=self._request_tcp("/fontNames", workspace_id=workspace_id).data,
                           families_and_styles=self._request_tcp("/fontFamiliesAndStyles", workspace_id=workspace_id).data)

    def _selected_video_effects(self, result, selectors):
        if not selectors or result.identity is None:
            return result
        from ..write.video_fx import read_selected
        from ..sanitizer import sanitize_exception_message
        try:
            result.selected_video_effects = read_selected(self, result.workspace_id, result.cue_id, selectors)
            if result.video and result.video.videoEffects:
                for item in result.selected_video_effects:
                    result.video.videoEffects[item['index']].type = item['type']
                    result.video.videoEffects[item['index']].enabled = item['enabled']
                from ..write.visual import capabilities
                result.edit_capabilities = capabilities(result.identity.type, result)
        except Exception as exc:
            result.partial = True
            result.status = 'partial'
            result.errors['videoEffectSelectors'] = sanitize_exception_message(exc)
            result.coverage.failed_routes.append('videoEffectIndex/selected')
        return result
    def get_video_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                     VideoCuesResult, VideoCueSummary)

    def get_text_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                     TextCuesResult, TextCueSummary)

    def get_camera_cues(self, workspace_id, cue_list_id, limit=100, offset=0, max_cues_scanned=5000):
        return self._get_family_cues(workspace_id, cue_list_id, limit, offset, max_cues_scanned,
                                     CameraCuesResult, CameraCueSummary)

    def get_video_cue_details(self, workspace_id, cue_id, profile="safe", input_channel=None, output_channel=None, video_effects=None, include_native_triggers=False):
        result = self._get_family_details(workspace_id, cue_id, profile, input_channel, output_channel,
                                         VideoCueDetailsResult, VideoCueSummary, VIDEO_MODELS, include_native_triggers=include_native_triggers)
        return self._selected_video_effects(result, video_effects)

    def get_camera_cue_details(self, workspace_id, cue_id, profile="safe", input_channel=None, output_channel=None, video_effects=None, include_native_triggers=False):
        result = self._get_family_details(workspace_id, cue_id, profile, input_channel, output_channel,
                                         CameraCueDetailsResult, CameraCueSummary, CAMERA_MODELS, include_native_triggers=include_native_triggers)
        return self._selected_video_effects(result, video_effects)

    def get_text_cue_details(self, workspace_id, cue_id, profile="safe", video_effects=None, include_native_triggers=False):
        result = self._get_family_details(workspace_id, cue_id, profile, None, None,
                                         TextCueDetailsResult, TextCueSummary, TEXT_MODELS, include_native_triggers=include_native_triggers)
        return self._selected_video_effects(result, video_effects)
