"""Focused checks for root Cue List and Cue Cart write tools."""

from types import SimpleNamespace
import asyncio
from uuid import UUID

from pydantic import ValidationError

from qlab_mcp.models import CueListEditProperties
from qlab_mcp.errors import UnsafeWriteOperationError
from qlab_mcp.write import cue_lists as module
from qlab_mcp.write.registry import validate_update_profile_for_cue


class RootWriteReader:
    workspace_id = str(UUID(int=100))

    def __init__(self):
        self.roots = []
        self.sent = []
        self.client = SimpleNamespace(
            config=SimpleNamespace(write_dry_run_default=True),
            request=self.request,
        )

    def _resolve_workspace_id_strict(self, workspace_id):
        assert workspace_id == self.workspace_id
        return workspace_id

    def get_cue_lists(self, *args, **kwargs):
        assert kwargs["cacheable"] is False
        return {"cue_lists": list(self.roots)}

    def get_cue_children(self, workspace, cue_id, **kwargs):
        return {"children": []}

    def read_cue_values(self, workspace, cue_id, keys, **kwargs):
        root = next(root for root in self.roots if root["uniqueID"] == cue_id)
        return {"values": {**root, "isBroken": False, "isWarning": False}}

    def get_running_cues(self, *args, **kwargs):
        return {"running_cues": []}

    def request(self, address, cue_type):
        self.sent.append((address, cue_type))
        cue_id = str(UUID(int=len(self.roots) + 1))
        root = {"uniqueID": cue_id, "type": "Cue List" if cue_type == "cuelist" else "Cue Cart"}
        self.roots.append(root)
        return SimpleNamespace(status="ok", data=cue_id)


def test_create_mixed_root_batch(monkeypatch):
    reader = RootWriteReader()
    monkeypatch.setattr(module, "ensure_write_ready", lambda *args: None)
    plan = module.create_cue_lists(
        reader, reader.workspace_id, ["cue_list", "cue_cart"], dry_run=True
    )
    assert plan["confirm_token"].startswith("confirm:createCueLists:v1:")

    result = module.create_cue_lists(
        reader,
        reader.workspace_id,
        ["cue_list", "cue_cart"],
        dry_run=False,
        confirm_token=plan["confirm_token"],
    )

    assert result["ok"] is True
    assert result["created_count"] == 2
    assert result["batch_verified"] is True
    assert result["pending_indices"] == []
    assert [root["type"] for root in reader.roots] == ["Cue List", "Cue Cart"]
    assert [cue_type for _, cue_type in reader.sent] == ["cuelist", "cart"]


def test_edit_maps_typed_fields_to_signed_motor(monkeypatch):
    reader = RootWriteReader()
    reader.roots = [{"uniqueID": str(UUID(int=1)).upper(), "type": "Cue List"}]
    calls = []
    monkeypatch.setattr(module, "edit_control_cues", lambda *args, **kwargs: calls.append((args, kwargs)) or {"ok": True})

    result = module.edit_cue_lists(
        reader,
        reader.workspace_id,
        [{"cue_list_id": str(UUID(int=1)), "properties": {
            "name": "Main", "timecode_sync_mode": "ltc", "smpte_format": "25_fps"
        }}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert calls[0][1] == {"_family": "cue_list"}
    assert calls[0][0][2] == [{
        "cue_id": str(UUID(int=1)).upper(),
        "properties": {"name": "Main", "timecodeSyncMode": 1, "timecodeSMPTEFormat": 1},
        "confirm_gates": [],
    }]



def test_create_rejects_stale_structure_and_transport_failure_is_uncertain(monkeypatch):
    reader = RootWriteReader()
    monkeypatch.setattr(module, "ensure_write_ready", lambda *args: None)
    plan = module.create_cue_lists(reader, reader.workspace_id, ["cue_list"], dry_run=True)
    reader.roots.append({"uniqueID": str(UUID(int=10)), "type": "Cue List"})
    stale = module.create_cue_lists(reader, reader.workspace_id, ["cue_list"], dry_run=False,
                                    confirm_token=plan["confirm_token"])
    assert stale["status"] == "preflight_failed"
    assert reader.sent == []

    plan = module.create_cue_lists(reader, reader.workspace_id, ["cue_cart"], dry_run=True)
    reader.client.request = lambda *args: (_ for _ in ()).throw(TimeoutError("lost reply"))
    failed = module.create_cue_lists(reader, reader.workspace_id, ["cue_cart"], dry_run=False,
                                     confirm_token=plan["confirm_token"])
    assert failed["created_count"] == 0
    assert failed["uncertain_indices"] == [0]
    assert failed["pending_indices"] == []
    assert failed["results"][0]["status"] == "verification_failed"


def test_create_limits_and_single_use_token(monkeypatch):
    reader = RootWriteReader()
    monkeypatch.setattr(module, "ensure_write_ready", lambda *args: None)
    plan = module.create_cue_lists(reader, reader.workspace_id, ["cue_list"], dry_run=True)
    result = module.create_cue_lists(reader, reader.workspace_id, ["cue_list"], dry_run=False,
                                     confirm_token=plan["confirm_token"])
    assert result["ok"] is True
    reused = module.create_cue_lists(reader, reader.workspace_id, ["cue_list"], dry_run=False,
                                     confirm_token=plan["confirm_token"])
    assert "already been consumed" in reused["errors"]["confirm_token"]
    assert len(reader.sent) == 1

    module.create_cue_lists(reader, reader.workspace_id, ["cue_list"] * 50, dry_run=True)
    try:
        module.create_cue_lists(reader, reader.workspace_id, ["cue_list"] * 51, dry_run=True)
    except UnsafeWriteOperationError:
        pass
    else:
        raise AssertionError("more than 50 root creations must be rejected")


def test_typed_edit_bounds_are_strict():
    CueListEditProperties(freewheel_seconds=2, lookback_seconds=0)
    try:
        CueListEditProperties(freewheel_seconds=2.1)
    except ValidationError:
        pass
    else:
        raise AssertionError("freewheel_seconds above two must be rejected")


def test_qlab_cart_type_uses_group_basic_profile():
    validate_update_profile_for_cue("group_basic", {"type": "Cart"})


def test_public_tool_schemas(monkeypatch):
    from fastmcp import Client
    import qlab_mcp.server as server

    reader = RootWriteReader()
    reader.create_cue_lists = lambda **kwargs: module.create_cue_lists(reader, **kwargs)
    reader.edit_cue_lists = lambda **kwargs: module.edit_cue_lists(reader, **kwargs)
    reader.edit_cues = lambda **kwargs: {
        "ok": True, "status": "dry_run", "workspace_id": reader.workspace_id,
        "dry_run": True, "requested_count": 1, "planned_count": 1,
        "updated_count": 0, "failed_count": 0, "timeout_confirmed_count": 0,
        "results": [], "warnings": [], "message": "planned",
    }
    monkeypatch.setattr(server, "_reader", lambda: reader)

    async def calls():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert len(tools) == 83
            create = tools["qlab_create_cue_lists"].inputSchema["properties"]["container_types"]
            assert (create["minItems"], create["maxItems"]) == (1, 50)
            edit = tools["qlab_edit_cue_lists"].inputSchema["properties"]["updates"]
            assert (edit["minItems"], edit["maxItems"]) == (1, 50)
            assert edit["items"]["additionalProperties"] is False

    asyncio.run(calls())
