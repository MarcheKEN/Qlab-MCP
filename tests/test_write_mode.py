from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache
from qlab_mcp.write.registry import UPDATE_PROFILE_NAMES, profile_catalog


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
            property_name = self._property_name_from_address(address, known_ids)
            if property_name == self.fail_set_property:
                raise QLabReplyError("error", f"Failed setting {property_name}", address)
            self.cue_values[property_name] = args[0] if args else None
            if property_name == self.timeout_set_property:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected fake write request: {address}")

    @staticmethod
    def _property_name_from_address(address: str, known_ids: set[str]) -> str:
        for cue_id in known_ids:
            prefix = f"/workspace/ws-1/cue_id/{cue_id}/"
            if address.startswith(prefix):
                return address.removeprefix(prefix)
        return address.removeprefix("/workspace/ws-1/cue/1/")


def test_update_registry_covers_all_profiles_and_planned_only_risk() -> None:
    catalog = profile_catalog()

    assert set(UPDATE_PROFILE_NAMES) == {
        "common",
        "memo_basic",
        "wait_basic",
        "group_basic",
        "audio_basic",
        "mic_basic",
        "video_basic",
        "camera_basic",
        "text_basic",
        "light_basic",
        "fade_basic",
        "network_basic",
        "midi_basic",
        "midi_file_basic",
        "timecode_basic",
        "target_basic",
        "reset_basic",
        "devamp_basic",
        "script_basic",
    }
    for profile in catalog.values():
        assert "properties" in profile
        assert "risk_tier" in profile
        assert "real_write_enabled" in profile

    assert catalog["audio_basic"]["properties"]["level"]["planned_only_reason"]
    assert catalog["audio_basic"]["properties"]["fileTarget"]["planned_only_reason"]
    assert catalog["group_basic"]["properties"]["moveCartCue"]["planned_only_reason"]
    assert catalog["mic_basic"]["real_write_enabled"] is True
    assert catalog["mic_basic"]["properties"]["channels"]["real_write_enabled"] is True
    assert catalog["video_basic"]["real_write_enabled"] is True
    assert catalog["video_basic"]["properties"]["translation/x"]["real_write_enabled"] is True
    assert catalog["video_basic"]["properties"]["crop"]["planned_only_reason"]
    assert catalog["camera_basic"]["real_write_enabled"] is True
    assert catalog["midi_file_basic"]["properties"]["rate"]["real_write_enabled"] is True
    assert catalog["network_basic"]["properties"]["protocol"]["planned_only_reason"]
    assert catalog["network_basic"]["real_write_enabled"] is True
    assert catalog["midi_basic"]["properties"]["note"]["path"] == "byte1"
    assert catalog["midi_basic"]["real_write_enabled"] is True
    assert catalog["timecode_basic"]["real_write_enabled"] is True
    assert catalog["timecode_basic"]["properties"]["timecodeFrameRate"]["path"] == "framerate"
    assert catalog["target_basic"]["properties"]["cueTargetID"]["planned_only_reason"]
    assert catalog["light_basic"]["properties"]["lightCommandText"]["planned_only_reason"]
    assert catalog["fade_basic"]["properties"]["stopTargetWhenDone"]["planned_only_reason"]
    assert catalog["script_basic"]["real_write_enabled"] is True
    assert catalog["script_basic"]["properties"]["scriptSource"]["planned_only_reason"] == "script_execution_risk"


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


def test_update_cue_audio_basic_dry_run_allows_small_audio_profile() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "rate": 1.0,
            "startTime": 0,
            "endTime": 10,
            "playCount": 1,
            "infiniteLoop": False,
            "preservePitch": True,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"rate": 1.25, "startTime": 1, "endTime": 9, "preservePitch": False},
        dry_run=True,
        profile="audio_basic",
    )

    planned_setters = [
        operation["property"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["profile"] == "audio_basic"
    assert planned_setters == ["rate", "startTime", "endTime", "preservePitch"]
    assert result["executed_operations"] == []


def test_update_cue_audio_basic_real_updates_and_verifies() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "rate": 1.0,
            "startTime": 0,
            "endTime": 10,
            "playCount": 1,
            "infiniteLoop": False,
            "preservePitch": True,
        },
        timeout_set_property="rate",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"rate": 1.25}, dry_run=False, profile="audio_basic")

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == "audio_basic"
    assert result["before"]["rate"] == 1.0
    assert result["after"]["rate"] == 1.25
    assert result["errors"] is None
    assert result["executed_operations"][0]["status"] == "timeout_pending_verification"


def test_update_cue_audio_basic_rejects_invalid_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="rate"):
        reader.update_cue("ws-1", "1", {"rate": 0.01}, dry_run=True, profile="audio_basic")

    with pytest.raises(UnsafeWriteOperationError, match="endTime"):
        reader.update_cue(
            "ws-1",
            "1",
            {"startTime": 5, "endTime": 5},
            dry_run=True,
            profile="audio_basic",
        )

    with pytest.raises(UnsafeWriteOperationError, match="infiniteLoop"):
        reader.update_cue(
            "ws-1",
            "1",
            {"infiniteLoop": True, "playCount": 2},
            dry_run=True,
            profile="audio_basic",
        )

    assert client.requests == []


def test_update_cue_audio_basic_rejects_non_audio_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "rate": 1.0},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Audio cue"):
        reader.update_cue("ws-1", cue_id, {"rate": 1.2}, dry_run=False, profile="audio_basic")

    addresses = [request[0] for request in client.requests]
    assert f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/rate" not in addresses


def test_update_cue_text_basic_dry_run_allows_small_text_profile() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text": "Old title",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {
            "text": "New title",
            "fixedWidth": 640,
            "text/format/alignment": "center",
            "text/format/fontName": "Courier New",
            "text/format/fontSize": 56,
        },
        dry_run=True,
        profile="text_basic",
    )

    planned_setters = [
        operation["property"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["profile"] == "text_basic"
    assert planned_setters == [
        "text",
        "fixedWidth",
        "text/format/alignment",
        "text/format/fontName",
        "text/format/fontSize",
    ]
    assert result["executed_operations"] == []


def test_update_cue_text_basic_real_updates_and_verifies_slash_properties() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text": "Old title",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
        },
        timeout_set_property="text/format/fontSize",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"text/format/alignment": "right", "text/format/fontSize": 60},
        dry_run=False,
        profile="text_basic",
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == "text_basic"
    assert result["after"]["text/format/alignment"] == "right"
    assert result["after"]["text/format/fontSize"] == 60
    assert result["errors"] is None
    assert result["executed_operations"][1]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/text/format/fontSize"
    assert result["executed_operations"][1]["status"] == "timeout_pending_verification"


def test_update_cue_text_basic_rejects_invalid_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="alignment"):
        reader.update_cue("ws-1", "1", {"text/format/alignment": "middle"}, dry_run=True, profile="text_basic")

    with pytest.raises(UnsafeWriteOperationError, match="fontSize"):
        reader.update_cue("ws-1", "1", {"text/format/fontSize": 0}, dry_run=True, profile="text_basic")

    with pytest.raises(UnsafeWriteOperationError, match="fontName"):
        reader.update_cue("ws-1", "1", {"text/format/fontName": ""}, dry_run=True, profile="text_basic")

    assert client.requests == []


def test_update_cue_text_basic_rejects_non_text_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "text": "Not a Text cue"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Text cue"):
        reader.update_cue("ws-1", cue_id, {"text": "New text"}, dry_run=False, profile="text_basic")

    addresses = [request[0] for request in client.requests]
    assert f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/text" not in addresses


def test_update_cue_operations_dry_run_builds_structured_osc_paths() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {
                "property": "level",
                "args": {"inChannel": 1, "outChannel": 2, "decibel": -6},
                "mode": "live",
            }
        ],
        dry_run=True,
        profile="audio_basic",
    )

    setters = [operation for operation in result["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert result["properties"] == {}
    assert setters == [
        {
            "operation": "set_property",
            "property": "level",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/level/1/2/live",
            "args": [-6],
            "mode": "live",
            "risk_tier": "high",
            "real_write_enabled": False,
            "planned_only_reason": "audio_levels_can_affect_live_output",
        }
    ]
    assert result["executed_operations"] == []


def test_update_cue_operations_support_video_text_and_midi_dry_run_shapes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"

    video_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    video_result = video.update_cue(
        "ws-1",
        cue_id,
        operations=[{"property": "crop", "args": {"top": 1, "bottom": 2, "left": 3, "right": 4}}],
        dry_run=True,
        profile="video_basic",
    )

    text_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Text"},
    )
    text = QLabReader(text_client)  # type: ignore[arg-type]
    text_result = text.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {
                "property": "text/format/color",
                "args": {"red": 255, "green": 128, "blue": 0, "alpha": 1},
            }
        ],
        dry_run=True,
        profile="text_basic",
    )

    midi_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "MIDI"},
    )
    midi = QLabReader(midi_client)  # type: ignore[arg-type]
    midi_result = midi.update_cue(
        "ws-1",
        cue_id,
        properties={"channel": 1, "byte1": 64},
        dry_run=True,
        profile="midi_basic",
    )

    video_setter = [op for op in video_result["planned_operations"] if op["operation"] == "set_property"][0]
    text_setter = [op for op in text_result["planned_operations"] if op["operation"] == "set_property"][0]
    midi_setters = [op["address"] for op in midi_result["planned_operations"] if op["operation"] == "set_property"]
    assert video_setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/crop"
    assert video_setter["args"] == [1, 2, 3, 4]
    assert text_setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/text/format/color"
    assert text_setter["args"] == [255, 128, 0, 1]
    assert midi_setters == [f"/workspace/ws-1/cue_id/{cue_id}/channel", f"/workspace/ws-1/cue_id/{cue_id}/byte1"]


def test_update_cue_real_blocks_dry_run_only_profiles_and_properties_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"

    video_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        video.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "crop", "args": {"top": 1, "bottom": 2, "left": 3, "right": 4}}],
            dry_run=False,
            profile="video_basic",
        )
    assert video_client.requests == []

    audio_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    audio = QLabReader(audio_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        audio.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}],
            dry_run=False,
            profile="audio_basic",
        )
    assert audio_client.requests == []

    for profile, cue_type, properties in (
        ("light_basic", "Light", {"lightCommandText": "1 thru 5 @ 80"}),
        ("network_basic", "Network", {"message": "/eos/cue/1/fire"}),
        ("midi_basic", "MIDI", {"note": 64}),
        ("script_basic", "Script", {"scriptSource": "display dialog \"blocked\""}),
    ):
        client = FakeWriteClient(
            QLabConfig(enable_write=True, passcode="server-pass"),
            existing_cue_id=cue_id,
            cue_values={"uniqueID": cue_id, "type": cue_type},
        )
        reader = QLabReader(client)  # type: ignore[arg-type]
        with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
            reader.update_cue("ws-1", cue_id, properties, dry_run=False, profile=profile)
        assert client.requests == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "properties"),
    [
        ("mic_basic", "Mic", {"channels": 2, "channelOffset": 1}),
        ("video_basic", "Video", {"translation/x": 100, "opacity": 80, "cropTop": 5}),
        ("camera_basic", "Camera", {"scale/x": 1.2, "rotation": 15, "channels": 2}),
        ("midi_file_basic", "MIDI File", {"rate": 1.1, "startTime": 0, "endTime": 8, "playCount": 2}),
        ("timecode_basic", "Timecode", {"timecodeString": "01:00:00:00", "timecodeFormat": 1}),
        ("target_basic", "Start", {"name": "Start cue renamed"}),
        ("reset_basic", "Reset", {"name": "Reset cue renamed"}),
        ("devamp_basic", "Devamp", {"name": "Devamp cue renamed"}),
        ("light_basic", "Light", {"name": "Light cue renamed"}),
        ("fade_basic", "Fade", {"name": "Fade cue renamed"}),
        ("network_basic", "Network", {"name": "Network cue renamed"}),
        ("midi_basic", "MIDI", {"name": "MIDI cue renamed"}),
        ("script_basic", "Script", {"name": "Script cue renamed"}),
    ],
)
def test_update_cue_real_updates_new_safe_profiles(profile: str, cue_type: str, properties: dict[str, Any]) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values = {
        "uniqueID": cue_id,
        "type": cue_type,
        "name": "Stale",
        "channels": 1,
        "channelOffset": 0,
        "translation/x": 0,
        "opacity": 100,
        "cropTop": 0,
        "scale/x": 1,
        "rotation": 0,
        "rate": 1,
        "startTime": 0,
        "endTime": 10,
        "playCount": 1,
        "timecodeString": "00:00:00:00",
        "timecodeFormat": 0,
    }
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, properties, dry_run=False, profile=profile)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == profile
    for key, value in properties.items():
        assert result["after"][key] == value
        assert f"/workspace/ws-1/cue_id/{cue_id}/{key}" in [request[0] for request in client.requests]


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
