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
    status: str
    workspace_id: str
    write_enabled: bool
    dry_run_default: bool
    passcode_configured: bool
    capabilities: dict[str, Any]
    checks: dict[str, Any]
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str


class CreateCueResult(BaseModel):
    """Result for gated cue creation or dry-run planning."""

    ok: bool
    status: str
    workspace_id: str
    cue_type: str
    dry_run: bool
    created_cue_id: str | None = None
    placement: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    message: str


class UpdateCueResult(BaseModel):
    """Result for gated cue update or dry-run planning."""

    ok: bool
    status: str
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

    cue_ref: str
    profile: UpdateCueProfile = "common"
    properties: dict[str, Any] | None = None
    operations: list[dict[str, Any]] | None = None


class UpdateCueItemResult(BaseModel):
    """Per-cue result for a batch update."""

    cue_ref: str
    cue_id: str | None = None
    profile: str = "common"
    status: str
    properties: dict[str, Any] = Field(default_factory=dict)
    operations: list[dict[str, Any]] = Field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff: dict[str, dict[str, Any]] = Field(default_factory=dict)
    planned_operations: list[dict[str, Any]] = Field(default_factory=list)
    executed_operations: list[dict[str, Any]] = Field(default_factory=list)
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, Any] | None = None


class UpdateCuesResult(BaseModel):
    """Batch result for gated cue updates or dry-run planning."""

    ok: bool
    status: str
    workspace_id: str
    dry_run: bool
    requested_count: int
    planned_count: int
    updated_count: int
    failed_count: int
    timeout_confirmed_count: int
    results: list[UpdateCueItemResult]
    errors: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)
    message: str
