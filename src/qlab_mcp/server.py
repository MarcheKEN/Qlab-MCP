"""FastMCP server exposing read-only QLab cue information tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .models import (
    CueDetailsResult,
    CueQueryResult,
    QlabConnectionCheckResult,
    WorkspaceOverviewResult,
)
from .qlab import QLabReader


CueProfile = Literal[
    "basic_safe",
    "basic",
    "technical",
    "health",
    "timing",
    "status",
    "targets",
    "group",
    "type_specific",
    "full",
    "full_sensitive",
]
CueQueryFilter = Literal[
    "type",
    "flagged",
    "armed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "colorName",
    "name_contains",
    "number_prefix",
    "cue_list_id",
    "parent_id",
]

WorkspaceId = Annotated[
    str,
    Field(
        min_length=1,
        description=(
            "QLab workspace unique ID or OSC-compatible workspace display name returned by "
            "qlab_check_connection.available_workspaces."
        ),
    ),
]
CueRef = Annotated[
    str,
    Field(
        min_length=1,
        description="Cue number, cue unique ID, selected, playhead, playbackPosition, or active.",
    ),
]
READ_ONLY_QLAB_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


mcp = FastMCP(
    "QLab Cue Reader",
    instructions="""
Use these tools to read QLab 5 workspace and cue information over OSC.

All tools are read-only and intentionally avoid playback, editing, deletion, and raw OSC.

Start with qlab_check_connection to verify QLab, workspace candidates, passcode, and read access.

Then use qlab_get_workspace_overview for a bounded show map.

Use qlab_query_cues for filtered cue searches, then qlab_get_cue_details for one cue that needs deeper inspection.

The public interface is intentionally limited to these four tools. Internal OSC reads for workspaces, cue lists, children, and values are composed behind them.
""",
)


def _reader() -> QLabReader:
    return QLabReader()


@mcp.tool(
    title="Check QLab Connection",
    tags={"qlab", "diagnostics", "orientation", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
)
def qlab_check_connection(
    workspace_id: Annotated[
        str | None,
        Field(
            description=(
                "Optional QLab workspace unique ID or OSC-compatible display name to validate. "
                "When omitted, exactly one workspace must be open for a ready result."
            ),
        ),
    ] = None,
    require_read_access: Annotated[
        bool,
        Field(
            description=(
                "When true, verify that the MCP can read /cueLists/shallow from the workspace. "
                "Leave true when checking whether the MCP is ready to inspect a show. "
                "Edit/control scopes are reported as not_checked because proving them requires non-read-only probes."
            )
        ),
    ] = True,
) -> QlabConnectionCheckResult:
    """Check whether QLab, workspace resolution, passcode, and safe read access are ready.

    Use this before the overview; it reports safe permission evidence and explains edit/control limits.
    """
    return QlabConnectionCheckResult.model_validate(
        _reader().check_connection(workspace_id=workspace_id, require_read_access=require_read_access)
    )


@mcp.tool(
    title="Get QLab Workspace Overview",
    tags={"qlab", "orientation", "structure", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
)
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
            description=(
                "How many child layers of cue lists/groups to inspect using shallow OSC reads. "
                "Use 0 for cue-list names only; increase only when the show map is incomplete."
            ),
        ),
    ] = 2,
    max_cues: Annotated[
        int,
        Field(
            ge=1,
            le=1000,
            description=(
                "Maximum cue/list/group nodes to include before marking the overview as truncated. "
                "Keeps large shows from producing oversized UDP replies."
            ),
        ),
    ] = 200,
    include_live_state: Annotated[
        bool,
        Field(
            description=(
                "When true, add a live_state block with shallow selected and running-or-paused cues. "
                "Leave false when you only need the show structure."
            )
        ),
    ] = False,
) -> WorkspaceOverviewResult:
    """Map what the QLab show contains and how cue lists, groups, and cues are organized.

    Use this as the first structural read after selecting a workspace; it is bounded and shallow by default.
    """
    return WorkspaceOverviewResult.model_validate(
        _reader().get_workspace_overview(
            workspace_id=workspace_id,
            max_depth=max_depth,
            max_cues=max_cues,
            include_live_state=include_live_state,
        )
    )


@mcp.tool(
    title="Query QLab Cues",
    tags={"qlab", "query", "inventory", "details", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
)
def qlab_query_cues(
    workspace_id: WorkspaceId,
    primary_filter: Annotated[
        CueQueryFilter,
        Field(
            description=(
                "Required first filter. Supported filters: type, flagged, armed, isBroken, isWarning, "
                "isRunning, isPaused, colorName, name_contains, number_prefix, cue_list_id, parent_id."
            ),
        ),
    ],
    primary_value: Annotated[
        Any,
        Field(
            description=(
                "Value for primary_filter. Use booleans for flagged/armed/isBroken/isWarning/isRunning/isPaused; "
                "strings for type, colorName, name_contains, number_prefix, cue_list_id, or parent_id."
            ),
        ),
    ],
    optional_filters: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description=(
                "Additional filters combined with AND. Each entry should be {'filter': '<name>', 'value': <value>} "
                "using the same filter names and value rules as primary_filter."
            ),
        ),
    ] = None,
    profile: Annotated[
        CueProfile,
        Field(
            description=(
                "Read-only data profile to return for matching cues. Default basic_safe gives compact identity/status; "
                "health adds warning/broken state; full_sensitive can expose notes, paths, or scripts."
            ),
        ),
    ] = "basic_safe",
    max_results: Annotated[
        int,
        Field(
            ge=1,
            le=1000,
            description="Maximum matching cues to return. Scanning may continue past this to report matched_count.",
        ),
    ] = 100,
    max_cues_scanned: Annotated[
        int,
        Field(
            ge=1,
            le=5000,
            description="Maximum cue IDs to scan from cueLists/uniqueIDs before marking the result truncated.",
        ),
    ] = 1000,
) -> CueQueryResult:
    """Search many QLab cues with one required filter plus optional AND filters.

    Use this after the overview to find cue sets such as Audio cues, flagged cues, warnings, or named/numbered ranges.
    """
    return CueQueryResult.model_validate(
        _reader().query_cues(
            workspace_id=workspace_id,
            primary_filter=primary_filter,
            primary_value=primary_value,
            optional_filters=optional_filters,
            profile=profile,
            max_results=max_results,
            max_cues_scanned=max_cues_scanned,
        )
    )


@mcp.tool(
    title="Get QLab Cue Details",
    tags={"qlab", "details", "diagnostics", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
)
def qlab_get_cue_details(
    workspace_id: WorkspaceId,
    cue_ref: CueRef,
    profile: Annotated[
        CueProfile,
        Field(
            description=(
                "Read-only detail profile. Use basic_safe for normal inspection, health for warnings/broken cues, "
                "technical for notes/targets/routing, and full_sensitive only for deep audits."
            )
        ),
    ] = "basic_safe",
) -> CueDetailsResult:
    """Return batched read-only details for one cue using QLab valuesForKeys when possible.

    Use basic_safe for normal inspection, health for warnings, and technical/full_sensitive only when justified.
    """
    return CueDetailsResult.model_validate(_reader().get_cue_details(workspace_id, cue_ref, profile))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
