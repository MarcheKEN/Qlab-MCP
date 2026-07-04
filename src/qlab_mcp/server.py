"""FastMCP server exposing safe QLab inspection and gated write tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from .errors import QLabMcpError
from .models import (
    CreateCueResult,
    CueDetailsBatchResult,
    CueDetailsResult,
    CueUpdateInput,
    CueQueryResult,
    QlabConnectionCheckResult,
    WorkspaceStatusResult,
    WorkspaceSettingRequestInput,
    UpdateCuesResult,
    WriteReadinessResult,
    WorkspaceSettingDetailsResult,
    WorkspaceOverviewResult,
    WorkspaceSettingsResult,
)
from .qlab import QLabReader
from .sanitizer import sanitize_exception_message
from .server_responses import (
    cue_details_success_payload as _cue_details_success_payload,
    overview_success_payload as _overview_success_payload,
    query_success_payload as _query_success_payload,
    safe_tool_error_message as _safe_tool_error_message,
    settings_success_payload as _settings_success_payload,
    structured_error_result as _structured_error_result,
)


CueQueryProfile = Literal[
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
    "inspector_safe",
    "editable",
    "full",
    "full_sensitive",
]
CueDetailsProfile = Literal[
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
    "inspector_safe",
    "editable",
    "full",
    "full_sensitive",
    "exhaustive",
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
WorkspaceSettingsMode = Literal["summary", "details"]
WorkspaceSettingsProfile = Literal["safe", "technical", "exhaustive"]
WorkspaceStatusProfile = Literal["summary", "technical"]
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
WritableCueType = Literal[
    "memo",
    "group",
    "wait",
    "audio",
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
CueRefs = Annotated[
    list[CueRef],
    Field(
        min_length=1,
        description="List of cue numbers, cue unique IDs, selected, playhead, playbackPosition, or active. Maximum 50.",
        json_schema_extra={"maxItems": 50},
    ),
]
READ_ONLY_QLAB_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
GATED_CREATE_QLAB_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
CHECK_CONNECTION_TIMEOUT = 6.0
WORKSPACE_OVERVIEW_TIMEOUT = 45.0
WORKSPACE_STATUS_TIMEOUT = 60.0
WORKSPACE_SETTINGS_TIMEOUT = 60.0
WORKSPACE_SETTING_DETAILS_TIMEOUT = 60.0
QUERY_CUES_TIMEOUT = 60.0
CUE_DETAILS_TIMEOUT = 20.0
WRITE_READINESS_TIMEOUT = 6.0
CREATE_CUE_TIMEOUT = 30.0
UPDATE_CUES_TIMEOUT = 180.0

T = TypeVar("T")


mcp = FastMCP(
    "QLab Workspace Inspector",
    mask_error_details=True,
    instructions="""
Use these tools to read QLab 5 workspace and cue information over OSC.

The seven inspector tools are read-only and intentionally avoid playback, editing, deletion, and raw OSC.
Write mode is a separate gated preface: it is disabled unless QLAB_ENABLE_WRITE=true and defaults to dry-run.
When write mode is ready, all update profiles may exist; safe properties can execute as real writes, while dangerous or high-risk properties require explicit per-item confirm_gates.
Write mode also requires QLAB_PASSCODE on the server plus edit confirmed by /connect, and currently only supports basic cue creation plus gated batch cue updates.

Start with qlab_check_connection to verify QLab, workspace candidates, passcode, and read access.

Then use qlab_get_workspace_overview for a bounded show map.

Use qlab_get_workspace_status for compact operational status derived from documented read-only OSC reads: cue warnings, trigger/timecode summaries, settings summary, and explicit not_exposed sections for Workspace Status data QLab does not expose over OSC.

Use qlab_get_workspace_settings(mode="summary") when you need compact infrastructure/settings inventory such as patches, stages, routes, MIDI, network, or light availability. It returns available_detail_requests and avoids heavy light-patch dumps.

Use qlab_get_workspace_settings(mode="details", requests=[...]) after settings when you need one or more specific patches, stages, routes, maps, MIDI/network items, or the light patch. Use profile="safe" first for compact normalized details; use profile="technical" or profile="exhaustive" only when raw routing/device diagnostics are justified. qlab_get_workspace_setting_details remains as a single-request compatibility wrapper.

Use qlab_query_cues for filtered cue searches across up to 500 cues by default, or up to 5000 cues when a caller explicitly raises the scan limit, then qlab_get_cue_details for one cue that needs deeper inspection.

For write preflight, call qlab_check_write_readiness with an explicit workspace_id. Only call qlab_create_cue or qlab_update_cues after reviewing dry_run output. This server does not expose GO, stop, panic, raw OSC, or playback control.
""",
)


def _reader() -> QLabReader:
    return QLabReader()


def _run_tool(factory: Callable[[], T]) -> T:
    try:
        return factory()
    except (QLabMcpError, ValueError) as exc:
        raise ToolError(_safe_tool_error_message(exc)) from exc


def _workspace_overview_error(workspace_id: Any, **error: Any) -> WorkspaceOverviewResult:
    payload = {
        **_structured_error_result(**error),
        "workspace_id": str(workspace_id or ""),
        "workspace": None,
        "cue_count": 0,
        "cue_count_meaning": "failed",
        "summary": {},
        "cue_lists": [],
        "limits": {},
        "warnings": [error["message"]],
        "errors": {"validation": error["message"], "error_code": error["error_code"]},
    }
    return WorkspaceOverviewResult.model_validate(payload)


def _workspace_status_error(workspace_id: Any, profile: Any, **error: Any) -> WorkspaceStatusResult:
    payload = {
        **_structured_error_result(**error),
        "workspace_id": str(workspace_id or ""),
        "profile": str(profile or "summary"),
        "partial": False,
        "sections": {},
        "summary": {},
        "limits": {},
        "warnings": [error["message"]],
        "errors": {"validation": error["message"], "error_code": error["error_code"]},
    }
    return WorkspaceStatusResult.model_validate(payload)


def _settings_error(workspace_id: Any, mode: Any, profile: Any, **error: Any) -> WorkspaceSettingsResult:
    payload = {
        **_structured_error_result(**error),
        "workspace_id": str(workspace_id or ""),
        "mode": str(mode or "summary"),
        "profile": str(profile or "safe"),
        "requested_profile": str(profile or "safe"),
        "sections": {},
        "summary": {"error_count": 1},
        "available_detail_requests": [],
        "results": [],
        "redactions": [],
        "warnings": [error["message"]],
        "errors": {"validation": error["message"], "error_code": error["error_code"]},
    }
    return WorkspaceSettingsResult.model_validate(payload)


def _setting_details_error(workspace_id: Any, section: Any, kind: Any, profile: Any, **error: Any) -> WorkspaceSettingDetailsResult:
    payload = {
        **_structured_error_result(**error),
        "workspace_id": str(workspace_id or ""),
        "section": str(section or ""),
        "kind": str(kind or ""),
        "profile": str(profile or "safe"),
        "details": None,
        "choices": [],
        "redactions": [],
        "warnings": [error["message"]],
        "errors": {"validation": error["message"], "error_code": error["error_code"]},
        "message": error["message"],
    }
    return WorkspaceSettingDetailsResult.model_validate(payload)


def _query_error(workspace_id: Any, primary_filter: Any, profile: Any, max_results: Any, max_cues_scanned: Any, **error: Any) -> CueQueryResult:
    payload = {
        **_structured_error_result(**error),
        "workspace_id": str(workspace_id or ""),
        "filters": [{"filter": str(primary_filter or ""), "value": None}],
        "profile": str(profile or "basic_safe"),
        "scanned_count": 0,
        "matched_count": 0,
        "returned_count": 0,
        "total_cue_ids": 0,
        "query_completeness": "failed",
        "query_completeness_reasons": ["validation"],
        "truncated": False,
        "scanned_all_cues": False,
        "result_limited": False,
        "limits": {"max_results": max_results, "max_cues_scanned": max_cues_scanned},
        "cues": [],
        "warnings": [error["message"]],
        "errors": {"validation": error["message"], "error_code": error["error_code"]},
    }
    return CueQueryResult.model_validate(payload)


def _cue_details_error(workspace_id: Any, cue_ref: Any, profile: Any, **error: Any) -> CueDetailsResult | CueDetailsBatchResult:
    base = _structured_error_result(**error)
    if isinstance(cue_ref, list):
        return CueDetailsBatchResult.model_validate(
            {
                **base,
                "workspace_id": str(workspace_id or ""),
                "requested_count": len(cue_ref),
                "succeeded_count": 0,
                "failed_count": len(cue_ref),
                "profile": str(profile or "auto"),
                "results": [],
                "warnings": [error["message"]],
                "errors": {"validation": error["message"], "error_code": error["error_code"]},
            }
        )
    return CueDetailsResult.model_validate(
        {
            **base,
            "workspace_id": str(workspace_id or ""),
            "cue_ref": str(cue_ref or ""),
            "profile": str(profile or "auto"),
            "properties": {},
            "warnings": [error["message"]],
            "errors": {"validation": error["message"], "error_code": error["error_code"]},
        }
    )


@mcp.tool(
    title="Check QLab Connection",
    tags={"qlab", "diagnostics", "orientation", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=CHECK_CONNECTION_TIMEOUT,
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
                "The result also reports /connect scopes and /showMode Edit/Show state when available."
            )
        ),
    ] = True,
) -> QlabConnectionCheckResult:
    """Check whether QLab, workspace resolution, passcode, and safe read access are ready.

    Use this before the overview; it reports /connect permission scopes, /showMode state, and safe read access.
    """
    return _run_tool(
        lambda: QlabConnectionCheckResult.model_validate(
            _reader().check_connection(workspace_id=workspace_id, require_read_access=require_read_access)
        )
    )


@mcp.tool(
    title="Get QLab Workspace Overview",
    tags={"qlab", "orientation", "structure", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_OVERVIEW_TIMEOUT,
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
            description=(
                "How many child layers of cue lists/groups to inspect using shallow OSC reads. "
                "Use 0 for cue-list names only; increase only when the show map is incomplete."
            ),
        ),
    ] = 2,
    max_cues: Annotated[
        int,
        Field(
            description=(
                "Maximum cue/list/group nodes to include in the bounded tree preview before marking it as truncated. "
                "Raise up to 5000 for large workspace load checks."
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
            description=(
                "Maximum cue IDs to include in cue_index before marking the index as truncated. "
                "This does not change the bounded tree preview limits."
            ),
        ),
    ] = 5000,
    cue_index_profile: Annotated[
        str,
        Field(
            description=(
                "Cue index shape. minimal returns identity and position columns; health adds armed, flagged, "
                "color, broken/warning, and continue-mode diagnostics."
            ),
        ),
    ] = "minimal",
    include_global_count: Annotated[
        bool,
        Field(
            description=(
                "When true, read cueLists/uniqueIDs to calculate the real total cue-item count, "
                "including cue list roots and Group children. "
                "This is potentially expensive and is off by default."
            ),
        ),
    ] = False,
) -> WorkspaceOverviewResult:
    """Map what the QLab show contains and how cue lists, groups, and cues are organized.

    Use this as the first structural read after selecting a workspace; it includes Edit/Show mode and is bounded and shallow by default.
    """
    try:
        return WorkspaceOverviewResult.model_validate(
            _overview_success_payload(_reader().get_workspace_overview(
                workspace_id=workspace_id,
                max_depth=max_depth,
                max_cues=max_cues,
                include_live_state=include_live_state,
                include_cue_index=include_cue_index,
                max_index_cues=max_index_cues,
                cue_index_profile=cue_index_profile,
                include_global_count=include_global_count,
            ))
        )
    except (QLabMcpError, ValueError, TypeError) as exc:
        return _workspace_overview_error(
            workspace_id,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={
                "workspace_id": workspace_id,
                "max_depth": max_depth,
                "max_cues": max_cues,
                "max_index_cues": max_index_cues,
                "cue_index_profile": cue_index_profile,
            },
            allowed={"max_depth": "0..5", "max_cues": "1..5000", "max_index_cues": "1..5000", "cue_index_profile": ["minimal", "health"]},
        )


@mcp.tool(
    title="Get QLab Workspace Status",
    tags={"qlab", "status", "diagnostics", "timecode", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_STATUS_TIMEOUT,
)
def qlab_get_workspace_status(
    workspace_id: WorkspaceId,
    profile: Annotated[
        str,
        Field(
            description=(
                "summary returns compact derived operational status. technical adds safe settings section payloads. "
                "This is not a full clone of QLab's Workspace Status window; unavailable OSC sections are explicit."
            ),
        ),
    ] = "summary",
    include_timecode: Annotated[
        bool,
        Field(description="When true, include timecode config and per-list/cart currentTimecode/text samples when exposed."),
    ] = True,
    max_cues_scanned: Annotated[
        int,
        Field(
            description="Maximum cues to scan for cue-derived status summaries before marking them partial.",
        ),
    ] = 1000,
    sample_limit: Annotated[
        int,
        Field(
            description="Maximum sample cue/status rows returned inside compact sections.",
        ),
    ] = 10,
) -> WorkspaceStatusResult:
    """Return compact read-only Workspace Status context for a QLab workspace.

    Uses documented OSC reads and derived summaries. Sections that QLab does not expose as safe read-only OSC
    endpoints are returned with source='not_exposed' instead of invented values.
    """
    try:
        return WorkspaceStatusResult.model_validate(
            _reader().get_workspace_status(
                workspace_id=workspace_id,
                profile=profile,
                include_timecode=include_timecode,
                max_cues_scanned=max_cues_scanned,
                sample_limit=sample_limit,
            )
        )
    except (QLabMcpError, ValueError, TypeError) as exc:
        return _workspace_status_error(
            workspace_id,
            profile,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={"profile": profile, "max_cues_scanned": max_cues_scanned, "sample_limit": sample_limit},
            allowed={"profile": ["summary", "technical"], "max_cues_scanned": "1..5000", "sample_limit": "0..50"},
        )


@mcp.tool(
    title="Get QLab Workspace Settings",
    tags={"qlab", "settings", "patches", "routing", "inventory", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_settings(
    workspace_id: WorkspaceId,
    mode: Annotated[
        str,
        Field(
            description=(
                "summary returns compact inventory plus available_detail_requests. "
                "details runs one or more focused detail requests and returns a batch result."
            ),
        ),
    ] = "summary",
    sections: Annotated[
        list[str] | None,
        Field(
            description=(
                "Summary mode sections to inspect. Use audio, video, network, midi, light, and/or general. "
                "When omitted in summary mode, all sections are read. Ignored in details mode."
            ),
        ),
    ] = None,
    requests: Annotated[
        list[WorkspaceSettingRequestInput] | None,
        Field(
            description=(
                "Details mode requests. Each item has section, kind, and optional ref. "
                "Examples: {'section':'audio','kind':'output_patch','ref':'Main'}, "
                "{'section':'video','kind':'stage','ref':'TELON'}, or "
                "{'section':'light','kind':'light_patch'}."
            ),
        ),
    ] = None,
    profile: Annotated[
        str,
        Field(
            description=(
                "Read-only profile for details mode. safe returns compact redacted summaries; technical can include "
                "routing, regions, interfaces, IPs/ports, device data, and raw payloads when needed; exhaustive returns "
                "the deepest allowlisted read-only data and may be large. Summary mode stays compact."
            ),
        ),
    ] = "safe",
) -> WorkspaceSettingsResult:
    """Return read-only QLab Workspace Settings summary or batched details.

    Summary mode is the first settings read after the overview: it returns compact sections, counts, redactions,
    errors, and available_detail_requests. Details mode accepts one or more requests and returns independent
    per-request results; one failed request does not block other valid requests.
    """
    try:
        return WorkspaceSettingsResult.model_validate(
            _settings_success_payload(_reader().get_workspace_settings(
                workspace_id=workspace_id,
                mode=mode,
                sections=sections,
                requests=[request.model_dump() if hasattr(request, "model_dump") else request for request in requests]
                if requests is not None
                else None,
                profile=profile,
            ))
        )
    except (QLabMcpError, ValueError, TypeError) as exc:
        return _settings_error(
            workspace_id,
            mode,
            profile,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={"mode": mode, "sections": sections, "requests": requests, "profile": profile},
            allowed={"mode": ["summary", "details"], "sections": ["audio", "video", "network", "midi", "light", "general"], "profile": ["safe", "technical", "exhaustive"]},
        )


@mcp.tool(
    title="Get QLab Workspace Setting Details",
    tags={"qlab", "settings", "patches", "routing", "details", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTING_DETAILS_TIMEOUT,
)
def qlab_get_workspace_setting_details(
    workspace_id: WorkspaceId,
    section: Annotated[
        str,
        Field(description="Workspace settings section to inspect in detail."),
    ],
    kind: Annotated[
        str | None,
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
        str,
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

    Backwards-compatible wrapper around qlab_get_workspace_settings(mode="details"). The default safe profile
    summarizes large structures: light patches become instrument indexes, video stages become stage/region/route
    summaries, and audio maps omit long level arrays. Use technical or exhaustive only for explicit low-level audits.
    """
    try:
        return WorkspaceSettingDetailsResult.model_validate(
            _settings_success_payload(_reader().get_workspace_setting_details(
                workspace_id=workspace_id,
                section=section,
                kind=kind,
                ref=ref,
                profile=profile,
            ))
        )
    except (QLabMcpError, ValueError, TypeError) as exc:
        return _setting_details_error(
            workspace_id,
            section,
            kind,
            profile,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={"section": section, "kind": kind, "ref": ref, "profile": profile},
            allowed={"sections": ["audio", "video", "network", "midi", "light", "general"], "kinds": list(WorkspaceSettingDetailKind.__args__) if hasattr(WorkspaceSettingDetailKind, "__args__") else None, "profile": ["safe", "technical", "exhaustive"]},
        )


@mcp.tool(
    title="Query QLab Cues",
    tags={"qlab", "query", "inventory", "details", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=QUERY_CUES_TIMEOUT,
)
def qlab_query_cues(
    workspace_id: WorkspaceId,
    primary_filter: Annotated[
        str,
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
        str,
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
            description="Maximum matching cues to return. Scanning may continue past this to report matched_count.",
        ),
    ] = 500,
    max_cues_scanned: Annotated[
        int,
        Field(
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
    try:
        return CueQueryResult.model_validate(
            _query_success_payload(_reader().query_cues(
                workspace_id=workspace_id,
                primary_filter=primary_filter,
                primary_value=primary_value,
                optional_filters=optional_filters,
                profile=profile,
                max_results=max_results,
                max_cues_scanned=max_cues_scanned,
            ))
        )
    except (QLabMcpError, ValueError, TypeError) as exc:
        return _query_error(
            workspace_id,
            primary_filter,
            profile,
            max_results,
            max_cues_scanned,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={"primary_filter": primary_filter, "optional_filters": optional_filters, "profile": profile, "max_results": max_results, "max_cues_scanned": max_cues_scanned},
            allowed={"filters": list(CueQueryFilter.__args__) if hasattr(CueQueryFilter, "__args__") else None, "profiles": list(CueQueryProfile.__args__) if hasattr(CueQueryProfile, "__args__") else None, "max_results": "1..5000", "max_cues_scanned": "1..5000"},
        )


@mcp.tool(
    title="Get QLab Cue Details",
    tags={"qlab", "details", "diagnostics", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=CUE_DETAILS_TIMEOUT,
)
def qlab_get_cue_details(
    workspace_id: WorkspaceId,
    cue_ref: CueRef | CueRefs,
    profile: Annotated[
        str,
        Field(
            description=(
                "Read-only detail profile. Use auto for safe type-aware sections, health for warnings/broken cues, "
                "inspector_safe for broader QLab Inspector-style details without file paths or scripts, "
                "targets for target IDs without file paths, technical for notes/targets/routing/paths, "
                "editable for safe details plus qlab_update_cues profile/property capabilities, "
                "full_sensitive for deep audits, and exhaustive for the deepest allowlisted read-only read "
                "including heavy/sensitive payloads; exhaustive may be large."
            )
        ),
    ] = "auto",
) -> CueDetailsResult | CueDetailsBatchResult:
    """Return read-only details for one cue, or a batch of up to 50 cues, using QLab valuesForKeys when possible.

    Use auto for safe type-aware inspection, inspector_safe for broader non-sensitive Inspector context,
    editable for update capability discovery,
    health for warnings, technical/full_sensitive only when justified, and exhaustive only for deep audits
    or load testing because it can expose large/sensitive payloads.
    """
    try:
        return (
            CueDetailsBatchResult.model_validate(_cue_details_success_payload(_reader().get_cue_details(workspace_id, cue_ref, profile)))
            if isinstance(cue_ref, list)
            else CueDetailsResult.model_validate(_cue_details_success_payload(_reader().get_cue_details(workspace_id, cue_ref, profile)))
        )
    except (QLabMcpError, ValueError, TypeError) as exc:
        return _cue_details_error(
            workspace_id,
            cue_ref,
            profile,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={"cue_ref": cue_ref, "profile": profile},
            allowed={"profiles": list(CueDetailsProfile.__args__) if hasattr(CueDetailsProfile, "__args__") else None, "batch_max": MAX_BATCH_CUE_DETAILS if "MAX_BATCH_CUE_DETAILS" in globals() else 50},
        )


@mcp.tool(
    title="Check QLab Write Readiness",
    tags={"qlab", "write-mode", "diagnostics", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WRITE_READINESS_TIMEOUT,
)
def qlab_check_write_readiness(
    workspace_id: WorkspaceId,
) -> WriteReadinessResult:
    """Check local write-mode readiness without sending any mutating OSC commands.

    This verifies QLAB_ENABLE_WRITE, required workspace_id, server-side QLAB_PASSCODE presence,
    planned write capabilities, edit permission confirmed by QLab /connect scopes, and Edit Mode from /showMode.
    """
    return _run_tool(
        lambda: WriteReadinessResult.model_validate(
            _reader().check_write_readiness(workspace_id)
        )
    )


@mcp.tool(
    title="Create QLab Cue",
    tags={"qlab", "write-mode", "cue-create", "gated-write"},
    annotations=GATED_CREATE_QLAB_TOOL,
    timeout=CREATE_CUE_TIMEOUT,
)
def qlab_create_cue(
    workspace_id: WorkspaceId,
    cue_type: Annotated[
        WritableCueType,
        Field(
            description=(
                "Cue type to create. This preface allows only blank memo, group, wait, or audio cues."
            ),
        ),
    ],
    properties: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "Optional safe initial properties. Allowed keys: name, number, armed, flagged, colorName, "
                "preWait, postWait, duration, and continueMode."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool | None,
        Field(
            description=(
                "When true, plan the OSC operations but send no mutating commands. "
                "When omitted, QLAB_WRITE_DRY_RUN_DEFAULT is used and defaults to true."
            ),
        ),
    ] = None,
    after_cue_id: Annotated[
        str | None,
        Field(
            description=(
                "Optional future placement target. In this preface it is accepted for dry-run planning only; "
                "real creation with after_cue_id fails safely."
            ),
        ),
    ] = None,
) -> CreateCueResult:
    """Create one blank allowlisted cue or return a dry-run plan.

    Real creation requires QLAB_ENABLE_WRITE, server-side QLAB_PASSCODE, edit confirmed by /connect, and Edit Mode from /showMode.
    Dry-run planning never sends mutating OSC.
    This tool never exposes playback control, raw OSC, target edits, scripts, routing, or media paths.
    """
    return _run_tool(
        lambda: CreateCueResult.model_validate(
            _reader().create_cue(
                workspace_id=workspace_id,
                cue_type=cue_type,
                properties=properties,
                dry_run=dry_run,
                after_cue_id=after_cue_id,
            )
        )
    )


@mcp.tool(
    title="Edit QLab Cues",
    tags={"qlab", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_CREATE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_cues(
    workspace_id: WorkspaceId,
    updates: Annotated[
        list[CueUpdateInput],
        Field(
            min_length=1,
            max_length=50,
            description=(
                "Cue updates to plan or apply. Each item has cue_ref, profile, properties, operations, and optional confirm_gates "
                "containing exact confirm_token values from reviewed dry-run planned_operations. "
                "cue_ref must be a concrete cue number or unique ID; selected, active, playhead, and playbackPosition "
                "are not accepted."
            ),
        ),
    ],
    dry_run: Annotated[
        bool | None,
        Field(
            description=(
                "When true, plan and diff the update but send no mutating commands. "
                "When omitted, QLAB_WRITE_DRY_RUN_DEFAULT is used and defaults to true."
            ),
        ),
    ] = None,
) -> UpdateCuesResult:
    """Edit one or more existing cues through the cue editing registry, or return a dry-run plan.

    Real updates require QLAB_ENABLE_WRITE, server-side QLAB_PASSCODE, edit confirmed by /connect, and Edit Mode from /showMode.
    Dry-run planning never sends mutating OSC.
    High-risk profiles and unvalidated properties are cataloged for planning and require exact dry-run confirm_tokens for real writes.
    Batch real writes run all preflight checks before sending any setter and use cue unique IDs for setters.
    """
    return _run_tool(
        lambda: UpdateCuesResult.model_validate(
            _reader().edit_cues(
                workspace_id=workspace_id,
                updates=[update.model_dump() if hasattr(update, "model_dump") else update for update in updates],
                dry_run=dry_run,
            )
        )
    )


@mcp.tool(
    title="Update QLab Cues (compatibility alias)",
    tags={"qlab", "write-mode", "cue-update", "batch-update", "gated-write", "deprecated-alias"},
    annotations=GATED_CREATE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_update_cues(
    workspace_id: WorkspaceId,
    updates: Annotated[
        list[CueUpdateInput],
        Field(
            min_length=1,
            max_length=50,
            description=(
                "Compatibility alias for qlab_edit_cues. Prefer qlab_edit_cues for new work. "
                "Each item has cue_ref, profile, properties, operations, and optional confirm_gates "
                "containing exact confirm_token values from reviewed dry-run planned_operations."
            ),
        ),
    ],
    dry_run: Annotated[
        bool | None,
        Field(
            description=(
                "When true, plan and diff the update but send no mutating commands. "
                "When omitted, QLAB_WRITE_DRY_RUN_DEFAULT is used and defaults to true."
            ),
        ),
    ] = None,
) -> UpdateCuesResult:
    """Compatibility alias for qlab_edit_cues.

    Dry-run planning never sends mutating OSC. Prefer qlab_edit_cues for new work.
    """
    return qlab_edit_cues(workspace_id=workspace_id, updates=updates, dry_run=dry_run)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
