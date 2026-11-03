from __future__ import annotations

import hashlib

import pytest

from qlab_mcp.write import control, moves, remaining, remaining_context
from qlab_mcp.write.remaining import _fingerprint, check_dependencies


WORKSPACE = "00000000-0000-0000-0000-000000000001"
EDITED_CUE = "00000000-0000-0000-0000-000000000002"
SOURCE_CUE = "00000000-0000-0000-0000-000000000010"
NESTED_CUE = "00000000-0000-0000-0000-000000000011"
COLLISION_CUE = "00000000-0000-0000-0000-000000000012"


def _snapshot(*nodes):
    return {"nodes": {node["uniqueID"]: node for node in nodes}}


def _source(number="10", text="Front = 50"):
    return {
        "uniqueID": SOURCE_CUE,
        "number": number,
        "type": "Light",
        "lightCommandText": text,
    }


def test_no_pull_does_not_read_the_structural_cue_tree(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("A command without cue pulls must not read the structural cue tree.")

    monkeypatch.setattr(moves, "_read_snapshot", unexpected)

    assert remaining_context._light_cue_pull_context(
        object(), WORKSPACE, EDITED_CUE, "Front = 50", {}
    ) == {}


def test_pull_context_binds_transitive_sources_by_hash_and_number_index(monkeypatch):
    source_text = "Front = cue 11 * 0.5"
    nested_text = "Back = 25"
    snapshot = _snapshot(
        {"uniqueID": EDITED_CUE, "number": "1", "type": "Light"},
        {"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"},
        {"uniqueID": NESTED_CUE, "number": "11", "type": "Light"},
    )
    monkeypatch.setattr(moves, "_read_snapshot", lambda *_args, **_kwargs: snapshot)

    def read(_reader, _workspace, cue_id, keys):
        assert keys == ["number", "lightCommandText"]
        return _source("10", source_text) if cue_id == SOURCE_CUE else {
            "uniqueID": NESTED_CUE,
            "number": "11",
            "type": "Light",
            "lightCommandText": nested_text,
        }

    monkeypatch.setattr(remaining_context, "read", read)
    dependencies = {}

    references = remaining_context._light_cue_pull_context(
        object(), WORKSPACE, EDITED_CUE, "Front = cue 10", dependencies
    )

    assert set(references) == {"10", "11"}
    assert dependencies["light_pull_sources"] == {
        SOURCE_CUE: {
            "uniqueID": SOURCE_CUE,
            "number": "10",
            "type": "Light",
            "text_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
        },
        NESTED_CUE: {
            "uniqueID": NESTED_CUE,
            "number": "11",
            "type": "Light",
            "text_sha256": hashlib.sha256(nested_text.encode()).hexdigest(),
        },
    }
    assert dependencies["light_pull_number_index"]["numbers"] == ["10", "11"]
    assert "cues" not in dependencies
    assert source_text not in repr(dependencies)
    assert nested_text not in repr(dependencies)


@pytest.mark.parametrize(
    ("snapshot", "source_texts", "message"),
    [
        (
            _snapshot(
                {"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"},
                {"uniqueID": NESTED_CUE, "number": "11", "type": "Light"},
            ),
            {"10": "Front = cue 11", "11": "Back = cue 10"},
            "form a cycle",
        ),
        (
            _snapshot(
                {"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"},
                {"uniqueID": COLLISION_CUE, "number": "10", "type": "Light"},
            ),
            {},
            "ambiguous",
        ),
        (
            _snapshot({"uniqueID": SOURCE_CUE, "number": "10", "type": "Audio"}),
            {},
            "not a Light cue",
        ),
    ],
)
def test_pull_context_rejects_cycles_ambiguous_numbers_and_non_light_sources(
    monkeypatch, snapshot, source_texts, message
):
    monkeypatch.setattr(moves, "_read_snapshot", lambda *_args, **_kwargs: snapshot)

    def read(_reader, _workspace, cue_id, _keys):
        number = "10" if cue_id == SOURCE_CUE else "11"
        return {
            "uniqueID": cue_id,
            "number": number,
            "type": "Light",
            "lightCommandText": source_texts[number],
        }

    monkeypatch.setattr(remaining_context, "read", read)

    with pytest.raises(ValueError, match=message):
        remaining_context._light_cue_pull_context(
            object(), WORKSPACE, EDITED_CUE, "Front = cue 10", {}
        )


def test_pull_context_rejects_source_number_change_during_preflight(monkeypatch):
    snapshot = _snapshot({"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"})
    monkeypatch.setattr(moves, "_read_snapshot", lambda *_args, **_kwargs: snapshot)
    monkeypatch.setattr(
        remaining_context,
        "read",
        lambda *_args, **_kwargs: _source("changed", "Front = 50"),
    )

    with pytest.raises(ValueError, match="changed during preflight"):
        remaining_context._light_cue_pull_context(
            object(), WORKSPACE, EDITED_CUE, "Front = cue 10", {}
        )


def _pull_dependencies(snapshot, text="Front = 50"):
    index = remaining_context._light_pull_number_index(snapshot, ["10"])
    return {
        "light_pull_sources": {
            SOURCE_CUE: {
                "uniqueID": SOURCE_CUE,
                "number": "10",
                "type": "Light",
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        },
        "light_pull_number_index": {
            "numbers": ["10"],
            "fingerprint": _fingerprint(index),
        },
    }


def _check_pull_dependencies(monkeypatch, dependencies, snapshot, source=None):
    monkeypatch.setattr(moves, "_read_snapshot", lambda *_args, **_kwargs: snapshot)
    observed = source or _source()
    monkeypatch.setattr(remaining, "read", lambda *_args, **_kwargs: observed)
    check_dependencies(object(), WORKSPACE, EDITED_CUE, dependencies)


def test_fresh_dependency_check_allows_unrelated_number_changes(monkeypatch):
    source = _source()
    snapshot = _snapshot(
        {"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"},
        {"uniqueID": COLLISION_CUE, "number": "20", "type": "Audio", "name": "unrelated"},
    )

    _check_pull_dependencies(monkeypatch, _pull_dependencies(snapshot), snapshot, source)


def test_fresh_dependency_check_rejects_changed_source_text(monkeypatch):
    snapshot = _snapshot({"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"})
    dependencies = _pull_dependencies(snapshot)

    with pytest.raises(ValueError, match="Light cue pull source changed"):
        _check_pull_dependencies(monkeypatch, dependencies, snapshot, _source(text="Front = 75"))


def test_fresh_dependency_check_rejects_new_same_number_candidate(monkeypatch):
    snapshot = _snapshot({"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"})
    dependencies = _pull_dependencies(snapshot)
    changed_snapshot = _snapshot(
        {"uniqueID": SOURCE_CUE, "number": "10", "type": "Light"},
        {"uniqueID": COLLISION_CUE, "number": "10", "type": "Audio"},
    )

    with pytest.raises(ValueError, match="Light cue pull number resolution changed"):
        _check_pull_dependencies(monkeypatch, dependencies, changed_snapshot)


def test_batch_guard_rejects_editing_a_pull_source_or_its_number():
    pull = {
        "cue_id": EDITED_CUE,
        "properties": {"lightCommandText": "Front = cue 10"},
        "before": {"number": "1"},
        "dependencies": {
            "light_pull_sources": {SOURCE_CUE: {"number": "10", "text_sha256": "hash"}},
            "light_pull_number_index": {"numbers": ["10"]},
        },
    }
    source_text_edit = {
        "cue_id": SOURCE_CUE,
        "properties": {"lightCommandText": "Front = 90"},
        "before": {"number": "10"},
        "dependencies": {},
    }
    source_number_edit = {
        **source_text_edit,
        "properties": {"number": "11"},
    }

    assert control._batch_dependency_conflict([pull, source_text_edit])
    assert control._batch_dependency_conflict([pull, source_number_edit])


class _Reader:
    def _resolve_workspace_id_strict(self, workspace_id):
        return workspace_id


def _preview(monkeypatch, destination_number):
    monkeypatch.setattr(control, "check_write_readiness", lambda *_args: {"ok": True})
    monkeypatch.setattr(control, "_activity_snapshot", lambda *_args: {"active_count": 0})

    def preflight(_reader, _workspace, item, _family):
        changes = item.properties.model_dump(by_alias=True, exclude_unset=True)
        before = {
            key: ("1" if str(item.cue_id) == EDITED_CUE else "20")
            if key == "number"
            else "Front = cue 10"
            for key in changes
        }
        dependencies = (
            {"light_pull_number_index": {"numbers": ["10"], "fingerprint": "baseline"}}
            if str(item.cue_id) == EDITED_CUE
            else {}
        )
        operations = [
            {"property": key, "key": key, "path": key, "args": [value]}
            for key, value in changes.items()
        ]
        return before, changes, operations, dependencies

    monkeypatch.setattr(control, "_preflight", preflight)
    return control.edit_control_cues(
        _Reader(),
        WORKSPACE,
        [
            {"cue_id": EDITED_CUE, "properties": {"lightCommandText": "Front = cue 10"}},
            {"cue_id": COLLISION_CUE, "properties": {"number": destination_number}},
        ],
        dry_run=True,
        _family="light",
    )


def test_rejected_batch_preview_has_no_confirmation_tokens(monkeypatch):
    result = _preview(monkeypatch, "10")

    assert result["status"] == "preflight_failed"
    assert "number changes" in result["results"][0]["errors"]["dependencies"]
    assert all(
        "confirm_token" not in operation
        for cue_result in result["results"]
        for operation in cue_result["planned_operations"]
    )


def test_nonconflicting_batch_preview_still_returns_confirmation_tokens(monkeypatch):
    result = _preview(monkeypatch, "21")

    assert result["status"] == "dry_run"
    assert all(
        operation.get("confirm_token")
        for cue_result in result["results"]
        for operation in cue_result["planned_operations"]
    )
