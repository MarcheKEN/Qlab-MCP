"""FastMCP server exposing read-only QLab cue information tools."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from .models import (
    CueChildrenResult,
    CueDetailsResult,
    CueIdsResult,
    CueListsResult,
    CuePropertyResult,
    CueValuesResult,
    RunningCuesResult,
    SelectedCuesResult,
    WorkspaceCueInventoryResult,
    WorkspaceListResult,
    WorkspaceOverviewResult,
)
from .qlab import QLabReader


CueProfile = Literal["basic", "timing", "status", "targets", "group", "type_specific", "full"]

WorkspaceId = Annotated[
    str,
    Field(
        min_length=1,
        description="QLab workspace unique ID or OSC-compatible workspace display name returned by qlab_get_workspaces.",
    ),
]
CueRef = Annotated[
    str,
    Field(
        min_length=1,
        description="Cue number, cue unique ID, selected, playhead, playbackPosition, or active.",
    ),
]
ReadOnlyPropertyPath = Annotated[
    str,
    Field(
        min_length=1,
        description="Allowlisted read-only QLab cue property path, for example name, type, duration, or opacity.",
    ),
]
CueValueKeys = Annotated[
    list[str],
    Field(
        min_length=1,
        max_length=100,
        description="Allowlisted read-only cue property paths to read with QLab valuesForKeys.",
    ),
]


mcp = FastMCP(
    "QLab Cue Reader",
    instructions=(
        "Use these tools to read QLab 5 workspace and cue information over OSC. "
        "All tools are read-only. Most tools require an explicit workspace_id; "
        "qlab_get_workspaces and qlab_get_workspace_overview can orient from the currently open workspace. "
        "Start with qlab_get_workspace_overview for a bounded first-pass show summary, "
        "then use focused ID/detail tools for deeper inspection."
    ),
)


def _reader() -> QLabReader:
    return QLabReader()


@mcp.tool
def qlab_get_workspaces() -> WorkspaceListResult:
    """Return the open QLab workspaces so a client can choose a workspace_id."""
    return WorkspaceListResult.model_validate(_reader().get_workspaces())


@mcp.tool
def qlab_get_workspace_overview(
    workspace_id: Annotated[
        str | None,
        Field(
            description=(
                "QLab workspace unique ID or OSC-compatible display name. "
                "When omitted, exactly one workspace must be open."
            ),
        ),
    ] = None,
    max_depth: Annotated[
        int,
        Field(
            ge=0,
            le=5,
            description="How many child layers to inspect with shallow OSC reads. Use 0 for cue lists only.",
        ),
    ] = 2,
    max_cues: Annotated[
        int,
        Field(
            ge=1,
            le=1000,
            description="Maximum number of cue/list/group nodes to include in the overview tree.",
        ),
    ] = 200,
    include_selected_and_running: Annotated[
        bool,
        Field(description="When true, include shallow selected and running-or-paused cue snapshots."),
    ] = True,
) -> WorkspaceOverviewResult:
    """Return a bounded first-pass summary of a QLab workspace for orientation."""
    return WorkspaceOverviewResult.model_validate(
        _reader().get_workspace_overview(
            workspace_id=workspace_id,
            max_depth=max_depth,
            max_cues=max_cues,
            include_selected_and_running=include_selected_and_running,
        )
    )


@mcp.tool
def qlab_get_cue_lists(
    workspace_id: WorkspaceId,
    include_children: Annotated[
        bool,
        Field(description="When true, include nested cue data. Large workspaces may produce large UDP replies."),
    ] = True,
) -> CueListsResult:
    """Return cue lists and cue carts for an explicit QLab workspace."""
    return CueListsResult.model_validate(_reader().get_cue_lists(workspace_id, include_children))


@mcp.tool
def qlab_get_workspace_cue_ids(
    workspace_id: WorkspaceId,
    include_children: Annotated[
        bool,
        Field(description="When true, include IDs for nested cues; when false, only top-level cue lists and carts."),
    ] = True,
) -> CueIdsResult:
    """Return unique IDs for all cue lists, carts, and optionally nested cues in a workspace."""
    return CueIdsResult.model_validate(_reader().get_workspace_cue_ids(workspace_id, include_children))


@mcp.tool
def qlab_get_workspace_cue_inventory(
    workspace_id: WorkspaceId,
    include_details: Annotated[
        bool,
        Field(description="When true, read the selected detail profile for each cue ID. This can make many OSC requests."),
    ] = False,
    detail_profile: Annotated[
        CueProfile,
        Field(description="Grouped read-only cue detail profile to request when include_details is true."),
    ] = "basic",
) -> WorkspaceCueInventoryResult:
    """Return a workspace cue inventory, optionally adding detail profiles for every cue ID."""
    return WorkspaceCueInventoryResult.model_validate(
        _reader().get_workspace_cue_inventory(workspace_id, include_details, detail_profile)
    )


@mcp.tool
def qlab_get_selected_cues(
    workspace_id: WorkspaceId,
    include_children: Annotated[
        bool,
        Field(description="When true, include nested cue data for selected groups. Large selections may produce large UDP replies."),
    ] = True,
) -> SelectedCuesResult:
    """Return the currently selected cues for an explicit QLab workspace."""
    return SelectedCuesResult.model_validate(_reader().get_selected_cues(workspace_id, include_children))


@mcp.tool
def qlab_get_running_cues(
    workspace_id: WorkspaceId,
    include_paused: Annotated[
        bool,
        Field(description="When true, include paused active cues as well as currently running cues."),
    ] = True,
    include_children: Annotated[
        bool,
        Field(description="When true, include nested cue data. Large active cue sets may produce large UDP replies."),
    ] = True,
) -> RunningCuesResult:
    """Return running cues, optionally including paused active cues, for a QLab workspace."""
    return RunningCuesResult.model_validate(
        _reader().get_running_cues(workspace_id, include_paused, include_children)
    )


@mcp.tool
def qlab_get_cue_children(
    workspace_id: WorkspaceId,
    cue_ref: CueRef,
    shallow: Annotated[
        bool,
        Field(description="When true, return only the first child layer."),
    ] = False,
    ids_only: Annotated[
        bool,
        Field(description="When true, return unique IDs instead of full child cue data."),
    ] = False,
) -> CueChildrenResult:
    """Return children for a group, cue list, or cue cart by cue number or cue unique ID."""
    return CueChildrenResult.model_validate(
        _reader().get_cue_children(workspace_id, cue_ref, shallow, ids_only)
    )


@mcp.tool
def qlab_get_cue_details(
    workspace_id: WorkspaceId,
    cue_ref: CueRef,
    profile: Annotated[
        CueProfile,
        Field(description="Grouped read-only cue detail profile."),
    ] = "basic",
) -> CueDetailsResult:
    """Return grouped read-only cue details for one cue."""
    return CueDetailsResult.model_validate(_reader().get_cue_details(workspace_id, cue_ref, profile))


@mcp.tool
def qlab_get_cue_values(
    workspace_id: WorkspaceId,
    cue_ref: CueRef,
    keys: CueValueKeys,
) -> CueValuesResult:
    """Read a custom batch of allowlisted QLab cue state keys via valuesForKeys."""
    return CueValuesResult.model_validate(_reader().read_cue_values(workspace_id, cue_ref, keys))


@mcp.tool
def qlab_read_cue_property(
    workspace_id: WorkspaceId,
    cue_ref: CueRef,
    property_path: ReadOnlyPropertyPath,
) -> CuePropertyResult:
    """Read one allowlisted QLab cue property without exposing action or write OSC commands."""
    return CuePropertyResult.model_validate(_reader().read_cue_property(workspace_id, cue_ref, property_path))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
