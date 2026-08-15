from __future__ import annotations

import math
import struct
from typing import get_args

import pytest
from pydantic import ValidationError

from qlab_mcp.models import (
    GeneralSettingsEditInput,
    GeneralSettingsEditResult,
    GeneralSettingsOperation,
    GeneralSettingsWriteStatus,
)
from qlab_mcp.settings.write_operations import WorkspaceSettingsWriteMixin
from qlab_mcp.settings.write_registry import MIN_GO_TIME_SPEC, get_workspace_settings_write_spec


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"


def test_general_settings_edit_input_schema_accepts_min_go_time_contract() -> None:
    model = GeneralSettingsEditInput(
        workspace_id=WORKSPACE_ID,
        operation="minGoTime",
        value=0.4,
        dry_run=True,
        confirm_token="confirm:workspaceSettings:v1:test",
    )

    assert str(model.workspace_id) == WORKSPACE_ID
    assert model.operation == "minGoTime"
    assert model.value == pytest.approx(0.4)
    assert model.dry_run is True
    assert model.confirm_token == "confirm:workspaceSettings:v1:test"


@pytest.mark.parametrize("workspace_id", ["ws-1", "selected", "11111111-1111-4111-8111-11111111111z"])
def test_general_settings_edit_input_validation_rejects_non_uuid_workspace_ids(workspace_id: str) -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=workspace_id, operation="minGoTime", value=0.4)


@pytest.mark.parametrize(
    "workspace_id",
    [
        "11111111111141118111111111111111",
        "{11111111-1111-4111-8111-111111111111}",
        "urn:uuid:11111111-1111-4111-8111-111111111111",
    ],
)
def test_general_settings_edit_input_validation_rejects_non_canonical_uuid_forms(workspace_id: str) -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=workspace_id, operation="minGoTime", value=0.4)


@pytest.mark.parametrize("value", [True, False, "0.4", None])
def test_general_settings_edit_input_validation_rejects_non_numeric_values(value: object) -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=WORKSPACE_ID, operation="minGoTime", value=value)


def test_general_settings_edit_input_rejects_deferred_operations() -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=WORKSPACE_ID, operation="selectionIsPlayhead", value=0.4)


@pytest.mark.parametrize("value", [-0.1, math.inf, -math.inf, math.nan])
def test_general_settings_edit_input_validation_rejects_invalid_numeric_values(value: float) -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=WORKSPACE_ID, operation="minGoTime", value=value)


@pytest.mark.parametrize("value", [2_147_483_648, -2_147_483_649])
def test_general_settings_edit_input_validation_rejects_values_outside_osc_int32_range(value: int) -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=WORKSPACE_ID, operation="minGoTime", value=value)


@pytest.mark.parametrize("value", [3.5e38, -3.5e38])
def test_general_settings_edit_input_validation_rejects_values_outside_osc_float32_range(value: float) -> None:
    with pytest.raises(ValidationError):
        GeneralSettingsEditInput(workspace_id=WORKSPACE_ID, operation="minGoTime", value=value)


@pytest.mark.parametrize(
    ("value", "expected_type"),
    [
        (0, int),
        (0.0, float),
        (1, int),
        (0.4, float),
        (2_147_483_647, int),
        (struct.unpack(">f", struct.pack(">f", 3.4028235e38))[0], float),
    ],
)
def test_general_settings_edit_input_validation_accepts_transport_representable_values(
    value: int | float, expected_type: type[int] | type[float]
) -> None:
    model = GeneralSettingsEditInput(workspace_id=WORKSPACE_ID, operation="minGoTime", value=value)

    assert isinstance(model.value, expected_type)
    assert model.value == pytest.approx(float(value))


def test_general_settings_edit_result_exposes_typed_contract_fields() -> None:
    result = GeneralSettingsEditResult(
        ok=True,
        status="updated",
        workspace_id=WORKSPACE_ID,
        operation="minGoTime",
        dry_run=False,
        requested_value=0.4,
        baseline=0.2,
        readback=0.4,
        planned_operations=[{"operation": "set"}],
        executed_operations=[{"operation": "set"}],
        confirm_token=None,
        readiness={"ok": True},
        activity={"active_cues": 0},
        verification={"matched": True},
        timeout_confirmation={"confirmed": False},
        retry_unsafe=False,
        errors=None,
        warnings=[],
        error_code=None,
        suggested_action=None,
        message="updated",
    )

    assert result.operation == "minGoTime"
    assert result.requested_value == pytest.approx(0.4)
    assert result.readback == pytest.approx(0.4)
    assert result.retry_unsafe is False


def test_general_settings_contract_type_aliases_are_narrow() -> None:
    assert get_args(GeneralSettingsOperation) == ("minGoTime",)
    assert get_args(GeneralSettingsWriteStatus) == (
        "dry_run",
        "dry_run_preflight_failed",
        "updated",
        "updated_with_confirmed_timeouts",
        "preflight_failed",
        "verification_failed",
        "verification_inconclusive",
    )


class _SettingsFakeReader(WorkspaceSettingsWriteMixin):
    def __init__(self, *, timeout_setter: bool = False, running: list[object] | None = None,
                 readback_error: bool = False, apply_setter: bool = True,
                 workspace_id: str = WORKSPACE_ID) -> None:
        from types import SimpleNamespace

        self.client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))
        self._read_cache = SimpleNamespace(clear=lambda: None)
        self.value: int | float = 0.2
        self.timeout_setter = timeout_setter
        self.running = running or []
        self.readback_error = readback_error
        self.apply_setter = apply_setter
        self.setter_done = False
        self.workspace_id = workspace_id
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def get_workspaces(self) -> dict[str, object]:
        return {"workspaces": [{"uniqueID": self.workspace_id, "displayName": "Demo"}]}

    def get_running_cues(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        return {"running_cues": self.running}

    def _request(self, address: str, *args: object, **_kwargs: object) -> object:
        from types import SimpleNamespace
        from qlab_mcp.errors import OscTimeoutError

        self.calls.append((address, args))
        if not args and self.readback_error and self.setter_done:
            raise RuntimeError("readback unavailable")
        if args:
            if self.apply_setter:
                self.value = args[0]  # one and only mutating request
            self.setter_done = True
            if self.timeout_setter:
                raise OscTimeoutError("setter timed out")
        return SimpleNamespace(status="ok", data=self.value)


def test_workspace_settings_registry_is_one_exact_saved_operation() -> None:
    assert MIN_GO_TIME_SPEC.osc_path == "settings/general/minGoTime"
    assert MIN_GO_TIME_SPEC.readback_path == MIN_GO_TIME_SPEC.osc_path
    assert MIN_GO_TIME_SPEC.activity_policy == "running_or_paused_zero"
    with pytest.raises(ValueError):
        get_workspace_settings_write_spec("selectionIsPlayhead")


def test_workspace_settings_uuid_resolution_preserves_qlab_canonical_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    reader = _SettingsFakeReader(workspace_id=WORKSPACE_ID.upper())

    result = reader.edit_general_settings(WORKSPACE_ID.lower(), "minGoTime", 0.4, dry_run=True)

    assert result.status == "dry_run"
    assert result.workspace_id == WORKSPACE_ID.upper()
    assert result.planned_operations[0]["address"] == f"/workspace/{WORKSPACE_ID.upper()}/settings/general/minGoTime"


def test_workspace_settings_readback_keeps_existing_numeric_tolerance() -> None:
    from qlab_mcp.write.comparison import SETTINGS_NUMERIC_MATCH_REL_TOLERANCE, numeric_values_match

    assert SETTINGS_NUMERIC_MATCH_REL_TOLERANCE == 1e-5
    assert numeric_values_match(1000.005, 1000.0, rel_tol=SETTINGS_NUMERIC_MATCH_REL_TOLERANCE)


def test_workspace_settings_dry_run_issues_token_without_setter(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    reader = _SettingsFakeReader()
    result = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)

    assert result.status == "dry_run"
    assert result.confirm_token and result.confirm_token.startswith("confirm:workspaceSettings:v1:")
    assert result.planned_operations[0]["address"] == f"/workspace/{WORKSPACE_ID}/settings/general/minGoTime"
    assert result.executed_operations == []
    assert [args for _, args in reader.calls if args] == []


def test_workspace_settings_real_write_attempts_one_setter_and_reads_back(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )

    expected_address = f"/workspace/{WORKSPACE_ID}/settings/general/minGoTime"
    setter_calls = [(address, args) for address, args in reader.calls if args]
    readback_calls = [address for address, args in reader.calls if not args]
    assert result.status == "updated"
    assert setter_calls == [(expected_address, (0.4,))]
    assert readback_calls and all(address == expected_address for address in readback_calls)
    assert result.readback == pytest.approx(0.4)


def test_workspace_settings_timeout_is_confirmed_by_matching_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader(timeout_setter=True)
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )

    setter_calls = [args for address, args in reader.calls if args and address.endswith("settings/general/minGoTime")]
    assert result.status == "updated_with_confirmed_timeouts"
    assert result.retry_unsafe is False
    assert len(setter_calls) == 1


def test_workspace_settings_timeout_with_mismatch_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader(timeout_setter=True, apply_setter=False)
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )

    setter_calls = [args for address, args in reader.calls if args and address.endswith("settings/general/minGoTime")]
    assert result.status == "verification_failed"
    assert result.retry_unsafe is False
    assert len(setter_calls) == 1


def test_workspace_settings_token_binds_numeric_wire_type(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 1, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 1.0, dry_run=False, confirm_token=dry.confirm_token
    )

    assert result.status == "preflight_failed"
    assert result.executed_operations == []

    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.1, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.10000000149011612, dry_run=False, confirm_token=dry.confirm_token
    )
    assert result.status == "preflight_failed"
    assert result.executed_operations == []


def test_workspace_settings_rejects_missing_malformed_and_changed_request_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader()

    for token, requested in ((None, 0.4), ("not-a-confirm-token", 0.4)):
        result = reader.edit_general_settings(
            WORKSPACE_ID, "minGoTime", requested, dry_run=False, confirm_token=token
        )
        assert result.status == "preflight_failed"
        assert result.executed_operations == []

    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    changed_request = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.5, dry_run=False, confirm_token=dry.confirm_token
    )
    assert changed_request.status == "preflight_failed"
    assert changed_request.executed_operations == []


def test_workspace_settings_token_bindings_reject_workspace_operation_and_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    spec = MIN_GO_TIME_SPEC

    for workspace_id, operation, requested_value in (
        ("22222222-2222-4222-8222-222222222222", "minGoTime", 0.4),
        (WORKSPACE_ID, "selectionIsPlayhead", 0.4),
        (WORKSPACE_ID, "minGoTime", 0.5),
    ):
        token = write_operations.encode_confirm_token(
            write_operations.SETTINGS_TOKEN_FAMILY,
            write_operations.SETTINGS_TOKEN_VERSION,
            write_operations._token_payload(workspace_id, operation, 0.2, requested_value, spec),
            write_operations._SETTINGS_TOKEN_SECRET,
        )
        reader = _SettingsFakeReader()
        result = reader.edit_general_settings(
            WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=token
        )
        assert result.status == "preflight_failed"
        assert result.executed_operations == []


class _ActivityChangesReader(_SettingsFakeReader):
    def __init__(self) -> None:
        super().__init__()
        self.activity_reads = 0

    def get_running_cues(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        self.activity_reads += 1
        return {"running_cues": [] if self.activity_reads == 1 else [{"uniqueID": "cue-3"}]}


def test_workspace_settings_rechecks_activity_before_setter(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _ActivityChangesReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )
    assert result.status == "preflight_failed"
    assert result.executed_operations == []


def test_workspace_settings_rejects_changed_workspace_and_stale_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)

    reader.workspace_id = "22222222-2222-4222-8222-222222222222"
    changed_workspace = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )
    assert changed_workspace.status == "preflight_failed"
    assert changed_workspace.executed_operations == []

    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    reader.value = 0.3
    stale_baseline = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )
    assert stale_baseline.status == "preflight_failed"
    assert stale_baseline.executed_operations == []


def test_workspace_settings_rejects_active_cues_and_exact_uuid_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    active = _SettingsFakeReader(running=[{"uniqueID": "cue-1"}])
    result = active.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    assert result.status == "dry_run_preflight_failed"
    assert result.confirm_token is None
    assert not [args for _, args in active.calls if args]

    auditioning = _SettingsFakeReader(running=[{"uniqueID": "cue-2", "isAuditioning": True}])
    result = auditioning.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    assert result.status == "dry_run_preflight_failed"
    assert result.confirm_token is None
    assert not [args for _, args in auditioning.calls if args]

    missing = _SettingsFakeReader(workspace_id="22222222-2222-4222-8222-222222222222")
    result = missing.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    assert result.status == "dry_run_preflight_failed"
    assert result.confirm_token is None


def test_workspace_settings_replay_and_inconclusive_readback_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    first = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )
    replay = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )
    assert first.status == "updated"
    assert replay.status == "preflight_failed"
    assert replay.executed_operations == []

    unavailable = _SettingsFakeReader(readback_error=True)
    dry = unavailable.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    result = unavailable.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )
    setter_calls = [args for _, args in unavailable.calls if args]
    assert result.status == "verification_inconclusive"
    assert result.retry_unsafe is True
    assert setter_calls == [(0.4,)]


def test_workspace_settings_expired_token_is_rejected_before_setter(monkeypatch: pytest.MonkeyPatch) -> None:
    import time
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader()
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    now = time.time()
    monkeypatch.setattr(write_operations.time, "time", lambda: now + 301)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )

    assert result.status == "preflight_failed"
    assert result.executed_operations == []


def test_workspace_settings_readable_mismatch_is_verification_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    import qlab_mcp.settings.write_operations as write_operations

    monkeypatch.setattr(write_operations, "check_write_readiness", lambda *_: {"ok": True, "status": "ready"})
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    reader = _SettingsFakeReader(apply_setter=False)
    dry = reader.edit_general_settings(WORKSPACE_ID, "minGoTime", 0.4, dry_run=True)
    result = reader.edit_general_settings(
        WORKSPACE_ID, "minGoTime", 0.4, dry_run=False, confirm_token=dry.confirm_token
    )

    assert result.status == "verification_failed"
    assert result.retry_unsafe is False
    assert result.executed_operations and len(result.executed_operations) == 1
