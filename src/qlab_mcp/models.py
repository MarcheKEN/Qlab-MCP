"""Typed request and response shapes exposed through FastMCP."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    errors: dict[str, str] | None = None
    active_count: int | None = None
    message: str | None = None
