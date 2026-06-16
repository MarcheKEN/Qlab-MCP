from __future__ import annotations

from pathlib import Path

from qlab_mcp.cues.coverage import extract_readable_cue_osc_inventory, read_allowlist_coverage, read_coverage_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_PATH = PROJECT_ROOT / "references" / "qlab" / "qlab_osc_dictionary.md"


def test_read_allowlist_coverage_snapshot_matches_qlab_dictionary() -> None:
    report = read_coverage_report(DICTIONARY_PATH.read_text())

    assert report["readable_route_count"] == 509
    assert report["allowlisted_property_count"] == 290
    assert report["gap_count"] == 192
    assert report["status_counts"] == {
        "covered_by_aggregate": 20,
        "covered_by_structural_reader": 4,
        "direct": 293,
        "indexed_read_gap": 90,
        "live_omitted": 66,
        "read_gap": 33,
        "runtime_read_gap": 3,
    }
    assert report["section_status_counts"]["Audio"] == {
        "covered_by_aggregate": 13,
        "direct": 37,
        "indexed_read_gap": 38,
        "live_omitted": 18,
        "read_gap": 21,
        "runtime_read_gap": 3,
    }
    assert report["section_status_counts"]["Fade"] == {
        "direct": 17,
        "indexed_read_gap": 4,
        "read_gap": 4,
    }


def test_read_allowlist_coverage_classifies_every_readable_route() -> None:
    inventory = extract_readable_cue_osc_inventory(DICTIONARY_PATH.read_text())
    coverage = read_allowlist_coverage(inventory)

    assert coverage
    assert all(entry["coverage_status"] for entry in coverage)
    assert not any(entry["coverage_status"] == "unclassified" for entry in coverage)
    assert any(entry["coverage_status"] == "live_omitted" for entry in coverage)
    assert any(entry["coverage_status"] == "indexed_read_gap" for entry in coverage)
