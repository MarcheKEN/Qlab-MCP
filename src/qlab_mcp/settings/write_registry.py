"""Allowlisted Workspace Settings write operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


WorkspaceSettingsOperation = Literal["minGoTime"]


@dataclass(frozen=True)
class WorkspaceSettingsWriteSpec:
    operation: WorkspaceSettingsOperation
    osc_path: str
    readback_path: str
    value_kind: str
    risk_tier: str
    mode: str
    real_write_enabled: bool
    activity_policy: str
    registry_version: str


MIN_GO_TIME_SPEC = WorkspaceSettingsWriteSpec(
    operation="minGoTime",
    osc_path="settings/general/minGoTime",
    readback_path="settings/general/minGoTime",
    value_kind="non_negative_finite_number",
    risk_tier="tier2",
    mode="saved",
    real_write_enabled=True,
    activity_policy="running_or_paused_zero",
    registry_version="workspace-settings-v1",
)

WORKSPACE_SETTINGS_WRITE_REGISTRY: dict[WorkspaceSettingsOperation, WorkspaceSettingsWriteSpec] = {
    "minGoTime": MIN_GO_TIME_SPEC,
}


def get_workspace_settings_write_spec(operation: str) -> WorkspaceSettingsWriteSpec:
    try:
        return WORKSPACE_SETTINGS_WRITE_REGISTRY[operation]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"Unsupported Workspace Settings operation: {operation!r}") from exc
