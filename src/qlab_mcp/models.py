"""Typed request and response shapes exposed through FastMCP."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorkspaceListResult(BaseModel):
    """Open QLab workspaces."""

    workspaces: Any = Field(description="QLab workspace data returned by /workspaces.")
    status: str = Field(description="QLab reply status.")


class CueListsResult(BaseModel):
    """Cue lists and carts in a workspace."""

    workspace_id: str
    cue_lists: Any


class CueIdsResult(BaseModel):
    """Unique cue IDs in a workspace."""

    workspace_id: str
    include_children: bool
    cue_count: int
    cue_ids: list[str]


class WorkspaceCueInventoryResult(BaseModel):
    """Workspace cue inventory, with optional details."""

    workspace_id: str
    cue_count: int
    cue_ids: list[str]
    detail_profile: str | None = None
    cues: list[dict[str, Any]] | None = None
    errors: dict[str, str] | None = None


class SelectedCuesResult(BaseModel):
    """Selected cues in a workspace."""

    workspace_id: str
    selected_cues: Any


class RunningCuesResult(BaseModel):
    """Running or paused cues in a workspace."""

    workspace_id: str
    running_cues: Any


class CueChildrenResult(BaseModel):
    """Children of a cue list, cart, or group."""

    workspace_id: str
    cue_ref: str
    children: Any
    ids_only: bool
    shallow: bool


class CueDetailsResult(BaseModel):
    """Grouped cue details for one cue."""

    workspace_id: str
    cue_ref: str
    profile: str
    properties: dict[str, Any]
    errors: dict[str, str] | None = None


class CueValuesResult(BaseModel):
    """Custom read-only cue values."""

    workspace_id: str
    cue_ref: str
    keys: list[str]
    values: Any


class CuePropertyResult(BaseModel):
    """One read-only cue property."""

    workspace_id: str
    cue_ref: str
    property: str
    value: Any
