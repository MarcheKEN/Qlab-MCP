from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import UnsafeWriteOperationError
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache


class FakeWriteClient:
    def __init__(self, config: QLabConfig, created_cue_id: str | None = None):
        self.config = config
        self.created_cue_id = created_cue_id
        self.created = False
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []

    def request(self, address: str, *args: Any, workspace_id: str | None = None) -> Any:
        self.requests.append((address, args, workspace_id))
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        if address == "/workspace/ws-1/new":
            self.created = True
            return SimpleNamespace(data={"uniqueID": self.created_cue_id}, status="ok")
        if self.created_cue_id and address.startswith(f"/workspace/ws-1/cue_id/{self.created_cue_id}/"):
            if address.endswith("/valuesForKeys"):
                name = "Created" if self.created else "Stale"
                return SimpleNamespace(
                    data={
                        "uniqueID": self.created_cue_id,
                        "number": "1",
                        "name": name,
                        "displayName": f"1 {name}",
                        "type": "Audio",
                        "armed": True,
                        "flagged": False,
                    },
                    status="ok",
                )
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


def test_check_write_readiness_resolves_workspace_when_gates_are_ready() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["checks"]["workspace_resolution"]["ok"] is True
    assert result["checks"]["edit_permission"]["status"] == "not_checked"
    assert client.requests == [("/workspaces", (), None)]


def test_create_cue_disabled_blocks_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Write mode is disabled"):
        reader.create_cue("ws-1", "audio", properties={"name": "Intro"}, dry_run=False)

    assert client.requests == []


def test_create_cue_dry_run_sends_no_mutating_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
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
        "audio",
        properties={"name": "Created", "number": "1", "armed": True, "continueMode": 1},
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "created"
    assert result["created_cue_id"] == cue_id
    assert result["verification"]["properties"]["name"] == "Created"
    assert "/workspace/ws-1/new" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/number" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/armed" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/continueMode" in addresses
    assert addresses.count(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys") >= 2
