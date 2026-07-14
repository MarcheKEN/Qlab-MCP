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
from qlab_mcp.errors import QLabReplyError
from qlab_mcp.server import (
    CHECK_CONNECTION_TIMEOUT,
    CREATE_CUE_TIMEOUT,
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NOISE_KEYS = {"description", "title"}
EXPECTED_FASTMCP_TOOL_CONTRACTS = {
    "qlab_check_connection": {
        "title": "Check QLab Connection",
        "timeout": CHECK_CONNECTION_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["diagnostics", "orientation", "qlab", "safe-read"],
        "input_schema_hash": "3c1421fec20d831fb3b0220cebf8f7e280875c06d85b4862946550d6f3717f57",
        "output_schema_hash": "f0c06b61b1bf2863b649b46d386b3b199ec81449446f1631fc8b759c8a35cc4c",
    },
    "qlab_check_write_readiness": {
        "title": "Check QLab Write Readiness",
        "timeout": WRITE_READINESS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["diagnostics", "qlab", "safe-read", "write-mode"],
        "input_schema_hash": "614f112549e5fdf796242506fdc6a63b4eadab384ea7c01460262a36efbde86c",
        "output_schema_hash": "42caaba0a23ffe174d0ffce943c35b0dae73ef36c1970eb4ee1cfd43fe83518f",
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
        "input_schema_hash": "a41f7916a34170006cd76c2cdce8590f2a93ee86f5f88fee91f4b3b836dac61b",
        "output_schema_hash": "80ffefed7d3cb667574e96746da8caeac0680eb5731915c0f186b84d1f73e9c3",
    },
    "qlab_get_cue_details": {
        "title": "Get QLab Cue Details",
        "timeout": CUE_DETAILS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["details", "diagnostics", "qlab", "safe-read"],
        "input_schema_hash": "21bab2f935cc8a4e971975a26a1ed10d82dc315374d3a0646a5607fc6e356f35",
        "output_schema_hash": "da79d543184f2edbba73a34704dde72e95dd60480905b788819f237692613acf",
    },
    "qlab_get_workspace_overview": {
        "title": "Get QLab Workspace Overview",
        "timeout": WORKSPACE_OVERVIEW_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["orientation", "qlab", "safe-read", "structure"],
        "input_schema_hash": "7aa799e3dbf7884bd6d2b259568e83894d00c17212b3e882b8563132b8e134b9",
        "output_schema_hash": "84484094570badc3b9d29073783b83e84c8e930d4ddeea4f26799b03f5ca8cc2",
    },
    "qlab_get_workspace_setting_details": {
        "title": "Get QLab Workspace Setting Details",
        "timeout": WORKSPACE_SETTING_DETAILS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["details", "patches", "qlab", "routing", "safe-read", "settings"],
        "input_schema_hash": "d105b796940efc5714fd42001a733042c391a419c3207623925736fd40b79a7c",
        "output_schema_hash": "e5c910941d0fd52c04cb8229a336b74b33fc1bb4ff96c921780e24dfed3ccba4",
    },
    "qlab_get_workspace_settings": {
        "title": "Get QLab Workspace Settings",
        "timeout": WORKSPACE_SETTINGS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["inventory", "patches", "qlab", "routing", "safe-read", "settings"],
        "input_schema_hash": "0d11116604c2a2cf5f3fb06ee689d5a1225e4cc58fbb9a43f241a15a83c8779d",
        "output_schema_hash": "b22ec5ba261a2cdb7bfc5d1423069c98961e6db0284b762ea9429188821c282d",
    },
    "qlab_get_workspace_status": {
        "title": "Get QLab Workspace Status",
        "timeout": WORKSPACE_STATUS_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["diagnostics", "qlab", "safe-read", "status", "timecode"],
        "input_schema_hash": "23f7bda8ae859d4f82418863e6fa3ff2a3ff6b4ab9fb56fd2a93066ea74c221c",
        "output_schema_hash": "9e61708ab098aec05fddf13e81b5e9751480ff0e478b7167728296407d39467c",
    },
    "qlab_query_cues": {
        "title": "Query QLab Cues",
        "timeout": QUERY_CUES_TIMEOUT,
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
        "tags": ["details", "inventory", "qlab", "query", "safe-read"],
        "input_schema_hash": "b2c0c530c681dc61407675be8fd3b30006dbd113edb2c5f26dbbfd2100fda8d0",
        "output_schema_hash": "4981dabcf1bfb2e82e83bbf29f9a2aed315ddbea4b0f5634c3ed4ad14dbe6060",
    },
    "qlab_update_cues": {
        "title": "Update QLab Cues (compatibility alias)",
        "timeout": UPDATE_CUES_TIMEOUT,
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "tags": ["batch-update", "cue-update", "deprecated-alias", "gated-write", "qlab", "write-mode"],
        "input_schema_hash": "d5202803e7b8b5bf7a07bc3693b27b3c86715258957fa8283284656cd6b280f6",
        "output_schema_hash": "853257a5192b69f070e159611c4aa2151bc998d905a789cca4b93eaea37b7e61",
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
        "input_schema_hash": "d5202803e7b8b5bf7a07bc3693b27b3c86715258957fa8283284656cd6b280f6",
        "output_schema_hash": "853257a5192b69f070e159611c4aa2151bc998d905a789cca4b93eaea37b7e61",
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
        "input_schema_hash": "fec08910a4b5a41d443c26ce52701c570879db1328dcddd09aec5fdb0c9c47f6",
        "output_schema_hash": "6077de39ee5fc10c022c1da360c5d3dda0b69bece497b2608f1f4af39f849a3c",
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
        "input_schema_hash": "8a629659d575ba24e69f9280ead889b593ea510ef24cd7b147d4ccfcb2a01701",
        "output_schema_hash": "9e0c11dd1fa9e530ca8d3c70737d9bd743c6ceac834487facb435d7d95a1ab8d",
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
    "qlab_edit_cues": ("Dry-run planning never sends mutating OSC", "High-risk profiles"),
    "qlab_update_cues": ("Compatibility alias", "qlab_edit_cues"),
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

    assert parsed.source.path == "src/qlab_mcp/server.py"
    assert parsed.source.entrypoint == "mcp"
    assert parsed.environment.project == Path(".")
    assert parsed.deployment.transport == "stdio"

    deployment_env = raw_config.get("deployment", {}).get("env", {})
    assert "QLAB_PASSCODE" not in deployment_env
    assert "QLAB_ENABLE_WRITE" not in deployment_env
    assert "QLAB_WRITE_DRY_RUN_DEFAULT" not in deployment_env


def test_fastmcp_tool_contract_snapshot_matches_current_public_surface() -> None:
    assert asyncio.run(_tool_contract_snapshot()) == EXPECTED_FASTMCP_TOOL_CONTRACTS


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


def test_delete_cues_fastmcp_schema_limits_and_nested_uuid_model() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_delete_cues")

    schema = asyncio.run(get_tool_schema())
    cue_ids = schema["properties"]["cue_ids"]

    assert cue_ids["minItems"] == 1
    assert cue_ids["maxItems"] == 10
    assert cue_ids["items"]["format"] == "uuid"
    assert "confirm_token" in schema["properties"]


def test_delete_cues_fastmcp_returns_structured_plan(monkeypatch) -> None:
    class FakeReader:
        def delete_cues(self, workspace_id, cue_ids, dry_run, confirm_token):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_ids == ["11111111-1111-4111-8111-111111111111"]
            assert dry_run is True
            assert confirm_token is None
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
    write_tools = {"qlab_create_cue", "qlab_edit_cues", "qlab_update_cues", "qlab_move_cues", "qlab_delete_cues"}
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


def test_update_cues_fastmcp_schema_keeps_batch_contract() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    update_schema = tools["qlab_update_cues"].inputSchema
    update_properties = update_schema["properties"]
    update_items = update_properties["updates"]["items"]
    update_item_properties = update_items["properties"]
    update_output = tools["qlab_update_cues"].outputSchema

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

    class FakeReader:
        def edit_cues(self, workspace_id, updates, dry_run):
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

    assert planned[0]["confirm_token"].startswith("confirm:fadeBasic:v1:")
    assert result.structured_content["results"][0]["executed_operations"] == []


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
        "qlab_edit_cues",
        "qlab_update_cues",
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
    ]
    assert "dry_run" in create.inputSchema["properties"]
    assert "workspace_id" in create.inputSchema["required"]
    assert "cue_type" in create.inputSchema["required"]
    assert create.outputSchema["properties"]["status"]["enum"] == [
        "dry_run",
        "created",
        "verification_failed",
        "workspace_not_found",
        "workspace_ambiguous",
        "workspace_unavailable",
    ]

    edit = tools["qlab_edit_cues"]
    assert edit.title == "Edit QLab Cues"
    assert "Dry-run planning" in edit.description
    assert "batch-edit" in edit.meta["fastmcp"]["tags"]

    update = tools["qlab_update_cues"]
    assert update.title == "Update QLab Cues (compatibility alias)"
    assert "Dry-run planning" in update.description
    assert "Compatibility alias" in update.description
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
    assert "enum" not in update_item["profile"]
    assert "updated_with_confirmed_timeouts" in update.outputSchema["properties"]["status"]["enum"]
    assert "workspace_not_found" in update.outputSchema["properties"]["status"]["enum"]
    assert "workspace_ambiguous" in update.outputSchema["properties"]["status"]["enum"]
    assert "workspace_unavailable" in update.outputSchema["properties"]["status"]["enum"]
    assert "per cue item" in update.outputSchema["properties"]["timeout_confirmed_count"]["description"]
    result_item = update.outputSchema["properties"]["results"]["items"]["properties"]
    assert "dry_run_preflight_failed" in result_item["status"]["enum"]
    assert "QLAB_UPDATE_DEBUG" in result_item["debug"]["description"]

    delete = tools["qlab_delete_cues"]
    assert delete.title == "Delete QLab Cues"
    assert "explicit leaf cues" in delete.description
    assert delete.annotations.readOnlyHint is False
    assert delete.annotations.destructiveHint is True
    assert delete.annotations.idempotentHint is False
    assert delete.inputSchema["properties"]["cue_ids"]["minItems"] == 1
    assert delete.inputSchema["properties"]["cue_ids"]["maxItems"] == 10
    assert delete.inputSchema["properties"]["cue_ids"]["items"]["format"] == "uuid"
    assert "confirm:deleteCues:v1:" in delete.inputSchema["properties"]["confirm_token"]["description"]
    assert "verification_failed" in delete.outputSchema["properties"]["status"]["enum"]


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
                "qlab_edit_cues",
                "qlab_update_cues",
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
        "qlab_edit_cues": UPDATE_CUES_TIMEOUT,
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
    assert payload["error_code"] == "validation_failed"
    assert "cue_ref list can include at most 50 cues" in payload["message"]
    assert payload["requested_count"] == 51
    assert payload["failed_count"] == 51


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
