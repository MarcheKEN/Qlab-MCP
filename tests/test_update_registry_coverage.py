from __future__ import annotations

from pathlib import Path

from qlab_mcp.write.osc_inventory import (
    coverage_summary,
    extract_cue_osc_inventory,
    extract_workspace_video_osc_inventory,
    registry_coverage,
)
from qlab_mcp.write.registry import profile_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_PATH = PROJECT_ROOT / "docs" / "references" / "qlab_osc_dictionary.md"


def test_update_registry_has_specs_for_all_mutating_cue_osc_routes() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    coverage = registry_coverage(inventory, profile_catalog())
    missing = [entry for entry in coverage if entry["registry_status"] == "missing"]

    assert missing == []
    assert coverage_summary(coverage) == {
        "common/global cue properties": {"real_write": 15, "gated": 21},
        "Group/List/Cart": {"real_write": 7, "planned_only": 6},
        "Audio": {"gated": 65, "real_write": 6},
        "Mic": {"gated": 5, "real_write": 2},
        "Video": {"gated": 79},
        "Camera": {"gated": 4, "real_write": 2},
        "Text": {"gated": 19},
        "Light": {"gated": 11},
        "Fade": {"gated": 25},
        "Network": {"gated": 20},
        "MIDI": {"gated": 29},
        "MIDI File": {"gated": 4, "real_write": 1},
        "Timecode": {"gated": 6, "real_write": 3, "planned_only": 2},
        "Reset": {"gated": 3},
        "Devamp": {"gated": 3},
        "Script": {"gated": 1},
    }


def test_audio_time_route_metadata_keeps_profile_specific_policies() -> None:
    catalog = profile_catalog()
    routes = (
        ("rate", "rate"),
        ("startTime", "non_negative_number"),
        ("endTime", "non_negative_number"),
        ("playCount", "positive_int"),
        ("infiniteLoop", "boolean"),
        ("preservePitch", "boolean"),
    )
    policies = (
        ("audio_basic", "safe", True, None, None),
        ("video_basic", "high", False, "video_audio_time_requires_confirm_token", "audio_output"),
    )

    for profile, risk_tier, real_write_enabled, planned_only_reason, capability_gate in policies:
        properties = catalog[profile]["properties"]
        for name, validator in routes:
            property_spec = properties[name]
            assert property_spec["path"] == name
            assert property_spec["args"] == [{"name": "value", "validator": validator}]
            assert property_spec["read_key"] == name
            assert property_spec["modes"] == ["saved"]
            assert property_spec["risk_tier"] == risk_tier
            assert property_spec["real_write_enabled"] is real_write_enabled
            assert property_spec["planned_only_reason"] == planned_only_reason
            assert property_spec["capability_gate"] == capability_gate
            assert property_spec["readback"] == "value"
            assert property_spec["contextual_requirements"] == []


def test_audio_mic_scope_keeps_time_loops_and_format_type_specific() -> None:
    catalog = profile_catalog()
    audio = catalog["audio_basic"]["properties"]
    mic = catalog["mic_basic"]["properties"]

    for property_name in ("rate", "startTime", "endTime", "playCount", "infiniteLoop", "preservePitch"):
        assert audio[property_name]["real_write_enabled"] is True
        assert property_name not in mic

    for property_name in ("audioOutputPatchID", "audioInputPatchID"):
        if property_name == "audioOutputPatchID":
            assert property_name in audio
        assert property_name in mic
        assert mic[property_name]["real_write_enabled"] is False

    assert mic["channelOffset"]["planned_only_reason"] == "audio_input_channel_offset_needs_patch_bounds_validation"
    assert mic["channels"]["planned_only_reason"] == "audio_input_channel_count_needs_patch_bounds_validation"


def test_updateq_coverage_snapshot_doc_matches_summary() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    summary = coverage_summary(registry_coverage(inventory, profile_catalog()))
    snapshot = (PROJECT_ROOT / "docs" / "current" / "coverage" / "osc_coverage_snapshot.md").read_text()

    for section, counts in summary.items():
        expected_row = (
            f"| {section} | {counts.get('real_write', 0)} | {counts.get('gated', 0)} | "
            f"{counts.get('planned_only', 0)} | {counts.get('missing', 0)} |"
        )
        assert expected_row in snapshot


def test_update_registry_coverage_prefers_exact_indexed_route_matches() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    coverage = registry_coverage(inventory, profile_catalog())
    by_section_property = {(entry["section"], entry["property"]): entry for entry in coverage}

    assert by_section_property[("Audio", "object/{name}/name")]["registry_property"] == "object/name"
    assert by_section_property[("Audio", "object/{name}/colorName")]["registry_property"] == "object/colorName"
    assert by_section_property[("Video", "stage/regionIndex/{index}/bounds/origin")]["registry_property"] == (
        "stage/regionIndex/bounds/origin"
    )
    assert by_section_property[("Video", "videoEffect/{name}/enabled")]["registry_property"] == "videoEffect/enabled"


def test_update_registry_marks_script_source_as_not_editable_by_osc() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    catalog = profile_catalog()

    assert not any(entry["property"] == "scriptSource" for entry in inventory)
    assert catalog["script_basic"]["properties"]["scriptSource"]["planned_only_reason"] == "not_editable_by_osc"
    assert catalog["script_basic"]["properties"]["compileSource"]["capability_gate"] == "script_compile"


def test_video_phase1_inventory_tracks_live_increment_and_deprecation() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    by_property = {(entry["section"], entry["property"]): entry for entry in inventory}

    assert by_property[("Video", "opacity")]["live"] is True
    assert by_property[("Video", "opacity")]["read"] is True
    assert by_property[("Video", "opacity")]["write"] is True
    assert by_property[("Text", "text/format/fontSize")]["increment_decrement"] is True
    assert by_property[("Camera", "cameraPatch")]["deprecated"] is True


def test_workspace_video_inventory_is_explicitly_read_only_or_blocked() -> None:
    inventory = extract_workspace_video_osc_inventory(DICTIONARY_PATH.read_text())
    by_property = {entry["property"]: entry for entry in inventory}

    assert len(inventory) == 118
    assert by_property["inputPatchList"]["mcp_status"] == "read_only"
    assert by_property["routes"]["mcp_status"] == "read_only"
    assert by_property["stage/{current_name}/name"]["mcp_status"] == "blocked"
    assert by_property["undo"]["kind"] == "action"
    assert by_property["undo"]["mcp_status"] == "blocked"


def test_video_phase1_matrix_documents_required_columns_and_blocked_families() -> None:
    matrix = (PROJECT_ROOT / "docs" / "current" / "coverage" / "video_phase1_osc_matrix.md").read_text()

    assert "| Area | Property | OSC path | Read | Write | Live | +/- | Deprecated | MCP status | Risk |" in matrix
    assert "`/cue/{cue_number}/cameraPatch`" in matrix
    assert "`/settings/video/undo`, `/redo`" in matrix
    assert "scalar rotation" in matrix
    assert "blocked; removed from Video/Camera registry" in matrix
