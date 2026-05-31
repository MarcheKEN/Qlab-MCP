"""Typed request and response shapes exposed through FastMCP."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    "workspace_unavailable",
    "qlab_unreachable",
    "edit_not_confirmed",
    "workspace_in_show_mode",
    "show_mode_unknown",
]
CreateCueStatus = Literal["dry_run", "created", "verification_failed"]
UpdateCueStatus = Literal[
    "dry_run",
    "dry_run_preflight_failed",
    "planned",
    "preflight_failed",
    "updated",
    "updated_with_confirmed_timeouts",
    "partial_failed",
    "verification_failed",
    "cue_not_found",
]
UpdateCuesStatus = Literal[
    "dry_run",
    "preflight_failed",
    "updated",
    "updated_with_confirmed_timeouts",
    "partial_failed",
    "verification_failed",
]


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
    warnings: list[str] = Field(default_factory=list)


class WorkspaceOverviewResult(BaseModel):
    """Bounded structural map of a QLab workspace."""

    workspace_id: str
    workspace: Any
    cue_count: int
    summary: dict[str, Any]
    cue_lists: list[dict[str, Any]]
    cue_index: dict[str, Any] | None = None
    editorial_health: dict[str, Any] | None = None
    limits: dict[str, Any]
    warnings: list[str]
    errors: dict[str, str] | None = None
    live_state: dict[str, Any] | None = None


class WorkspaceSettingsResult(BaseModel):
    """Read-only infrastructure/settings inventory for a QLab workspace."""

    workspace_id: str
    profile: str
    sections: dict[str, Any]
    summary: dict[str, Any]
    redactions: list[dict[str, str]] = Field(default_factory=list)
    errors: dict[str, str] | None = None


class WorkspaceSettingDetailsResult(BaseModel):
    """Read-only safe or technical details for one QLab workspace setting item."""

    workspace_id: str
    section: str
    kind: str
    ref: str | None = None
    profile: str
    details: Any = None
    choices: list[dict[str, Any]] = Field(default_factory=list)
    redactions: list[dict[str, str]] = Field(default_factory=list)
    errors: dict[str, str] | None = None
    message: str | None = None


class CueQueryResult(BaseModel):
    """Filtered cue query result."""

    workspace_id: str
    filters: list[dict[str, Any]]
    profile: str
    scanned_count: int
    matched_count: int
    returned_count: int
    total_cue_ids: int
    truncated: bool
    truncation_reasons: list[str] = Field(default_factory=list)
    scanned_all_cues: bool
    result_limited: bool
    limits: dict[str, Any]
    cues: list[dict[str, Any]]
    errors: dict[str, str] | None = None


class CueDetailsResult(BaseModel):
    """Grouped cue details for one cue."""

    workspace_id: str
    cue_ref: str
    profile: str
    cue_type: str | None = None
    properties: dict[str, Any]
    sections: dict[str, dict[str, Any]] | None = None
    update_capabilities: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    active_count: int | None = None
    message: str | None = None


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
    created_cue_id: str | None = None
    placement: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    errors: dict[str, str] | None = Field(
        default=None,
        description="Per-property or verification errors; null when no errors were detected.",
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
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff: dict[str, dict[str, Any]] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
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
    profile: UpdateCueProfile = Field(
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


class UpdateCueItemResult(BaseModel):
    """Per-cue result for a batch update."""

    cue_ref: str
    cue_id: str | None = None
    profile: str = "common"
    status: UpdateCueStatus = Field(description="Machine-readable result status for this cue update item.")
    properties: dict[str, Any] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)
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
