"""Typed Group edits reuse the existing guarded Group writer."""

import pytest
from pydantic import ValidationError

from qlab_mcp.write.group import (
    GroupCueEditInput,
    edit_group_cues,
    group_edit_capabilities,
)

WORKSPACE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
GROUP = "11111111-1111-4111-8111-111111111111"


class Reader:
    def __init__(self):
        self.calls = []



def test_group_editor_maps_to_common_signed_motor(monkeypatch):
    from qlab_mcp.write import group
    calls = []
    monkeypatch.setattr(group, "edit_control_cues", lambda *args, **kwargs: calls.append((args, kwargs)) or {"status": "dry_run"})
    reader = Reader()
    result = edit_group_cues(reader, WORKSPACE, [{"cue_id": GROUP, "properties": {"mode": 6}}], True)
    assert result == {"status": "dry_run"}
    assert calls[0][1] == {"_family": "group"}
    assert calls[0][0][2][0].properties.mode == 6
    assert reader.calls == []


@pytest.mark.parametrize(
    "properties",
    [
        {"mode": 5},
        {"mode": True},
        {"unknown": 1},
        {"notes": None},
        {"playlist/doLoop": "yes"},
    ],
)
def test_group_editor_rejects_invalid_or_unknown_properties(properties):
    with pytest.raises(ValidationError):
        GroupCueEditInput.model_validate({"cue_id": GROUP, "properties": properties})


def test_mode_and_playlist_writes_keep_single_property_gate():
    reader = Reader()
    with pytest.raises(ValueError, match="one cue and one property"):
        edit_group_cues(
            reader,
            WORKSPACE,
            [{"cue_id": GROUP, "properties": {"mode": 6, "notes": "change"}}],
            dry_run=True,
        )
    assert reader.calls == []


@pytest.mark.parametrize(
    "updates",
    [
        [],
        [
            {"cue_id": GROUP, "properties": {"name": "A"}},
            {"cue_id": GROUP, "properties": {"name": "B"}},
        ],
        [
            {"cue_id": f"00000000-0000-4000-8000-{index:012d}", "properties": {"name": "A"}}
            for index in range(1, 52)
        ],
    ],
)
def test_group_editor_requires_one_to_fifty_distinct_cues(updates):
    reader = Reader()
    with pytest.raises(ValueError, match="1–50 distinct cue UUIDs"):
        edit_group_cues(reader, WORKSPACE, updates, dry_run=True)
    assert reader.calls == []


def test_group_capabilities_show_playlist_mode_requirement():
    mode_three = group_edit_capabilities(3)
    assert "mode" in mode_three["allowed_properties"]
    assert "playlist/doLoop" not in mode_three["allowed_properties"]
    assert "mode=6" in mode_three["blocked_properties"]["playlist/doLoop"]
    assert "playlist/doLoop" in group_edit_capabilities(6)["allowed_properties"]


def test_crossfade_duration_uses_archive_and_osc_stays_blocked():
    from qlab_mcp.write.groups import group_preflight

    key = "playlist/crossfade/duration"
    capability = group_edit_capabilities(6)
    assert key in capability["allowed_properties"]
    assert capability["property_transports"][key] == "saved_archive"
    item = {"profile": "group_basic", "cue_ref": GROUP, "operations": [{"property": key, "args": [0.75]}]}
    errors, _ = group_preflight(Reader(), WORKSPACE, item, {})
    assert "curve" in errors[key].lower()


def test_crossfade_duration_uses_saved_transaction(monkeypatch):
    from qlab_mcp.write import playlist_archive

    calls = []
    monkeypatch.setattr(playlist_archive, "edit_playlist_crossfade",
        lambda *args: calls.append(args) or {"status": "dry_run"})
    reader = Reader()
    result = edit_group_cues(reader, WORKSPACE, [{"cue_id": GROUP,
        "properties": {"playlist/crossfade/duration": 4.5}}], True)
    assert result == {"status": "dry_run"}
    assert calls[0][0] is reader and calls[0][1] == WORKSPACE
    assert calls[0][2].properties.playlist_crossfade_duration == 4.5
    assert calls[0][3] is True
