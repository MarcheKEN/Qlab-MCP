from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache


class FakeWriteClient:
    def __init__(
        self,
        config: QLabConfig,
        created_cue_id: str | None = None,
        existing_cue_id: str | None = None,
        cue_values: dict[str, Any] | None = None,
        connect_data: str = "ok:view|edit",
        connect_status: str = "ok",
        show_mode_data: Any = False,
        show_mode_status: str = "ok",
        fail_set_property: str | None = None,
        timeout_set_property: str | None = None,
        missing_cue: bool = False,
    ):
        self.config = config
        self.created_cue_id = created_cue_id
        self.existing_cue_id = existing_cue_id
        self.cue_values = cue_values or {
            "uniqueID": existing_cue_id or created_cue_id,
            "number": "1",
            "name": "Stale",
            "displayName": "1 Stale",
            "type": "Memo",
            "armed": True,
            "flagged": False,
        }
        self.connect_data = connect_data
        self.connect_status = connect_status
        self.show_mode_data = show_mode_data
        self.show_mode_status = show_mode_status
        self.fail_set_property = fail_set_property
        self.timeout_set_property = timeout_set_property
        self.missing_cue = missing_cue
        self.created = False
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []

    def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
        self.requests.append((address, args, workspace_id))
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        if address == "/workspace/ws-1/connect":
            return SimpleNamespace(data=self.connect_data, status=self.connect_status)
        if address == "/workspace/ws-1/showMode":
            return SimpleNamespace(data=self.show_mode_data, status=self.show_mode_status)
        if address == "/workspace/ws-1/new":
            self.created = True
            self.cue_values["uniqueID"] = self.created_cue_id
            return SimpleNamespace(data={"uniqueID": self.created_cue_id}, status="ok")
        known_ids = {value for value in (self.created_cue_id, self.existing_cue_id) if value}
        if any(address.startswith(f"/workspace/ws-1/cue_id/{cue_id}/") for cue_id in known_ids) or address.startswith(
            "/workspace/ws-1/cue/1/"
        ):
            if self.missing_cue:
                raise QLabReplyError("error", "No cue found", address)
            if address.endswith("/valuesForKeys"):
                if self.created and self.created_cue_id:
                    self.cue_values["name"] = self.cue_values.get("name", "Created")
                return SimpleNamespace(
                    data=dict(self.cue_values),
                    status="ok",
                )
            property_name = address.rsplit("/", 1)[1]
            if property_name == self.fail_set_property:
                raise QLabReplyError("error", f"Failed setting {property_name}", address)
            self.cue_values[property_name] = args[0] if args else None
            if property_name == self.timeout_set_property:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected fake write request: {address}")


def test_write_config_defaults_to_disabled_and_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QLAB_ENABLE_WRITE", raising=False)
    monkeypatch.delenv("QLAB_WRITE_DRY_RUN_DEFAULT", raising=False)

    config = QLabConfig.from_env()

    assert config.enable_write is False
    assert config.write_dry_run_default is True


def test_check_write_readiness_reports_disabled_without_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "write_disabled"
    assert result["blockers"] == ["write_disabled"]
    assert result["passcode_configured"] is True
    assert result["capabilities"]["create_cue"]["dry_run_default"] is True
    assert client.requests == []


def test_check_write_readiness_requires_passcode_without_leaking_secret() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "passcode_missing"
    assert result["blockers"] == ["passcode_missing"]
    assert "passcode" in result["checks"]
    assert "secret" not in str(result)
    assert client.requests == []


def test_check_write_readiness_requires_edit_confirmed_by_connect() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["checks"]["workspace_resolution"]["ok"] is True
    assert result["checks"]["edit_permission"]["status"] == "confirmed"
    assert result["checks"]["connect"]["scopes"] == ["view", "edit"]
    assert result["checks"]["show_mode"]["mode"] == "edit"
    assert client.requests == [
        ("/workspaces", (), None),
        ("/workspace/ws-1/connect", ("server-pass",), None),
        ("/workspace/ws-1/showMode", (), "ws-1"),
    ]


@pytest.mark.parametrize("connect_data", ["ok:view", "ok:view|control", "ok:admin"])
def test_check_write_readiness_blocks_without_edit_scope(connect_data: str) -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data=connect_data)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "edit_not_confirmed"
    assert result["blockers"] == ["edit_not_confirmed"]
    assert result["checks"]["edit_permission"]["ok"] is False


def test_check_write_readiness_blocks_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "workspace_in_show_mode"
    assert result["blockers"] == ["workspace_in_show_mode"]
    assert result["checks"]["show_mode"]["mode"] == "show"


def test_check_write_readiness_blocks_unknown_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data="nope")
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "show_mode_unknown"
    assert result["blockers"] == ["show_mode_unknown"]
    assert result["checks"]["show_mode"]["status"] == "unexpected_data"


def test_create_cue_disabled_blocks_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Write mode is disabled"):
        reader.create_cue("ws-1", "audio", properties={"name": "Intro"}, dry_run=False)

    assert client.requests == []


def test_create_cue_dry_run_sends_no_mutating_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.create_cue(
        "ws-1",
        "audio",
        properties={"name": "Intro", "continueMode": "auto_follow"},
        dry_run=True,
        after_cue_id="cue-before",
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["cue_type"] == "Audio"
    assert result["properties"]["continueMode"] == 2
    assert result["placement"]["after_cue_id"] == "cue-before"
    assert [operation["operation"] for operation in result["planned_operations"]] == [
        "new",
        "move_after",
        "set_property",
        "set_property",
        "verify",
    ]
    assert client.requests == []


def test_create_cue_rejects_unallowlisted_cue_type_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
        reader.create_cue("ws-1", "script", dry_run=True)

    with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
        reader.create_cue("ws-1", "video", dry_run=True)

    assert client.requests == []


def test_create_cue_rejects_unallowlisted_properties_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
        reader.create_cue("ws-1", "audio", properties={"fileTarget": "/tmp/secret.wav"}, dry_run=True)

    assert client.requests == []


def test_create_cue_rejects_invalid_property_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="duration must be a non-negative number"):
        reader.create_cue("ws-1", "audio", properties={"duration": -1}, dry_run=True)

    assert client.requests == []


def test_create_cue_real_with_after_cue_id_fails_safely_without_passcode_leak() -> None:
    secret = "server-super-secret"
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode=secret))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError) as exc_info:
        reader.create_cue("ws-1", "audio", dry_run=False, after_cue_id="cue-before")

    message = str(exc_info.value)
    assert "after_cue_id" in message
    assert secret not in message
    assert client.requests == []


def test_create_cue_real_blocks_without_confirmed_edit() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data="ok:view|control")
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="edit permission"):
        reader.create_cue("ws-1", "memo", dry_run=False)

    assert [request[0] for request in client.requests] == ["/workspaces", "/workspace/ws-1/connect"]


def test_create_cue_real_blocks_in_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Show Mode"):
        reader.create_cue("ws-1", "memo", dry_run=False)

    assert [request[0] for request in client.requests] == [
        "/workspaces",
        "/workspace/ws-1/connect",
        "/workspace/ws-1/showMode",
    ]
    assert client.requests[-1][2] == "ws-1"


def test_create_cue_real_creates_applies_properties_and_verifies_fresh_details() -> None:
    shared_read_cache().clear()
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        created_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    stale = reader.get_cue_details("ws-1", cue_id, "auto")
    assert stale["properties"]["name"] == "Stale"

    result = reader.create_cue(
        "ws-1",
        "memo",
        properties={"name": "Created", "number": "1", "armed": True, "continueMode": 1},
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "created"
    assert result["cue_type"] == "Memo"
    assert result["created_cue_id"] == cue_id
    assert result["verification"]["properties"]["name"] == "Created"
    assert "/workspace/ws-1/connect" in addresses
    assert "/workspace/ws-1/showMode" in addresses
    assert next(request[2] for request in client.requests if request[0] == "/workspace/ws-1/showMode") == "ws-1"
    assert "/workspace/ws-1/new" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/number" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/armed" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/continueMode" in addresses
    assert addresses.count(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys") >= 2


def test_update_cue_dry_run_sends_no_mutating_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=True)

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["before"]["name"] == "Stale"
    assert result["diff"]["name"] == {"before": "Stale", "requested": "New"}
    assert [operation["operation"] for operation in result["planned_operations"]] == [
        "read_before",
        "set_property",
        "set_property",
        "verify",
    ]
    assert [request[0] for request in client.requests] == [f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys"]


def test_update_cue_rejects_ambiguous_refs_and_bad_properties_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="concrete cue"):
        reader.update_cue("ws-1", "selected", {"name": "Nope"}, dry_run=True)

    with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
        reader.update_cue("ws-1", "1", {"fileTarget": "/tmp/nope.wav"}, dry_run=True)

    assert client.requests == []


def test_update_cue_real_blocks_missing_cue_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        missing_cue=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New"}, dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "cue_not_found"
    assert result["executed_operations"] == []
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" not in [request[0] for request in client.requests]


def test_update_cue_real_blocks_when_before_has_no_unique_id() -> None:
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=None,
        cue_values={"number": "1", "name": "Stale", "type": "Memo"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", "1", {"name": "New"}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "cue_not_found"
    assert result["executed_operations"] == []
    assert "/workspace/ws-1/cue/1/name" not in addresses


def test_update_cue_real_updates_and_verifies_fresh_details() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["before"]["name"] == "Stale"
    assert result["after"]["name"] == "New"
    assert result["diff"]["armed"] == {"before": True, "requested": False, "after": False}
    assert result["verification"]["properties"]["name"] == "New"
    assert "/workspace/ws-1/connect" in addresses
    assert "/workspace/ws-1/showMode" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/armed" in addresses


def test_update_cue_real_accepts_setter_timeout_when_after_read_confirms_value() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        timeout_set_property="flagged",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"flagged": True}, dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["after"]["flagged"] is True
    assert result["diff"]["flagged"] == {"before": False, "requested": True, "after": True}
    assert result["errors"] is None
    assert result["executed_operations"][0]["status"] == "timeout_pending_verification"
    assert result["warnings"] == ["One or more setters did not reply, but fresh after-read confirmed requested values."]


def test_update_cue_real_resolves_number_to_unique_id_for_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", "1", {"name": "New"}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    planned_setters = [
        operation["address"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert "/workspace/ws-1/cue/1/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert "/workspace/ws-1/cue/1/name" not in addresses
    assert planned_setters == [f"/workspace/ws-1/cue_id/{cue_id}/name"]


def test_update_cue_real_blocks_in_show_mode() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        show_mode_data=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Show Mode"):
        reader.update_cue("ws-1", cue_id, {"name": "New"}, dry_run=False)

    assert [request[0] for request in client.requests] == [
        "/workspaces",
        "/workspace/ws-1/connect",
        "/workspace/ws-1/showMode",
    ]


def test_update_cue_real_reports_partial_failure() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        fail_set_property="armed",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert [operation["property"] for operation in result["executed_operations"]] == ["name"]
    assert "armed" in result["errors"]
    assert result["after"]["name"] == "New"
