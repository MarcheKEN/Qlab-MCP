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
    WorkspaceSettingDetailsResult,
    WorkspaceOverviewResult,
    WorkspaceSettingsResult,
)
from .qlab import QLabReader


CueProfile = Literal[
    "auto",
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
CueIndexProfile = Literal["minimal", "health"]
CueQueryFilter = Literal[
    "type",
    "flagged",
    "armed",
    "disarmed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "isLoaded",
    "isOverridden",
    "isAuditioning",
    "colorName",
    "name_contains",
    "number_prefix",
    "cue_list_id",
    "parent_id",
    "hasFileTargets",
    "hasCueTargets",
    "skipIfDisarmed",
    "autoLoad",
    "continueMode",
    "hasPreWait",
    "hasPostWait",
    "hasDuration",
    "name_empty",
    "displayName_empty",
    "number_empty",
    "ambiguous_label",
    "flagged_or_broken",
]
WorkspaceSettingsSection = Literal["audio", "video", "network", "midi", "light", "general"]
WorkspaceSettingsProfile = Literal["safe", "technical"]
WorkspaceSettingDetailKind = Literal[
    "all",
    "output_patch",
    "input_patch",
    "audio_map",
    "route",
    "stage",
    "video_input_patch",
    "network_patch",
    "midi_patch",
    "light_patch",
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

Use qlab_get_workspace_settings when you need compact infrastructure/settings inventory such as patches, stages, routes, MIDI, network, or light availability. It is the default settings map and avoids heavy light-patch dumps.

Use qlab_get_workspace_setting_details after settings when you need one specific patch, stage, route, map, or light patch. Use profile="safe" first for compact normalized details; use profile="technical" only when raw routing/device diagnostics are justified.

Use qlab_query_cues for filtered cue searches across up to 500 cues by default, or up to 5000 cues when a caller explicitly raises the scan limit, then qlab_get_cue_details for one cue that needs deeper inspection.

The public interface is intentionally limited to six read-only tools. Internal OSC reads for workspaces, cue lists, children, values, and settings are composed behind them.
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
                "Maximum cue/list/group nodes to include in the bounded tree preview before marking it as truncated. "
                "Defaults to 1000 so large workspaces can be mapped while cue_index stays compact."
            ),
        ),
    ] = 1000,
    include_live_state: Annotated[
        bool,
        Field(
            description=(
                "When true, add a live_state block with shallow selected and running-or-paused cues. "
                "Leave false when you only need the show structure."
            )
        ),
    ] = False,
    include_cue_index: Annotated[
        bool,
        Field(
            description=(
                "When true, add a compact complete cue_index with columns and rows. "
                "Keep enabled when an agent needs a full workspace map beyond the bounded tree preview."
            )
        ),
    ] = True,
    max_index_cues: Annotated[
        int,
        Field(
            ge=1,
            le=5000,
            description=(
                "Maximum cue IDs to include in cue_index before marking the index as truncated. "
                "This does not change the bounded tree preview limits."
            ),
        ),
    ] = 1000,
    cue_index_profile: Annotated[
        CueIndexProfile,
        Field(
            description=(
                "Cue index shape. minimal returns identity and position columns; health adds armed, flagged, "
                "color, broken/warning, and continue-mode diagnostics."
            ),
        ),
    ] = "minimal",
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
            include_cue_index=include_cue_index,
            max_index_cues=max_index_cues,
            cue_index_profile=cue_index_profile,
        )
    )


@mcp.tool(
    title="Get QLab Workspace Settings",
    tags={"qlab", "settings", "patches", "routing", "inventory", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
)
def qlab_get_workspace_settings(
    workspace_id: WorkspaceId,
    sections: Annotated[
        list[WorkspaceSettingsSection] | None,
        Field(
            description=(
                "Workspace settings sections to inspect. Use audio, video, network, midi, light, and/or general. "
                "When omitted, all sections are read."
            ),
        ),
    ] = None,
) -> WorkspaceSettingsResult:
    """Return compact read-only QLab Workspace Settings infrastructure inventory.

    Use this after the overview when an agent needs audio patches/maps, video stages/routes, network patches,
    MIDI patches, light availability, or general workspace settings. This is the default settings map:
    it returns names, IDs, counts, relationships, connection state, and redaction metadata, but it does not
    read the full light patch or raw hardware payloads.
    """
    return WorkspaceSettingsResult.model_validate(
        _reader().get_workspace_settings(
            workspace_id=workspace_id,
            sections=sections,
        )
    )


@mcp.tool(
    title="Get QLab Workspace Setting Details",
    tags={"qlab", "settings", "patches", "routing", "details", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
)
def qlab_get_workspace_setting_details(
    workspace_id: WorkspaceId,
    section: Annotated[
        WorkspaceSettingsSection,
        Field(description="Workspace settings section to inspect in detail."),
    ],
    kind: Annotated[
        WorkspaceSettingDetailKind | None,
        Field(
            description=(
                "Specific settings item kind. Use all, output_patch, input_patch, audio_map, route, stage, "
                "video_input_patch, network_patch, midi_patch, or light_patch. Defaults to all except light, "
                "where it defaults to light_patch."
            ),
        ),
    ] = None,
    ref: Annotated[
        str | None,
        Field(
            description=(
                "Optional settings item name or uniqueID. If omitted for a kind with multiple candidates, "
                "the tool returns choices instead of guessing."
            ),
        ),
    ] = None,
    profile: Annotated[
        WorkspaceSettingsProfile,
        Field(
            description=(
                "Read-only detail profile. safe returns compact normalized details suitable for normal agent use. "
                "technical can include diagnostic IPs, ports, interfaces, device details, raw routes, regions, "
                "geometry, mesh/warp, audio-map levels, and light-patch payloads. Passcodes are always redacted."
            ),
        ),
    ] = "safe",
) -> WorkspaceSettingDetailsResult:
    """Return read-only details for one workspace setting item.

    Use this after qlab_get_workspace_settings when a specific patch, stage, route, map, or light patch needs
    deeper inspection. The default safe profile summarizes large structures: light patches become instrument
    indexes, video stages become stage/region/route summaries, and audio maps omit long level arrays. Use
    technical only for explicit low-level audits.
    """
    return WorkspaceSettingDetailsResult.model_validate(
        _reader().get_workspace_setting_details(
            workspace_id=workspace_id,
            section=section,
            kind=kind,
            ref=ref,
            profile=profile,
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
                "Required first filter. Supported filters: type, flagged, armed, disarmed, isBroken, isWarning, "
                "isRunning, isPaused, isLoaded, isOverridden, isAuditioning, colorName, name_contains, "
                "number_prefix, cue_list_id, parent_id, hasFileTargets, hasCueTargets, skipIfDisarmed, "
                "autoLoad, continueMode, hasPreWait, hasPostWait, hasDuration, name_empty, "
                "displayName_empty, number_empty, ambiguous_label, flagged_or_broken."
            ),
        ),
    ],
    primary_value: Annotated[
        Any,
        Field(
            description=(
                "Value for primary_filter. Use booleans for state/target/timing-presence filters; "
                "strings for type, colorName, name_contains, number_prefix, cue_list_id, parent_id, or continueMode."
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
                "health/targets add warning, target, and file-target presence without paths; "
                "technical/full_sensitive can expose notes, paths, scripts, or heavy stage payloads."
            ),
        ),
    ] = "basic_safe",
    max_results: Annotated[
        int,
        Field(
            ge=1,
            le=5000,
            description="Maximum matching cues to return. Scanning may continue past this to report matched_count.",
        ),
    ] = 500,
    max_cues_scanned: Annotated[
        int,
        Field(
            ge=1,
            le=5000,
            description="Maximum cue IDs to scan from cueLists/uniqueIDs before marking the result truncated.",
        ),
    ] = 500,
) -> CueQueryResult:
    """Search many QLab cues with one required filter plus optional AND filters.

    Use this after the overview to find cue sets such as Audio cues, Light cues, flagged cues, broken cues,
    warnings, media-target cues, cue-target transport cues, or named/numbered ranges. Results are capped at
    500 returned matches and 500 scanned cue IDs by default so agents stay compact. Callers can explicitly
    raise either limit up to 5000 for large shows; truncation metadata reports incomplete scans or result caps.
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
                "Read-only detail profile. Use auto for safe type-aware sections, health for warnings/broken cues, "
                "targets for target IDs without file paths, technical for notes/targets/routing/paths, "
                "and full_sensitive only for deep audits."
            )
        ),
    ] = "auto",
) -> CueDetailsResult:
    """Return batched read-only details for one cue using QLab valuesForKeys when possible.

    Use auto for safe type-aware inspection, health for warnings, and technical/full_sensitive only when justified.
    """
    return CueDetailsResult.model_validate(_reader().get_cue_details(workspace_id, cue_ref, profile))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
