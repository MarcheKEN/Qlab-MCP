from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.utilities.mcp_server_config.v1.mcp_server_config import MCPServerConfig

import qlab_mcp.server as server_module
from qlab_mcp.errors import QLabReplyError
from qlab_mcp.server import (
    CHECK_CONNECTION_TIMEOUT,
    CREATE_CUE_TIMEOUT,
    CUE_DETAILS_TIMEOUT,
    QUERY_CUES_TIMEOUT,
    UPDATE_CUES_TIMEOUT,
    WORKSPACE_OVERVIEW_TIMEOUT,
    WORKSPACE_SETTING_DETAILS_TIMEOUT,
    WORKSPACE_SETTINGS_TIMEOUT,
    WRITE_READINESS_TIMEOUT,
    _run_tool,
    mcp,
    qlab_get_workspace_overview,
    qlab_get_cue_details,
    qlab_query_cues,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_fastmcp_json_points_to_stdio_server_without_write_env() -> None:
    raw_config = json.loads((PROJECT_ROOT / "fastmcp.json").read_text())
    parsed = MCPServerConfig.model_validate(raw_config)

    assert parsed.source.path == "src/qlab_mcp/server.py"
    assert parsed.source.entrypoint == "mcp"
    assert parsed.environment.project == Path(".")
    assert parsed.deployment.transport == "stdio"

    deployment_env = raw_config.get("deployment", {}).get("env", {})
    assert "QLAB_PASSCODE" not in deployment_env
    assert "QLAB_ENABLE_WRITE" not in deployment_env
    assert "QLAB_WRITE_DRY_RUN_DEFAULT" not in deployment_env


def test_tool_metadata_exposes_titles_descriptions_and_read_only_annotations() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    assert set(tools) == {
        "qlab_check_connection",
        "qlab_get_workspace_overview",
        "qlab_get_workspace_settings",
        "qlab_get_workspace_setting_details",
        "qlab_query_cues",
        "qlab_get_cue_details",
        "qlab_check_write_readiness",
        "qlab_create_cue",
        "qlab_update_cues",
    }

    check = tools["qlab_check_connection"]
    assert check.title == "Check QLab Connection"
    assert "passcode" in check.description
    assert "/connect permission scopes" in check.description
    assert check.annotations.readOnlyHint is True
    assert check.annotations.destructiveHint is False

    overview = tools["qlab_get_workspace_overview"]
    assert overview.title == "Get QLab Workspace Overview"
    assert "first structural read" in overview.description
    assert overview.inputSchema["properties"]["cue_index_profile"]["default"] == "minimal"
    assert overview.inputSchema["properties"]["max_cues"]["maximum"] == 5000
    assert overview.inputSchema["properties"]["max_index_cues"]["maximum"] == 5000
    assert overview.inputSchema["properties"]["max_index_cues"]["default"] == 5000
    assert overview.inputSchema["properties"]["include_global_count"]["default"] is False
    assert "cueLists/uniqueIDs" in overview.inputSchema["properties"]["include_global_count"]["description"]
    assert "cue list roots" in overview.inputSchema["properties"]["include_global_count"]["description"]
    assert "agent_summary" in overview.outputSchema["properties"]
    agent_summary_schema = overview.outputSchema["properties"]["agent_summary"]
    agent_summary_variants = agent_summary_schema.get("anyOf", [agent_summary_schema])
    assert any(variant.get("type") == "object" for variant in agent_summary_variants)
    assert overview.annotations.readOnlyHint is True
    assert overview.annotations.destructiveHint is False
    assert overview.annotations.idempotentHint is True
    assert overview.annotations.openWorldHint is True

    settings = tools["qlab_get_workspace_settings"]
    assert settings.title == "Get QLab Workspace Settings"
    assert "Workspace Settings" in settings.description
    assert settings.annotations.readOnlyHint is True
    assert settings.annotations.destructiveHint is False
    assert settings.inputSchema["properties"]["mode"]["default"] == "summary"
    assert settings.inputSchema["properties"]["mode"]["enum"] == ["summary", "details"]
    assert settings.inputSchema["properties"]["profile"]["default"] == "safe"
    assert settings.inputSchema["properties"]["profile"]["enum"] == ["safe", "technical", "exhaustive"]
    assert "requests" in settings.inputSchema["properties"]
    assert "available_detail_requests" in settings.outputSchema["properties"]
    assert "succeeded_count" in settings.outputSchema["properties"]
    assert "failed_count" in settings.outputSchema["properties"]
    assert "summary" in settings.description
    assert "one failed request does not block" in settings.description

    setting_details = tools["qlab_get_workspace_setting_details"]
    assert setting_details.title == "Get QLab Workspace Setting Details"
    assert "Backwards-compatible wrapper" in setting_details.description
    assert setting_details.inputSchema["properties"]["profile"]["default"] == "safe"
    assert "exhaustive" in setting_details.inputSchema["properties"]["profile"]["enum"]
    assert setting_details.annotations.readOnlyHint is True
    assert setting_details.annotations.destructiveHint is False

    query = tools["qlab_query_cues"]
    assert query.title == "Query QLab Cues"
    assert "optional AND filters" in query.description
    assert query.inputSchema["properties"]["max_results"]["default"] == 500
    assert query.inputSchema["properties"]["max_results"]["maximum"] == 5000
    assert query.inputSchema["properties"]["max_cues_scanned"]["default"] == 500
    assert query.inputSchema["properties"]["max_cues_scanned"]["maximum"] == 5000
    query_filters = set(query.inputSchema["properties"]["primary_filter"]["enum"])
    assert {"name_empty", "displayName_empty", "number_empty", "ambiguous_label", "flagged_or_broken"} <= query_filters
    assert "query_completeness" in query.outputSchema["properties"]
    assert "query_completeness_reasons" in query.outputSchema["properties"]
    assert "id_only_unscanned_count" in query.outputSchema["properties"]
    assert "omitted_branches" in query.outputSchema["properties"]
    assert "partial_branches" in query.outputSchema["properties"]
    assert "warnings" in query.outputSchema["properties"]
    assert query.annotations.readOnlyHint is True
    assert query.annotations.destructiveHint is False

    details = tools["qlab_get_cue_details"]
    assert details.title == "Get QLab Cue Details"
    assert "valuesForKeys" in details.description
    assert "editable" in details.inputSchema["properties"]["profile"]["enum"]
    assert "inspector_safe" in details.inputSchema["properties"]["profile"]["enum"]
    assert "exhaustive" in details.inputSchema["properties"]["profile"]["enum"]
    assert "Inspector-style" in details.inputSchema["properties"]["profile"]["description"]
    assert "heavy/sensitive" in details.inputSchema["properties"]["profile"]["description"]
    assert "exhaustive" not in query.inputSchema["properties"]["profile"]["enum"]
    cue_ref_schema = details.inputSchema["properties"]["cue_ref"]
    assert cue_ref_schema["anyOf"][0]["type"] == "string"
    assert cue_ref_schema["anyOf"][1]["type"] == "array"
    assert cue_ref_schema["anyOf"][1]["maxItems"] == 50
    assert details.annotations.readOnlyHint is True

    readiness = tools["qlab_check_write_readiness"]
    assert readiness.title == "Check QLab Write Readiness"
    assert "without sending any mutating OSC commands" in readiness.description
    assert readiness.annotations.readOnlyHint is True
    assert readiness.annotations.destructiveHint is False
    assert "workspace_id" in readiness.inputSchema["required"]
    assert "write_disabled" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "suggested_action" in readiness.outputSchema["properties"]

    create = tools["qlab_create_cue"]
    assert create.title == "Create QLab Cue"
    assert "dry-run plan" in create.description
    assert create.annotations.readOnlyHint is False
    assert create.annotations.destructiveHint is False
    assert create.annotations.idempotentHint is False
    assert create.inputSchema["properties"]["cue_type"]["enum"] == [
        "memo",
        "group",
        "wait",
        "audio",
    ]
    assert "dry_run" in create.inputSchema["properties"]
    assert "workspace_id" in create.inputSchema["required"]
    assert "cue_type" in create.inputSchema["required"]
    assert create.outputSchema["properties"]["status"]["enum"] == ["dry_run", "created", "verification_failed"]

    update = tools["qlab_update_cues"]
    assert update.title == "Update QLab Cues"
    assert "Dry-run planning" in update.description
    assert "batch-update" in update.meta["fastmcp"]["tags"]
    assert update.annotations.readOnlyHint is False
    assert update.annotations.destructiveHint is False
    assert update.annotations.idempotentHint is False
    assert "workspace_id" in update.inputSchema["required"]
    assert "updates" in update.inputSchema["required"]
    assert "cue_ref" not in update.inputSchema["properties"]
    assert update.inputSchema["properties"]["updates"]["minItems"] == 1
    assert update.inputSchema["properties"]["updates"]["maxItems"] == 50
    update_item = update.inputSchema["properties"]["updates"]["items"]["properties"]
    assert update_item["cue_ref"]["minLength"] == 1
    assert "Ambiguous refs" in update_item["cue_ref"]["description"]
    assert "qlab_get_cue_details" in update_item["profile"]["description"]
    assert "updated_with_confirmed_timeouts" in update.outputSchema["properties"]["status"]["enum"]
    assert "per cue item" in update.outputSchema["properties"]["timeout_confirmed_count"]["description"]
    result_item = update.outputSchema["properties"]["results"]["items"]["properties"]
    assert "dry_run_preflight_failed" in result_item["status"]["enum"]
    assert "QLAB_UPDATE_DEBUG" in result_item["debug"]["description"]


def test_server_masks_internal_error_details_and_sets_tool_timeouts() -> None:
    async def tool_timeouts():
        return {
            name: (await mcp.get_tool(name)).timeout
            for name in (
                "qlab_check_connection",
                "qlab_get_workspace_overview",
                "qlab_get_workspace_settings",
                "qlab_get_workspace_setting_details",
                "qlab_query_cues",
                "qlab_get_cue_details",
                "qlab_check_write_readiness",
                "qlab_create_cue",
                "qlab_update_cues",
            )
        }

    assert mcp._mask_error_details is True
    assert asyncio.run(tool_timeouts()) == {
        "qlab_check_connection": CHECK_CONNECTION_TIMEOUT,
        "qlab_get_workspace_overview": WORKSPACE_OVERVIEW_TIMEOUT,
        "qlab_get_workspace_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_setting_details": WORKSPACE_SETTING_DETAILS_TIMEOUT,
        "qlab_query_cues": QUERY_CUES_TIMEOUT,
        "qlab_get_cue_details": CUE_DETAILS_TIMEOUT,
        "qlab_check_write_readiness": WRITE_READINESS_TIMEOUT,
        "qlab_create_cue": CREATE_CUE_TIMEOUT,
        "qlab_update_cues": UPDATE_CUES_TIMEOUT,
    }


def test_expected_tool_errors_are_sanitized() -> None:
    def denied_with_sensitive_payload() -> None:
        raise QLabReplyError(
            "denied",
            {"fileTarget": "/Users/stage/secret.wav", "passcode": "1234"},
            "/workspace/ws-1/settings/network/patchList",
        )

    try:
        _run_tool(denied_with_sensitive_payload)
    except ToolError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ToolError")

    assert "denied" in message
    assert "secret.wav" not in message
    assert "1234" not in message
    assert "patchList" not in message


def test_tool_wrapper_converts_validation_errors_to_tool_error() -> None:
    try:
        qlab_query_cues("ws-1", "type", "Audio", max_results=0)
    except ToolError as exc:
        assert "max_results must be 1 or greater" in str(exc)
    else:
        raise AssertionError("Expected ToolError")


def test_public_cue_details_reports_clear_batch_limit(monkeypatch) -> None:
    class FakeReader:
        def get_cue_details(self, workspace_id, cue_ref, profile):
            raise ValueError("cue_ref list can include at most 50 cues")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    try:
        qlab_get_cue_details("ws-1", ["10"] * 51)
    except ToolError as exc:
        assert "cue_ref list can include at most 50 cues" in str(exc)
    else:
        raise AssertionError("Expected ToolError")


def test_overview_public_tool_preserves_agent_summary(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "workspace": {"displayName": "demo.qlab5"},
                "cue_count": 879,
                "cue_count_meaning": "inspected_cues",
                "known_total_cues": 1424,
                "known_total_cues_status": "partial",
                "known_total_cues_source": "bounded_shallow_traversal+children/uniqueIDs/shallow",
                "known_total_cues_meaning": "cue_items_including_cue_lists",
                "summary": {"cue_lists": 7, "inspected_cues": 879},
                "agent_summary": {
                    "workspace_total_for_humans": "1417 cues in 7 lists",
                    "workspace_total_status": "partial",
                    "known_total_cue_items": 1424,
                    "cue_lists": 7,
                    "metadata_inspected_cues": 879,
                    "id_only_counted_cues": 545,
                    "metadata_partial": True,
                    "main_partial_branches": [{"number": "TEKNO", "child_count": 545}],
                },
                "cue_lists": [],
                "limits": {"truncated": True, "truncation_reasons": ["child_metadata_unavailable"]},
                "warnings": ["metadata partial"],
                "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_workspace_overview()
    payload = result.model_dump()

    assert payload["agent_summary"]["workspace_total_for_humans"] == "1417 cues in 7 lists"
    assert payload["agent_summary"]["id_only_counted_cues"] == 545
    assert payload["known_total_cues_meaning"] == "cue_items_including_cue_lists"


def test_query_public_tool_preserves_completeness_fields(monkeypatch) -> None:
    class FakeReader:
        def query_cues(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "filters": [{"filter": "type", "value": "Light"}],
                "profile": "basic_safe",
                "scanned_count": 879,
                "matched_count": 391,
                "returned_count": 20,
                "total_cue_ids": 879,
                "query_completeness": "partial",
                "query_completeness_reasons": ["id_only_unscanned"],
                "id_only_unscanned_count": 545,
                "omitted_branches": [
                    {
                        "cue_ref": "C7105E58-F911-4A2E-9BD9-40CEDDC79AE1",
                        "number": "TEKNO",
                        "child_count": 545,
                        "fallback_used": True,
                    }
                ],
                "partial_branches": [
                    {
                        "cue_ref": "C7105E58-F911-4A2E-9BD9-40CEDDC79AE1",
                        "number": "TEKNO",
                        "child_count": 545,
                        "fallback_used": True,
                    }
                ],
                "truncated": True,
                "truncation_reasons": ["child_metadata_unavailable"],
                "scanned_all_cues": False,
                "result_limited": False,
                "limits": {"max_results": 20, "max_cues_scanned": 5000},
                "cues": [],
                "warnings": ["Query scanned only cues with metadata available."],
                "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_query_cues("ws-1", "type", "Light", max_cues_scanned=5000, max_results=20)
    payload = result.model_dump()

    assert payload["query_completeness"] == "partial"
    assert payload["query_completeness_reasons"] == ["id_only_unscanned"]
    assert payload["id_only_unscanned_count"] == 545
    assert payload["omitted_branches"][0]["number"] == "TEKNO"
    assert payload["partial_branches"][0]["child_count"] == 545
    assert "metadata available" in payload["warnings"][0]
