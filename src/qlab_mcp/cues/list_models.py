"""Typed read-only Cue List contracts; OSC-unavailable values remain unknown."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictInt, StrictStr


class CueListIdentity(BaseModel):
    model_config = ConfigDict(strict=True)

    uniqueID: Annotated[str, Field(min_length=1)]
    type: Literal["Cue List"] = "Cue List"
    name: str | None = None
    displayName: str | None = None
    listName: str | None = None
    number: str | None = None
    colorName: str | None = None
    secondColorName: str | None = None
    useSecondColor: bool | None = None


class CueListInventoryItem(CueListIdentity):
    type: Literal["Cue List", "Cue Cart", "Cart"] = "Cue List"
    armed: StrictBool | None = None
    flagged: StrictBool | None = None
    isBroken: StrictBool | None = None
    isWarning: StrictBool | None = None
    is_current: StrictBool | None = None
    root_position: StrictInt


class CueListState(BaseModel):
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
    isChildAuditioning: StrictBool | None = None
    isChildFlagged: StrictBool | None = None
    isPanicking: StrictBool | None = None
    isTailingOut: StrictBool | None = None


class CueContainerBasics(BaseModel):
    defaultName: StrictStr | None = None
    notes: StrictStr | None = None
    mode: StrictInt | None = None
    autoLoad: StrictBool | None = None
    skipIfDisarmed: StrictBool | None = None
    secondTriggerAction: StrictInt | None = None
    secondTriggerOnRelease: StrictBool | None = None


class CueListPosition(BaseModel):
    number: StrictStr | None = None
    uniqueID: StrictStr | None = None
    present: StrictBool | None = None


class CueListEnum(BaseModel):
    value: StrictInt
    label: str


FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class CueTimecodeComponents(BaseModel):
    hours: Annotated[StrictInt, Field(ge=0)]
    minutes: Annotated[StrictInt, Field(ge=0)]
    seconds: Annotated[StrictInt, Field(ge=0)]
    frames: Annotated[StrictInt, Field(ge=0)]
    bits: Annotated[StrictInt, Field(ge=0)]


class CueListTimecode(BaseModel):
    current: FiniteNumber | None = None
    text: StrictStr | None = None
    sync_mode: CueListEnum | None = None
    smpte_format: CueListEnum | None = None
    start_behavior: CueListEnum | None = None
    stop_behavior: CueListEnum | None = None
    freewheel_seconds: Annotated[FiniteNumber, Field(ge=0, le=2)] | None = None
    lookback_seconds: Annotated[FiniteNumber, Field(ge=0)] | None = None
    trigger: CueTimecodeComponents | None = None
    trigger_text: StrictStr | None = None


class CueListChild(BaseModel):
    model_config = ConfigDict(strict=True)

    uniqueID: Annotated[str, Field(min_length=1)]
    type: Annotated[str, Field(min_length=1)]
    number: str | None = None
    name: str | None = None
    displayName: str | None = None
    listName: str | None = None
    colorName: str | None = None
    armed: bool | None = None
    flagged: bool | None = None
    child_count: int | None = None
    children: list["CueListChild"] = Field(default_factory=list)
    children_complete: bool | None = None


class CueListContents(BaseModel):
    children: list[CueListChild] = Field(default_factory=list)
    direct_child_count: StrictInt | None = None
    returned_count: StrictInt = 0
    max_depth: StrictInt
    max_cues: StrictInt
    truncated: bool = False
    truncation_reasons: list[str] = Field(default_factory=list)


class CueListCoverage(BaseModel):
    source: Literal["documented_osc"] = "documented_osc"
    unavailable_via_osc: list[str] = Field(default_factory=list)
    unavailable_fields: list[str] = Field(default_factory=list)
    failed_routes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CueListReadResult(BaseModel):
    ok: bool = True
    status: Literal["ok", "partial", "error"] = "ok"
    partial: bool = False
    workspace_id: str
    error_code: str | None = None
    message: str | None = None
    suggested_action: str | None = None
    coverage: CueListCoverage = Field(default_factory=CueListCoverage)
    warnings: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)


class CueListsResult(CueListReadResult):
    cue_list_count: StrictInt = 0
    cue_cart_count: StrictInt = 0
    container_count: StrictInt = 0
    current_cue_list_id: str | None = None
    current_container_id: str | None = None
    excluded_cue_cart_count: StrictInt = 0
    cue_lists: list[CueListInventoryItem] = Field(default_factory=list)


class CueListDetailsResult(CueListReadResult):
    cue_list_id: str
    profile: Literal["safe", "technical"] = "safe"
    identity: CueListIdentity | None = None
    basics: CueContainerBasics | None = None
    state: CueListState | None = None
    playhead: CueListPosition | None = None
    playback_position: CueListPosition | None = None
    incoming_timecode: CueListTimecode | None = None
    contents: CueListContents | None = None
    technical_payload: JsonValue = None


class CueCartIdentity(CueListIdentity):
    type: Literal["Cue Cart", "Cart"] = "Cue Cart"


class CueCartCell(CueListChild):
    row: Annotated[StrictInt, Field(ge=0)] | None = None
    column: Annotated[StrictInt, Field(ge=0)] | None = None


class CueCartGrid(BaseModel):
    rows: Annotated[StrictInt, Field(ge=1)] | None = None
    columns: Annotated[StrictInt, Field(ge=1)] | None = None
    cells: list[CueCartCell] = Field(default_factory=list)
    complete: bool = False


class CueCartContents(BaseModel):
    direct_child_count: StrictInt | None = None
    returned_count: StrictInt = 0
    max_cues: StrictInt
    truncated: bool = False
    truncation_reasons: list[str] = Field(default_factory=list)


class CueCartDetailsResult(CueListReadResult):
    cue_cart_id: str
    profile: Literal["safe", "technical"] = "safe"
    identity: CueCartIdentity | None = None
    basics: CueContainerBasics | None = None
    state: CueListState | None = None
    incoming_timecode: CueListTimecode | None = None
    contents: CueCartContents | None = None
    grid: CueCartGrid | None = None
    technical_payload: JsonValue = None
