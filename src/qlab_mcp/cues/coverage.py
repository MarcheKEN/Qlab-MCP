"""Read coverage inventory for QLab cue OSC routes."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ..allowlist import READ_ONLY_CUE_PROPERTIES
from ..write.osc_inventory import _access_row, _arg_names, _route_only, _section_ranges, _suffix, normalize_registry_key


READ_COVERAGE_NOTE = (
    "profile='exhaustive' is the deepest allowlisted read-only cue detail profile. "
    "It is not full parity with every readable route in QLab's OSC Dictionary."
)
DEFAULT_GAP_LIMIT = 8
STRUCTURAL_PREFIXES = (
    "children",
    "children/shallow",
    "children/uniqueIDs",
    "children/uniqueIDs/shallow",
)
AGGREGATE_PREFIXES = (
    "audioMap",
    "currentTimecode",
    "fadeEntries",
    "levels",
    "stage/regions",
    "text/format",
    "videoEffects",
)
RUNTIME_READ_PREFIXES = (
    "currentFileTime",
    "liveAverageLevel",
    "livePeakLevel",
    "peakLevel",
)


def default_qlab_dictionary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "references" / "qlab_osc_dictionary.md"


def extract_readable_cue_osc_inventory(dictionary_text: str) -> list[dict[str, Any]]:
    """Return readable cue OSC routes grouped by official QLab dictionary section."""
    lines = dictionary_text.splitlines()
    entries: list[dict[str, Any]] = []
    for start, end, section in _section_ranges(lines):
        line_index = start + 1
        while line_index < end:
            if not lines[line_index].startswith("/cue/{cue_number}"):
                line_index += 1
                continue
            route_group: list[str] = []
            group_index = line_index
            while group_index < end and lines[group_index].startswith("/cue/{cue_number}"):
                route_group.append(_route_only(lines[group_index]))
                group_index += 1
            access_row = _access_row(lines, group_index, end)
            if "read" in access_row:
                for route in route_group:
                    suffix = _suffix(route)
                    entries.append(
                        {
                            "section": section,
                            "route": route,
                            "property": suffix,
                            "normalized_property": _normalize_read_key(suffix),
                            "base_property": _normalize_read_key(suffix.removesuffix("/live")),
                            "args": _arg_names(lines[line_index]),
                            "access": access_row,
                            "line": line_index + 1,
                            "live": suffix.endswith("/live"),
                            "templated": "{" in suffix,
                        }
                    )
            line_index = group_index
    return entries


def read_allowlist_coverage(
    inventory: list[dict[str, Any]],
    allowlist: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = {_normalize_read_key(item) for item in (allowlist or READ_ONLY_CUE_PROPERTIES)}
    return [{**entry, **_classify_read_entry(entry, allowed)} for entry in inventory]


def read_coverage_summary(coverage: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for entry in coverage:
        status = entry["coverage_status"]
        summary[status] = summary.get(status, 0) + 1
    return dict(sorted(summary.items()))


def read_coverage_section_summary(coverage: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for entry in coverage:
        section = entry["section"]
        status = entry["coverage_status"]
        summary.setdefault(section, {})
        summary[section][status] = summary[section].get(status, 0) + 1
    return {section: dict(sorted(counts.items())) for section, counts in summary.items()}


def read_coverage_report(dictionary_text: str, gap_limit: int = DEFAULT_GAP_LIMIT) -> dict[str, Any]:
    inventory = extract_readable_cue_osc_inventory(dictionary_text)
    coverage = read_allowlist_coverage(inventory)
    status_counts = read_coverage_summary(coverage)
    gap_statuses = ("indexed_read_gap", "live_omitted", "read_gap", "runtime_read_gap")
    return {
        "source": "qlab_osc_dictionary",
        "status": "available",
        "note": READ_COVERAGE_NOTE,
        "readable_route_count": len(inventory),
        "allowlisted_property_count": len(READ_ONLY_CUE_PROPERTIES),
        "status_counts": status_counts,
        "section_status_counts": read_coverage_section_summary(coverage),
        "gap_count": sum(status_counts.get(status, 0) for status in gap_statuses),
        "gap_examples": _gap_examples(coverage, gap_statuses, gap_limit),
    }


@lru_cache(maxsize=1)
def default_read_coverage_report() -> dict[str, Any]:
    path = default_qlab_dictionary_path()
    if not path.exists():
        return {
            "source": "qlab_osc_dictionary",
            "status": "unavailable",
            "note": READ_COVERAGE_NOTE,
            "message": "Local QLab OSC Dictionary reference file was not found.",
        }
    return read_coverage_report(path.read_text())


def _classify_read_entry(entry: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    normalized = str(entry["normalized_property"])
    base = str(entry["base_property"])

    if entry["live"]:
        return {
            "coverage_status": "live_omitted",
            "covered_by": _coverage_target(base, allowed),
            "coverage_note": "Live routes expose active values and are not part of saved exhaustive details yet.",
        }
    if normalized in allowed:
        return {"coverage_status": "direct", "covered_by": normalized, "coverage_note": None}
    if normalized.rstrip("/") in allowed:
        return {"coverage_status": "direct_alias", "covered_by": normalized.rstrip("/"), "coverage_note": "Trailing slash alias."}
    structural = _matching_prefix(normalized, STRUCTURAL_PREFIXES)
    if structural:
        return {
            "coverage_status": "covered_by_structural_reader",
            "covered_by": structural,
            "coverage_note": "Read through cue tree/child traversal helpers, not cue detail properties.",
        }
    aggregate = _matching_prefix(normalized, AGGREGATE_PREFIXES)
    if aggregate and aggregate in allowed:
        return {
            "coverage_status": "covered_by_aggregate",
            "covered_by": aggregate,
            "coverage_note": "Covered semantically by a larger aggregate payload.",
        }
    runtime = _matching_prefix(normalized, RUNTIME_READ_PREFIXES)
    if runtime:
        return {
            "coverage_status": "runtime_read_gap",
            "covered_by": None,
            "coverage_note": "Runtime metric not represented in saved cue details.",
        }
    if entry["templated"]:
        return {
            "coverage_status": "indexed_read_gap",
            "covered_by": None,
            "coverage_note": "Route needs channel/object/index arguments and is not modeled as a cue detail family yet.",
        }
    return {
        "coverage_status": "read_gap",
        "covered_by": None,
        "coverage_note": "Readable OSC route is not represented in the current cue detail allowlist.",
    }


def _coverage_target(property_name: str, allowed: set[str]) -> str | None:
    if property_name in allowed:
        return property_name
    if property_name.rstrip("/") in allowed:
        return property_name.rstrip("/")
    aggregate = _matching_prefix(property_name, AGGREGATE_PREFIXES)
    if aggregate and aggregate in allowed:
        return aggregate
    return None


def _matching_prefix(value: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in sorted(prefixes, key=len, reverse=True):
        if value == prefix or value.startswith(f"{prefix}/"):
            return prefix
    return None


def _gap_examples(
    coverage: list[dict[str, Any]],
    statuses: tuple[str, ...],
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    examples: dict[str, list[dict[str, Any]]] = {status: [] for status in statuses}
    for entry in coverage:
        status = entry["coverage_status"]
        if status not in examples or len(examples[status]) >= limit:
            continue
        examples[status].append(
            {
                "section": entry["section"],
                "property": entry["property"],
                "route": entry["route"],
                "line": entry["line"],
                "covered_by": entry.get("covered_by"),
                "note": entry.get("coverage_note"),
            }
        )
    return examples


def _normalize_read_key(value: str) -> str:
    return normalize_registry_key(value).strip("/")
