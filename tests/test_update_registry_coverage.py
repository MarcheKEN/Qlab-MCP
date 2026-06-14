from __future__ import annotations

from pathlib import Path

from qlab_mcp.write.osc_inventory import coverage_summary, extract_cue_osc_inventory, registry_coverage
from qlab_mcp.write.registry import profile_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_PATH = PROJECT_ROOT / "references" / "qlab" / "QLab's OSC Dictionary.txt"


def test_update_registry_has_specs_for_all_mutating_cue_osc_routes() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    coverage = registry_coverage(inventory, profile_catalog())
    missing = [entry for entry in coverage if entry["registry_status"] == "missing"]

    assert missing == []
    assert coverage_summary(coverage) == {
        "common/global cue properties": {"real_write": 15, "gated": 21},
        "Group/List/Cart": {"real_write": 7, "planned_only": 6},
        "Audio": {"gated": 65, "real_write": 6},
        "Mic": {"gated": 4, "real_write": 3},
        "Video": {"gated": 66, "real_write": 13},
        "Camera": {"gated": 4, "real_write": 2},
        "Text": {"real_write": 5, "gated": 14},
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


def test_updateq_coverage_snapshot_doc_matches_summary() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    summary = coverage_summary(registry_coverage(inventory, profile_catalog()))
    snapshot = (PROJECT_ROOT / "docs" / "updateq_osc_coverage_snapshot.md").read_text()

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
