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
