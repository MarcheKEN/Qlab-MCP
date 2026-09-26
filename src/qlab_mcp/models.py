"""Typed request and response shapes exposed through FastMCP."""

from __future__ import annotations

import math
import struct
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BeforeValidator, BaseModel, ConfigDict, Field, JsonValue, StrictFloat, StrictInt, field_validator
from typing_extensions import TypedDict


UpdateCueProfile = Literal[
    "common",
    "memo_basic",
    "wait_basic",
    "group_basic",
    "audio_basic",
    "mic_basic",
    "video_basic",
    "camera_basic",
    "text_basic",
    "light_basic",
    "fade_basic",
    "network_basic",
    "midi_basic",
    "midi_file_basic",
    "timecode_basic",
    "target_basic",
    "reset_basic",
    "devamp_basic",
    "script_basic",
]
WriteReadinessStatus = Literal[
    "ready",
    "write_disabled",
    "passcode_missing",
    "workspace_not_found",
    "workspace_ambiguous",
    "workspace_unavailable",
    "qlab_unreachable",
    "edit_not_confirmed",
    "workspace_in_show_mode",
    "show_mode_unknown",
]
CreateCueStatus = Literal[
    "dry_run",
    "preflight_failed",
    "created",
    "verification_failed",
    "workspace_not_found",
    "workspace_ambiguous",
    "workspace_unavailable",
]
CreateCuesStatus = Literal[
    "dry_run",
    "created",
    "partial_failed",
    "preflight_failed",
    "verification_failed",
    "workspace_not_found",
    "workspace_ambiguous",
    "workspace_unavailable",
]
UpdateCueStatus = Literal[
    "dry_run",
    "dry_run_preflight_failed",
    "planned",
    "preflight_failed",
    "updated",
    "updated_with_confirmed_timeouts",
    "partial_failed",
    "verification_failed",
    "verification_inconclusive",
    "cue_not_found",
]
UpdateCuesStatus = Literal[
    "dry_run",
    "preflight_failed",
    "updated",
    "updated_with_confirmed_timeouts",
    "partial_failed",
    "verification_failed",
    "verification_inconclusive",
    "workspace_not_found",
    "workspace_ambiguous",
    "workspace_unavailable",
]
WorkspaceSettingsOperationId = Literal["general.minGoTime"]
WorkspaceSettingsWriteStatus = Literal[
    "dry_run",
    "dry_run_preflight_failed",
    "unsupported",
    "unchanged",
    "updated",
    "updated_with_confirmed_timeouts",
    "preflight_failed",
    "verification_failed",
    "verification_inconclusive",
]


def _general_settings_numeric_value(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("value must be a non-negative OSC-representable number.")
    if value < 0:
        raise ValueError("value must be non-negative.")
    if isinstance(value, int):
        try:
            struct.pack(">i", value)
        except (OverflowError, struct.error) as exc:
            raise ValueError("value must fit the OSC signed int32 range.") from exc
        return value
    if not math.isfinite(value):
        raise ValueError("value must be finite.")
    try:
        struct.pack(">f", value)
    except (OverflowError, struct.error) as exc:
        raise ValueError("value must fit the OSC float32 range.") from exc
    return value


def _canonical_workspace_uuid(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        canonical = str(UUID(value))
    except ValueError as exc:
        raise ValueError("workspace_id must be an exact workspace UUID.") from exc
    if canonical.casefold() != value.casefold():
        raise ValueError("workspace_id must be an exact workspace UUID.")
    return value


CanonicalWorkspaceUUID = Annotated[UUID, BeforeValidator(_canonical_workspace_uuid)]


class GeneralMinGoTimeOperation(BaseModel):
    """The only executable Workspace Settings operation in Wave 1."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["general.minGoTime"]
    value: Annotated[
        StrictInt | StrictFloat,
        Field(
            ge=0,
            json_schema_extra={"minimum": 0},
            description=(
                "Finite non-negative seconds for the allowlisted general.minGoTime setting. "
                "The OSC encoder preserves integer versus float transport types."
            ),
        ),
    ]

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> int | float:
        return _general_settings_numeric_value(value)


# Keep the public request shape extensible without advertising a one-item union
# in FastMCP's JSON Schema. Add the next typed operation and promote this alias
# to an Annotated discriminated union in that operation's implementation wave.
WorkspaceSettingsOperation = GeneralMinGoTimeOperation


class QlabConnectionCheckResult(BaseModel):
    """Operational readiness check for QLab OSC access."""

    ok: bool
    status: str
    qlab_reachable: bool
    workspace_available: bool
    workspace_readable: bool
    workspace_id: str | None = None
    workspace_name: str | None = None
    qlab_version: str | None = None
    workspace_count: int
    available_workspaces: list[dict[str, Any]]
    passcode_configured: bool
    passcode_status: str | None = None
    connect_scopes: dict[str, Any] | None = None
    workspace_mode: dict[str, Any] | None = None
    message: str
    connection: dict[str, Any]
    permissions: dict[str, Any]
    capabilities: dict[str, Any]
    checks: dict[str, Any]
    overrides_scope: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)
    override_warnings: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkspaceOverviewResult(BaseModel):
    """Bounded structural map of a QLab workspace."""

    ok: bool | None = None
    status: str | None = None
    partial: bool | None = None
    error_code: str | None = None
    suggested_action: str | None = None
    message: str | None = None
    details: Any = None
    received: Any = None
    allowed: Any = None
    workspace_id: str
    workspace: Any
    cue_count: int
    cue_count_meaning: str | None = None
    known_total_cues: int | None = None
    known_total_cues_status: str | None = None
    known_total_cues_source: str | None = None
    known_total_cues_meaning: str | None = None
    summary: dict[str, Any]
    agent_summary: dict[str, Any] | None = None
    cue_lists: list[dict[str, Any]]
    cue_index: dict[str, Any] | None = None
    editorial_health: dict[str, Any] | None = None
    limits: dict[str, Any]
    warnings: list[str]
    errors: dict[str, str] | None = None
    live_state: dict[str, Any] | None = None


class SettingsItemIdentity(BaseModel):
    name: str | None = None
    uniqueID: str | None = None
    type: str | None = None
    number: int | None = None
    key: str | None = None


class WorkspaceDomainSettingsResult(BaseModel):
    """Shared result envelope for one documented Workspace Settings domain."""

    ok: bool
    status: Literal["ok", "partial", "error"]
    partial: bool
    workspace_id: str
    domain: Literal["general", "audio", "video", "light", "network", "midi"]
    coverage: Literal["partial"] = "partial"
    profile: Literal["safe", "technical", "exhaustive"] = "safe"
    view: str
    ref: str | None = None
    choices: list[SettingsItemIdentity] = Field(default_factory=list)
    redactions: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: dict[str, str] | None = None
    error_code: str | None = None
    suggested_action: str | None = None
    message: str | None = None
    received: JsonValue | None = None
    allowed: JsonValue | None = None


class WorkspaceGeneralSettingsData(BaseModel):
    minGoTime: Annotated[StrictInt | StrictFloat, Field(ge=0, allow_inf_nan=False)] | None = None
    selectionIsPlayhead: bool | None = None


class SettingsInventoryEmpty(BaseModel):
    items: list[SettingsItemIdentity] = Field(default_factory=list, max_length=0)
    empty: Literal[True] = True
    available: Literal[False] = False


class AudioOutputChannelName(BaseModel):
    channel: Annotated[StrictInt, Field(ge=1)]
    name: str


class AudioPatchLevel(BaseModel):
    input_channel: Annotated[StrictInt, Field(ge=1, le=128)]
    output_channel: Annotated[StrictInt, Field(ge=1)]
    decibels: Annotated[StrictInt | StrictFloat, Field(allow_inf_nan=False)] | Literal["-inf"]


class AudioPatchSummary(SettingsItemIdentity):
    cue_outputs: int | None = None
    cue_output_count: int | None = None
    routing: list[Annotated[StrictInt, Field(ge=1)]] | None = None
    routing_present: bool | None = None
    routing_count: int | None = None
    device_presence_known: bool = False
    device_present: bool | None = None
    output_channel_names: list[AudioOutputChannelName] = Field(default_factory=list)


class AudioOutputPatchDetail(AudioPatchSummary):
    mute_channels: list[Annotated[StrictInt, Field(ge=1)]] = Field(default_factory=list)
    solo_channels: list[Annotated[StrictInt, Field(ge=1)]] = Field(default_factory=list)
    level: AudioPatchLevel | None = None


class AudioInputPatchDetail(AudioPatchSummary):
    pass


class WorkspaceAudioSettingsOverview(BaseModel):
    output_patches: list[AudioPatchSummary] = Field(default_factory=list)
    input_patches: list[AudioPatchSummary] = Field(default_factory=list)
    cue_output_channel_counts: JsonValue | None = None
    output_channel_names: JsonValue | None = None
    max_volume: Annotated[StrictInt | StrictFloat, Field(allow_inf_nan=False)] | None = None
    min_volume: Annotated[StrictInt | StrictFloat, Field(allow_inf_nan=False)] | None = None


class WorkspaceAudioSettingsData(BaseModel):
    overview: WorkspaceAudioSettingsOverview | None = None
    detail: AudioOutputPatchDetail | AudioInputPatchDetail | SettingsInventoryEmpty | None = None
    technical_payload: JsonValue | None = None


class VideoItemSummary(BaseModel):
    uniqueID: str | None = None
    name: str | None = None


class VideoSize(BaseModel):
    width: float | None = None
    height: float | None = None


class VideoBounds(VideoSize):
    x: float | None = None
    y: float | None = None


class VideoDeviceSummary(BaseModel):
    present: bool = False
    name: str | None = None
    type: str | None = None
    connected: bool | None = None


class VideoRouteAttention(BaseModel):
    status: Literal["disconnected"]
    message: str


class VideoRouteSummary(VideoItemSummary):
    connected: bool | None = None
    destination_type: str | None = None
    device: VideoDeviceSummary | None = None
    destination_present: bool | None = None
    enableGuides: bool | None = None
    rotationDegrees: float | None = None
    scalingMode: str | int | None = None
    naturalSize: VideoSize | None = None
    partialScreen: VideoBounds | bool | None = None
    rear: bool | None = None
    guides_present: bool | None = None
    attention: VideoRouteAttention | None = None


class VideoRegionSummary(VideoItemSummary):
    index: int | None = None
    boundsOnStage: VideoBounds | None = None
    meshWidth: int | None = None
    meshHeight: int | None = None
    warpType: str | int | None = None
    autoEdgeBlends: bool | None = None
    edgeBlendTopPixels: float | None = None
    edgeBlendRightPixels: float | None = None
    edgeBlendBottomPixels: float | None = None
    edgeBlendLeftPixels: float | None = None
    edgeBlendPower: float | None = None
    edgeBlendGamma: float | None = None
    route: VideoRouteSummary | None = None
    control_point_count: int | None = None
    shadow_control_point_count: int | None = None
    mesh_subregion_count: int | None = None


class VideoStageSummary(VideoItemSummary):
    size: VideoSize | None = None
    region_count: int | None = None


class VideoStageDetail(VideoStageSummary):
    regions: list[VideoRegionSummary] | None = None
    multi_output: bool | None = None


class VideoInputPatchSummary(VideoItemSummary):
    number: int | None = None


class VideoSettingsProblem(BaseModel):
    code: str
    route: VideoItemSummary | None = None
    stage: VideoItemSummary | None = None


class WorkspaceVideoSettingsOverview(BaseModel):
    input_patches: list[VideoInputPatchSummary] | None = None
    routes: list[VideoRouteSummary] | None = None
    stages: list[VideoStageSummary] | None = None
    problems: list[VideoSettingsProblem] = Field(default_factory=list)


class WorkspaceVideoSettingsData(BaseModel):
    overview: WorkspaceVideoSettingsOverview | None = None


class VideoStageData(BaseModel):
    detail: VideoStageDetail | None = None
    technical_payload: JsonValue | None = None


class VideoOutputRouteData(BaseModel):
    detail: VideoRouteSummary | None = None
    technical_payload: JsonValue | None = None


class LightPatchSummary(BaseModel):
    patch_present: bool
    top_level_count: StrictInt | None = None
    instrument_count: StrictInt | None = None
    group_count: StrictInt | None = None
    definition_count: StrictInt | None = None
    read_transport: Literal["udp", "tcp_fallback"] | None = None
    read_transport_meaning: str | None = None


class LightDefinitionSummary(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    version: StrictInt | StrictFloat | str | None = None
    broken: bool | None = None
    default_parameter_index: StrictInt | str | None = None
    default_parameter_name: str | None = None
    parameter_count: StrictInt | None = None
    parameter_names: list[str] = Field(default_factory=list)


class LightInstrumentSummary(SettingsItemIdentity):
    comment: str | None = None
    patched: bool | None = None
    conflicted: bool | None = None
    definition: LightDefinitionSummary | None = None
    parameter_count: StrictInt | None = None
    parameter_names: list[str] = Field(default_factory=list)


class LightGroupSummary(SettingsItemIdentity):
    instrument_count: StrictInt = 0
    instrument_names: list[str] = Field(default_factory=list)
    parameter_names: list[str] = Field(default_factory=list)


class LightParameterSummary(BaseModel):
    scope: Literal["instrument", "group"]
    owner_name: str | None = None
    name: str | None = None
    unique_name: str | None = None
    type: str
    broken: bool | None = None
    home_value: StrictInt | StrictFloat | str | None = None
    home_value_dmx: StrictInt | StrictFloat | str | None = None
    value_is_percentage: bool | None = None
    two_bytes: bool | None = None


class LightInstrumentIndex(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[JsonValue]] = Field(default_factory=list)


class LightPatchDetail(BaseModel):
    summary: LightPatchSummary
    instruments: list[LightInstrumentSummary] = Field(default_factory=list)
    groups: list[LightGroupSummary] = Field(default_factory=list)
    parameters: list[LightParameterSummary] = Field(default_factory=list)
    instrument_index: LightInstrumentIndex | None = None
    definition_counts: dict[str, StrictInt] = Field(default_factory=dict)
    technical_payloads_omitted: list[str] = Field(default_factory=list)


class WorkspaceLightSettingsData(BaseModel):
    detail: LightPatchDetail | None = None
    technical_payload: JsonValue | None = None


class NetworkPatchSummary(SettingsItemIdentity):
    destination_count: StrictInt | None = None
    destination_present: bool | None = None
    passcode_present: bool | None = None


class WorkspaceNetworkSettingsOverview(BaseModel):
    patches: list[NetworkPatchSummary] = Field(default_factory=list)


class WorkspaceNetworkSettingsData(BaseModel):
    overview: WorkspaceNetworkSettingsOverview | None = None
    detail: NetworkPatchSummary | SettingsInventoryEmpty | None = None
    technical_payload: JsonValue | None = None


class MidiPatchSummary(SettingsItemIdentity):
    destination_present: bool | None = None


class WorkspaceMidiSettingsOverview(BaseModel):
    patches: list[MidiPatchSummary] = Field(default_factory=list)


class WorkspaceMidiSettingsData(BaseModel):
    overview: WorkspaceMidiSettingsOverview | None = None
    detail: MidiPatchSummary | SettingsInventoryEmpty | None = None
    technical_payload: JsonValue | None = None


class WorkspaceGeneralSettingsResult(WorkspaceDomainSettingsResult):
    domain: Literal["general"] = "general"
    data: WorkspaceGeneralSettingsData | None = None


class WorkspaceAudioSettingsResult(WorkspaceDomainSettingsResult):
    domain: Literal["audio"] = "audio"
    data: WorkspaceAudioSettingsData | None = None


class WorkspaceVideoSettingsResult(WorkspaceDomainSettingsResult):
    domain: Literal["video"] = "video"
    data: WorkspaceVideoSettingsData | None = None


class VideoStageResult(WorkspaceDomainSettingsResult):
    domain: Literal["video"] = "video"
    data: VideoStageData | None = None


class VideoOutputRouteResult(WorkspaceDomainSettingsResult):
    domain: Literal["video"] = "video"
    data: VideoOutputRouteData | None = None


class WorkspaceLightSettingsResult(WorkspaceDomainSettingsResult):
    domain: Literal["light"] = "light"
    data: WorkspaceLightSettingsData | None = None


class WorkspaceNetworkSettingsResult(WorkspaceDomainSettingsResult):
    domain: Literal["network"] = "network"
    data: WorkspaceNetworkSettingsData | None = None


class WorkspaceMidiSettingsResult(WorkspaceDomainSettingsResult):
    domain: Literal["midi"] = "midi"
    data: WorkspaceMidiSettingsData | None = None


class WorkspaceSettingsEditRequest(BaseModel):
    """Typed input for the unified Workspace Settings write tool."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: CanonicalWorkspaceUUID = Field(description="Exact workspace UUID.")
    operation: WorkspaceSettingsOperation
    dry_run: bool | None = None
    confirm_token: str | None = None

class WorkspaceSettingsEditResult(BaseModel):
    """Result for the gated Workspace Settings write slice."""

    ok: bool
    status: WorkspaceSettingsWriteStatus = Field(description="Machine-readable workspace settings write result status.")
    workspace_id: str
    operation: WorkspaceSettingsOperationId
    dry_run: bool
    requested_value: int | float
    baseline: int | float | None = None
    readback: int | float | None = None
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    confirm_token: str | None = None
    readiness: dict[str, Any] | None = None
    activity: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    timeout_confirmation: dict[str, Any] | None = None
    retry_unsafe: bool
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    suggested_action: str | None = None
    message: str


WorkspaceStatusCoverage = Literal["complete", "partial", "not_exposed"]


class WorkspaceStatusCueIdentity(BaseModel):
    uniqueID: str | None = None
    number: str | int | None = None
    name: str | None = None
    displayName: str | None = None
    type: str | None = None


class WorkspaceStatusKnownProblem(BaseModel):
    domain: Literal["video"]
    code: str
    route: VideoItemSummary | None = None
    stage: VideoItemSummary | None = None


class WorkspaceStatusSectionBase(BaseModel):
    source: str
    available: bool
    coverage: WorkspaceStatusCoverage | None = None
    status: str | None = None
    notes: list[str] = Field(default_factory=list)


class WorkspaceStatusWarningsSection(WorkspaceStatusSectionBase):
    evidence_sources: list[Literal["derived_from_cues", "derived_from_settings"]] = Field(default_factory=list)
    cue_evidence_available: bool = False
    settings_evidence_available: bool = False
    scanned_count: StrictInt | None = None
    warning_count: StrictInt | None = None
    broken_count: StrictInt | None = None
    flagged_count: StrictInt | None = None
    running_count: StrictInt | None = None
    paused_count: StrictInt | None = None
    sample_warning_cues: list[WorkspaceStatusCueIdentity] = Field(default_factory=list)
    sample_broken_cues: list[WorkspaceStatusCueIdentity] = Field(default_factory=list)
    sample_flagged_cues: list[WorkspaceStatusCueIdentity] = Field(default_factory=list)
    known_settings_problem_count: StrictInt = 0
    known_settings_problem_counts: dict[str, StrictInt] = Field(default_factory=dict)
    sample_settings_problems: list[WorkspaceStatusKnownProblem] = Field(default_factory=list)


class WorkspaceStatusTriggerSection(WorkspaceStatusSectionBase):
    timecode_trigger_count: StrictInt | None = None
    auto_continue_count: StrictInt | None = None
    auto_follow_count: StrictInt | None = None
    default_timecode_values_seen: bool | None = None
    default_timecode_values_not_counted: bool | None = None
    general_trigger_status: str | None = None


class WorkspaceStatusTimecodeConfigSection(WorkspaceStatusSectionBase):
    configured_count: StrictInt | None = None
    sample: list[dict[str, JsonValue]] = Field(default_factory=list)
    default_timecode_values_seen: bool | None = None
    default_timecode_values_not_counted: bool | None = None


class WorkspaceStatusTimecodeLiveItem(BaseModel):
    cue_ref: str
    current_timecode_text: JsonValue = Field(alias="currentTimecode/text")

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class WorkspaceStatusTimecodeLiveSection(WorkspaceStatusSectionBase):
    sample: list[WorkspaceStatusTimecodeLiveItem] = Field(default_factory=list)


class WorkspaceStatusSettingsCounts(BaseModel):
    requested_sections: list[str] = Field(default_factory=list)
    returned_sections: list[str] = Field(default_factory=list)
    section_count: StrictInt | None = None
    error_count: StrictInt | None = None
    redaction_count: StrictInt | None = None
    audio_output_patch_count: StrictInt | None = None
    audio_input_patch_count: StrictInt | None = None
    video_route_count: StrictInt | None = None
    video_stage_count: StrictInt | None = None
    video_input_patch_count: StrictInt | None = None
    video_problem_count: StrictInt = 0
    video_problem_counts: dict[str, StrictInt] = Field(default_factory=dict)
    network_patch_count: StrictInt | None = None
    midi_patch_count: StrictInt | None = None


class WorkspaceStatusSettingsSection(WorkspaceStatusSectionBase):
    summary: WorkspaceStatusSettingsCounts | None = None
    sections: dict[str, JsonValue] | None = None
    errors: dict[str, str] | None = None
    known_problems: list[WorkspaceStatusKnownProblem] = Field(default_factory=list)
    problem_counts: dict[str, StrictInt] = Field(default_factory=dict)


class WorkspaceStatusInfoSection(WorkspaceStatusSectionBase):
    workspace_id: str
    machine_id: Literal["redacted"]


class WorkspaceStatusSections(TypedDict, total=False):
    warnings_summary: WorkspaceStatusWarningsSection
    trigger_summary: WorkspaceStatusTriggerSection
    timecode_config: WorkspaceStatusTimecodeConfigSection
    timecode_live_status: WorkspaceStatusTimecodeLiveSection
    settings_summary: WorkspaceStatusSettingsSection
    logs: WorkspaceStatusSectionBase
    artnet: WorkspaceStatusSectionBase
    video_metrics: WorkspaceStatusSectionBase
    info: WorkspaceStatusInfoSection


class WorkspaceStatusSummary(TypedDict, total=False):
    available_sections: list[str]
    unavailable_sections: list[str]
    cue_scan_completeness: str
    scanned_count: StrictInt
    matched_timecode_config_count: StrictInt
    settings_error_count: StrictInt


class WorkspaceStatusLimits(TypedDict, total=False):
    max_cues_scanned: StrictInt
    sample_limit: StrictInt


class WorkspaceStatusResult(BaseModel):
    """Read-only operational status derived from documented QLab OSC reads."""

    workspace_id: str
    profile: str = "summary"
    ok: bool | None = None
    partial: bool | None = None
    status: str | None = None
    error_code: str | None = None
    suggested_action: str | None = None
    message: str | None = None
    details: Any = None
    received: Any = None
    allowed: Any = None
    sections: WorkspaceStatusSections = Field(default_factory=dict)
    summary: WorkspaceStatusSummary = Field(default_factory=dict)
    limits: WorkspaceStatusLimits = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: dict[str, str] | None = None


class CueQueryResult(BaseModel):
    """Filtered cue query result."""

    ok: bool | None = None
    status: str | None = None
    partial: bool | None = None
    error_code: str | None = None
    suggested_action: str | None = None
    message: str | None = None
    details: Any = None
    received: Any = None
    allowed: Any = None
    workspace_id: str
    filters: list[dict[str, Any]]
    profile: str
    scanned_count: int
    matched_count: int
    returned_count: int
    total_cue_ids: int
    query_completeness: str | None = None
    query_completeness_reasons: list[str] = Field(default_factory=list)
    id_only_unscanned_count: int = 0
    omitted_branches: list[dict[str, Any]] = Field(default_factory=list)
    partial_branches: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool
    truncation_reasons: list[str] = Field(default_factory=list)
    scanned_all_cues: bool
    result_limited: bool
    limits: dict[str, Any]
    cues: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
    errors: dict[str, str] | None = None


class CueDetailsResult(BaseModel):
    """Grouped cue details for one cue."""

    ok: bool | None = None
    status: str | None = None
    partial: bool | None = None
    error_code: str | None = None
    suggested_action: str | None = None
    message: str | None = None
    details: Any = None
    received: Any = None
    allowed: Any = None
    workspace_id: str
    cue_ref: str
    profile: str
    cue_type: str | None = None
    properties: dict[str, Any]
    sections: dict[str, dict[str, Any]] | None = None
    update_capabilities: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    active_count: int | None = None
    read_coverage: dict[str, Any] | None = None


class CueDetailsBatchResult(BaseModel):
    """Batch details for up to 50 cues."""

    ok: bool
    status: str | None = None
    partial: bool | None = None
    error_code: str | None = None
    suggested_action: str | None = None
    message: str | None = None
    details: Any = None
    received: Any = None
    allowed: Any = None
    workspace_id: str
    requested_count: int
    succeeded_count: int
    failed_count: int
    profile: str
    results: list[CueDetailsResult]
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    read_coverage: dict[str, Any] | None = None


class WriteReadinessResult(BaseModel):
    """Non-mutating readiness check for gated QLab write mode."""

    ok: bool
    status: WriteReadinessStatus = Field(description="Machine-readable readiness state for QLab write mode.")
    workspace_id: str
    write_enabled: bool
    dry_run_default: bool
    passcode_configured: bool
    capabilities: dict[str, Any]
    checks: dict[str, Any]
    blockers: list[str] = Field(
        default_factory=list,
        description="Machine-readable blockers that must be cleared before real write tools can run.",
    )
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = Field(
        default=None,
        description="Stable error code for agents; null when ok is true.",
    )
    suggested_action: str | None = Field(
        default=None,
        description="Short next action for clearing the readiness blocker; null when ok is true.",
    )
    message: str


class CreateCueResult(BaseModel):
    """Result for gated cue creation or dry-run planning."""

    ok: bool
    status: CreateCueStatus = Field(description="Machine-readable create result status.")
    workspace_id: str
    cue_type: str
    dry_run: bool
    confirm_token: str | None = Field(
        default=None,
        description="Dedicated confirm:createCue:v2 token returned by dry-run and consumed by real creation.",
    )
    created_cue_id: str | None = None
    placement: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    cleanup_required: bool = Field(
        default=False,
        description=(
            "True when creation may have mutated QLab but fresh identity, structural placement, "
            "or inactive-state verification did not complete. Broken or warning health alone is informational."
        ),
    )
    cleanup: dict[str, Any] | None = Field(
        default=None,
        description="Manual cleanup guidance and any non-authoritative candidate cue IDs.",
    )
    errors: dict[str, str] | None = Field(
        default=None,
        description="Verification or placement errors; null when no errors were detected.",
    )
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = Field(
        default=None,
        description="Stable error code for agents; null when ok is true.",
    )
    suggested_action: str | None = Field(
        default=None,
        description="Short next action for resolving failed creation or verification; null when ok is true.",
    )
    message: str


class CreateCuesDestination(BaseModel):
    kind: Literal["cue_list", "group", "cue_cart"]
    id: str
    after_cue_id: str | None = None
    resolved_after_cue_id: str | None = None
    insertion_index: int | None = None
    placement_mode: str | None = None


class CreateCuesItemResult(BaseModel):
    index: StrictInt = Field(description="Zero-based position in the requested cue_types list.")
    cue_type: str
    status: CreateCueStatus | Literal["planned"]
    created_cue_id: str | None = None
    verified: bool | None = None
    parent_id: str | None = None
    position_index: int | None = None
    health_status: str | None = None
    cleanup_required: bool = False
    cleanup: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    suggested_action: str | None = None


class CreateCuesResult(BaseModel):
    """Result for an ordered, sequential multi-cue creation."""

    ok: bool
    status: CreateCuesStatus = Field(description="Machine-readable batch create status.")
    workspace_id: str
    dry_run: bool
    requested_count: int
    planned_count: int = Field(
        default=0,
        description=(
            "Number of generated plan operations, including per-item creation and "
            "identity/structure verification steps; requested_count and created_count count logical cues."
        ),
    )
    created_count: int = 0
    destination: CreateCuesDestination | None = None
    results: list[CreateCuesItemResult] = Field(default_factory=list)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    confirm_token: str | None = Field(
        default=None,
        description="Dedicated confirm:createCues:v2 token returned by dry-run.",
    )
    error_code: str | None = None
    suggested_action: str | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    message: str


class UpdateCueResult(BaseModel):
    """Result for gated cue update or dry-run planning."""

    ok: bool
    status: UpdateCueStatus = Field(description="Machine-readable single-cue update result status.")
    workspace_id: str
    cue_ref: str
    profile: str = "common"
    dry_run: bool
    properties: dict[str, Any] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)
    confirm_gates: list[str] = Field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff: dict[str, dict[str, Any]] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    updateq_plan: dict[str, Any] | None = None
    group_child_readback: dict[str, Any] | None = Field(
        default=None,
        description="Fresh ordered direct-child snapshot after a token-gated Group write.",
    )
    side_effects: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Explicit Group or child state changes observed beyond the requested scalar write.",
    )
    message: str


class CueUpdateInput(BaseModel):
    """One cue update request inside a batch."""

    cue_ref: str = Field(
        min_length=1,
        description=(
            "Concrete QLab cue number or cue unique ID to update. "
            "Ambiguous refs such as selected, active, playhead, and playbackPosition are rejected."
        ),
    )
    profile: str = Field(
        default="common",
        description=(
            "Update registry profile for this cue. Each batch item may use a different profile; "
            "use qlab_get_cue_details(profile='editable') to discover compatible profiles."
        ),
    )
    properties: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Simple one-argument setter values keyed by allowlisted property name. "
            "At least one of properties or operations is required."
        ),
    )
    operations: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Structured setter operations for properties with multiple arguments. "
            "Each operation uses {'property': string, 'args': object, 'mode': 'saved'|'live'}."
        ),
    )
    confirm_gates: list[str] | None = Field(
        default=None,
        description=(
            "Exact confirm_token values accepted for this update item after reviewing a dry-run plan. "
            "Broad capability gate labels are discovery metadata, not real-write approval tokens."
        ),
    )


class UpdateCueItemResult(BaseModel):
    """Per-cue result for a batch update."""

    cue_ref: str
    cue_id: str | None = None
    profile: str = "common"
    status: UpdateCueStatus = Field(description="Machine-readable result status for this cue update item.")
    properties: dict[str, Any] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)
    confirm_gates: list[str] = Field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff: dict[str, dict[str, Any]] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    errors: dict[str, str] | None = Field(
        default=None,
        description="Per-cue read, setter, timeout, profile, or verification errors; null when none.",
    )
    warnings: list[str] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
    updateq_plan: dict[str, Any] | None = None
    group_child_readback: dict[str, Any] | None = Field(
        default=None,
        description="Fresh ordered direct-child snapshot after a token-gated Group write.",
    )
    side_effects: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Explicit Group or child state changes observed beyond the requested scalar write.",
    )
    debug: dict[str, Any] | None = Field(
        default=None,
        description="Optional verification diagnostics when QLAB_UPDATE_DEBUG is enabled.",
    )


class UpdateCuesResult(BaseModel):
    """Batch result for gated cue updates or dry-run planning."""

    ok: bool
    status: UpdateCuesStatus = Field(description="Machine-readable aggregate status for the batch update.")
    workspace_id: str
    dry_run: bool
    requested_count: int
    planned_count: int
    updated_count: int
    failed_count: int
    timeout_confirmed_count: int = Field(
        description=(
            "Number of cue update items with one or more setter timeouts that were confirmed by fresh after-read. "
            "This is per cue item, not per setter."
        )
    )
    results: list[UpdateCueItemResult]
    errors: dict[str, str] | None = Field(
        default=None,
        description="Batch-level errors; inspect results for per-cue failures.",
    )
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = Field(
        default=None,
        description="Stable error code for agents; null when ok is true.",
    )
    suggested_action: str | None = Field(
        default=None,
        description="Short next action for resolving failed batch updates; null when ok is true.",
    )
    message: str


DeleteCuesStatus = Literal[
    "planned",
    "deleted",
    "deleted_with_confirmed_timeouts",
    "deleted_immediately",
    "deleted_after_convergence",
    "indeterminate",
    "failed",
    "preflight_failed",
    "partial_failed",
    "verification_failed",
]


class DeleteCuesResult(BaseModel):
    """Result for explicit leaves, one empty Group, or recursive container emptying."""

    ok: bool
    status: DeleteCuesStatus
    workspace_id: str
    dry_run: bool
    requested_count: int
    planned_count: int
    deleted_count: int
    failed_count: int
    timeout_confirmed_count: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    confirm_token: str | None = None
    container_id: str | None = None
    recursive: bool = False
    preserved_container_id: str | None = None
    expanded_count: int = 0
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    message: str


MoveCueStatus = Literal[
    "planned",
    "runtime_blocked",
    "moved",
    "moved_after_convergence",
    "moved_with_confirmed_timeout",
    "partial_failed",
    "verification_failed",
    "verification_inconclusive",
    "rollback_required",
    "rollback_failed",
    "preflight_failed",
]


class MoveCueInput(BaseModel):
    """One explicit structural cue move."""

    cue_id: UUID = Field(description="Exact source cue UUID; cue numbers and implicit selections are not accepted.")
    destination_parent_id: UUID | None = Field(
        default=None,
        description=(
            "Exact destination parent UUID. Omit for a same-parent linear move; required for Cue Cart coordinates."
        ),
    )
    destination_index: int | None = Field(
        default=None,
        description="Non-negative insertion index; use exactly one linear placement field.",
    )
    before_cue_id: UUID | None = Field(
        default=None,
        description="Exact sibling UUID to place before; use exactly one linear placement field.",
    )
    after_cue_id: UUID | None = Field(
        default=None,
        description="Exact sibling UUID to place after; use exactly one linear placement field.",
    )
    position: Literal["first", "last"] | None = Field(
        default=None,
        description="Place first or last; use exactly one linear placement field.",
    )
    cart_row: int | None = Field(
        default=None,
        description="Non-negative Cue Cart row; requires both cart_row and cart_column and no linear placement field.",
    )
    cart_column: int | None = Field(
        default=None,
        description="Non-negative Cue Cart column; requires both cart_row and cart_column and no linear placement field.",
    )


class MoveCuesResult(BaseModel):
    """Result for one gated, sequential structural move batch."""

    ok: bool
    status: MoveCueStatus
    workspace_id: str
    dry_run: bool
    requested_count: int
    planned_count: int
    moved_count: int
    failed_count: int
    timeout_confirmed_count: int = 0
    results: list[dict[str, Any]] = Field(default_factory=list)
    confirm_token: str | None = None
    rollback: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    message: str
