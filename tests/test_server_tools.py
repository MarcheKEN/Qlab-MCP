from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.utilities.mcp_server_config.v1.mcp_server_config import MCPServerConfig

import qlab_mcp.server as server_module
from qlab_mcp.errors import OscTimeoutError, QLabReplyError
from qlab_mcp.server import (
    CHECK_CONNECTION_TIMEOUT,
    CREATE_CUE_TIMEOUT,
    CREATE_CUES_TIMEOUT,
    CUE_DETAILS_TIMEOUT,
    QUERY_CUES_TIMEOUT,
    UPDATE_CUES_TIMEOUT,
    WORKSPACE_OVERVIEW_TIMEOUT,
    WORKSPACE_STATUS_TIMEOUT,
    WORKSPACE_SETTING_DETAILS_TIMEOUT,
    WORKSPACE_SETTINGS_TIMEOUT,
    WRITE_READINESS_TIMEOUT,
    _run_tool,
    mcp,
    qlab_get_workspace_overview,
    qlab_get_workspace_status,
    qlab_get_workspace_setting_details,
    qlab_get_workspace_settings,
    qlab_get_cue_details,
    qlab_query_cues,
)
from qlab_mcp.write.registry import UPDATE_PROFILES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NOISE_KEYS: frozenset[str] = frozenset()
EXPECTED_FASTMCP_TOOL_CONTRACTS = {
    "qlab_check_connection": {
        "title": "Check QLab Connection",
        "timeout": CHECK_CONNECTION_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["diagnostics", "orientation", "qlab", "safe-read"],
        "input_schema_hash": "c8967eca6cd7a45b2f08cc835ff932aea3551d133cc6fd5c8388ffc177e44b83",
        "output_schema_hash": "abf13920f210805507d32c24c3166d28c8dd6fdbfe04b50678924063d4508e56",
    },
    "qlab_check_write_readiness": {
        "title": "Check QLab Write Readiness",
        "timeout": WRITE_READINESS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["diagnostics", "qlab", "safe-read", "write-mode"],
        "input_schema_hash": "a100d2c71d8a6573be48039f083c85ed16c495c4b69cc2a248b81336bb589578",
        "output_schema_hash": "0f27f2df78299a76f441eeb8d81064c38cda1bdf763bddb1f5ae79b67451de26",
    },
    "qlab_create_cue": {
        "title": "Create QLab Cue",
        "timeout": CREATE_CUE_TIMEOUT,
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "tags": ["cue-create", "gated-write", "qlab", "write-mode"],
        "input_schema_hash": "faa9110ad1e9ba3b77634190668c61f1f7f03addbb76aa85fcc88c4e8efded6d",
        "output_schema_hash": "bb5ea5c46ac0b602557a64f66362903acafd2a02498cc1d39749dcf5eb06e4f5",
    },
    "qlab_create_cues": {
        "title": "Create QLab Cues",
        "timeout": CREATE_CUES_TIMEOUT,
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "tags": ["batch-create", "cue-create", "gated-write", "qlab", "write-mode"],
        "input_schema_hash": "5797a769a3cd5c64c8e6635013ec0156e19914d864827922c181e935523b9b33",
        "output_schema_hash": "e6e0ef7fdaf321850769bc0afe6a8cf1342c4cc22c38519e3483345eb8efb4f5",
    },
    "qlab_get_cue_details": {
        "title": "Get QLab Cue Details",
        "timeout": CUE_DETAILS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["details", "diagnostics", "qlab", "safe-read"],
        "input_schema_hash": "5a71f63ffc5db72a1b7f270fc16a03fe6942155a4eb8b22ef9bab4e0f8862925",
        "output_schema_hash": "f5d340a970b906607ed9c3a2015c17a8da6f3eee5d70b36971c26920aa14da72",
    },
    "qlab_get_workspace_overview": {
        "title": "Get QLab Workspace Overview",
        "timeout": WORKSPACE_OVERVIEW_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["orientation", "qlab", "safe-read", "structure"],
        "input_schema_hash": "02908bfb5dd7d423c04a7d1e071a711db5cf76ce5b00d0355de38585df5a0608",
        "output_schema_hash": "dcf4a4fc455bb3ebc3e62b0ca04e3cbc75bd91fc7e19fdb978283796f3f50454",
    },
    "qlab_get_workspace_setting_details": {
        "title": "Get QLab Workspace Setting Details",
        "timeout": WORKSPACE_SETTING_DETAILS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["details", "patches", "qlab", "routing", "safe-read", "settings"],
        "input_schema_hash": "9bf79634d0ff17fccb9fc8b3bfe70bbbbdaed6ccbb8f709a52ad9e1cb8170ac0",
        "output_schema_hash": "21e6efa3493bb4c6108339758493006c3b27ef4fe6e884201372db7c77dc7d3f",
    },
    "qlab_get_workspace_settings": {
        "title": "Get QLab Workspace Settings",
        "timeout": WORKSPACE_SETTINGS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["inventory", "patches", "qlab", "routing", "safe-read", "settings"],
        "input_schema_hash": "d7267c1e7ab87ba58b13c0efadbd7d30ad9e431445844779f6656fec8ee1bca1",
        "output_schema_hash": "3c4381ac3b10af3e7655c8cb65240d8909bf89f3c0c58d04513299380781b8d0",
    },
    "qlab_get_workspace_status": {
        "title": "Get QLab Workspace Status",
        "timeout": WORKSPACE_STATUS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["diagnostics", "qlab", "safe-read", "status", "timecode"],
        "input_schema_hash": "e2257d4dd2a0f5ad860001e3fb2e58347fbd1802d4fc0ca35dfe1c4712bffd46",
        "output_schema_hash": "a313d8fccd6b881ef920a3782fa3381f17854dcd88ce902b5f376ef2fdfc8a8a",
    },
    "qlab_query_cues": {
        "title": "Query QLab Cues",
        "timeout": QUERY_CUES_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["details", "inventory", "qlab", "query", "safe-read"],
        "input_schema_hash": "500535ba62fbc315e4af2af2fcd7074e41e16e0389bc4496925804a80edeb511",
        "output_schema_hash": "16613ad3378154e2b01bb1dabe40ba6d56ff1394ffea2ad960ae14cd775549a5",
    },
    "qlab_edit_cues": {
        "title": "Edit QLab Cues",
        "timeout": UPDATE_CUES_TIMEOUT,
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "tags": ["batch-edit", "cue-edit", "gated-write", "qlab", "write-mode"],
        "input_schema_hash": "ed9ba9bbfec6d77e87994f66680f65dcf2399f17e963c226f1daaf6c8b62f7df",
        "output_schema_hash": "016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d",
    },
    "qlab_move_cues": {
        "title": "Move QLab Cues",
        "timeout": UPDATE_CUES_TIMEOUT,
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "tags": ["cue-move", "gated-write", "qlab", "write-mode"],
        "input_schema_hash": "947607daa76e34b06f01d84f95d19107735b865150c48203ab6fb0978a864c8a",
        "output_schema_hash": "1338128f239451d8d5d14fe5847888f657b4f5864972c221b5466606fa90f33a",
    },
    "qlab_delete_cues": {
        "title": "Delete QLab Cues",
        "timeout": 180.0,
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "tags": ["cue-delete", "gated-write", "qlab", "write-mode"],
        "input_schema_hash": "d761f60fcb5e204262098c4d16fdf9b8cf2bc2875dd4c9114959975bbf10a270",
        "output_schema_hash": "d1a1e6c0d3df47ee9f83366133c85d20f71e7356396acb61b3c6b29e57f24bd6",
    },
}
EXPECTED_DESCRIPTION_PHRASES = {
    "qlab_check_connection": ("passcode", "/connect permission scopes"),
    "qlab_get_workspace_overview": ("first structural read", "bounded and shallow"),
    "qlab_get_workspace_status": ("Workspace Status", "not expose"),
    "qlab_get_workspace_settings": ("Summary mode", "one failed request does not block"),
    "qlab_get_workspace_setting_details": ("Backwards-compatible wrapper", "safe profile"),
    "qlab_query_cues": ("optional AND filters", "truncation metadata"),
    "qlab_get_cue_details": ("editable for update capability discovery", "exhaustive only for deep audits"),
    "qlab_check_write_readiness": ("without sending any mutating OSC commands", "Edit Mode"),
    "qlab_create_cue": ("dry-run plan", "Dry-run planning never sends mutating OSC"),
    "qlab_create_cues": ("one verified /new per item", "no automatic rollback"),
    "qlab_edit_cues": ("Dry-run planning never sends mutating OSC", "High-risk profiles"),
    "qlab_move_cues": ("sequential QLab cue moves", "never claims atomicity"),
    "qlab_delete_cues": ("sequential deletions", "not atomic"),
}


def _normalized_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalized_schema(child)
            for key, child in sorted(value.items())
            if key not in SCHEMA_NOISE_KEYS
        }
    if isinstance(value, list):
        return [_normalized_schema(child) for child in value]
    return value


def _schema_hash(schema: dict[str, Any]) -> str:
    normalized = json.dumps(_normalized_schema(schema), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


def _annotation_contract(tool: Any) -> dict[str, bool | None]:
    return {
        "readOnlyHint": tool.annotations.readOnlyHint,
        "destructiveHint": tool.annotations.destructiveHint,
        "idempotentHint": tool.annotations.idempotentHint,
        "openWorldHint": tool.annotations.openWorldHint,
    }


async def _tool_contract_snapshot() -> dict[str, dict[str, Any]]:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    snapshot = {}
    for tool in sorted(tools, key=lambda item: item.name):
        runtime_tool = await mcp.get_tool(tool.name)
        snapshot[tool.name] = {
            "title": tool.title,
            "timeout": runtime_tool.timeout,
            "annotations": _annotation_contract(tool),
            "tags": (tool.meta or {}).get("fastmcp", {}).get("tags", []),
            "input_schema_hash": _schema_hash(tool.inputSchema),
            "output_schema_hash": _schema_hash(tool.outputSchema or {}),
        }
    return snapshot


def test_fastmcp_json_points_to_stdio_server_without_write_env() -> None:
    raw_config = json.loads((PROJECT_ROOT / "fastmcp.json").read_text())
    parsed = MCPServerConfig.model_validate(raw_config)

    assert parsed.source.path == "fastmcp_entrypoint.py"
    assert parsed.source.entrypoint == "mcp"
    assert parsed.environment.project is None
    assert parsed.environment.dependencies == ["qlab-mcp @ ."]
    assert parsed.deployment.transport == "stdio"
    assert (PROJECT_ROOT / parsed.source.path).read_text() == "from qlab_mcp.server import mcp\n"

    deployment_env = raw_config.get("deployment", {}).get("env", {})
    assert "QLAB_PASSCODE" not in deployment_env
    assert "QLAB_ENABLE_WRITE" not in deployment_env
    assert "QLAB_WRITE_DRY_RUN_DEFAULT" not in deployment_env


def test_fastmcp_initialization_reports_project_version_and_universal_guidance() -> None:
    async def initialize():
        async with Client(mcp) as client:
            return client.initialize_result

    initialize_result = asyncio.run(initialize())
    assert initialize_result.serverInfo.version == "0.3.0"
    instructions = initialize_result.instructions
    assert instructions
    for phrase in (
        "exact UUIDs",
        "qlab_check_write_readiness",
        "dry-run",
        "fresh readback",
        "Do not retry",
        "GO-ready",
        "QLab 5.5.10",
    ):
        assert phrase in instructions
    assert "seven inspector tools" not in instructions


def test_fastmcp_tool_contract_snapshot_matches_current_public_surface() -> None:
    assert asyncio.run(_tool_contract_snapshot()) == EXPECTED_FASTMCP_TOOL_CONTRACTS


def test_readme_tool_inventory_matches_current_public_surface() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text()
    tool_groups = readme.split("## Tool Groups", 1)[1].split("## Read Model", 1)[0]
    documented_tools = [
        line.split("`", 2)[1]
        for line in tool_groups.splitlines()
        if line.startswith("| `qlab_")
    ]

    assert len(documented_tools) == len(EXPECTED_FASTMCP_TOOL_CONTRACTS)
    assert set(documented_tools) == set(EXPECTED_FASTMCP_TOOL_CONTRACTS)


def test_fastmcp_public_inventory_excludes_control_and_raw_osc_surface() -> None:
    async def list_tools() -> list[Any]:
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())
    tool_names = {tool.name for tool in tools}

    assert len(tools) == 13
    assert tool_names == set(EXPECTED_FASTMCP_TOOL_CONTRACTS)
    forbidden_surface_tokens = {"go", "stop", "panic", "raw", "osc", "playback", "live"}
    assert all(
        token not in tool_name.casefold()
        for tool_name in tool_names
        for token in forbidden_surface_tokens
    )

    def schema_fields(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value.get("properties", {})).union(
                *(schema_fields(child) for child in value.values())
            )
        if isinstance(value, list):
            return set().union(*(schema_fields(child) for child in value))
        return set()

    public_input_fields = set().union(
        *(schema_fields(tool.inputSchema) for tool in tools)
    )
    assert public_input_fields.isdisjoint(
        {"address", "osc_address", "osc_path", "raw_osc", "raw_osc_message"}
    )

    real_write_specs = [
        property_spec
        for profile in UPDATE_PROFILES.values()
        for property_spec in profile.properties
        if property_spec.real_write_enabled
    ]
    assert {
        property_spec.name
        for property_spec in real_write_specs
        if "live" in property_spec.modes
    } == {"secondColorName"}

    control_properties = {
        "playbackPosition",
        "playbackPositionID",
        "playbackPosition/next",
        "playbackPosition/previous",
        "playbackPosition/none",
        "playbackPosition/nextSequence",
        "playbackPosition/previousSequence",
        "playlist/next",
        "playlist/previous",
        "panic",
        "auditionGo",
        "auditionPreview",
        "preview",
    }
    assert not {
        property_spec.name
        for property_spec in real_write_specs
        if property_spec.name in control_properties
    }


def test_move_cues_fastmcp_schema_limits_and_nested_model() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_move_cues")

    schema = asyncio.run(get_tool_schema())
    moves = schema["properties"]["moves"]

    assert moves["minItems"] == 1
    assert moves["maxItems"] == 10
    assert moves["items"]["required"] == ["cue_id"]
    assert moves["items"]["properties"]["cue_id"]["format"] == "uuid"


def test_move_cues_fastmcp_returns_structured_plan(monkeypatch) -> None:
    class FakeReader:
        def move_cues(self, workspace_id, moves, dry_run, confirm_token):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert moves == [{"cue_id": "11111111-1111-4111-8111-111111111111", "position": "last"}]
            assert dry_run is True
            assert confirm_token is None
            return {
                "ok": True,
                "status": "planned",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 1,
                "moved_count": 0,
                "failed_count": 0,
                "results": [{"cue_id": moves[0]["cue_id"], "position": "last"}],
                "confirm_token": "confirm:moveCues:v1:payload:signature",
                "rollback": None,
                "errors": None,
                "warnings": ["Dry run only."],
                "message": "Cue move batch planned.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_move_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "moves": [{"cue_id": "11111111-1111-4111-8111-111111111111", "position": "last"}],
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.structured_content["status"] == "planned"
    assert result.structured_content["confirm_token"].startswith("confirm:moveCues:v1:")


def test_create_cue_fastmcp_forwards_anchor_and_returns_structured_plan(monkeypatch) -> None:
    class FakeReader:
        def create_cue(self, workspace_id, cue_type, dry_run, after_cue_id, parent_container_id, confirm_token):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_type == "wait"
            assert dry_run is True
            assert after_cue_id == "11111111-1111-4111-8111-111111111111"
            assert parent_container_id is None
            assert confirm_token is None
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace_id,
                "cue_type": "Wait",
                "dry_run": True,
                "confirm_token": "confirm:createCue:v2:payload:signature",
                "created_cue_id": None,
                "placement": {
                    "after_cue_id": after_cue_id,
                    "expected_index": 1,
                    "status": "anchored",
                },
                "planned_operations": [
                    {"operation": "new", "args": ["Wait", after_cue_id]},
                    {"operation": "verify"},
                    {"operation": "verify_structure"},
                ],
                "executed_operations": [],
                "verification": None,
                "cleanup_required": False,
                "cleanup": None,
                "errors": None,
                "warnings": ["Dry run only."],
                "message": "Cue create batch planned.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_create_cue",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cue_type": "wait",
                    "after_cue_id": "11111111-1111-4111-8111-111111111111",
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.is_error is False
    assert result.structured_content["status"] == "dry_run"
    assert result.structured_content["confirm_token"].startswith("confirm:createCue:v2:")
    assert result.structured_content["planned_operations"][0]["args"] == [
        "Wait",
        "11111111-1111-4111-8111-111111111111",
    ]
    assert result.structured_content["executed_operations"] == []


def test_create_cues_fastmcp_forwards_ordered_types_and_initial_anchor(monkeypatch) -> None:
    class FakeReader:
        def create_cues(self, workspace_id, cue_types, dry_run, after_cue_id, parent_container_id, confirm_token):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_types == ["memo", "audio", "video"]
            assert dry_run is True
            assert after_cue_id == "11111111-1111-4111-8111-111111111111"
            assert parent_container_id is None
            assert confirm_token is None
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 3,
                "planned_count": 3,
                "created_count": 0,
                "results": [],
                "planned_operations": [
                    {"operation": "new", "args": ["memo", "<anchor>"]},
                    {"operation": "new", "args": ["audio", "<previous_created_cue_id>"]},
                    {"operation": "new", "args": ["video", "<previous_created_cue_id>"]},
                ],
                "executed_operations": [],
                "confirm_token": "confirm:createCues:v1:payload:signature",
                "errors": None,
                "warnings": [],
                "message": "planned",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_create_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cue_types": ["memo", "audio", "video"],
                    "after_cue_id": "11111111-1111-4111-8111-111111111111",
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.is_error is False
    assert result.structured_content["status"] == "dry_run"
    assert result.structured_content["requested_count"] == 3
    assert result.structured_content["confirm_token"].startswith("confirm:createCues:v1:")


def test_delete_cues_fastmcp_schema_limits_and_nested_uuid_model() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_delete_cues")

    schema = asyncio.run(get_tool_schema())
    cue_ids = schema["properties"]["cue_ids"]["anyOf"][0]

    assert cue_ids["minItems"] == 0
    assert cue_ids["maxItems"] == 10
    assert cue_ids["items"]["format"] == "uuid"
    assert "confirm_token" in schema["properties"]


def test_delete_cues_fastmcp_returns_structured_plan(monkeypatch) -> None:
    class FakeReader:
        def delete_cues(self, workspace_id, cue_ids, dry_run, confirm_token, container_id=None, recursive=False):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_ids == ["11111111-1111-4111-8111-111111111111"]
            assert dry_run is True
            assert confirm_token is None
            assert container_id is None
            assert recursive is False
            return {
                "ok": True,
                "status": "planned",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 1,
                "deleted_count": 0,
                "failed_count": 0,
                "timeout_confirmed_count": 0,
                "results": [{"cue_id": cue_ids[0]}],
                "confirm_token": "confirm:deleteCues:v1:payload:signature",
                "errors": None,
                "warnings": ["Dry run only."],
                "message": "Cue delete batch planned.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_delete_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cue_ids": ["11111111-1111-4111-8111-111111111111"],
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.structured_content["status"] == "planned"
    assert result.structured_content["confirm_token"].startswith("confirm:deleteCues:v1:")


def test_delete_cues_fastmcp_forwards_recursive_container(monkeypatch) -> None:
    class FakeReader:
        def delete_cues(self, workspace_id, cue_ids, dry_run, confirm_token, container_id=None, recursive=False):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_ids == []
            assert dry_run is True
            assert confirm_token is None
            assert container_id == "22222222-2222-4222-8222-222222222222"
            assert recursive is True
            return {
                "ok": True,
                "status": "planned",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 2,
                "deleted_count": 0,
                "failed_count": 0,
                "expanded_count": 2,
                "container_id": container_id,
                "recursive": True,
                "preserved_container_id": container_id,
                "results": [],
                "confirm_token": "confirm:deleteCues:v1:payload:signature",
                "errors": None,
                "warnings": [],
                "message": "planned",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_delete_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "container_id": "22222222-2222-4222-8222-222222222222",
                    "recursive": True,
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.is_error is False
    assert result.structured_content["recursive"] is True
    assert result.structured_content["preserved_container_id"] == "22222222-2222-4222-8222-222222222222"


def test_fastmcp_tool_descriptions_keep_agent_safety_phrases() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    assert set(tools) == set(EXPECTED_DESCRIPTION_PHRASES)
    for tool_name, phrases in EXPECTED_DESCRIPTION_PHRASES.items():
        description = tools[tool_name].description or ""
        for phrase in phrases:
            assert phrase in description, f"{tool_name} description lost phrase: {phrase!r}"


def test_fastmcp_tool_contract_keeps_safety_annotations_and_output_schemas() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    write_tools = {"qlab_create_cue", "qlab_create_cues", "qlab_edit_cues", "qlab_move_cues", "qlab_delete_cues"}
    read_only_tools = set(EXPECTED_FASTMCP_TOOL_CONTRACTS) - write_tools

    for tool_name in read_only_tools:
        assert tools[tool_name].annotations.readOnlyHint is True, f"{tool_name} lost readOnlyHint"
        if tool_name != "qlab_delete_cues":
            assert tools[tool_name].annotations.destructiveHint is False, f"{tool_name} became destructive"
        assert tools[tool_name].outputSchema, f"{tool_name} lost outputSchema"

    for tool_name in write_tools:
        assert tools[tool_name].annotations.readOnlyHint is False, f"{tool_name} was marked read-only"
        if tool_name == "qlab_delete_cues":
            assert tools[tool_name].annotations.destructiveHint is True
        else:
            assert tools[tool_name].annotations.destructiveHint is False, f"{tool_name} became destructive"
        assert tools[tool_name].annotations.idempotentHint is False, f"{tool_name} was marked idempotent"
        assert tools[tool_name].outputSchema, f"{tool_name} lost outputSchema"


def test_edit_cues_fastmcp_schema_keeps_batch_contract() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    update_schema = tools["qlab_edit_cues"].inputSchema
    update_properties = update_schema["properties"]
    update_items = update_properties["updates"]["items"]
    update_item_properties = update_items["properties"]
    update_output = tools["qlab_edit_cues"].outputSchema

    assert update_schema["required"] == ["workspace_id", "updates"]
    assert set(update_properties) == {"workspace_id", "updates", "dry_run"}
    assert update_properties["updates"]["minItems"] == 1
    assert update_properties["updates"]["maxItems"] == 50
    assert update_items["required"] == ["cue_ref"]
    assert set(update_item_properties) == {"cue_ref", "profile", "properties", "operations", "confirm_gates"}
    assert "enum" not in update_item_properties["profile"]
    assert update_output["required"] == [
        "ok",
        "status",
        "workspace_id",
        "dry_run",
        "requested_count",
        "planned_count",
        "updated_count",
        "failed_count",
        "timeout_confirmed_count",
        "results",
        "message",
    ]
    assert "updated_with_confirmed_timeouts" in update_output["properties"]["status"]["enum"]
    assert "updateq_plan" in update_output["properties"]["results"]["items"]["properties"]


def test_qlab_edit_cues_fastmcp_response_keeps_fade_basic_token(monkeypatch) -> None:
    token = "confirm:fadeBasic:v1:test-payload:test-signature"
    calls = []

    class FakeReader:
        def edit_cues(self, workspace_id, updates, dry_run):
            calls.append((workspace_id, updates, dry_run))
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert dry_run is True
            assert updates == [
                {
                    "cue_ref": "11111111-1111-4111-8111-111111111111",
                    "profile": "fade_basic",
                    "properties": {"name": "Renamed Fade"},
                    "operations": None,
                    "confirm_gates": None,
                }
            ]
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 1,
                "updated_count": 0,
                "failed_count": 0,
                "timeout_confirmed_count": 0,
                "results": [
                    {
                        "cue_ref": updates[0]["cue_ref"],
                        "cue_id": updates[0]["cue_ref"],
                        "profile": "fade_basic",
                        "status": "dry_run",
                        "properties": updates[0]["properties"],
                        "planned_operations": [
                            {
                                "operation": "set_property",
                                "property": "name",
                                "confirm_token": token,
                            }
                        ],
                        "executed_operations": [],
                    }
                ],
                "message": "Dry run succeeded.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "updates": [
                        {
                            "cue_ref": "11111111-1111-4111-8111-111111111111",
                            "profile": "fade_basic",
                            "properties": {"name": "Renamed Fade"},
                        }
                    ],
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    planned = result.structured_content["results"][0]["planned_operations"]

    assert len(calls) == 1
    assert result.is_error is False
    assert result.structured_content["dry_run"] is True
    assert result.structured_content["planned_count"] == 1
    assert result.structured_content["updated_count"] == 0
    assert planned[0]["confirm_token"].startswith("confirm:fadeBasic:v1:")
    assert result.structured_content["results"][0]["executed_operations"] == []


def test_qlab_edit_cues_fastmcp_response_keeps_structured_group_failure(monkeypatch) -> None:
    workspace_uuid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "group_basic",
        "properties": {"mode": 6},
    }

    class FakeReader:
        def edit_cues(self, *, workspace_id: str, updates, dry_run):
            assert workspace_id == workspace_uuid
            assert dry_run is False
            assert updates[0]["properties"] == {"mode": 6}
            return {
                "ok": False,
                "status": "verification_failed",
                "workspace_id": workspace_uuid,
                "dry_run": False,
                "requested_count": 1,
                "planned_count": 1,
                "updated_count": 0,
                "failed_count": 1,
                "timeout_confirmed_count": 0,
                "results": [
                    {
                        "cue_ref": cue_id,
                        "cue_id": cue_id,
                        "profile": "group_basic",
                        "status": "verification_failed",
                        "properties": {"mode": 6},
                        "before": {"mode": 3},
                        "after": {"mode": 3},
                        "executed_operations": [
                            {
                                "operation": "set_property",
                                "property": "mode",
                                "address": f"/workspace/{workspace_uuid}/cue_id/{cue_id}/mode",
                                "args": [6],
                                "mode": "saved",
                                "status": "ok",
                            }
                        ],
                        "errors": {"verification": "Fresh readback did not match requested mode."},
                        "warnings": [],
                    }
                ],
                "message": "Group write was not confirmed by fresh readback.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_cues",
                {"workspace_id": workspace_uuid, "updates": [update], "dry_run": False},
            )

    result = asyncio.run(call_tool())
    payload = result.structured_content
    item = payload["results"][0]

    assert result.is_error is False
    assert payload["status"] == "verification_failed"
    assert item["status"] == "verification_failed"
    assert len(item["executed_operations"]) == 1
    assert item["executed_operations"][0]["address"].endswith("/mode")
    assert item["after"]["mode"] == 3


def test_tool_metadata_exposes_titles_descriptions_and_read_only_annotations() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    assert set(tools) == {
        "qlab_check_connection",
        "qlab_get_workspace_overview",
        "qlab_get_workspace_status",
        "qlab_get_workspace_settings",
        "qlab_get_workspace_setting_details",
        "qlab_query_cues",
        "qlab_get_cue_details",
        "qlab_check_write_readiness",
        "qlab_create_cue",
        "qlab_create_cues",
        "qlab_edit_cues",
        "qlab_move_cues",
        "qlab_delete_cues",
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
    assert "maximum" not in overview.inputSchema["properties"]["max_cues"]
    assert "maximum" not in overview.inputSchema["properties"]["max_index_cues"]
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

    status = tools["qlab_get_workspace_status"]
    assert status.title == "Get QLab Workspace Status"
    assert "Workspace Status" in status.description
    assert status.inputSchema["properties"]["profile"]["default"] == "summary"
    assert "enum" not in status.inputSchema["properties"]["profile"]
    assert status.inputSchema["properties"]["max_cues_scanned"]["default"] == 1000
    assert "maximum" not in status.inputSchema["properties"]["sample_limit"]
    assert "sections" in status.outputSchema["properties"]
    assert status.annotations.readOnlyHint is True
    assert status.annotations.destructiveHint is False

    settings = tools["qlab_get_workspace_settings"]
    assert settings.title == "Get QLab Workspace Settings"
    assert "Workspace Settings" in settings.description
    assert settings.annotations.readOnlyHint is True
    assert settings.annotations.destructiveHint is False
    assert settings.inputSchema["properties"]["mode"]["default"] == "summary"
    assert "enum" not in settings.inputSchema["properties"]["mode"]
    assert settings.inputSchema["properties"]["profile"]["default"] == "safe"
    assert "enum" not in settings.inputSchema["properties"]["profile"]
    assert "requests" in settings.inputSchema["properties"]
    requests_schema = settings.inputSchema["properties"]["requests"]
    assert requests_schema["maxItems"] == 50
    sections_schema = settings.inputSchema["properties"]["sections"]
    assert sections_schema["maxItems"] == 6
    assert "available_detail_requests" in settings.outputSchema["properties"]
    assert "succeeded_count" in settings.outputSchema["properties"]
    assert "failed_count" in settings.outputSchema["properties"]
    assert "summary" in settings.description
    assert "one failed request does not block" in settings.description

    setting_details = tools["qlab_get_workspace_setting_details"]
    assert setting_details.title == "Get QLab Workspace Setting Details"
    assert "Backwards-compatible wrapper" in setting_details.description
    assert setting_details.inputSchema["properties"]["profile"]["default"] == "safe"
    assert "enum" not in setting_details.inputSchema["properties"]["profile"]
    assert setting_details.annotations.readOnlyHint is True
    assert setting_details.annotations.destructiveHint is False

    query = tools["qlab_query_cues"]
    assert query.title == "Query QLab Cues"
    assert "optional AND filters" in query.description
    assert query.inputSchema["properties"]["max_results"]["default"] == 500
    assert "maximum" not in query.inputSchema["properties"]["max_results"]
    assert query.inputSchema["properties"]["max_cues_scanned"]["default"] == 500
    assert "maximum" not in query.inputSchema["properties"]["max_cues_scanned"]
    assert "enum" not in query.inputSchema["properties"]["primary_filter"]
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
    assert "enum" not in details.inputSchema["properties"]["profile"]
    assert "Inspector-style" in details.inputSchema["properties"]["profile"]["description"]
    assert "heavy/sensitive" in details.inputSchema["properties"]["profile"]["description"]
    assert "enum" not in query.inputSchema["properties"]["profile"]
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
    assert "workspace_not_found" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "workspace_ambiguous" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "workspace_unavailable" in readiness.outputSchema["properties"]["status"]["enum"]
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
    assert "dry_run" in create.inputSchema["properties"]
    assert "workspace_id" in create.inputSchema["required"]
    assert "cue_type" in create.inputSchema["required"]
    assert "after_cue_id" not in create.inputSchema.get("required", [])
    assert "parent_container_id" in create.inputSchema["properties"]
    assert create.outputSchema["properties"]["status"]["enum"] == [
        "dry_run",
        "preflight_failed",
        "created",
        "verification_failed",
        "workspace_not_found",
        "workspace_ambiguous",
        "workspace_unavailable",
    ]
    assert "cleanup_required" in create.outputSchema["properties"]

    edit = tools["qlab_edit_cues"]
    assert edit.title == "Edit QLab Cues"
    assert "Dry-run planning" in edit.description
    assert "batch-edit" in edit.meta["fastmcp"]["tags"]

    edit = tools["qlab_edit_cues"]
    assert edit.title == "Edit QLab Cues"
    assert "Dry-run planning" in edit.description
    assert "batch-edit" in edit.meta["fastmcp"]["tags"]
    assert edit.annotations.readOnlyHint is False
    assert edit.annotations.destructiveHint is False
    assert edit.annotations.idempotentHint is False
    assert "workspace_id" in edit.inputSchema["required"]
    assert "updates" in edit.inputSchema["required"]
    assert "cue_ref" not in edit.inputSchema["properties"]
    assert edit.inputSchema["properties"]["updates"]["minItems"] == 1
    assert edit.inputSchema["properties"]["updates"]["maxItems"] == 50
    edit_item = edit.inputSchema["properties"]["updates"]["items"]["properties"]
    assert edit_item["cue_ref"]["minLength"] == 1
    assert "Ambiguous refs" in edit_item["cue_ref"]["description"]
    assert "qlab_get_cue_details" in edit_item["profile"]["description"]
    assert "enum" not in edit_item["profile"]
    assert "updated_with_confirmed_timeouts" in edit.outputSchema["properties"]["status"]["enum"]
    assert "workspace_not_found" in edit.outputSchema["properties"]["status"]["enum"]
    assert "workspace_ambiguous" in edit.outputSchema["properties"]["status"]["enum"]
    assert "workspace_unavailable" in edit.outputSchema["properties"]["status"]["enum"]
    assert "per cue item" in edit.outputSchema["properties"]["timeout_confirmed_count"]["description"]
    result_item = edit.outputSchema["properties"]["results"]["items"]["properties"]
    assert "dry_run_preflight_failed" in result_item["status"]["enum"]
    assert "QLAB_UPDATE_DEBUG" in result_item["debug"]["description"]

    delete = tools["qlab_delete_cues"]
    assert delete.title == "Delete QLab Cues"
    assert "explicit leaf" in delete.description
    assert delete.annotations.readOnlyHint is False
    assert delete.annotations.destructiveHint is True
    assert delete.annotations.idempotentHint is False
    delete_cue_ids_schema = delete.inputSchema["properties"]["cue_ids"]["anyOf"][0]
    assert delete_cue_ids_schema["minItems"] == 0
    assert delete_cue_ids_schema["maxItems"] == 10
    assert delete_cue_ids_schema["items"]["format"] == "uuid"
    assert "container_id" in delete.inputSchema["properties"]
    assert "recursive" in delete.inputSchema["properties"]
    assert "confirm:deleteCues:v1:" in delete.inputSchema["properties"]["confirm_token"]["description"]
    assert "verification_failed" in delete.outputSchema["properties"]["status"]["enum"]


def test_create_tool_uses_qlab_template_defaults_without_property_input() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_create_cue")

    schema = asyncio.run(get_tool_schema())

    assert "properties" not in schema["properties"]


def test_server_masks_internal_error_details_and_sets_tool_timeouts() -> None:
    async def tool_timeouts():
        return {
            name: (await mcp.get_tool(name)).timeout
            for name in (
                "qlab_check_connection",
                "qlab_get_workspace_overview",
                "qlab_get_workspace_status",
                "qlab_get_workspace_settings",
                "qlab_get_workspace_setting_details",
                "qlab_query_cues",
                "qlab_get_cue_details",
                "qlab_check_write_readiness",
                "qlab_create_cue",
                "qlab_create_cues",
                "qlab_edit_cues",
            )
        }

    assert mcp._mask_error_details is True
    assert asyncio.run(tool_timeouts()) == {
        "qlab_check_connection": CHECK_CONNECTION_TIMEOUT,
        "qlab_get_workspace_overview": WORKSPACE_OVERVIEW_TIMEOUT,
        "qlab_get_workspace_status": WORKSPACE_STATUS_TIMEOUT,
        "qlab_get_workspace_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_setting_details": WORKSPACE_SETTING_DETAILS_TIMEOUT,
        "qlab_query_cues": QUERY_CUES_TIMEOUT,
        "qlab_get_cue_details": CUE_DETAILS_TIMEOUT,
        "qlab_check_write_readiness": WRITE_READINESS_TIMEOUT,
        "qlab_create_cue": CREATE_CUE_TIMEOUT,
        "qlab_create_cues": CREATE_CUES_TIMEOUT,
        "qlab_edit_cues": UPDATE_CUES_TIMEOUT,
    }


def test_run_tool_closes_reader_on_success(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    result = _run_tool(lambda supplied_reader: supplied_reader)

    assert result is reader
    assert reader.closed is True


def test_run_tool_sets_read_deadline_and_closes_reader(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False
            self.deadline: float | None = None

        def set_read_deadline(self, timeout: float) -> None:
            self.deadline = timeout

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    assert _run_tool(lambda supplied_reader: supplied_reader, timeout=3.0) is reader
    assert reader.deadline == 3.0
    assert reader.closed is True


def test_read_tool_wrappers_pass_their_fastmcp_timeout_to_run_tool(monkeypatch) -> None:
    timeouts: list[float | None] = []

    def capture(_factory, timeout=None):
        timeouts.append(timeout)
        return "ok"

    monkeypatch.setattr(server_module, "_run_tool", capture)

    assert server_module.qlab_check_connection() == "ok"
    assert server_module.qlab_check_write_readiness("ws-1") == "ok"
    assert timeouts == [CHECK_CONNECTION_TIMEOUT, WRITE_READINESS_TIMEOUT]


def test_write_tool_wrappers_do_not_pass_outer_reader_deadlines(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def capture(_factory, **kwargs):
        calls.append(kwargs)
        return "ok"

    monkeypatch.setattr(server_module, "_run_tool", capture)

    assert server_module.qlab_create_cue("ws-1", "memo", dry_run=True, after_cue_id="11111111-1111-4111-8111-111111111111") == "ok"
    assert server_module.qlab_edit_cues("ws-1", [], dry_run=True) == "ok"
    assert server_module.qlab_move_cues("ws-1", [], dry_run=True) == "ok"
    assert server_module.qlab_delete_cues("ws-1", [], dry_run=True) == "ok"
    assert calls == [{}, {}, {}, {}]


def test_run_tool_closes_reader_on_failure(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    try:
        _run_tool(lambda _reader: (_ for _ in ()).throw(QLabReplyError("denied", "badpass", "/workspaces")))
    except ToolError:
        pass
    else:
        raise AssertionError("Expected ToolError")

    assert reader.closed is True


def test_expected_tool_errors_are_sanitized() -> None:
    def denied_with_sensitive_payload(_reader: Any) -> None:
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


def test_public_tool_validation_returns_structured_json_error() -> None:
    result = qlab_query_cues("ws-1", "type", "Audio", max_results=0)
    payload = result.model_dump()

    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["partial"] is False
    assert payload["error_code"] == "validation_failed"
    assert "max_results must be 1 or greater" in payload["message"]
    assert payload["received"]["max_results"] == 0
    assert payload["allowed"]["max_results"] == "1..5000"
    assert "Traceback" not in json.dumps(payload)


def test_workspace_settings_batch_limit_is_structured_and_pre_transport(monkeypatch) -> None:
    class ExplodingReader:
        def get_workspace_settings(self, **kwargs):
            raise AssertionError("reader must not be constructed for an oversized batch")

    monkeypatch.setattr(server_module, "_reader", lambda: ExplodingReader())

    result = qlab_get_workspace_settings(
        "ws-1",
        mode="details",
        requests=[{"section": "light", "kind": "light_patch"}] * 51,
    )
    payload = result.model_dump()

    assert payload["ok"] is False
    assert payload["error_code"] == "workspace_detail_batch_too_large"
    assert payload["received"] == {"request_count": 51}
    assert payload["allowed"] == {"max_requests": 50}


def test_workspace_settings_section_limit_is_structured_and_pre_transport(monkeypatch) -> None:
    class ExplodingReader:
        def get_workspace_settings(self, **kwargs):
            raise AssertionError("reader must not be constructed for too many sections")

    monkeypatch.setattr(server_module, "_reader", lambda: ExplodingReader())

    payload = qlab_get_workspace_settings(
        "ws-1",
        sections=["audio", "video", "network", "midi", "light", "general", "audio"],
    ).model_dump()

    assert payload["ok"] is False
    assert payload["error_code"] == "workspace_sections_too_many"
    assert payload["received"] == {"section_count": 7}
    assert payload["allowed"] == {"max_sections": 6}


def test_query_cues_rejects_exhaustive_profile_before_reader(monkeypatch) -> None:
    class ExplodingReader:
        def query_cues(self, **kwargs):
            raise AssertionError("exhaustive query profile must be rejected before reading cues")

    monkeypatch.setattr(server_module, "_reader", lambda: ExplodingReader())

    payload = qlab_query_cues("ws-1", "type", "Audio", profile="exhaustive").model_dump()

    assert payload["ok"] is False
    assert payload["error_code"] == "cue_profile_not_supported"
    assert payload["received"]["profile"] == "exhaustive"


def test_sensitive_cue_query_limit_rejects_large_result_count_before_reader(monkeypatch) -> None:
    class ExplodingReader:
        def query_cues(self, **kwargs):
            raise AssertionError("large sensitive query must be rejected before reading cues")

    monkeypatch.setattr(server_module, "_reader", lambda: ExplodingReader())

    payload = qlab_query_cues("ws-1", "type", "Audio", profile="full_sensitive", max_results=51).model_dump()

    assert payload["ok"] is False
    assert payload["error_code"] == "cue_payload_too_large"
    assert payload["allowed"]["max_results"] == 50


def test_public_cue_details_reports_clear_batch_limit_as_structured_json(monkeypatch) -> None:
    class FakeReader:
        def get_cue_details(self, workspace_id, cue_ref, profile):
            raise ValueError("cue_ref list can include at most 50 cues")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_cue_details("ws-1", ["10"] * 51)
    payload = result.model_dump()

    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["partial"] is False
    assert payload["error_code"] == "cue_batch_too_large"
    assert payload["allowed"] == {"max_cues": 50}
    assert "cue_ref list can include at most 50 cues" in payload["message"]
    assert payload["requested_count"] == 51
    assert payload["failed_count"] == 51


def test_structured_read_error_keeps_original_sanitized_message(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            raise OscTimeoutError("read deadline exhausted")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    payload = qlab_get_workspace_overview("ws-1").model_dump()

    assert payload["message"] == "read deadline exhausted"


def test_public_read_tools_redact_internal_exception_paths(monkeypatch) -> None:
    internal_message = "/Users/filarmonica/Documents/qlab-mcp-osc/src/qlab_mcp/server.py: bad profile"

    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            raise ValueError(internal_message)

        def get_workspace_status(self, **kwargs):
            raise ValueError(internal_message)

        def get_workspace_settings(self, **kwargs):
            raise ValueError(internal_message)

        def get_workspace_setting_details(self, **kwargs):
            raise ValueError(internal_message)

        def query_cues(self, **kwargs):
            raise ValueError(internal_message)

        def get_cue_details(self, workspace_id, cue_ref, profile):
            raise ValueError(internal_message)

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    results = [
        qlab_get_workspace_overview("ws-1").model_dump(),
        qlab_get_workspace_status("ws-1").model_dump(),
        qlab_get_workspace_settings("ws-1").model_dump(),
        qlab_get_workspace_setting_details("ws-1", "audio", "bad_kind").model_dump(),
        qlab_query_cues("ws-1", "type", "Audio").model_dump(),
        qlab_get_cue_details("ws-1", "10", "bad_profile").model_dump(),
    ]

    for payload in results:
        serialized = json.dumps(payload)
        assert payload["ok"] is False
        assert payload["status"] == "error"
        assert payload["partial"] is False
        assert payload["error_code"] == "validation_failed"
        assert payload["message"] == "[redacted_internal_path]"
        assert "/qlab-mcp-osc/" not in serialized
        assert "Traceback" not in serialized
        assert "pydantic" not in serialized.lower()


def test_public_setting_details_validation_error_preserves_received_allowed_details(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_setting_details(self, **kwargs):
            raise ValueError("Unsupported setting kind: bad_kind")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_workspace_setting_details("ws-1", "audio", "bad_kind", profile="bad_profile")
    payload = result.model_dump()

    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["partial"] is False
    assert payload["error_code"] == "validation_failed"
    assert payload["received"] == {"section": "audio", "kind": "bad_kind", "ref": None, "profile": "bad_profile"}
    assert "audio" in payload["allowed"]["sections"]
    assert "output_patch" in payload["allowed"]["kinds"]
    assert payload["details"] is None


def test_public_read_success_shapes_have_meaningful_ok_status_partial(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "workspace": {"displayName": "demo.qlab5"},
                "cue_count": 1,
                "summary": {"total_cue_ids_status": "known", "health_counts_status": "known"},
                "cue_lists": [],
                "limits": {"truncated": False},
                "warnings": [],
                "errors": None,
            }

        def query_cues(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "filters": [{"filter": "type", "value": "Audio"}],
                "profile": "basic_safe",
                "scanned_count": 1,
                "matched_count": 1,
                "returned_count": 1,
                "total_cue_ids": 1,
                "query_completeness": "complete",
                "truncated": False,
                "scanned_all_cues": True,
                "result_limited": False,
                "limits": {"max_results": 500, "max_cues_scanned": 500},
                "cues": [{"uniqueID": "cue-1", "type": "Audio"}],
                "warnings": [],
                "errors": None,
            }

        def get_cue_details(self, workspace_id, cue_ref, profile):
            return {
                "workspace_id": workspace_id,
                "cue_ref": cue_ref,
                "profile": profile,
                "cue_type": "Audio",
                "properties": {"uniqueID": "cue-1", "type": "Audio"},
                "errors": None,
                "warnings": [],
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    overview = qlab_get_workspace_overview("ws-1").model_dump()
    query = qlab_query_cues("ws-1", "type", "Audio").model_dump()
    details = qlab_get_cue_details("ws-1", "cue-1").model_dump()

    for payload in (overview, query, details):
        assert payload["ok"] is True
        assert payload["status"] == "ok"
        assert payload["partial"] is False


def test_public_read_partial_success_shapes_have_meaningful_ok_status_partial(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "workspace": {"displayName": "demo.qlab5"},
                "cue_count": 1,
                "summary": {"total_cue_ids_status": "partial", "health_counts_status": "partial_non_authoritative"},
                "cue_lists": [],
                "limits": {"truncated": True},
                "warnings": ["partial"],
                "errors": None,
            }

        def query_cues(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "filters": [{"filter": "type", "value": "Audio"}],
                "profile": "basic_safe",
                "scanned_count": 1,
                "matched_count": 1,
                "returned_count": 1,
                "total_cue_ids": 2,
                "query_completeness": "partial",
                "query_completeness_reasons": ["max_cues_scanned"],
                "truncated": True,
                "truncation_reasons": ["max_cues_scanned"],
                "scanned_all_cues": False,
                "result_limited": False,
                "limits": {"max_results": 500, "max_cues_scanned": 1},
                "cues": [{"uniqueID": "cue-1", "type": "Audio"}],
                "warnings": ["partial"],
                "errors": None,
            }

        def get_cue_details(self, workspace_id, cue_ref, profile):
            return {
                "workspace_id": workspace_id,
                "cue_ref": cue_ref,
                "profile": profile,
                "cue_type": None,
                "properties": {},
                "errors": {"error_code": "cue_ref_unresolved"},
                "warnings": ["partial"],
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    overview = qlab_get_workspace_overview("ws-1").model_dump()
    query = qlab_query_cues("ws-1", "type", "Audio", max_cues_scanned=1).model_dump()
    details = qlab_get_cue_details("ws-1", "missing").model_dump()

    for payload in (overview, query, details):
        assert payload["status"] in {"partial", "error"}
        if payload["status"] == "partial":
            assert payload["ok"] is True
            assert payload["partial"] is True
        else:
            assert payload["ok"] is False
            assert payload["partial"] is False


def test_public_cue_details_batch_normalizes_item_shapes(monkeypatch) -> None:
    class FakeReader:
        def get_cue_details(self, workspace_id, cue_ref, profile):
            return {
                "ok": True,
                "workspace_id": workspace_id,
                "requested_count": 3,
                "succeeded_count": 2,
                "failed_count": 1,
                "profile": profile,
                "results": [
                    {
                        "workspace_id": workspace_id,
                        "cue_ref": "ok",
                        "profile": profile,
                        "cue_type": "Audio",
                        "properties": {"uniqueID": "ok"},
                        "errors": None,
                        "warnings": [],
                    },
                    {
                        "workspace_id": workspace_id,
                        "cue_ref": "partial",
                        "profile": profile,
                        "cue_type": "Audio",
                        "properties": {"uniqueID": "partial"},
                        "errors": {"notes": "read failed"},
                        "warnings": [],
                    },
                    {
                        "workspace_id": workspace_id,
                        "cue_ref": "missing",
                        "profile": profile,
                        "cue_type": None,
                        "properties": {},
                        "errors": {"error_code": "cue_ref_unresolved", "message": "Cue ref could not be resolved or read."},
                        "warnings": [],
                    },
                ],
                "errors": {"missing": "cue_ref_unresolved"},
                "warnings": ["partial"],
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    payload = qlab_get_cue_details("ws-1", ["ok", "partial", "missing"]).model_dump()

    assert payload["ok"] is True
    assert payload["status"] == "partial"
    assert payload["partial"] is True
    assert [(item["ok"], item["status"], item["partial"]) for item in payload["results"]] == [
        (True, "ok", False),
        (True, "partial", True),
        (False, "error", False),
    ]


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


def test_workspace_status_public_tool_preserves_sections(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_status(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "profile": "summary",
                "sections": {
                    "warnings_summary": {"source": "derived_from_cues", "available": True, "broken_count": 1},
                    "logs": {"source": "not_exposed", "available": False},
                },
                "summary": {"cue_scan_completeness": "complete", "scanned_count": 12},
                "limits": {"max_cues_scanned": 1000, "sample_limit": 10},
                "warnings": [],
                "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_workspace_status("ws-1")
    payload = result.model_dump()

    assert payload["sections"]["warnings_summary"]["broken_count"] == 1
    assert payload["sections"]["logs"]["source"] == "not_exposed"


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
