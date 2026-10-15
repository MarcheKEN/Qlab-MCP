"""FastMCP server exposing safe QLab inspection and gated write tools."""

from __future__ import annotations

import asyncio
import threading

from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from mcp.types import ToolAnnotations
from pathlib import Path
from pydantic import Field, StrictBool, StrictInt, StrictStr, TypeAdapter

from . import __version__
from .media import search_media_files
from .audio_analysis_models import AudioAnalysisRequest, AudioAnalysisResult, Resolution
from .errors import QLabMcpError
from .models import (
    CreateCueListsResult,
    CreateCuesResult,
    DeleteCuesResult,
    CueDetailsBatchResult,
    CueDetailsResult,
    CueListEditInput,
    CueQueryResult,
    MoveCueInput,
    MoveCueListInput,
    MoveCuesResult,
    QlabConnectionCheckResult,
    WorkspaceAudioSettingsResult,
    WorkspaceDomainSettingsResult,
    WorkspaceGeneralSettingsResult,
    WorkspaceLightSettingsResult,
    WorkspaceMidiSettingsResult,
    WorkspaceNetworkSettingsResult,
    WorkspaceStatusResult,
    UpdateCuesResult,
    WriteReadinessResult,
    WorkspaceOverviewResult,
    WorkspaceSettingsEditRequest,
    WorkspaceSettingsEditResult,
    GeneralSettingsOperation,
    AudioOutputPatchOperation,
    VideoRouteOperation,
    VideoStageOperation,
    VideoRegionOperation,
    WorkspaceVideoSettingsResult,
    VideoStageResult,
    VideoOutputRouteResult,
    VideoRegionResult,
    CanonicalWorkspaceUUID,
)
from .qlab import QLabReader
from .workspace_documents import (
    get_workspace_document, open_workspace, save_workspace, close_workspace,
)
from .write.control import (ControlCueEditInput, DevampCueEditInput, TargetCueEditInput,
                            edit_control_cues, edit_devamp_cues, edit_target_cues)
from .write.group import GroupCueEditInput, edit_group_cues
from .write.video_fx import FxReadSelector, EffectType, catalogue as video_effect_catalogue
from .write.remaining import (
    AudioCueEditInput, MicCueEditInput, LightCueEditInput, FadeCueEditInput,
    NetworkCueEditInput, MidiCueEditInput, MidiFileCueEditInput,
    TimecodeCueEditInput, ScriptCueEditInput, edit_remaining_cues,
)
from .write.remaining import INSPECTIONS, inspect as inspect_remaining
AudioInspection = INSPECTIONS["audio"]
MicInspection = INSPECTIONS["mic"]
LightInspection = INSPECTIONS["light"]
FadeInspection = INSPECTIONS["fade"]
NetworkInspection = INSPECTIONS["network"]
MidiInspection = INSPECTIONS["midi"]
MidiFileInspection = INSPECTIONS["midi_file"]
TimecodeInspection = INSPECTIONS["timecode"]
ScriptInspection = INSPECTIONS["script"]
from .write.visual import (VideoCueEditInput, CameraCueEditInput, TextCueEditInput,
                           edit_video_cues, edit_camera_cues, edit_text_cues)
from .cues.details import MAX_BATCH_CUE_DETAILS
from .cues.list_models import CueListsResult, CueListDetailsResult, CueCartDetailsResult
from .cues.audio import AudioCuesResult, AudioCueDetailsResult
from .cues.mic import MicCuesResult, MicCueDetailsResult
from .cues.light_group import LightCuesResult, LightCueDetailsResult, GroupCuesResult, GroupCueDetailsResult
from .cues.control import ControlCueType, ControlCuesResult, ControlCueDetailsResult
from .cues.remaining import (
    FadeCuesResult, FadeCueDetailsResult,
    NetworkCuesResult, NetworkCueDetailsResult,
    MidiCuesResult, MidiCueDetailsResult,
    TimecodeCuesResult, TimecodeCueDetailsResult,
    ScriptCuesResult, ScriptCueDetailsResult,
)
from .cues.visual import (
    VideoCuesResult, VideoCueDetailsResult, TextCuesResult, TextCueDetailsResult,
    CameraCuesResult, CameraCueDetailsResult, FontsResult,
)
from .cues.limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES
from .cues.query import MAX_SENSITIVE_QUERY_RESULTS
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
WorkspaceSettingsProfile = Annotated[
    Literal["safe", "technical", "exhaustive"],
    Field(
        description=(
            "safe returns compact normalized data; technical and exhaustive return deeper redacted payloads. "
            "Credentials remain redacted in every profile."
        )
    ),
]
WorkspaceSettingsRef = Annotated[
    str | None,
    Field(description="Optional exact settings item name or UUID. Omit it to return the domain overview or choices."),
]
WorkspaceAudioSettingsView = Annotated[
    Literal["overview", "output_patch", "input_patch"],
    Field(description="Use overview, or select one output_patch or input_patch."),
]
AudioInputChannel = Annotated[
    StrictInt | None,
    Field(ge=0, le=128, description="Cue-output row; 0 selects Main/output gains in the patch matrix."),
]
AudioOutputChannel = Annotated[
    StrictInt | None,
    Field(ge=0, description="Device-output column; 0 selects Main/input gains in the patch matrix."),
]
VideoSettingsProfile = Annotated[
    Literal["safe", "technical"],
    Field(description="safe returns typed summaries; technical also returns the redacted OSC payload."),
]
WorkspaceStatusProfile = Literal["summary", "technical"]
WritableCueType = Literal[
    "memo",
    "group",
    "wait",
    "audio",
    "mic",
    "video",
    "camera",
    "text",
    "light",
    "fade",
    "network",
    "midi",
    "midi_file",
    "timecode",
    "start",
    "stop",
    "pause",
    "load",
    "reset",
    "devamp",
    "goto",
    "target",
    "arm",
    "disarm",
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
        json_schema_extra={"maxItems": MAX_BATCH_CUE_DETAILS},
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
GATED_DESTRUCTIVE_QLAB_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)
CHECK_CONNECTION_TIMEOUT = 6.0
WORKSPACE_OVERVIEW_TIMEOUT = 45.0
WORKSPACE_STATUS_TIMEOUT = 60.0
WORKSPACE_SETTINGS_TIMEOUT = 60.0
QUERY_CUES_TIMEOUT = 60.0
CUE_DETAILS_TIMEOUT = 20.0
WRITE_READINESS_TIMEOUT = 6.0
CREATE_CUES_TIMEOUT = 300.0
UPDATE_CUES_TIMEOUT = 180.0
DELETE_CUES_TIMEOUT = 180.0
WORKSPACE_SETTINGS_WRITE_TIMEOUT = 60.0

T = TypeVar("T")
WorkspaceDomainResultT = TypeVar("WorkspaceDomainResultT", bound=WorkspaceDomainSettingsResult)


mcp = FastMCP(
    "QLab Workspace Inspector",
    version=__version__,
    mask_error_details=True,
    # Cache the static catalogue only; tool execution and QLab state stay fresh.
    middleware=[ResponseCachingMiddleware(
        list_tools_settings={"ttl": 300},
        call_tool_settings={"enabled": False},
        list_resources_settings={"enabled": False},
        list_prompts_settings={"enabled": False},
        read_resource_settings={"enabled": False},
        get_prompt_settings={"enabled": False},
    )],
    instructions="""
QLab MCP exposes forty-nine read-only tools plus thirty gated write tools. QLab access primarily uses OSC; media discovery searches the MCP user's home folder after consent.
Write mode requires QLAB_ENABLE_WRITE=true, QLAB_PASSCODE, QLab /connect Edit permission, and Edit Mode; it remains dry-run first.
This server does not expose GO, stop, panic, playback, audition, /live writes, arbitrary AppleScript, or raw OSC passthrough. Load loadTime, Target assignedNumber and documented cue Triggers use fixed local AppleScript reads/writes. Native Trigger reads require include_native_triggers=true; configuration requires disabled triggers, activation requires disarmed/no continuation/no skip, and Hotkey enabling is blocked without key/modifier readback.

Orient first with qlab_check_connection, then use a bounded workspace overview/status or the relevant domain-specific settings read, qlab_query_cues, and qlab_get_cue_details as needed. Resolve one exact workspace before any write. Use exact UUIDs for workspace and cue writes; never infer a workspace or target from selection, playhead, or active state.

Before searching for, inspecting, or assigning a local media file, ask the person directly: "¿Me das permiso para buscar y acceder a los archivos que necesito?" Once granted, use qlab_search_media_files; it searches the MCP user's home folder. The operating system still controls which files the MCP process can read. Use the family editor's dry run and fresh readback before changing a cue.

For every real write, call qlab_check_write_readiness, inspect an explicit dry-run, review warnings/errors/planned operations, supply only the exact fresh confirmation token required by that operation, execute once, and require fresh readback. Do not retry a mutation after a timeout or identity ambiguity. Batches are not automatically transactional.

Create, Edit, Move, Delete, and Workspace Settings writes have different token, atomicity, rollback, and postcondition rules; follow each tool's description and output fields. A structural or settings result is not runtime validation: a successful write is not necessarily GO-ready. Runtime evidence in this project is bounded to QLab 5.5.10.
""",
)


def _reader() -> QLabReader:
    return QLabReader()


@mcp.tool(title="Get QLab Workspace Document", tags={"qlab", "workspace", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=30.0)
def qlab_get_workspace_document(workspace_id: CanonicalWorkspaceUUID) -> dict[str, Any]:
    """Read exact local workspace UUID, document path, dirty flag and native mode/activity.

    Requires the running /Applications/QLab.app. No save or close; unknown state blocks writes.
    """
    return _run_tool(lambda reader: get_workspace_document(reader, str(workspace_id)))


@mcp.tool(title="Open QLab Workspace", tags={"qlab", "workspace", "gated-write"},
          annotations=GATED_CREATE_QLAB_TOOL, timeout=30.0)
def qlab_open_workspace(path: StrictStr, dry_run: StrictBool = True,
                        confirm_token: StrictStr | None = None) -> dict[str, Any]:
    """Plan or open one existing local .qlab5 document by absolute path.

    Requires an empty inventory (no workspaces open), a bounded file fingerprint
    and a five-minute single-use token.
    One native event followed by fresh inventory. Do not retry an uncertain result automatically.
    Does not create a workspace, run cues or change file contents.
    """
    return _run_tool(lambda reader: open_workspace(reader, path, dry_run, confirm_token))


@mcp.tool(title="Save QLab Workspace", tags={"qlab", "workspace", "gated-write"},
          annotations=GATED_DESTRUCTIVE_QLAB_TOOL, timeout=30.0)
def qlab_save_workspace(workspace_id: CanonicalWorkspaceUUID, dry_run: StrictBool = True,
                        confirm_token: StrictStr | None = None) -> dict[str, Any]:
    """Plan or save an exact inactive local workspace at its existing path.

    Saves all current unsaved edits. Requires Edit Mode and a five-minute single-use token.
    The dirty flag is not an edit revision. One native event and fresh inventory; no Save As,
    automatic retry, or cue execution.
    """
    return _run_tool(lambda reader: save_workspace(reader, str(workspace_id), dry_run, confirm_token))


@mcp.tool(title="Close QLab Workspace", tags={"qlab", "workspace", "gated-write"},
          annotations=GATED_DESTRUCTIVE_QLAB_TOOL, timeout=30.0)
def qlab_close_workspace(workspace_id: CanonicalWorkspaceUUID, dry_run: StrictBool = True,
                         confirm_token: StrictStr | None = None) -> dict[str, Any]:
    """Plan or close an exact inactive local workspace only when it has no unsaved changes.

    Requires Edit Mode and a five-minute single-use token. Uses close saving no after a fresh
    dirty check, then verifies disappearance. No discard, implicit save or automatic retry.
    """
    return _run_tool(lambda reader: close_workspace(reader, str(workspace_id), dry_run, confirm_token))


@mcp.tool(title="Get QLab Video Effect Catalogue", tags={"qlab", "video", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=6.0)
def qlab_get_video_effect_catalogue(
    effect_types: Annotated[list[EffectType], Field(min_length=1, max_length=10)] | None = None,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    limit: Annotated[StrictInt, Field(ge=1, le=10)] = 10,
) -> dict[str, Any]:
    """Discover documented FX names, keys, types, enums and conservative write bands.

    Paged static catalogue; no workspace, OSC or AppleScript access. Defaults are
    recorded QLab 5.5.10 evidence. Metadata never grants permission to write a
    live effect: use its exact cue Get and a fresh family-editor dry run.
    """
    return video_effect_catalogue(effect_types, offset=offset, limit=limit)


@mcp.tool(title="Search QLab Media Files", tags={"qlab", "media", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=6.0)
def qlab_search_media_files(
    query: Annotated[StrictStr, Field(min_length=1, max_length=255)],
    max_results: Annotated[StrictInt, Field(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """After the user agrees, find local files by name in the MCP user's home folder.

    Returns absolute paths for fileTarget in qlab_edit_audio_cues,
    qlab_edit_video_cues or qlab_edit_midi_file_cues. Search is limited to
    20,000 entries and five seconds; truncated means results may be incomplete.
    Symlinks are skipped. Does not inspect contents or validate media formats.
    No OSC requests, downloads, copies or cue changes; use a dry-run before assignment.
    """
    try:
        return search_media_files((str(Path.home()),), query, max_results)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(title="Analyze QLab Audio File", tags={"qlab", "media", "audio", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=300.0)
async def qlab_analyze_audio_file(
    path: Annotated[StrictStr, Field(min_length=1, description="Absolute path to one local audio file; access requires user consent.")],
    start_ms: Annotated[StrictInt, Field(ge=0, description="Source-file start in milliseconds, a multiple of 10.")] = 0,
    end_ms: Annotated[StrictInt, Field(gt=0, description="Exclusive source-file end in milliseconds, a multiple of 10; null uses file end.")] | None = None,
    resolution_ms: Resolution = 100,
    offset: Annotated[StrictInt, Field(ge=0, description="Row offset within the requested interval; use next_offset to continue.")] = 0,
    max_frames: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
    expected_analysis_id: Annotated[StrictStr, Field(min_length=1, description="Use the previous page identity to detect changes to the source.")] | None = None,
) -> AudioAnalysisResult:
    """Read audio levels, frequency bands and estimated attacks/beats without OSC or playback.

    Default 100 ms tuples include columns and units. Pages contain at most 5000
    rows and 512 KiB; continue with next_offset and expected_analysis_id.
    Summaries cover this page; loudness and rhythm have explicit block/context
    scopes. Times refer to the source file, excluding QLab trims, rate and loops.
    Requires the optional audio extra and FFmpeg/ffprobe in the MCP process PATH.
    No file changes, cue changes, downloads or dependency installation.
    """
    from .audio_analysis import analyze_audio_file

    request = AudioAnalysisRequest(path=path, start_ms=start_ms, end_ms=end_ms,
                                   resolution_ms=resolution_ms, offset=offset,
                                   max_frames=max_frames, expected_analysis_id=expected_analysis_id)
    cancelled = threading.Event()
    worker = asyncio.create_task(asyncio.to_thread(analyze_audio_file, request, cancelled))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        cancelled.set()
        # Wait for cleanup even if the caller cancels more than once.
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
        raise


def _run_tool(
    factory: Callable[[QLabReader], T],
    timeout: float | None = None,
    *,
    translate_errors: bool = True,
) -> T:
    reader = _reader()
    try:
        if timeout is not None:
            set_read_deadline = getattr(reader, "set_read_deadline", None)
            if callable(set_read_deadline):
                set_read_deadline(timeout)
        return factory(reader)
    except (QLabMcpError, ValueError) as exc:
        if not translate_errors:
            raise
        raise ToolError(_safe_tool_error_message(exc)) from exc
    finally:
        close = getattr(reader, "close", None)
        if callable(close):
            close()


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


def _workspace_domain_data(domain: str, view: str, profile: str, value: Any) -> Any:
    if value is None:
        return None
    if domain == "general":
        return value
    if domain == "video" and view in {"stage", "route"}:
        return value
    if domain in {"audio", "network", "midi"} and view != "overview" and isinstance(value, dict):
        technical_payload = value.get("technical_payload")
        detail = {key: item for key, item in value.items() if key != "technical_payload"}
        return {"detail": detail, "technical_payload": technical_payload}
    if domain == "light" and isinstance(value, dict):
        if profile == "safe":
            return {"detail": value}
        return {
            "detail": {"summary": value.get("summary") or {"patch_present": False}},
            "technical_payload": value.get("patch"),
        }
    if profile in {"technical", "exhaustive"}:
        return {"technical_payload": value}
    if view == "overview":
        return {"overview": value}
    return {"detail": value}


def _workspace_domain_payload(
    payload: dict[str, Any],
    *,
    domain: str,
    view: str,
    ref: str | None,
    profile: str,
) -> dict[str, Any]:
    is_overview = "sections" in payload
    value = (payload.get("sections") or {}).get(domain) if is_overview else payload.get("details")
    if domain == "video" and is_overview and isinstance(value, dict):
        value = dict(value)
        errors = payload.get("errors") or {}
        for key, route in (("input_patches", "inputPatchList"), ("routes", "routes"), ("stages", "stages")):
            if f"video.{route}" in errors:
                value[key] = None
    normalized = {
        key: payload.get(key)
        for key in (
            "ok",
            "status",
            "partial",
            "error_code",
            "suggested_action",
            "message",
            "received",
            "allowed",
        )
        if payload.get(key) is not None
    }
    normalized.update(
        {
            "workspace_id": str(payload.get("workspace_id") or ""),
            "domain": domain,
            "coverage": "partial",
            "profile": str(payload.get("profile") or profile),
            "view": view,
            "ref": ref,
            "data": _workspace_domain_data(domain, view, profile, value),
            "choices": payload.get("choices") or [],
            "redactions": payload.get("redactions") or [],
            "warnings": payload.get("warnings") or [],
            "errors": payload.get("errors"),
        }
    )
    return _settings_success_payload(normalized)


def _run_workspace_settings_domain(
    workspace_id: str,
    *,
    domain: str,
    view: str,
    ref: str | None,
    profile: WorkspaceSettingsProfile,
    detail_kind: str | None,
    result_model: type[WorkspaceDomainResultT],
    allowed: dict[str, Any],
    exact_video: bool = False,
    detail_options: dict[str, Any] | None = None,
    validation_error: str | None = None,
) -> WorkspaceDomainResultT:
    try:
        if validation_error is not None:
            raise ValueError(validation_error)
        if view == "overview" and ref is not None:
            raise ValueError("ref is not allowed when view='overview'")

        def read(reader: QLabReader) -> WorkspaceDomainResultT:
            if exact_video:
                payload = reader.get_video_setting(
                    workspace_id=workspace_id, kind=detail_kind, ref=ref, profile=profile,
                )
            elif detail_kind is None:
                payload = reader.get_workspace_settings(
                    workspace_id=workspace_id,
                    mode="summary",
                    sections=[domain],
                    profile=profile,
                )
            else:
                payload = reader.get_workspace_setting_details(
                    workspace_id=workspace_id,
                    section=domain,
                    kind=detail_kind,
                    ref=ref,
                    profile=profile,
                    **(detail_options or {}),
                )
            return result_model.model_validate(
                _workspace_domain_payload(
                    payload,
                    domain=domain,
                    view=view,
                    ref=ref,
                    profile=profile,
                )
            )

        return _run_tool(read, timeout=WORKSPACE_SETTINGS_TIMEOUT, translate_errors=False)
    except (QLabMcpError, ValueError, TypeError, ToolError) as exc:
        message = sanitize_exception_message(exc)
        payload = {
            **_structured_error_result(
                error_code="validation_failed",
                message=message,
                received={"view": view, "ref": ref, "profile": profile, **(detail_options or {})},
                allowed=allowed,
            ),
            "workspace_id": str(workspace_id or ""),
            "domain": domain,
            "coverage": "partial",
            "profile": profile,
            "view": view,
            "ref": ref,
            "data": None,
            "choices": [],
            "redactions": [],
            "warnings": [message],
            "errors": {"validation": message, "error_code": "validation_failed"},
        }
        return result_model.model_validate(payload)


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
    Do not use it as write authorization; call qlab_check_write_readiness before any real write.
    """
    return _run_tool(
        lambda reader: QlabConnectionCheckResult.model_validate(
            reader.check_connection(workspace_id=workspace_id, require_read_access=require_read_access)
        ),
        timeout=CHECK_CONNECTION_TIMEOUT,
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
        StrictInt,
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
        StrictInt,
        Field(
            ge=1,
            le=5000,
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
        StrictInt,
        Field(
            ge=1,
            le=5000,
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
    Follow with qlab_query_cues for filtered discovery or qlab_get_cue_details for one cue's properties.
    """
    try:
        return _run_tool(
            lambda reader: WorkspaceOverviewResult.model_validate(
                _overview_success_payload(reader.get_workspace_overview(
                    workspace_id=workspace_id,
                    max_depth=max_depth,
                    max_cues=max_cues,
                    include_live_state=include_live_state,
                    include_cue_index=include_cue_index,
                    max_index_cues=max_index_cues,
                    cue_index_profile=cue_index_profile,
                    include_global_count=include_global_count,
                ))
            ),
            timeout=WORKSPACE_OVERVIEW_TIMEOUT,
            translate_errors=False,
        )
    except (QLabMcpError, ValueError, TypeError, ToolError) as exc:
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
        StrictInt,
        Field(
            ge=1,
            le=5000,
            description="Maximum cues to scan for cue-derived status summaries before marking them partial.",
        ),
    ] = 1000,
    sample_limit: Annotated[
        StrictInt,
        Field(
            ge=0,
            le=50,
            description="Maximum sample cue/status rows returned inside compact sections.",
        ),
    ] = 10,
) -> WorkspaceStatusResult:
    """Return compact read-only Workspace Status context for a QLab workspace.

    Uses documented OSC reads and derived operational status. Sections that QLab does not expose as safe read-only OSC
    endpoints are returned with source='not_exposed' instead of invented values. Use overview or query for structure,
    not this tool as a full Workspace Status window clone.
    """
    try:
        return _run_tool(
            lambda reader: WorkspaceStatusResult.model_validate(
                reader.get_workspace_status(
                    workspace_id=workspace_id,
                    profile=profile,
                    include_timecode=include_timecode,
                    max_cues_scanned=max_cues_scanned,
                    sample_limit=sample_limit,
                )
            ),
            timeout=WORKSPACE_STATUS_TIMEOUT,
            translate_errors=False,
        )
    except (QLabMcpError, ValueError, TypeError, ToolError) as exc:
        return _workspace_status_error(
            workspace_id,
            profile,
            error_code="validation_failed",
            message=sanitize_exception_message(exc),
            received={"profile": profile, "max_cues_scanned": max_cues_scanned, "sample_limit": sample_limit},
            allowed={"profile": ["summary", "technical"], "max_cues_scanned": "1..5000", "sample_limit": "0..50"},
        )


@mcp.tool(
    title="Get QLab Workspace General Settings",
    tags={"qlab", "settings", "general", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_general_settings(workspace_id: WorkspaceId) -> WorkspaceGeneralSettingsResult:
    """Return the documented read-only General settings for one exact QLab workspace.

    QLab OSC exposes only minimum GO time and selection/playhead locking from the larger General settings panel.
    """
    return _run_workspace_settings_domain(
        workspace_id,
        domain="general",
        view="overview",
        ref=None,
        profile="safe",
        detail_kind=None,
        result_model=WorkspaceGeneralSettingsResult,
        allowed={"view": ["overview"]},
    )


@mcp.tool(
    title="Get QLab Workspace Audio Settings",
    tags={"qlab", "settings", "audio", "patches", "routing", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_audio_settings(
    workspace_id: WorkspaceId,
    view: WorkspaceAudioSettingsView = "overview",
    ref: WorkspaceSettingsRef = None,
    profile: WorkspaceSettingsProfile = "safe",
    input_channel: AudioInputChannel = None,
    output_channel: AudioOutputChannel = None,
) -> WorkspaceAudioSettingsResult:
    """Return an Audio settings overview, one exact output patch, or one exact input patch.

    The safe profile returns normalized summaries. Technical and exhaustive profiles add deeper redacted payloads.
    Provide both selectors with output_patch: (0,0) Main, (input,0) input gain, (0,output) output gain,
    or positive indices for a crosspoint. The full matrix is never scanned.
    """
    detail_kind = None if view == "overview" and profile == "safe" else "all" if view == "overview" else view
    validation_error = None
    if (input_channel is None) != (output_channel is None):
        validation_error = "input_channel and output_channel must be provided together"
    elif input_channel is not None and view != "output_patch":
        validation_error = "channel selectors are only valid when view='output_patch'"
    detail_options = (
        {"input_channel": input_channel, "output_channel": output_channel}
        if input_channel is not None or output_channel is not None
        else {}
    )
    return _run_workspace_settings_domain(
        workspace_id,
        domain="audio",
        view=view,
        ref=ref,
        profile=profile,
        detail_kind=detail_kind,
        result_model=WorkspaceAudioSettingsResult,
        detail_options=detail_options,
        validation_error=validation_error,
        allowed={
            "view": ["overview", "output_patch", "input_patch"],
            "profile": ["safe", "technical", "exhaustive"],
            "input_channel": "0..128, with output_channel and output_patch",
            "output_channel": ">=0, with input_channel and output_patch",
        },
    )


@mcp.tool(
    title="Get QLab Workspace Video Settings",
    tags={"qlab", "settings", "video", "patches", "routing", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_video_settings(
    workspace_id: WorkspaceId,
) -> WorkspaceVideoSettingsResult:
    """List Video input patches, output routes, and stages with their exact uniqueIDs.

    Use qlab_get_video_stage or qlab_get_video_output_route for exact details.
    OSC exposes only names and uniqueIDs for input patches and no independent device inventory.
    """
    return _run_workspace_settings_domain(
        workspace_id,
        domain="video",
        view="overview",
        ref=None,
        profile="safe",
        detail_kind=None,
        result_model=WorkspaceVideoSettingsResult,
        allowed={},
    )


@mcp.tool(
    title="Get QLab Video Stage",
    tags={"qlab", "settings", "video", "stages", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_video_stage(
    workspace_id: WorkspaceId,
    stage_id: Annotated[UUID, Field(description="Exact stage uniqueID from qlab_get_workspace_video_settings.")],
    profile: VideoSettingsProfile = "safe",
) -> VideoStageResult:
    """Read one exact Video stage and its regions, geometry, and assigned output routes.

    Technical adds the redacted OSC payload, including full control-point and mesh data.
    """
    return _run_workspace_settings_domain(
        workspace_id, domain="video", view="stage", ref=str(stage_id), profile=profile,
        detail_kind="stage", result_model=VideoStageResult,
        allowed={"profile": ["safe", "technical"]}, exact_video=True,
    )


@mcp.tool(
    title="Get QLab Video Output Route",
    tags={"qlab", "settings", "video", "routing", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_video_output_route(
    workspace_id: WorkspaceId,
    route_id: Annotated[UUID, Field(description="Exact route uniqueID from qlab_get_workspace_video_settings.")],
    profile: VideoSettingsProfile = "safe",
) -> VideoOutputRouteResult:
    """Read one exact Video output route, its destination, geometry, and guides state.

    Technical adds the redacted OSC payload and available destination hardware metadata.
    """
    return _run_workspace_settings_domain(
        workspace_id, domain="video", view="route", ref=str(route_id), profile=profile,
        detail_kind="route", result_model=VideoOutputRouteResult,
        allowed={"profile": ["safe", "technical"]}, exact_video=True,
    )


@mcp.tool(
    title="Get QLab Video Region",
    tags={"qlab", "settings", "video", "regions", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_video_region(
    workspace_id: WorkspaceId,
    stage_id: Annotated[UUID, Field(description="Exact parent stage UUID.")],
    region_id: Annotated[UUID, Field(description="Exact region UUID.")],
    subregion_index: Annotated[StrictInt | None, Field(ge=0, description="Optional one control-point subregion index.")] = None,
    control_point_index: Annotated[StrictInt | None, Field(ge=0, description="Optional one control-point index.")] = None,
) -> VideoRegionResult:
    """Read one region's OSC bounds and visibility, optionally one indexed control point."""
    if (subregion_index is None) != (control_point_index is None):
        raise ToolError("Both control-point indices are required together.")
    return _run_tool(
        lambda reader: VideoRegionResult.model_validate(reader.get_video_region(
            str(workspace_id), str(stage_id), str(region_id), subregion_index, control_point_index,
        )),
        timeout=WORKSPACE_SETTINGS_TIMEOUT,
    )


@mcp.tool(
    title="Get QLab Workspace Light Settings",
    tags={"qlab", "settings", "light", "patches", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_light_settings(
    workspace_id: WorkspaceId,
    profile: WorkspaceSettingsProfile = "safe",
) -> WorkspaceLightSettingsResult:
    """Return a safe summary or redacted technical payload for the workspace Light Patch.

    The Light Patch is the only documented read surface for the larger Light settings panel.
    """
    return _run_workspace_settings_domain(
        workspace_id,
        domain="light",
        view="light_patch",
        ref=None,
        profile=profile,
        detail_kind="light_patch",
        result_model=WorkspaceLightSettingsResult,
        allowed={"profile": ["safe", "technical", "exhaustive"]},
    )


@mcp.tool(
    title="Get QLab Workspace Network Settings",
    tags={"qlab", "settings", "network", "patches", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_network_settings(
    workspace_id: WorkspaceId,
    ref: WorkspaceSettingsRef = None,
    profile: WorkspaceSettingsProfile = "safe",
) -> WorkspaceNetworkSettingsResult:
    """Return the Network Patch inventory or one exact Network Patch by name or UUID.

    QLab OSC exposes patch names and UUIDs, not the complete Network settings panel.
    """
    detail_kind = None if ref is None and profile == "safe" else "network_patch" if ref is not None else "all"
    return _run_workspace_settings_domain(
        workspace_id,
        domain="network",
        view="overview" if ref is None else "network_patch",
        ref=ref,
        profile=profile,
        detail_kind=detail_kind,
        result_model=WorkspaceNetworkSettingsResult,
        allowed={"profile": ["safe", "technical", "exhaustive"]},
    )


@mcp.tool(
    title="Get QLab Workspace MIDI Settings",
    tags={"qlab", "settings", "midi", "patches", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_TIMEOUT,
)
def qlab_get_workspace_midi_settings(
    workspace_id: WorkspaceId,
    ref: WorkspaceSettingsRef = None,
    profile: WorkspaceSettingsProfile = "safe",
) -> WorkspaceMidiSettingsResult:
    """Return the MIDI Patch inventory or one exact MIDI Patch by name or UUID.

    QLab OSC exposes patch names and UUIDs, not the complete MIDI settings panel.
    """
    detail_kind = None if ref is None and profile == "safe" else "midi_patch" if ref is not None else "all"
    return _run_workspace_settings_domain(
        workspace_id,
        domain="midi",
        view="overview" if ref is None else "midi_patch",
        ref=ref,
        profile=profile,
        detail_kind=detail_kind,
        result_model=WorkspaceMidiSettingsResult,
        allowed={"profile": ["safe", "technical", "exhaustive"]},
    )


@mcp.tool(
    title="Get QLab Cue Lists",
    tags={"qlab", "cue-lists", "inventory", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=CUE_DETAILS_TIMEOUT,
)
def qlab_get_cue_lists(workspace_id: WorkspaceId) -> CueListsResult:
    """Return all Cue Lists and Cue Carts with exact UUIDs, types and current-container status.

    cue_lists contains both types; counts distinguish lists, carts and total containers. No children are read.
    Follow with qlab_get_cue_list_details or qlab_get_cue_cart_details according to type.
    """
    return _run_tool(lambda reader: reader.get_cue_list_inventory(workspace_id), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(
    title="Get QLab Cue List Details",
    tags={"qlab", "cue-lists", "details", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_OVERVIEW_TIMEOUT,
)
def qlab_get_cue_list_details(
    workspace_id: WorkspaceId,
    cue_list_id: Annotated[UUID, Field(description="Exact Cue List UUID from qlab_get_cue_lists.")],
    profile: Literal["safe", "technical"] = "safe",
    max_depth: Annotated[StrictInt, Field(ge=0, le=5, description="Child layers; 0 reads no children.")] = 2,
    max_cues: Annotated[StrictInt, Field(ge=1, le=5000, description="Maximum descendants, excluding the list root.")] = 1000,
) -> CueListDetailsResult:
    """Read one exact Cue List: identity, state, playhead, incoming timecode and a bounded tree.

    safe returns typed sections; technical adds a redacted allowlisted payload.
    Timecode settings do not prove synchronization is enabled. coverage reports OSC limitations.
    Use qlab_get_cue_lists to resolve the UUID; Cue Carts and Groups are not Cue Lists.
    """
    return _run_tool(
        lambda reader: reader.get_cue_list_details(workspace_id, str(cue_list_id), profile, max_depth, max_cues),
        timeout=WORKSPACE_OVERVIEW_TIMEOUT,
    )


@mcp.tool(
    title="Get QLab Cue Cart Details",
    tags={"qlab", "cue-carts", "details", "safe-read"},
    annotations=READ_ONLY_QLAB_TOOL,
    timeout=WORKSPACE_OVERVIEW_TIMEOUT,
)
def qlab_get_cue_cart_details(
    workspace_id: WorkspaceId,
    cue_cart_id: Annotated[UUID, Field(description="Exact Cue Cart UUID from qlab_get_cue_lists.")],
    profile: Literal["safe", "technical"] = "safe",
    max_cues: Annotated[StrictInt, Field(ge=1, le=5000, description="Maximum cart cells to inspect.")] = 1000,
) -> CueCartDetailsResult:
    """Read one exact Cue Cart: identity, state, timecode, grid dimensions and occupied cell positions.

    Cue Carts have no playhead and no nested Groups. Inspect coverage, errors and grid.complete.
    technical adds a redacted allowlisted payload. Use qlab_get_cue_details for a cell's cue Inspector.
    """
    return _run_tool(
        lambda reader: reader.get_cue_cart_details(workspace_id, str(cue_cart_id), profile, max_cues),
        timeout=WORKSPACE_OVERVIEW_TIMEOUT,
    )


@mcp.tool(title="Get QLab Audio Cues", tags={"qlab", "audio", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_audio_cues(
    workspace_id: CanonicalWorkspaceUUID,
    cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> AudioCuesResult:
    """List Audio cues inside one exact Cue List, including nested groups, with compact identity/status.

    Resolve cue_list_id through qlab_get_cue_lists. Carts are not accepted. offset counts matching Audio cues.
    Inspect scan_complete and truncation_reasons; a bounded scan is not a whole-list total.
    Follow with qlab_get_audio_cue_details for one exact cue UUID. Audio Maps are excluded; use optional inspections for exact cue-owned object/indexed reads.
    """
    return _run_tool(lambda reader: reader.get_audio_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Audio Cue Details", tags={"qlab", "audio", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_audio_cue_details(
    workspace_id: CanonicalWorkspaceUUID,
    cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    input_channel: Annotated[StrictInt | None, Field(ge=0, le=24)] = None,
    output_channel: Annotated[StrictInt | None, Field(ge=0, le=128)] = None,
    inspections: Annotated[list[AudioInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> AudioCueDetailsResult:
    """Read one exact Audio cue: identity, state, timing, slices, output patch and levels.

    Both channel selectors must be supplied together; zero addresses main controls. A requested crosspoint
    is selected from the aggregate matrix. technical additionally exposes notes, file paths and payload.
    Optional inspections read only requested scalar/indexed endpoints, including Audio Objects; Audio Maps and live metrics are excluded. Inspect coverage and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_audio_cue_details(str(workspace_id), str(cue_id),
                     profile, input_channel, output_channel, include_native_triggers=include_native_triggers), inspections), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Mic Cues", tags={"qlab", "mic", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_mic_cues(
    workspace_id: CanonicalWorkspaceUUID,
    cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> MicCuesResult:
    """List Mic cues inside one exact Cue List, including nested groups, with compact identity/status.

    Resolve cue_list_id through qlab_get_cue_lists. Carts are not accepted. offset counts matching Mic cues.
    Inspect scan_complete and truncation_reasons; a bounded scan is not a whole-list total.
    Follow with qlab_get_mic_cue_details for one exact cue UUID. Audio Maps are excluded; use optional inspections for exact cue-owned object/indexed reads.
    """
    return _run_tool(lambda reader: reader.get_mic_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Mic Cue Details", tags={"qlab", "mic", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_mic_cue_details(
    workspace_id: CanonicalWorkspaceUUID,
    cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    input_channel: Annotated[StrictInt | None, Field(ge=0, le=24)] = None,
    output_channel: Annotated[StrictInt | None, Field(ge=0, le=128)] = None,
    inspections: Annotated[list[MicInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> MicCueDetailsResult:
    """Read one exact Mic cue: identity, state, timing, input/output patch references, channels and levels.

    Both channel selectors must be supplied together; zero addresses main controls. A requested crosspoint
    is selected from the aggregate matrix. technical additionally exposes notes and normalized payload.
    Optional inspections read only requested scalar/indexed endpoints, including Audio Objects; Audio Maps, live metrics and indexed effects are excluded. Patch configuration belongs
    to qlab_get_workspace_audio_settings. Inspect coverage and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_mic_cue_details(str(workspace_id), str(cue_id),
                     profile, input_channel, output_channel, include_native_triggers=include_native_triggers), inspections), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Video Cues", tags={"qlab", "video", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_video_cues(
    workspace_id: CanonicalWorkspaceUUID,
    cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> VideoCuesResult:
    """List Video cues inside one exact Cue List, including nested groups, with compact identity/status.

    Resolve cue_list_id through qlab_get_cue_lists. Carts are not accepted. offset counts matching Video cues.
    Inspect scan_complete and truncation_reasons; a bounded scan is not a whole-list total.
    Follow with qlab_get_video_cue_details for one exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_video_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Video Cue Details", tags={"qlab", "video", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_video_cue_details(
    workspace_id: CanonicalWorkspaceUUID,
    cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    input_channel: Annotated[StrictInt | None, Field(ge=0, le=24)] = None,
    output_channel: Annotated[StrictInt | None, Field(ge=0, le=128)] = None,
    video_effects: Annotated[list[FxReadSelector] | None, Field(max_length=50)] = None,
    include_native_triggers: StrictBool = False,
) -> VideoCueDetailsResult:
    """Read one exact Video cue: timing/loops, stage reference, geometry, effects inventory and audio levels.

    Both channel selectors must be supplied together; zero addresses main controls. Crosspoints use the aggregate matrix.
    technical additionally exposes notes, media paths and metadata.
    Stage and patch configuration belong to the workspace tools. Audio Maps, Objects, live metrics and
    playback are excluded. Optional video_effects selectors require an index; effect_type may be omitted to discover
    native identity. Only requested parameters are read, and ambiguous identity returns a partial result.
    Inspect coverage and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: reader.get_video_cue_details(str(workspace_id), str(cue_id),
                     profile, input_channel, output_channel, video_effects, include_native_triggers=include_native_triggers), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Fonts", tags={"qlab", "text", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_fonts(workspace_id: CanonicalWorkspaceUUID) -> FontsResult:
    """Read QLab's application-wide PostScript font names and font families/styles over TCP.

    Use the exact names when choosing Text typography. The two inventories do not
    provide a mapping from each PostScript name to its family/style or glyph coverage.
    """
    return _run_tool(lambda reader: reader.get_fonts(str(workspace_id)), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Text Cues", tags={"qlab", "text", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_text_cues(
    workspace_id: CanonicalWorkspaceUUID,
    cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> TextCuesResult:
    """List Text cues inside one exact Cue List, including nested groups, with compact identity/status.

    Resolve cue_list_id through qlab_get_cue_lists. Carts are not accepted. offset counts matching Text cues.
    Inspect scan_complete and truncation_reasons; a bounded scan is not a whole-list total.
    Follow with qlab_get_text_cue_details for one exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_text_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Text Cue Details", tags={"qlab", "text", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_text_cue_details(
    workspace_id: CanonicalWorkspaceUUID,
    cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    video_effects: Annotated[list[FxReadSelector] | None, Field(max_length=50)] = None,
    include_native_triggers: StrictBool = False,
) -> TextCueDetailsResult:
    """Read one exact Text cue: full text, formatted fragments, typography, stage reference, geometry and effects inventory.

    safe includes the text content; technical adds notes and redacted variable payload.
    Text never reads audio or file-playback properties.
    Stage and patch configuration belong to the workspace tools. Audio Maps, Objects, live metrics and
    playback are excluded. Optional video_effects selectors require an index; effect_type may be omitted to discover
    native identity. Only requested parameters are read, and ambiguous identity returns a partial result.
    Inspect coverage and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: reader.get_text_cue_details(str(workspace_id), str(cue_id),
                     profile, video_effects, include_native_triggers=include_native_triggers), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Camera Cues", tags={"qlab", "camera", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_camera_cues(
    workspace_id: CanonicalWorkspaceUUID,
    cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> CameraCuesResult:
    """List Camera cues inside one exact Cue List, including nested groups, with compact identity/status.

    Resolve cue_list_id through qlab_get_cue_lists. Carts are not accepted. offset counts matching Camera cues.
    Inspect scan_complete and truncation_reasons; a bounded scan is not a whole-list total.
    Follow with qlab_get_camera_cue_details for one exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_camera_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Camera Cue Details", tags={"qlab", "camera", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_camera_cue_details(
    workspace_id: CanonicalWorkspaceUUID,
    cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    input_channel: Annotated[StrictInt | None, Field(ge=0, le=24)] = None,
    output_channel: Annotated[StrictInt | None, Field(ge=0, le=128)] = None,
    video_effects: Annotated[list[FxReadSelector] | None, Field(max_length=50)] = None,
    include_native_triggers: StrictBool = False,
) -> CameraCueDetailsResult:
    """Read one exact Camera cue: input patches, stage reference, geometry, effects inventory and audio channels/levels.

    Both channel selectors must be supplied together; zero addresses main controls. Crosspoints use the aggregate matrix.
    technical additionally exposes notes and normalized payload.
    Stage and patch configuration belong to the workspace tools. Audio Maps, Objects, live metrics and
    playback are excluded. Optional video_effects selectors require an index; effect_type may be omitted to discover
    native identity. Only requested parameters are read, and ambiguous identity returns a partial result.
    Inspect coverage and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: reader.get_camera_cue_details(str(workspace_id), str(cue_id),
                     profile, input_channel, output_channel, video_effects, include_native_triggers=include_native_triggers), timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Control Cues", tags={"qlab", "control", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_control_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
    cue_type: ControlCueType | None = None,
) -> ControlCuesResult:
    """List control/organization cues in one exact Cue List, including nested groups.

    Includes Start, Stop, Pause, Load, Reset, Devamp, GoTo, Target, Arm, Disarm, Wait and Memo.
    Optional cue_type filters before pagination. Carts are rejected. Inspect scan_complete and truncation_reasons.
    Use qlab_get_control_cue_details for the exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_control_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned, cue_type), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Control Cue Details", tags={"qlab", "control", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_control_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    include_native_triggers: StrictBool = False,
) -> ControlCueDetailsResult:
    """Read one exact control/organization cue, detecting its type automatically.

    Returns common settings, state, timing and applicable target, Reset or Devamp fields.
    Memo notes are included in safe; technical adds other notes. Inspect coverage and partial errors.
    Load loadTime and Target assignedNumber use fixed local AppleScript reads; inspect partial errors
    and property_transports. Requires macOS Automation access and /Applications/QLab.app. Audio Maps are excluded.
    References do not expand targets or patches. Never starts, stops, loads or modifies cues.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: reader.get_control_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers),
                     timeout=CUE_DETAILS_TIMEOUT)




@mcp.tool(title="Get QLab Fade Cues", tags={"qlab", "fade", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_fade_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> FadeCuesResult:
    """List Fade cues in one exact Cue List, including nested groups.

    Carts are rejected. Inspect scan_complete and truncation_reasons.
    Use qlab_get_fade_cue_details for the exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_fade_cues(str(workspace_id), str(cue_list_id),
        limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Fade Cue Details", tags={"qlab", "fade", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_fade_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    inspections: Annotated[list[FadeInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> FadeCueDetailsResult:
    """Read one exact Fade cue. Inspect coverage and partial errors.

    Returns target references and documented fade settings. Audio target matrices and Video target opacity are supported; other inherited properties remain unverified.
    References do not expand Workspace Settings. Optional inspections read requested scalar/indexed endpoints; no live or automatic indexed scans.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_fade_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers), inspections),
        timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Network Cues", tags={"qlab", "network", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_network_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> NetworkCuesResult:
    """List Network cues in one exact Cue List, including nested groups.

    Carts are rejected. Inspect scan_complete and truncation_reasons.
    Use qlab_get_network_cue_details for the exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_network_cues(str(workspace_id), str(cue_list_id),
        limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Network Cue Details", tags={"qlab", "network", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_network_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    inspections: Annotated[list[NetworkInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> NetworkCueDetailsResult:
    """Read one exact Network cue. Inspect coverage and partial errors.

    Returns patch references and conditional fade settings. Free-form messages and parameter values require technical; embedded secrets may remain.
    References do not expand Workspace Settings. Optional inspections read requested scalar/indexed endpoints; no live or automatic indexed scans.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_network_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers), inspections),
        timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab MIDI Cues", tags={"qlab", "midi", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_midi_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
    cue_type: Literal["all", "midi", "midi_file"] = "all",
) -> MidiCuesResult:
    """List MIDI and MIDI File cues in one exact Cue List, including nested groups.

    Carts are rejected. Inspect scan_complete and truncation_reasons.
    Use qlab_get_midi_cue_details for the exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_midi_cues(str(workspace_id), str(cue_list_id),
        limit, offset, max_cues_scanned, cue_type), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab MIDI Cue Details", tags={"qlab", "midi", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_midi_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    inspections: Annotated[list[MidiInspection | MidiFileInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> MidiCueDetailsResult:
    """Read one exact MIDI cue. Inspect coverage and partial errors.

    Detects MIDI or MIDI File automatically. Reads only the selected message mode; file paths require technical. No message is sent.
    References do not expand Workspace Settings. Optional inspections read requested scalar/indexed endpoints; no live or automatic indexed scans.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_midi_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers), inspections),
        timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Timecode Cues", tags={"qlab", "timecode", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_timecode_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> TimecodeCuesResult:
    """List Timecode cues in one exact Cue List, including nested groups.

    Carts are rejected. Inspect scan_complete and truncation_reasons.
    Use qlab_get_timecode_cue_details for the exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_timecode_cues(str(workspace_id), str(cue_list_id),
        limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Timecode Cue Details", tags={"qlab", "timecode", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_timecode_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    inspections: Annotated[list[TimecodeInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> TimecodeCueDetailsResult:
    """Read one exact Timecode cue. Inspect coverage and partial errors.

    Reads MTC or LTC configuration and the applicable patch reference. Does not generate timecode.
    References do not expand Workspace Settings. Optional inspections read requested scalar/indexed endpoints; no live or automatic indexed scans.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_timecode_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers), inspections),
        timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Script Cues", tags={"qlab", "script", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_script_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> ScriptCuesResult:
    """List Script cues in one exact Cue List, including nested groups.

    Carts are rejected. Inspect scan_complete and truncation_reasons.
    Use qlab_get_script_cue_details for the exact cue UUID.
    """
    return _run_tool(lambda reader: reader.get_script_cues(str(workspace_id), str(cue_list_id),
        limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Script Cue Details", tags={"qlab", "script", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_script_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    inspections: Annotated[list[ScriptInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> ScriptCueDetailsResult:
    """Read one exact Script cue. Inspect coverage and partial errors.

    Safe reads common settings only. Technical includes untrusted script source, potentially containing secrets. Never compiles or executes code.
    References do not expand Workspace Settings. Optional inspections read requested scalar/indexed endpoints; no live or automatic indexed scans.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_script_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers), inspections),
        timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Light Cues", tags={"qlab", "light", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_light_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> LightCuesResult:
    """List Light cues in one exact Cue List, including nested groups. Inspect scan_complete and truncation_reasons.

    Carts are rejected. offset counts matching cues. Use qlab_get_light_cue_details for an exact UUID.
    """
    return _run_tool(lambda reader: reader.get_light_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Light Cue Details", tags={"qlab", "light", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_light_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    inspections: Annotated[list[LightInspection], Field(max_length=50)] = [],
    include_native_triggers: StrictBool = False,
) -> LightCueDetailsResult:
    """Read one exact Light cue: full command text, collate, subcontroller, state and timing.

    safe includes commands; technical adds notes. Commands are never executed or interpreted as live output.
    Use qlab_get_workspace_light_settings for the patch. Inspect coverage and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: inspect_remaining(reader, reader.get_light_cue_details(str(workspace_id), str(cue_id), profile, include_native_triggers=include_native_triggers), inspections),
                     timeout=CUE_DETAILS_TIMEOUT)


@mcp.tool(title="Get QLab Group Cues", tags={"qlab", "group", "inventory", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=QUERY_CUES_TIMEOUT)
def qlab_get_group_cues(
    workspace_id: CanonicalWorkspaceUUID, cue_list_id: UUID,
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100,
    offset: Annotated[StrictInt, Field(ge=0)] = 0,
    max_cues_scanned: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000,
) -> GroupCuesResult:
    """List Group cues in one exact Cue List, including nested groups. Inspect scan_complete and truncation_reasons.

    Lists and carts are not Groups. offset counts matching cues. Use qlab_get_group_cue_details for an exact UUID.
    """
    return _run_tool(lambda reader: reader.get_group_cues(str(workspace_id), str(cue_list_id),
                     limit, offset, max_cues_scanned), timeout=QUERY_CUES_TIMEOUT)


@mcp.tool(title="Get QLab Group Cue Details", tags={"qlab", "group", "details", "safe-read"},
          annotations=READ_ONLY_QLAB_TOOL, timeout=CUE_DETAILS_TIMEOUT)
def qlab_get_group_cue_details(
    workspace_id: CanonicalWorkspaceUUID, cue_id: UUID,
    profile: Literal["safe", "technical"] = "safe",
    max_depth: Annotated[StrictInt, Field(ge=0, le=5)] = 2,
    max_cues: Annotated[StrictInt, Field(ge=1, le=5000)] = 1000,
    include_native_triggers: StrictBool = False,
) -> GroupCueDetailsResult:
    """Read one exact Group cue: mode, state, timing and bounded ordered child summaries.

    Playlist settings are read only in Playlist mode. Lists and carts are rejected. Depth zero reads no children;
    max_cues counts descendants. technical adds notes. Inspect coverage, truncation and partial errors.
    Set include_native_triggers=true for fixed local Trigger reads; unavailable values block editing.
    """
    return _run_tool(lambda reader: reader.get_group_cue_details(str(workspace_id), str(cue_id),
                     profile, max_depth, max_cues, include_native_triggers=include_native_triggers), timeout=CUE_DETAILS_TIMEOUT)


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
                "technical can expose notes, paths, and diagnostic stage data; full_sensitive can additionally expose "
                "scriptSource and other explicitly sensitive payloads."
            ),
        ),
    ] = "basic_safe",
    max_results: Annotated[
        StrictInt,
        Field(
            ge=1,
            le=5000,
            description="Maximum matching cues to return. Scanning may continue past this to report matched_count.",
        ),
    ] = 500,
    max_cues_scanned: Annotated[
        StrictInt,
        Field(
            ge=1,
            le=5000,
            description="Maximum cue IDs to scan from cueLists/uniqueIDs before marking the result truncated.",
        ),
    ] = 500,
) -> CueQueryResult:
    """Search many QLab cues with one required filter plus optional AND filters.

    Use this after the overview to find cue sets such as Audio cues, Light cues, flagged cues, broken cues,
    warnings, media-target cues, cue-target transport cues, or named/numbered ranges. Follow with qlab_get_cue_details
    for exact properties. Results are capped at 500 returned matches and 500 scanned cue IDs by default so agents
    stay compact. Callers can explicitly raise either limit up to 5000 for large shows; truncation metadata reports
    incomplete scans or result caps.
    """
    if str(profile).strip().lower() == "exhaustive":
        return _query_error(
            workspace_id,
            primary_filter,
            profile,
            max_results,
            max_cues_scanned,
            error_code="cue_profile_not_supported",
            message="profile='exhaustive' is supported only by qlab_get_cue_details",
            received={"profile": profile},
            allowed={
                "query_profiles": list(CueQueryProfile.__args__)
                if hasattr(CueQueryProfile, "__args__")
                else None
            },
        )
    if str(profile).strip().lower() == "full_sensitive" and max_results > MAX_SENSITIVE_QUERY_RESULTS:
        return _query_error(
            workspace_id,
            primary_filter,
            profile,
            max_results,
            max_cues_scanned,
            error_code="cue_payload_too_large",
            message=f"full_sensitive cue queries can return at most {MAX_SENSITIVE_QUERY_RESULTS} cues",
            received={"max_results": max_results, "profile": profile},
            allowed={
                "max_results": MAX_SENSITIVE_QUERY_RESULTS,
                "max_payload_bytes": MAX_SENSITIVE_CUE_RESPONSE_BYTES,
            },
        )
    try:
        return _run_tool(
            lambda reader: CueQueryResult.model_validate(
                _query_success_payload(reader.query_cues(
                    workspace_id=workspace_id,
                    primary_filter=primary_filter,
                    primary_value=primary_value,
                    optional_filters=optional_filters,
                    profile=profile,
                    max_results=max_results,
                    max_cues_scanned=max_cues_scanned,
                ))
            ),
            timeout=QUERY_CUES_TIMEOUT,
            translate_errors=False,
        )
    except (QLabMcpError, ValueError, TypeError, ToolError) as exc:
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
    cue_ref: Annotated[
        CueRef | CueRefs,
        Field(
            description=(
                "Accept an exact cue number or unique ID for one cue, or a list of exact cue numbers/unique IDs for a batch. "
                "Resolve refs through qlab_query_cues or the workspace overview; ambiguous selected, playhead, "
                "playbackPosition, and active refs may be returned for read-only inspection but should not be used for writes."
            ),
        ),
    ],
    profile: Annotated[
        str,
        Field(
            description=(
                "Read-only detail profile. Use auto for safe type-aware sections, health for warnings/broken cues, "
                "inspector_safe for broader QLab Inspector-style details without file paths or scripts, "
                "targets for target IDs without file paths, technical for notes/targets/routing/paths, "
                "editable for safe details plus typed family editor capabilities, "
                "full_sensitive for deep audits, and exhaustive for the deepest allowlisted read-only read "
                "including heavy/sensitive payloads; exhaustive may be large."
            )
        ),
    ] = "auto",
) -> CueDetailsResult | CueDetailsBatchResult:
    """Return read-only details for one cue, or a batch of up to 50 cues, using QLab valuesForKeys when possible.

    Use after qlab_query_cues or the overview to inspect exact targets. Use auto for safe type-aware inspection,
    inspector_safe for broader non-sensitive Inspector context, editable for update capability discovery, health for
    warnings, technical/full_sensitive only when justified, and exhaustive only for deep audits or load testing
    because it can expose large/sensitive payloads.
    Cue List calls return a structured redirect; use qlab_get_cue_list_details with their exact UUID.
    """
    if isinstance(cue_ref, list) and len(cue_ref) > MAX_BATCH_CUE_DETAILS:
        return _cue_details_error(
            workspace_id,
            cue_ref,
            profile,
            error_code="cue_batch_too_large",
            message=f"cue_ref list can include at most {MAX_BATCH_CUE_DETAILS} cues",
            received={"cue_count": len(cue_ref)},
            allowed={"max_cues": MAX_BATCH_CUE_DETAILS},
        )
    try:
        return _run_tool(
            lambda reader: (
                CueDetailsBatchResult.model_validate(_cue_details_success_payload(reader.get_cue_details(workspace_id, cue_ref, profile)))
                if isinstance(cue_ref, list)
                else CueDetailsResult.model_validate(_cue_details_success_payload(reader.get_cue_details(workspace_id, cue_ref, profile)))
            ),
            timeout=CUE_DETAILS_TIMEOUT,
            translate_errors=False,
        )
    except (QLabMcpError, ValueError, TypeError, ToolError) as exc:
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

    This read-only preflight verifies QLAB_ENABLE_WRITE, required workspace_id, server-side QLAB_PASSCODE presence,
    planned write capabilities, edit permission confirmed by QLab /connect scopes, and Edit Mode from /showMode.
    Use it before Create, Edit, Move, or Delete; it is a readiness report, not a confirmation token.
    """
    return _run_tool(
        lambda reader: WriteReadinessResult.model_validate(
            reader.check_write_readiness(workspace_id)
        ),
        timeout=WRITE_READINESS_TIMEOUT,
    )


@mcp.tool(
    title="Create QLab Cue Lists",
    tags={"qlab", "write-mode", "cue-list-create", "batch-create", "gated-write"},
    annotations=GATED_CREATE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_create_cue_lists(
    workspace_id: WorkspaceId,
    container_types: Annotated[
        list[Literal["cue_list", "cue_cart"]],
        Field(min_length=1, max_length=50, description="Ordered root containers to create with QLab defaults."),
    ],
    dry_run: Annotated[bool | None, Field(description="Plan only by default; execution requires the reviewed token.")] = None,
    confirm_token: Annotated[str | None, Field(description="Exact confirm:createCueLists:v1 token from dry-run.")] = None,
) -> CreateCueListsResult:
    """Create one to fifty empty root Cue Lists and Cue Carts using QLab defaults.

    The requested order is preserved. Each /new response must contain a UUID and
    each root is read back with its type, position, and empty contents before the
    next creation. Creation is sequential and has no rollback. QLab may change
    the current container and selection. Use qlab_move_cue_lists afterwards when
    a different sidebar position is required.
    """
    return _run_tool(
        lambda reader: CreateCueListsResult.model_validate(reader.create_cue_lists(
            workspace_id=workspace_id,
            container_types=list(container_types),
            dry_run=dry_run,
            confirm_token=confirm_token,
        )),
        timeout=UPDATE_CUES_TIMEOUT,
    )


@mcp.tool(
    title="Edit QLab Cue Lists",
    tags={"qlab", "write-mode", "cue-list-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_cue_lists(
    workspace_id: WorkspaceId,
    updates: Annotated[list[CueListEditInput], Field(min_length=1, max_length=50)],
    dry_run: Annotated[bool | None, Field(description="Plan or execute through the existing verified Edit executor.")] = None,
) -> UpdateCuesResult:
    """Edit typed OSC properties on root Cue Lists or Cue Carts.

    Targets must be exact root UUIDs. The tool supports common metadata and the
    documented incoming-timecode settings. It excludes playhead, playback,
    mode conversion, Cart grid resizing, and fields unavailable through OSC.
    """
    return _run_tool(
        lambda reader: UpdateCuesResult.model_validate(reader.edit_cue_lists(
            workspace_id=workspace_id,
            updates=[update.model_dump(mode="json", exclude_none=True) for update in updates],
            dry_run=dry_run,
        )),
        timeout=UPDATE_CUES_TIMEOUT,
    )


@mcp.tool(
    title="Create QLab Cues",
    tags={"qlab", "write-mode", "cue-create", "batch-create", "gated-write"},
    annotations=GATED_CREATE_QLAB_TOOL,
    timeout=CREATE_CUES_TIMEOUT,
)
def qlab_create_cues(
    workspace_id: WorkspaceId,
    cue_types: Annotated[
        list[WritableCueType],
        Field(
            min_length=1,
            max_length=100,
            description=(
                "One to one hundred ordered cue types, including mixed types. Each cue uses its workspace Cue Template; "
                "every later cue is created after the UUID verified for the previous cue."
            ),
        ),
    ],
    cue_list_id: Annotated[
        UUID | None,
        Field(description="Exact Cue List UUID. Use exactly one of cue_list_id, group_id, or cue_cart_id."),
    ] = None,
    group_id: Annotated[
        UUID | None,
        Field(description="Exact Group UUID. Use exactly one destination selector."),
    ] = None,
    cue_cart_id: Annotated[
        UUID | None,
        Field(description="Exact empty Cue Cart UUID; accepts one non-Group cue only."),
    ] = None,
    after_cue_id: Annotated[
        UUID | None,
        Field(description="Optional direct-child UUID within the selected Cue List or Group; omit to append at the end."),
    ] = None,
    dry_run: Annotated[
        bool | None,
        Field(description="Plan without mutating OSC; omitted uses the configured dry-run default."),
    ] = None,
    confirm_token: Annotated[
        str | None,
        Field(description="Exact confirm:createCues:v2 token returned by the reviewed dry-run."),
    ] = None,
) -> CreateCuesResult:
    """Create 1–100 ordered cues from workspace Cue Templates, with one verified /new per item.

    Call qlab_check_write_readiness first, then review the dry-run and supply the
    exact confirm:createCues:v2 token. Specify one exact Cue List, Group, or empty
    Cue Cart UUID. Cue Lists and Groups append by default; after_cue_id inserts
    after a direct child. QLab selects each new cue, and first-cue creation in
    an empty Cue List can change the current list. QLab's General auto-numbering
    setting does not officially apply to OSC-created cues, although tested
    workspaces returned numbered cues. The MCP sends no cue number; use fresh
    readback and do not predict it from the setting or template. No initial
    setters, playback, or save are sent. Stop at the
    first failure; earlier successful cues remain without automatic rollback.
    Do not retry an ambiguous mutation. Structural success is not GO readiness.
    Execution has a 270-second budget within the 300-second public timeout.
    pending_indices are unattempted items; uncertain_indices may have been
    created without verification. batch_verified requires final full readback.
    """
    return _run_tool(
        lambda reader: CreateCuesResult.model_validate(
            reader.create_cues(
                workspace_id=workspace_id,
                cue_types=list(cue_types),
                dry_run=dry_run,
                cue_list_id=str(cue_list_id) if cue_list_id is not None else None,
                group_id=str(group_id) if group_id is not None else None,
                cue_cart_id=str(cue_cart_id) if cue_cart_id is not None else None,
                after_cue_id=str(after_cue_id) if after_cue_id is not None else None,
                confirm_token=confirm_token,
            )
        ),
        timeout=CREATE_CUES_TIMEOUT,
    )


@mcp.tool(
    title="Edit QLab Control Cues",
    tags={"qlab", "control", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_control_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[ControlCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 mixed Start/Stop/Pause/Load/Reset/GoTo/Arm/Disarm/Wait/Memo cues by UUID.

    Plan Basics, supported OSC Triggers and targets without executing cues. Review
    every planned setter and supply its exact confirm_token in confirm_gates.
    Tokens expire after five minutes and are reserved once for the whole batch.
    All items preflight before any setter; execution is sequential and non-atomic.
    Load loadTime uses local AppleScript and finite seconds (negative counts back from end).
    Change its cueTargetID separately, then request a new dry run. Target, Devamp, Hotkey/MIDI/Wall Clock setup, Audio Maps and /live
    are excluded. Fade & Stop scope is blocked when readback is only boolean.
    A setter timeout is never retried. Inspect fresh readback and pending operations.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_control_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Group Cues",
    tags={"qlab", "group", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_group_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[GroupCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 Group, Cue List, Cue Cart or Cart containers by exact UUID.

    Typed Basics are batchable. Group mode and canonical Playlist settings are
    one cue and one property per call; Playlist setters require mode 6. Read the
    Group and children first, review the dry-run, and copy its exact confirm_token.
    Existing Group gates expire after five minutes, bind the ordered child
    snapshot, and are consumed once. Writes are sequential and non-atomic, with fresh readback,
    no rollback and no cue execution. Playhead navigation, current-cue selection,
    deprecated Playlist aliases and Cart cell movement remain excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_group_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Devamp Cues",
    tags={"qlab", "devamp", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_devamp_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[DevampCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 Devamp cue UUIDs: Basics, OSC Triggers, Audio/Video target and Settings.

    devampType 1 selects looping slice; 2 selects looping cue. Configure startNextCueWhenSliceEnds
    and stopTargetWhenSliceEnds without executing cues. Stop target requires Start next enabled.
    Assign cueTargetID by exact UUID or clear with empty string. Review dry_run and copy each
    confirm_token into confirm_gates. Signed single-use tokens expire after five minutes.
    All items preflight before setters. Sequential, non-atomic; no rollback.
    Each setter is sent once and checked by fresh readback. Timeout is never retried.
    Audio Maps, /live, capture and trigger activation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_devamp_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Target Cues",
    tags={"qlab", "target", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_target_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[TargetCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 Target cue UUIDs: Basics, OSC Triggers and cueTargetID.

    The target must accept cue targets; Fade is excluded. Assign an exact workspace UUID
    or clear with empty string. The Cue Number tab's assignedNumber uses fixed local AppleScript:
    an existing unique workspace cue number, or empty string to clear. It configures a future
    temporary target; no action runs. number edits this Target cue's own number. Change cueTargetID
    or renumber the assigned cue separately, then request a new dry run.
    Review dry_run and copy each confirm_token into confirm_gates. Signed single-use
    tokens expire after five minutes. All items preflight before setters.
    Sequential, non-atomic; no rollback. Fresh readback verifies each setter.
    Timeout is never retried. No cues, temporary targets, /live or capture are executed.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_target_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Video Cues",
    tags={"qlab", "video", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_video_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[VideoCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 Video cues by exact UUID: Basics, OSC Triggers and saved family properties.

    Read details first. Dry run returns previous values and one signed confirm_token per setter.
    Copy every token into confirm_gates; tokens expire after five minutes and are single-use.
    Validate the entire batch before writing. Sequential, non-atomic, no rollback.
    Every setter uses alwaysReply and fresh readback; timeouts never trigger a retry.
    Routing uses exact UUIDs in this workspace; empty stage/input UUID clears routing.
    Fade & Stop requires integer scope readback. Text styles require readable uniform fragments.
    Ask the user before accessing files. File targets need an existing readable
    absolute path; macOS permissions apply to the MCP process. No folder allowlist
    is required. Audio Maps, /live, cue execution and external triggers are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_video_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Camera Cues",
    tags={"qlab", "camera", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_camera_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[CameraCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 Camera cues by exact UUID: Basics, OSC Triggers and saved family properties.

    Read details first. Dry run returns previous values and one signed confirm_token per setter.
    Copy every token into confirm_gates; tokens expire after five minutes and are single-use.
    Validate the entire batch before writing. Sequential, non-atomic, no rollback.
    Every setter uses alwaysReply and fresh readback; timeouts never trigger a retry.
    Routing uses exact UUIDs in this workspace; empty stage/input UUID clears routing.
    Fade & Stop requires integer scope readback. Text styles require readable uniform fragments.
    Audio Maps, /live, cue execution and external trigger configuration are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_camera_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Text Cues",
    tags={"qlab", "text", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_text_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[TextCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 Text cues by exact UUID: Basics, OSC Triggers and saved family properties.

    Read details first. Dry run returns previous values and one signed confirm_token per setter.
    Copy every token into confirm_gates; tokens expire after five minutes and are single-use.
    Validate the entire batch before writing. Sequential, non-atomic, no rollback.
    Every setter uses alwaysReply and fresh readback; timeouts never trigger a retry.
    Routing uses exact UUIDs in this workspace; empty stage/input UUID clears routing.
    Fade & Stop requires integer scope readback. Text styles require readable uniform fragments.
    Audio Maps, /live, cue execution and external trigger configuration are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_text_cues(reader, str(workspace_id), updates, dry_run)))


@mcp.tool(
    title="Edit QLab Audio Cues",
    tags={"qlab", "audio", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_audio_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[AudioCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Audio cue UUIDs: Basics, Triggers and file target, patch UUID, timing/loops, Levels and slices.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Ask the user before accessing files. File targets need an existing readable
    absolute path; macOS permissions apply to the MCP process. No folder allowlist
    is required. Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="audio")))


@mcp.tool(
    title="Edit QLab Mic Cues",
    tags={"qlab", "mic", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_mic_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[MicCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Mic cue UUIDs: Basics, Triggers and input/output patch UUIDs, Levels and input format.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Ask the user before accessing files. File targets need an existing readable
    absolute path and a supported MIDI format; macOS permissions apply to the MCP
    process. No folder allowlist is required. Audio Maps, /live, execution, and
    Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="mic")))


@mcp.tool(
    title="Edit QLab Light Cues",
    tags={"qlab", "light", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_light_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[LightCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Light cue UUIDs: Basics, Triggers and command text, alwaysCollate and subcontroller.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="light")))


@mcp.tool(
    title="Edit QLab Fade Cues",
    tags={"qlab", "fade", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_fade_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[FadeCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Fade cue UUIDs: Basics, Triggers and exact cue target, completion behavior, geometry and Levels.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="fade")))


@mcp.tool(
    title="Edit QLab Network Cues",
    tags={"qlab", "network", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_network_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[NetworkCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Network cue UUIDs: Basics, Triggers and patch UUID, message and fade configuration.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="network")))


@mcp.tool(
    title="Edit QLab MIDI Cues",
    tags={"qlab", "midi", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_midi_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[MidiCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact MIDI cue UUIDs: Basics, Triggers and patch UUID and Voice/MSC/SysEx message configuration.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="midi")))


@mcp.tool(
    title="Edit QLab MIDI File Cues",
    tags={"qlab", "midi_file", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_midi_file_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[MidiFileCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact MIDI File cue UUIDs: Basics, Triggers and file/patch targets, timing, rate and play count.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="midi_file")))


@mcp.tool(
    title="Edit QLab Timecode Cues",
    tags={"qlab", "timecode", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_timecode_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[TimecodeCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Timecode cue UUIDs: Basics, Triggers and MTC/LTC mode, frame rate, time bounds and patches.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="timecode")))


@mcp.tool(
    title="Edit QLab Script Cues",
    tags={"qlab", "script", "write-mode", "cue-edit", "batch-edit", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_edit_script_cues(
    workspace_id: CanonicalWorkspaceUUID,
    updates: Annotated[list[ScriptCueEditInput], Field(min_length=1, max_length=50)],
    dry_run: bool | None = None,
) -> UpdateCuesResult:
    """Edit 1–50 exact Script cue UUIDs: Basics, Triggers and saved Basics and supported OSC Triggers.

    Combine supported Basics, Triggers and saved settings. Optional typed operations
    select up to 50 indexed destinations per cue. Review the dry run and supply
    every signed confirm_token in confirm_gates after dry_run; five-minute expiry, single-use.
    Selectors which reset dependent state require a separate dry run. The complete
    batch is validated and confirmations reserved before the first setter.
    Sequential, non-atomic; each setter is sent once with immediate fresh readback.
    Failure or uncertain readback stops remaining setters. Never retry; no rollback.
    Audio Maps, /live, cue execution and Script source/compilation are excluded.
    """
    return _run_tool(lambda reader: UpdateCuesResult.model_validate(
        edit_remaining_cues(reader, str(workspace_id), updates, dry_run, family="script")))


@mcp.tool(
    title="Edit QLab Workspace General Settings",
    tags={"qlab", "settings", "general-settings", "write-mode", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT,
)
def qlab_edit_workspace_general_settings(
    workspace_id: CanonicalWorkspaceUUID,
    operation: GeneralSettingsOperation,
    dry_run: Annotated[
        bool | None,
        Field(description="Plan without mutating OSC; omitted uses QLAB_WRITE_DRY_RUN_DEFAULT."),
    ] = None,
    confirm_token: Annotated[
        str | None,
        Field(description="Exact fresh confirm:workspaceSettings:v1 token returned by the reviewed dry-run."),
    ] = None,
) -> WorkspaceSettingsEditResult:
    """Plan or execute one General setting: minGoTime or selectionIsPlayhead.

    Target an exact workspace UUID. Use seconds for minGoTime and a boolean for
    selectionIsPlayhead. Dry-run performs
    readiness, inactive-cue, baseline, and activity checks before issuing a fresh
    single-use token. Real execution rechecks readiness and activity, sends exactly one
    setter. One setter is attempted per real call. It requires fresh no-argument readback. A timeout-confirmed result is
    not retried; unavailable readback is inconclusive and unsafe to retry. The
    activity reader cannot prove workspace-wide Audition state, so keep Audition
    disabled. This tool has no GO, playback, panic, /live, or raw OSC behavior.
    """
    operation = TypeAdapter(GeneralSettingsOperation).validate_python(operation)
    if operation.kind == "general.minGoTime":
        request = WorkspaceSettingsEditRequest(
            workspace_id=workspace_id, operation=operation, dry_run=dry_run, confirm_token=confirm_token,
        )
        return _run_tool(
            lambda reader: WorkspaceSettingsEditResult.model_validate(reader.edit_workspace_settings(request)),
            timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT,
        )
    return _edit_object_setting(workspace_id, "general", {}, operation, dry_run, confirm_token)


def _edit_object_setting(
    workspace_id: UUID, family: str, ids: dict[str, str], operation: Any,
    dry_run: bool | None, confirm_token: str | None,
) -> WorkspaceSettingsEditResult:
    return _run_tool(
        lambda reader: WorkspaceSettingsEditResult.model_validate(reader.edit_object_setting(
            str(workspace_id), family, ids, operation, dry_run, confirm_token,
        )),
        timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT,
    )


@mcp.tool(title="Edit QLab Audio Output Patch", tags={"qlab", "settings", "audio", "gated-write"},
          annotations=GATED_DESTRUCTIVE_QLAB_TOOL, timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT)
def qlab_edit_audio_output_patch(
    workspace_id: CanonicalWorkspaceUUID,
    patch_id: CanonicalWorkspaceUUID,
    operation: AudioOutputPatchOperation,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> WorkspaceSettingsEditResult:
    """Edit one patch property, including name, or clear mutes/solos with a single-use token."""
    return _edit_object_setting(workspace_id, "audio", {"patch_id": str(patch_id)}, operation, dry_run, confirm_token)


@mcp.tool(title="Edit QLab Video Output Route", tags={"qlab", "settings", "video", "gated-write"},
          annotations=GATED_DESTRUCTIVE_QLAB_TOOL, timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT)
def qlab_edit_video_output_route(
    workspace_id: CanonicalWorkspaceUUID,
    route_id: CanonicalWorkspaceUUID,
    operation: VideoRouteOperation,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> WorkspaceSettingsEditResult:
    """Edit enableGuides on one exact Video output route."""
    return _edit_object_setting(workspace_id, "route", {"route_id": str(route_id)}, operation, dry_run, confirm_token)


@mcp.tool(title="Edit QLab Video Stage", tags={"qlab", "settings", "video", "gated-write"},
          annotations=GATED_DESTRUCTIVE_QLAB_TOOL, timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT)
def qlab_edit_video_stage(
    workspace_id: CanonicalWorkspaceUUID,
    stage_id: CanonicalWorkspaceUUID,
    operation: VideoStageOperation,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> WorkspaceSettingsEditResult:
    """Rename one exact Video stage."""
    return _edit_object_setting(workspace_id, "stage", {"stage_id": str(stage_id)}, operation, dry_run, confirm_token)


@mcp.tool(title="Edit QLab Video Region", tags={"qlab", "settings", "video", "gated-write"},
          annotations=GATED_DESTRUCTIVE_QLAB_TOOL, timeout=WORKSPACE_SETTINGS_WRITE_TIMEOUT)
def qlab_edit_video_region(
    workspace_id: CanonicalWorkspaceUUID,
    stage_id: CanonicalWorkspaceUUID,
    region_id: CanonicalWorkspaceUUID,
    operation: VideoRegionOperation,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> WorkspaceSettingsEditResult:
    """Edit one OSC-coordinate region property; points require exact indices."""
    return _edit_object_setting(workspace_id, "region", {"stage_id": str(stage_id), "region_id": str(region_id)}, operation, dry_run, confirm_token)


@mcp.tool(
    title="Move QLab Cue Lists",
    tags={"qlab", "write-mode", "cue-list-move", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_move_cue_lists(
    workspace_id: WorkspaceId,
    moves: Annotated[list[MoveCueListInput], Field(min_length=1, max_length=50)],
    dry_run: Annotated[bool | None, Field(description="Plan only by default; real execution requires the reviewed token.")] = None,
    confirm_token: Annotated[str | None, Field(description="Exact confirm:moveCueLists:v1 token from the dry run; expires after five minutes.")] = None,
) -> MoveCuesResult:
    """Reorder one to fifty root Cue Lists and Cue Carts in one workspace.

    UUID-only placements use exactly one index, before/after anchor, or first/last.
    Indices are zero-based insertion positions after removing the source and
    resolve sequentially against the simulated mixed sidebar order. Real writes
    require Edit Mode, idle workspace, a matching confirm:moveCueLists:v1 token,
    and fresh root order and content verification. No-op placements skip OSC.
    Moves are sequential and non-atomic; do not retry an ambiguous mutation.
    Moving a Cart here does not reposition its cells. Root deletion is deferred.
    """
    return _run_tool(
        lambda reader: MoveCuesResult.model_validate(reader.move_cue_lists(
            workspace_id=workspace_id,
            moves=[move.model_dump(mode="json", exclude_none=True) for move in moves],
            dry_run=dry_run, confirm_token=confirm_token,
        ))
    )


@mcp.tool(
    title="Move QLab Cues",
    tags={"qlab", "write-mode", "cue-move", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=UPDATE_CUES_TIMEOUT,
)
def qlab_move_cues(
    workspace_id: WorkspaceId,
    moves: Annotated[
        list[MoveCueInput],
        Field(
            min_length=1,
            max_length=50,
            description=(
                "One to fifty explicit UUID cue moves. List and Group placements use exactly one linear "
                "placement field; Cue Cart placements use cart_row and cart_column only."
            ),
        ),
    ],
    dry_run: Annotated[
        bool | None,
        Field(
            description=(
                "When true, plan the sequential move batch but send no mutating commands. "
                "When omitted, QLAB_WRITE_DRY_RUN_DEFAULT is used and defaults to true."
            ),
        ),
    ] = None,
    confirm_token: Annotated[
        str | None,
        Field(description="Exact confirm:moveCues:v1: token returned by a reviewed dry-run plan."),
    ] = None,
) -> MoveCuesResult:
    """Plan or execute one to fifty sequential QLab cue moves.

    Targets are UUID-only. Real moves require write readiness, Edit Mode, inactive
    cues, the exact confirm:moveCues:v1 token, stable structural dependencies,
    and fresh parent/order readback. Execution is sequential and non-atomic; this
    tool never claims atomicity. Cart execution remains runtime-blocked pending the
    documented QLab 5.5.10 evidence boundary. Do not retry an ambiguous mutation.
    Each source UUID must be unique. Anchors and destination parents cannot refer
    to another cue moved in the same batch; dependent moves need separate calls.
    Broken/warning health is reported as information; it does not block structural moves.
    """
    return _run_tool(
        lambda reader: MoveCuesResult.model_validate(
            reader.move_cues(
                workspace_id=workspace_id,
                moves=[move.model_dump(mode="json", exclude_none=True) for move in moves],
                dry_run=dry_run,
                confirm_token=confirm_token,
            )
        )
    )


@mcp.tool(
    title="Delete QLab Cues",
    tags={"qlab", "write-mode", "cue-delete", "gated-write"},
    annotations=GATED_DESTRUCTIVE_QLAB_TOOL,
    timeout=DELETE_CUES_TIMEOUT,
)
def qlab_delete_cues(
    workspace_id: WorkspaceId,
    cue_ids: Annotated[
        list[UUID] | None,
        Field(
            min_length=0,
            max_length=50,
            description=(
                "Optional explicit leaf cue UUIDs. For direct deletion of one exact empty Group, "
                "omit cue_ids and provide container_id with recursive=false. For recursive emptying, "
                "omit cue_ids and provide container_id with recursive=true."
            ),
        ),
    ] = None,
    container_id: Annotated[
        UUID | None,
        Field(
            description=(
                "Exact empty Group UUID to delete only when recursive=false; or exact "
                "Cue List, Cue Cart, Cart, or Group UUID to empty recursively with recursive=true. "
                "Recursive mode preserves the container unless delete_container=true for a Group."
            ),
        ),
    ] = None,
    recursive: Annotated[
        bool,
        Field(
            description=(
                "When true with container_id, delete descendants deepest-first; preserve the root unless delete_container=true. "
                "When false, container_id must identify one empty Group that will itself be deleted."
            ),
        ),
    ] = False,
    dry_run: Annotated[
        bool | None,
        Field(
            description=(
                "When true, plan the sequential leaf-cue deletion but send no mutating commands. "
                "When omitted, QLAB_WRITE_DRY_RUN_DEFAULT is used and defaults to true."
            ),
        ),
    ] = None,
    confirm_token: Annotated[
        str | None,
        Field(description="Exact confirm:deleteCues:v1: token returned by a reviewed dry-run plan."),
    ] = None,
    delete_container: Annotated[
        bool,
        Field(description="With container_id and recursive=true, delete a Group's descendants then the Group itself. Omit cue_ids. Default false preserves the root; Cue List and Cue Cart deletion stays blocked."),
    ] = False,
) -> DeleteCuesResult:
    """Plan or execute sequential deletions of explicit leaves or one exact empty Group.

    Real deletion requires write readiness, Edit Mode, zero activity, the exact
    confirm:deleteCues:v1 token, and independent existence readback after every delete.
    A non-recursive container request deletes only an empty Group. Recursive mode
    deletes descendants deepest-first and preserves the requested root container by default.
    Set delete_container=true only to delete a Group last after its descendants.
    Deletion is sequential and not atomic, with no automatic rollback.
    Do not retry after a timeout or identity ambiguity; verify disappearance of every
    requested UUID and the planned preservation or deletion of the root.
    """
    return _run_tool(
        lambda reader: DeleteCuesResult.model_validate(
            reader.delete_cues(
                workspace_id=workspace_id,
                cue_ids=[str(cue_id) for cue_id in cue_ids] if cue_ids is not None else None,
                container_id=str(container_id) if container_id is not None else None,
                recursive=recursive,
                delete_container=delete_container,
                dry_run=dry_run,
                confirm_token=confirm_token,
            )
        )
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
