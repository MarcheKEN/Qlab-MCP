"""Typed routing for live and saved-workspace audio patch edits."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .audio_archive import (
    DeletePatch,
    DuplicatePatch,
    ReorderPatches,
    RenamePatch,
    SetAudioBusName,
    SetAudioDevice,
    SetCueOutputName,
    SetSystemDevice,
    edit_saved_audio_patches,
)
from .audio_volume_limits import SetAudioVolumeLimits, edit_audio_volume_limits
from .models import (
    AudioBoolOperation,
    AudioClearOperation,
    AudioCueOutputsOperation,
    AudioLevelOperation,
    AudioOutputPatchBatchOperation,
    SettingNameOperation,
)


_INPUT_PATCH_OPERATIONS = Annotated[
    Union[RenamePatch, SetAudioDevice, SetSystemDevice], Field(discriminator="action")
]
_OUTPUT_PATCH_ARCHIVE_OPERATIONS = Annotated[
    Union[
        RenamePatch, SetAudioDevice, SetSystemDevice, SetCueOutputName, SetAudioBusName,
    ],
    Field(discriminator="action"),
]
_OUTPUT_PATCH_OSC_OPERATIONS = Annotated[
    Union[
        AudioCueOutputsOperation,
        AudioLevelOperation,
        AudioBoolOperation,
        AudioClearOperation,
        AudioOutputPatchBatchOperation,
        SettingNameOperation,
    ],
    Field(discriminator="kind"),
]
AudioPatchOperation = Union[_OUTPUT_PATCH_ARCHIVE_OPERATIONS, _OUTPUT_PATCH_OSC_OPERATIONS]
AudioPatchOperations = Annotated[
    Union[AudioPatchOperation, Annotated[list[AudioPatchOperation], Field(min_length=1, max_length=50)]],
    Field(),
]


class InputAudioPatchEdit(BaseModel):
    """One saved input patch edit. Input patches have no live OSC cell writer."""

    model_config = ConfigDict(extra="forbid", strict=True)
    patch_type: Literal["input"]
    patch_id: str
    operation: _INPUT_PATCH_OPERATIONS


class OutputAudioPatchEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    patch_type: Literal["output"]
    patch_id: str
    operation: Union[_OUTPUT_PATCH_ARCHIVE_OPERATIONS, _OUTPUT_PATCH_OSC_OPERATIONS]


AudioPatchEdit = Annotated[
    Union[InputAudioPatchEdit, OutputAudioPatchEdit],
    Field(discriminator="patch_type"),
]


_WORKSPACE_PATCH_OPERATIONS = Annotated[
    Union[DeletePatch, DuplicatePatch, ReorderPatches], Field(discriminator="action")
]
WorkspaceAudioPatchOperations = Annotated[
    list[_WORKSPACE_PATCH_OPERATIONS], Field(min_length=1, max_length=50)
]
WorkspaceAudioSettingsOperation = Annotated[
    Union[DeletePatch, DuplicatePatch, ReorderPatches, SetAudioVolumeLimits],
    Field(discriminator="action"),
]
WorkspaceAudioSettingsOperations = Annotated[
    list[WorkspaceAudioSettingsOperation], Field(min_length=1, max_length=50)
]


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True)
    if isinstance(value, dict):
        return value
    raise ValueError("Audio patch operations must be typed models or objects.")


def _audio_operation_kind(value: Any) -> str:
    """Classify before dispatch so an OSC/archive batch can never be split."""
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError("Audio patch batch must contain at least one operation.")
        kinds = {_audio_operation_kind(item) for item in value}
        if len(kinds) != 1:
            raise ValueError("An audio patch batch cannot mix OSC writes with saved-file operations.")
        return next(iter(kinds))
    operation = _as_mapping(value)
    if operation.get("action") in {"create_empty_patch", "create_patch"}:
        raise ValueError("Creating an empty audio patch is blocked; duplicate an existing patch instead.")
    if operation.get("action") == "set_volume_limits":
        return "volume_limits"
    if isinstance(operation.get("operations"), list):
        nested = {_audio_operation_kind(item) for item in operation["operations"]}
        if not nested:
            raise ValueError("Audio patch batch must contain at least one operation.")
        if len(nested) != 1:
            raise ValueError("An audio patch batch cannot mix OSC writes with saved-file operations.")
        return next(iter(nested))
    if "action" in operation:
        return "archive"
    if "kind" in operation:
        return "osc"
    raise ValueError("Audio patch operation must identify an OSC write or saved-file action.")


def _scoped_archive_patch_operations(operations: Any, patch_type: str) -> list[dict[str, Any]]:
    raw = [_as_mapping(item) for item in operations] if isinstance(operations, (list, tuple)) else [_as_mapping(operations)]
    if any(_audio_operation_kind(item) != "archive" for item in raw):
        raise ValueError("Saved audio patch batches accept saved-file operations only.")
    adapter = TypeAdapter(_INPUT_PATCH_OPERATIONS if patch_type == "input" else _OUTPUT_PATCH_ARCHIVE_OPERATIONS)
    typed = [adapter.validate_python(operation) for operation in raw]
    result = [operation.model_dump(exclude_none=True) for operation in typed]
    if any(operation["patch_type"] != patch_type for operation in result):
        raise ValueError("Audio patch type does not match the selected input/output patch.")
    return result


def _workspace_archive_operations(operations: Any) -> list[dict[str, Any]]:
    raw = [_as_mapping(item) for item in operations] if isinstance(operations, (list, tuple)) else [_as_mapping(operations)]
    if any(_audio_operation_kind(item) != "archive" for item in raw):
        raise ValueError("Workspace audio patch actions accept saved-file operations only.")
    typed = TypeAdapter(WorkspaceAudioPatchOperations).validate_python(raw)
    return [operation.model_dump(exclude_none=True) for operation in typed]


def _validate_scoped_archive_edits(
    operations: Any, *, patch_type: str, patch_id: str,
) -> list[dict[str, Any]]:
    normalized = _scoped_archive_patch_operations(operations, patch_type)
    for operation in normalized:
        if operation["action"] in {"duplicate_patch", "reorder_patches", "delete_patch"}:
            raise ValueError("Duplicate, delete, and reorder are workspace-level audio patch actions.")
        if str(operation.get("patch_id", "")).casefold() != str(patch_id).casefold():
            raise ValueError("Saved audio patch operation must target the selected patch ID.")
    return normalized


def edit_audio_patch(
    reader: Any,
    workspace_id: str,
    patch_type: Literal["input", "output"],
    patch_id: str,
    operation: Any,
    dry_run: bool | None = True,
    confirm_token: str | None = None,
) -> Any:
    """Edit one exact patch; preserve backend status and tokens."""
    kind = _audio_operation_kind(operation)
    if kind == "volume_limits":
        raise ValueError("Workspace volume limits belong to qlab_edit_workspace_audio_settings.")
    if kind == "archive":
        normalized = _validate_scoped_archive_edits(operation, patch_type=patch_type, patch_id=patch_id)
        return _named_tool_result(edit_saved_audio_patches(
            reader, workspace_id, normalized, dry_run=dry_run, confirm_token=confirm_token,
        ), "qlab_edit_audio_patch")
    if patch_type != "output":
        raise ValueError("Input audio patches do not expose live OSC setting writes.")

    if isinstance(operation, AudioOutputPatchBatchOperation):
        batch = operation
    elif isinstance(operation, dict) and operation.get("kind") == "batch":
        batch = AudioOutputPatchBatchOperation.model_validate(operation)
    elif isinstance(operation, (list, tuple)):
        if not operation:
            raise ValueError("Audio patch batch must contain at least one operation.")
        if any(_audio_operation_kind(item) != "osc" for item in operation):
            raise ValueError("An audio patch batch cannot mix OSC writes with saved-file operations.")
        batch = AudioOutputPatchBatchOperation.model_validate({
            "kind": "batch",
            "operations": [_as_mapping(item) for item in operation],
        })
    else:
        op = operation
        if isinstance(operation, dict):
            op = TypeAdapter(_OUTPUT_PATCH_OSC_OPERATIONS).validate_python(operation)
        return reader.edit_object_setting(
            str(workspace_id), "audio", {"patch_id": str(patch_id)}, op, dry_run, confirm_token,
        )
    return reader.edit_audio_patch_batch(
        str(workspace_id), str(patch_id), batch, dry_run, confirm_token,
    )


def _named_tool_result(result: Any, tool: str) -> Any:
    # Keep every archive result field/status/token; only report its public wrapper tool.
    if not isinstance(result, dict):
        return result
    named = dict(result)
    named["tool"] = tool
    return named


def edit_workspace_audio_settings(
    reader: Any,
    workspace_id: str,
    operations: Any,
    dry_run: bool | None = True,
    confirm_token: str | None = None,
) -> Any:
    """Edit saved patch collections or route the isolated volume-limit operation."""
    raw = [_as_mapping(item) for item in operations] if isinstance(operations, (list, tuple)) else [_as_mapping(operations)]
    if not raw:
        raise ValueError("Workspace audio settings require at least one operation.")
    kinds = {_audio_operation_kind(item) for item in raw}
    if len(kinds) != 1:
        raise ValueError("Workspace audio settings cannot mix OSC writes, volume limits, and saved-file edits.")
    kind = next(iter(kinds))
    if kind == "volume_limits":
        if len(raw) != 1:
            raise ValueError("A volume-limit edit must be a single workspace-level operation.")
        operation = SetAudioVolumeLimits.model_validate(raw[0])
        actual_dry_run = dry_run
        if actual_dry_run is None:
            from .write.safety import resolve_dry_run
            actual_dry_run = resolve_dry_run(reader, None)
        return _named_tool_result(edit_audio_volume_limits(
            reader, workspace_id, operation, dry_run=actual_dry_run, confirm_token=confirm_token,
        ), "qlab_edit_workspace_audio_settings")
    if kind != "archive":
        raise ValueError("Workspace audio settings accept saved patch actions or set_volume_limits.")
    normalized = _workspace_archive_operations(raw)
    # `edit_saved_audio_patches` owns the archive transaction/token protocol.
    return _named_tool_result(edit_saved_audio_patches(
        reader, workspace_id, normalized, dry_run=dry_run, confirm_token=confirm_token,
    ), "qlab_edit_workspace_audio_settings")


__all__ = [
    "AudioPatchEdit",
    "AudioPatchOperation",
    "AudioPatchOperations",
    "InputAudioPatchEdit",
    "OutputAudioPatchEdit",
    "SetAudioVolumeLimits",
    "WorkspaceAudioPatchOperations",
    "WorkspaceAudioSettingsOperation",
    "WorkspaceAudioSettingsOperations",
    "edit_audio_patch",
    "edit_workspace_audio_settings",
]
