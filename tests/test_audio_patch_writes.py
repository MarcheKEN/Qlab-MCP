from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter

from qlab_mcp.audio_patch_writes import (
    AudioPatchEdit,
    InputAudioPatchEdit,
    OutputAudioPatchEdit,
    SetAudioVolumeLimits,
    edit_audio_patch,
    edit_workspace_audio_settings,
)
from qlab_mcp.models import AudioOutputPatchBatchOperation


WS = "11111111-1111-4111-8111-111111111111"
INPUT_PATCH = "22222222-2222-4222-8222-222222222222"
OUTPUT_PATCH = "33333333-3333-4333-8333-333333333333"


class Reader:
    def __init__(self):
        self.calls = []
        self.client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))

    def edit_object_setting(self, *args):
        self.calls.append(("single", args))
        return self.result

    def edit_audio_patch_batch(self, *args):
        self.calls.append(("batch", args))
        return self.result


def test_audio_patch_schema_discriminates_input_and_output():
    adapter = TypeAdapter(AudioPatchEdit)
    input_edit = adapter.validate_python({
        "patch_type": "input",
        "patch_id": INPUT_PATCH,
        "operation": {"action": "set_device", "patch_type": "input",
                      "patch_id": INPUT_PATCH, "device_uid": "coreaudio:1"},
    })
    output_edit = adapter.validate_python({
        "patch_type": "output",
        "patch_id": OUTPUT_PATCH,
        "operation": {"action": "set_bus_name", "patch_type": "output",
                      "patch_id": OUTPUT_PATCH, "bus_type": "cue", "bus_index": 1,
                      "name": "Main"},
    })
    assert isinstance(input_edit, InputAudioPatchEdit)
    assert isinstance(output_edit, OutputAudioPatchEdit)
    assert output_edit.operation.action == "set_bus_name"
    with pytest.raises(Exception):
        adapter.validate_python({
            "patch_type": "input", "patch_id": INPUT_PATCH,
            "operation": {"kind": "level", "input_channel": 1,
                          "output_channel": 1, "value": -6},
        })


def test_audio_patch_live_batch_routes_once_and_preserves_response(monkeypatch):
    reader = Reader()
    reader.result = {"status": "verification_inconclusive", "confirm_token": "fresh-token"}
    operation = AudioOutputPatchBatchOperation.model_validate({
        "kind": "batch",
        "operations": [
            {"kind": "level", "input_channel": 1, "output_channel": 2, "value": -6},
            {"kind": "mute", "output_channel": 2, "value": True},
        ],
    })

    result = edit_audio_patch(reader, WS, "output", OUTPUT_PATCH, operation, False, "reviewed-token")

    assert result is reader.result
    assert reader.calls == [("batch", (
        WS, OUTPUT_PATCH, operation, False, "reviewed-token",
    ))]


def test_audio_patch_live_single_routes_to_object_writer():
    reader = Reader()
    reader.result = {"status": "updated", "confirm_token": None}
    operation = {"kind": "name", "value": "Main"}

    result = edit_audio_patch(reader, WS, "output", OUTPUT_PATCH, operation, True, None)

    assert result is reader.result
    assert reader.calls[0][0] == "single"
    assert reader.calls[0][1] == (WS, "audio", {"patch_id": OUTPUT_PATCH},
                                   TypeAdapter(OutputAudioPatchEdit).validate_python({
                                       "patch_type": "output", "patch_id": OUTPUT_PATCH,
                                       "operation": operation,
                                   }).operation, True, None)


def test_input_patch_rejects_live_osc_without_reader_call():
    reader = Reader()
    with pytest.raises(ValueError, match="Input audio patches do not expose live OSC"):
        edit_audio_patch(reader, WS, "input", INPUT_PATCH,
                         {"kind": "level", "input_channel": 1,
                          "output_channel": 1, "value": -6})
    assert reader.calls == []


def test_audio_patch_batch_rejects_osc_archive_mix_before_dispatch():
    reader = Reader()
    with pytest.raises(ValueError, match="cannot mix OSC writes with saved-file operations"):
        edit_audio_patch(reader, WS, "output", OUTPUT_PATCH, [
            {"kind": "mute", "output_channel": 1, "value": True},
            {"action": "set_device", "patch_type": "output",
             "patch_id": OUTPUT_PATCH, "device_uid": "coreaudio:1"},
        ])
    assert reader.calls == []


def test_audio_patch_archive_operation_requires_exact_selected_patch(monkeypatch):
    import qlab_mcp.audio_patch_writes as writes

    result = {"status": "dry_run", "confirm_token": "fresh-token"}
    calls = []
    monkeypatch.setattr(writes, "edit_saved_audio_patches", lambda *args, **kwargs: (calls.append((args, kwargs)) or result))
    operation = {"action": "rename_patch", "patch_type": "input",
                 "patch_id": INPUT_PATCH, "name": "Stage mics"}

    returned = edit_audio_patch(Reader(), WS, "input", INPUT_PATCH, operation, True, "old-token")

    assert returned["confirm_token"] == "fresh-token"
    assert returned["tool"] == "qlab_edit_audio_patch"
    assert calls[0][0][2] == [operation]
    assert calls[0][1] == {"dry_run": True, "confirm_token": "old-token"}


def test_workspace_audio_settings_routes_structural_input_and_output_actions(monkeypatch):
    import qlab_mcp.audio_patch_writes as writes

    result = {"status": "dry_run", "confirm_token": "fresh-token"}
    calls = []
    monkeypatch.setattr(writes, "edit_saved_audio_patches", lambda *args, **kwargs: (calls.append((args, kwargs)) or result))
    operations = [
        {"action": "duplicate_patch", "patch_type": "input", "client_ref": "copy-1",
         "source_patch_id": INPUT_PATCH, "name": "Mic copy"},
        {"action": "delete_patch", "patch_type": "output", "patch_id": OUTPUT_PATCH},
        {"action": "reorder_patches", "patch_type": "input", "patch_ids": [INPUT_PATCH]},
    ]

    returned = edit_workspace_audio_settings(Reader(), WS, operations, False, "reviewed-token")

    assert returned["confirm_token"] == "fresh-token"
    assert returned["tool"] == "qlab_edit_workspace_audio_settings"
    assert calls[0][0][2] == operations
    assert calls[0][1] == {"dry_run": False, "confirm_token": "reviewed-token"}


def test_workspace_audio_settings_rejects_mixed_families_before_archive_call(monkeypatch):
    import qlab_mcp.audio_patch_writes as writes

    calls = []
    monkeypatch.setattr(writes, "edit_saved_audio_patches", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="cannot mix OSC writes, volume limits, and saved-file edits"):
        edit_workspace_audio_settings(Reader(), WS, [
            {"action": "set_device", "patch_type": "output", "patch_id": OUTPUT_PATCH,
             "device_uid": "coreaudio:1"},
            {"action": "set_volume_limits", "max_volume": 12},
        ])
    assert calls == []


def test_volume_limits_route_to_dedicated_backend(monkeypatch):
    import qlab_mcp.audio_patch_writes as writes

    reader = Reader()
    operation = SetAudioVolumeLimits(action="set_volume_limits", max_volume=12)
    calls = []
    result = {"status": "dry_run", "confirm_token": "fresh-token"}
    monkeypatch.setattr(writes, "edit_audio_volume_limits", lambda *args, **kwargs: (calls.append((args, kwargs)) or result))

    returned = edit_workspace_audio_settings(reader, WS, operation, False, "reviewed-token")

    assert returned["status"] == "dry_run"
    assert returned["confirm_token"] == "fresh-token"
    assert returned["tool"] == "qlab_edit_workspace_audio_settings"
    assert calls[0][0] == (reader, WS, operation)
    assert calls[0][1] == {"dry_run": False, "confirm_token": "reviewed-token"}
    assert reader.calls == []


@pytest.mark.parametrize("operation", [
    {"action": "create_empty_patch", "patch_type": "output", "name": "Empty"},
    {"action": "create_patch", "patch_type": "input", "name": "Empty"},
])
def test_empty_audio_patch_creation_is_blocked_explicitly(operation):
    with pytest.raises(ValueError, match="Creating an empty audio patch is blocked"):
        edit_workspace_audio_settings(Reader(), WS, [operation])


def test_workspace_audio_settings_rejects_empty_batch():
    with pytest.raises(ValueError, match="require at least one operation"):
        edit_workspace_audio_settings(Reader(), WS, [])
