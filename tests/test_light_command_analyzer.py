from __future__ import annotations

import pytest

from qlab_mcp.settings.light_commands import analyze_light_command_text


@pytest.fixture
def light_patch() -> dict:
    return {
        "instruments": [
            {
                "name": "Front",
                "parameter_names": ["intensity"],
                "definition": {"default_parameter_name": "intensity"},
            },
            {
                "name": "Red Fixture",
                "parameter_names": ["intensity", "red"],
                "definition": {"default_parameter_name": "intensity"},
            },
            {
                "name": "Dimmer Only",
                "parameter_names": ["intensity"],
                "definition": {"default_parameter_name": "intensity"},
            },
            {
                "name": "No Default",
                "parameter_names": ["color"],
                "definition": {"default_parameter_name": None},
            },
            {
                "name": "Front-Left",
                "parameter_names": ["intensity"],
                "definition": {"default_parameter_name": "intensity"},
            },
        ],
        "groups": [
            {
                "name": "Back",
                "instrument_names": ["Red Fixture", "Dimmer Only", "No Default"],
                "parameter_names": ["intensity", "red", "color"],
            },
            {"name": "all", "instrument_names": ["Front", "Red Fixture"], "parameter_names": ["intensity", "red"]},
        ],
    }


def analyze(command: str, light_patch: dict) -> dict:
    return analyze_light_command_text(command, light_patch)["results"][0]


def test_empty_patch_returns_unknown_target() -> None:
    result = analyze("Front = 100", {"instruments": [], "groups": []})

    assert result["status"] == "invalid"
    assert result["errors"][0]["code"] == "unknown_target"
    assert result["affected"] == []


@pytest.mark.parametrize(
    ("command", "value_kind", "value_number"),
    [
        ("Front = 100", "number", 100),
        ("Front = home", "home", None),
        ("Front=-10.5", "number", -10.5),
        ("Front = +2", "number", 2),
    ],
)
def test_instrument_uses_explicit_or_default_parameter(
    light_patch: dict, command: str, value_kind: str, value_number: int | float | None
) -> None:
    result = analyze(command, light_patch)

    assert result["status"] == "valid"
    assert result["parameter"] == {"input": None, "exists": True, "defaulted": True}
    assert result["value"]["kind"] == value_kind
    assert result["value"]["number"] == value_number
    assert result["affected"] == [{"instrument": "Front", "parameter": "intensity"}]


def test_group_explicit_parameter_skips_incompatible_members(light_patch: dict) -> None:
    result = analyze("Back.red = 50", light_patch)

    assert result["status"] == "warning"
    assert result["affected"] == [{"instrument": "Red Fixture", "parameter": "red"}]
    assert result["skipped_members"] == [
        {"instrument": "Dimmer Only", "reason": "parameter_unavailable"},
        {"instrument": "No Default", "reason": "parameter_unavailable"},
    ]
    assert result["warnings"][0]["code"] == "group_members_skipped"


def test_group_pass_uses_each_member_default(light_patch: dict) -> None:
    result = analyze("Back = pass", light_patch)

    assert result["status"] == "warning"
    assert result["value"] == {"kind": "pass", "raw": "pass", "number": None}
    assert result["affected"] == [
        {"instrument": "Red Fixture", "parameter": "intensity"},
        {"instrument": "Dimmer Only", "parameter": "intensity"},
    ]
    assert result["skipped_members"] == [
        {"instrument": "No Default", "reason": "default_parameter_unavailable"}
    ]


@pytest.mark.parametrize(("raw", "kind"), [("HOME", "home"), ("Pass", "pass")])
def test_symbolic_values_are_case_insensitive_and_preserve_raw(light_patch: dict, raw: str, kind: str) -> None:
    result = analyze(f"Front = {raw}", light_patch)

    assert result["status"] == "valid"
    assert result["value"] == {"kind": kind, "raw": raw, "number": None}


def test_hyphenated_target_name_is_not_treated_as_range(light_patch: dict) -> None:
    result = analyze("Front-Left = 50", light_patch)

    assert result["status"] == "valid"
    assert result["target"]["resolved_name"] == "Front-Left"


def test_all_is_only_resolved_when_group_exists(light_patch: dict) -> None:
    present = analyze("All = 0", light_patch)
    missing = analyze("All = 0", {"instruments": light_patch["instruments"], "groups": []})

    assert present["status"] == "warning"
    assert present["target"]["resolved_name"] == "all"
    assert present["target"]["normalized_match"] is True
    assert missing["status"] == "invalid"
    assert missing["errors"][0]["code"] == "unknown_target"


@pytest.mark.parametrize(
    ("command", "error_code"),
    [
        ("Unknown = 50", "unknown_target"),
        ("Front.red = 50", "unknown_parameter"),
        ("No Default = 50", "default_parameter_unavailable"),
    ],
)
def test_invalid_targets_and_parameters(light_patch: dict, command: str, error_code: str) -> None:
    result = analyze(command, light_patch)

    assert result["status"] == "invalid"
    assert result["errors"][0]["code"] == error_code
    assert result["affected"] == []


def test_unique_case_insensitive_match_is_warning(light_patch: dict) -> None:
    result = analyze("front = 25", light_patch)

    assert result["status"] == "warning"
    assert result["target"]["resolved_name"] == "Front"
    assert result["target"]["normalized_match"] is True
    assert result["warnings"][0]["code"] == "normalized_target_match"


def test_ambiguous_case_insensitive_match_is_invalid() -> None:
    patch = {
        "instruments": [{"name": "Front", "parameter_names": ["intensity"]}],
        "groups": [{"name": "FRONT", "instrument_names": [], "parameter_names": []}],
    }

    result = analyze("front = 25", patch)

    assert result["status"] == "invalid"
    assert result["errors"][0]["code"] == "ambiguous_target"


def test_line_numbers_and_source_are_preserved(light_patch: dict) -> None:
    result = analyze_light_command_text("\n  Front = 100  \n\nBack.red=50", light_patch)

    assert result["line_count"] == 4
    assert result["analyzed_count"] == 2
    assert [(item["line"], item["source"]) for item in result["results"]] == [
        (2, "  Front = 100  "),
        (4, "Back.red=50"),
    ]


@pytest.mark.parametrize(
    ("command", "error_code"),
    [
        ("1 - 3 = 50", "range_or_list"),
        ("1, 2 = 50", "range_or_list"),
        ("[1 - 3] = 50", "ad_hoc_group"),
        ("Front = cue A", "cue_pull"),
        ("Front = rgb(1, 2, 3)", "compound_value"),
        ("Front = 50 + 10", "expression"),
        ("Front = 1 = 2", "multiple_assignments"),
        ("Front.red.extra = 1", "unsupported_syntax"),
        ("Front", "unsupported_syntax"),
    ],
)
def test_unsupported_syntax_never_partially_resolves(command: str, error_code: str, light_patch: dict) -> None:
    result = analyze(command, light_patch)

    assert result["status"] == "unsupported"
    assert result["errors"][0]["code"] == error_code
    assert result["target"]["resolved_name"] is None
    assert result["affected"] == []
