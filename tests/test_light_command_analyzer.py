from __future__ import annotations

import pytest

from qlab_mcp.errors import UnsafeWriteOperationError
from qlab_mcp.settings.light_commands import _light_command_line_count, analyze_light_command_text


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


def named_fixtures(prefix: str, count: int, parameters: list[str] | None = None) -> dict:
    parameters = parameters or ["intensity"]
    return {
        "instruments": [
            {
                "name": f"{prefix} {index}",
                "parameter_names": parameters,
                "definition": {"default_parameter_name": parameters[0]},
            }
            for index in range(1, count + 1)
        ],
        "groups": [],
    }


@pytest.mark.parametrize("target", ["Red Fixture", "Back", "all", "[Front,Red Fixture]"])
def test_parameterless_pull_reports_all_potential_parameters(light_patch, target):
    report = analyze_light_command_text(f"{target} = cue A * .5", light_patch,
        cue_references={"A": {"uniqueID": "source", "number": "A", "type": "Light"}})
    result = report["results"][0]
    assert result["status"] in {"valid", "warning"}
    assert {"instrument": "Red Fixture", "parameter": "red"} in result["affected"]
    assert result["parameter"]["defaulted"] is False
    assert result["value"]["dynamic"] is True
    assert report["dynamic_look_computed"] is False


def test_explicit_parameter_pull_keeps_only_requested_parameter(light_patch):
    report = analyze_light_command_text("Red Fixture.red = cue A", light_patch,
        cue_references={"A": {"uniqueID": "source", "number": "A", "type": "Light"}})
    assert report["results"][0]["affected"] == [{"instrument": "Red Fixture", "parameter": "red"}]


@pytest.mark.parametrize("kind,prototype,command", [
    ("rgbcolor", "rgb(0,0,0)", "rgb(20,40,60)"),
    ("cmycolor", "cmy(0,0,0)", "cmy(10,20,30)"),
    ("hsicolor", "hsi(0,0,0)", "hsi(60,30,70)"),
    ("pantilt", "pantilt(0,0)", "pantilt(25,75)")])
def test_native_compound_values_require_exact_parameter_prototype(kind, prototype, command):
    patch = named_fixtures("LED", 2, ["color"])
    patch["parameters"] = [dict(scope="instrument", owner_name=f"LED {n}", name="color",
        type=kind, home_value=prototype) for n in (1,2)]
    result = analyze_light_command_text(f"[LED 1,LED 2].color = {command}", patch)["results"][0]
    assert result["status"] == "valid"
    assert len(result["affected"]) == 2
    assert result["value"]["kind"] == "compound"


@pytest.mark.parametrize("value", ["rgb(20,40)", "rgb(101,0,0)", "rgb(-1,0,0)", "rgb(0,0,0)trailing", "rgb(1+2,0,0)", "rgb(NaN,0,0)"])
def test_compound_values_reject_wrong_arity_range_and_expressions(value):
    patch = named_fixtures("LED", 1, ["color"])
    patch["parameters"] = [dict(scope="instrument", owner_name="LED 1", name="color", type="rgbcolor", home_value="rgb(0,0,0)")]
    assert analyze_light_command_text(f"LED 1.color = {value}", patch)["results"][0]["status"] in {"invalid", "unsupported"}


def test_light_command_text_byte_limit_rejects_without_truncation(light_patch: dict) -> None:
    accepted = "x" * 65_536
    analyze_light_command_text(accepted, light_patch)
    with pytest.raises(UnsafeWriteOperationError, match="lightCommandText exceeds 65536 UTF-8 bytes"):
        analyze_light_command_text(accepted + "x", light_patch)


def test_light_command_text_line_limit_rejects_before_analysis(light_patch: dict) -> None:
    analyze_light_command_text("\n".join("Front = 1" for _ in range(2_000)), light_patch)
    with pytest.raises(UnsafeWriteOperationError, match="exceeds 2000 lines"):
        analyze_light_command_text("\n".join("Front = 1" for _ in range(2_001)), light_patch)


def test_light_command_text_counts_utf8_bytes(light_patch: dict) -> None:
    command = "é" * 32_768
    with pytest.raises(UnsafeWriteOperationError, match="65536 UTF-8 bytes"):
        analyze_light_command_text(command + "é", light_patch)


@pytest.mark.parametrize("command_text", ["", "Front = 1\n", "Front = 1\r\nBack = 2", "Front = 1\u2028Back = 2"])
def test_light_command_line_limit_count_matches_splitlines(command_text: str) -> None:
    assert _light_command_line_count(command_text) == len(command_text.splitlines())


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

    assert result["status"] == "valid"
    assert result["affected"] == [{"instrument": "Red Fixture", "parameter": "red"}]
    assert result["skipped_members"] == [
        {"instrument": "Dimmer Only", "reason": "parameter_unavailable"},
        {"instrument": "No Default", "reason": "parameter_unavailable"},
    ]
    assert result["warnings"] == []


def test_group_explicit_parameter_warns_on_unresolved_member(light_patch: dict) -> None:
    light_patch["groups"][0]["instrument_names"].append("Missing Fixture")

    result = analyze("Back.red = 50", light_patch)

    assert result["status"] == "warning"
    assert result["skipped_members"][-1] == {
        "instrument": "Missing Fixture",
        "reason": "instrument_unavailable",
    }
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


def test_all_is_reserved_and_includes_all_instruments(light_patch: dict) -> None:
    present = analyze("All = 0", light_patch)
    missing = analyze("all = 0", {"instruments": light_patch["instruments"], "groups": []})

    assert present["status"] == "warning"
    assert present["target"]["resolved_name"] == "all"
    assert present["target"]["normalized_match"] is True
    assert {item["instrument"] for item in present["affected"]} == {
        "Front", "Red Fixture", "Dimmer Only", "Front-Left"
    }
    assert missing["status"] == "warning"
    assert {item["instrument"] for item in missing["affected"]} == {
        "Front", "Red Fixture", "Dimmer Only", "Front-Left"
    }


def test_all_home_expands_to_every_parameter(light_patch: dict) -> None:
    result = analyze("all = home", light_patch)

    assert result["status"] == "valid"
    assert result["affected"] == [
        {"instrument": "Front", "parameter": "intensity"},
        {"instrument": "Red Fixture", "parameter": "intensity"},
        {"instrument": "Red Fixture", "parameter": "red"},
        {"instrument": "Dimmer Only", "parameter": "intensity"},
        {"instrument": "No Default", "parameter": "color"},
        {"instrument": "Front-Left", "parameter": "intensity"},
    ]


def test_all_home_expansion_is_bounded_without_partial_results() -> None:
    result = analyze("all = home", named_fixtures("Fixture", 2_001))

    assert result["status"] == "unsupported"
    assert result["errors"][0]["code"] == "target_expansion_limit"
    assert result["affected"] == []


def test_expansion_budget_is_shared_across_all_home_lines() -> None:
    results = analyze_light_command_text(
        "all = home\nall = home", named_fixtures("Fixture", 1_001)
    )["results"]

    assert results[0]["status"] == "valid"
    assert len(results[0]["affected"]) == 1_001
    assert results[1]["status"] == "unsupported"
    assert results[1]["errors"][0]["code"] == "target_expansion_limit"
    assert results[1]["affected"] == []


def test_all_parameter_home_only_affects_that_parameter(light_patch: dict) -> None:
    result = analyze("all.red = home", light_patch)

    assert result["status"] == "valid"
    assert result["affected"] == [{"instrument": "Red Fixture", "parameter": "red"}]


def test_named_numeric_range_expands_inclusive_targets() -> None:
    patch = named_fixtures("Frontal", 3)

    result = analyze("Frontal 1 - Frontal 3 = 25", patch)

    assert result["status"] == "valid"
    assert result["target"]["kind"] == "range"
    assert [item["instrument"] for item in result["affected"]] == ["Frontal 1", "Frontal 2", "Frontal 3"]


@pytest.mark.parametrize(
    ("command", "kind", "expected"),
    [
        ("1-3=50", "range", ["1", "2", "3"]),
        ("[1-3]=50", "ad_hoc_group", ["1", "2", "3"]),
        ("Frontal 1-Frontal 3=25", "range", ["Frontal 1", "Frontal 2", "Frontal 3"]),
        (
            "[Frontal 1-Frontal 3]=25",
            "ad_hoc_group",
            ["Frontal 1", "Frontal 2", "Frontal 3"],
        ),
        (
            "Front-Left 1-Front-Left 3=25",
            "range",
            ["Front-Left 1", "Front-Left 2", "Front-Left 3"],
        ),
    ],
)
def test_compact_numeric_ranges_expand_inclusively(
    command: str, kind: str, expected: list[str]
) -> None:
    patch = {
        "instruments": [
            {
                "name": name,
                "parameter_names": ["intensity"],
                "definition": {"default_parameter_name": "intensity"},
            }
            for name in expected
        ],
        "groups": [],
    }

    result = analyze(command, patch)

    assert result["status"] == "valid"
    assert result["target"]["kind"] == kind
    assert [item["instrument"] for item in result["affected"]] == expected


def test_exact_target_name_precedes_compact_range_parsing() -> None:
    patch = named_fixtures("Frontal", 3)
    patch["instruments"].append(
        {
            "name": "Frontal 1-Frontal 3",
            "parameter_names": ["intensity"],
            "definition": {"default_parameter_name": "intensity"},
        }
    )

    result = analyze("Frontal 1-Frontal 3=25", patch)

    assert result["status"] == "valid"
    assert result["target"]["resolved_name"] == "Frontal 1-Frontal 3"
    assert result["affected"] == [
        {"instrument": "Frontal 1-Frontal 3", "parameter": "intensity"}
    ]


def test_long_hyphen_heavy_non_range_stays_within_command_limit() -> None:
    command = "A1-" * 20_000 + "X=50"

    result = analyze(command, {"instruments": [], "groups": []})

    assert len(command.encode("utf-8")) < 65_536
    assert result["status"] == "invalid"
    assert result["errors"][0]["code"] == "unknown_target"


def test_named_numeric_range_crosses_digit_width_without_padding() -> None:
    patch = named_fixtures("Frontal", 10)

    result = analyze("Frontal 9 - Frontal 10 = 25", patch)

    assert result["status"] == "valid"
    assert [item["instrument"] for item in result["affected"]] == ["Frontal 9", "Frontal 10"]


def test_zero_padded_range_preserves_width() -> None:
    patch = {
        "instruments": [
            {
                "name": f"Frontal {index:02d}",
                "parameter_names": ["intensity"],
                "definition": {"default_parameter_name": "intensity"},
            }
            for index in range(1, 4)
        ],
        "groups": [],
    }

    result = analyze("Frontal 01 - Frontal 03 = 25", patch)

    assert result["status"] == "valid"
    assert [item["instrument"] for item in result["affected"]] == ["Frontal 01", "Frontal 02", "Frontal 03"]


def test_named_target_list_expands_explicit_members() -> None:
    patch = named_fixtures("Frontal", 5)

    result = analyze("Frontal 4, Frontal 5 = 50", patch)

    assert result["status"] == "valid"
    assert result["target"]["kind"] == "list"
    assert [item["instrument"] for item in result["affected"]] == ["Frontal 4", "Frontal 5"]


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("[LED 1 - LED 3].red = 20", ["LED 1", "LED 2", "LED 3"]),
        ("[LED 4, LED 5].blue = 30", ["LED 4", "LED 5"]),
    ],
)
def test_adhoc_group_expands_named_numeric_targets(command: str, expected: list[str]) -> None:
    patch = named_fixtures("LED", 5, ["intensity", "red", "blue"])

    result = analyze(command, patch)

    assert result["status"] == "valid"
    assert result["target"]["kind"] == "ad_hoc_group"
    assert [item["instrument"] for item in result["affected"]] == expected
    assert {item["parameter"] for item in result["affected"]} == {"red" if ".red" in command else "blue"}


@pytest.mark.parametrize("command", ["Frontal 1 - LED 3 = 25", "Frontal 1-LED 3=25"])
def test_target_range_requires_matching_numeric_suffix_prefix(command: str) -> None:
    patch = named_fixtures("Frontal", 3)

    result = analyze(command, patch)

    assert result["status"] == "unsupported"
    assert result["errors"][0]["code"] == "range_or_list"


def test_target_selectors_are_limited_to_known_instruments() -> None:
    patch = named_fixtures("Frontal", 3)

    result = analyze("Frontal 1 - Frontal 3 = 25", {**patch, "groups": [{"name": "Frontal 2", "instrument_names": []}]})

    assert result["status"] == "invalid"
    assert result["errors"][0]["code"] == "ambiguous_target"


def test_target_expansion_is_bounded_to_two_thousand() -> None:
    patch = named_fixtures("Frontal", 2_001)

    single_range = analyze("Frontal 1 - Frontal 2001 = 1", patch)
    cumulative = analyze_light_command_text(
        "Frontal 1 - Frontal 1000 = 1\nFrontal 1001 - Frontal 2001 = 1", patch
    )["results"]

    assert single_range["status"] == "unsupported"
    assert single_range["errors"][0]["code"] == "target_expansion_limit"
    assert cumulative[0]["status"] == "valid"
    assert len(cumulative[0]["affected"]) == 1_000
    assert cumulative[1]["status"] == "unsupported"
    assert cumulative[1]["errors"][0]["code"] == "target_expansion_limit"


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


def test_cue_pull_syntax_is_parsed_and_resolved_without_expansion(light_patch: dict) -> None:
    source_id = "00000000-0000-0000-0000-000000000101"
    result = analyze_light_command_text(
        "Front = cue 101 * 0.5",
        light_patch,
        cue_references={"101": {"uniqueID": source_id, "number": "101", "type": "Light"}},
    )["results"][0]

    assert result["status"] == "valid"
    assert result["value"]["kind"] == "cue_pull"
    assert result["value"]["scale"] == 0.5
    assert result["value"]["source"] == {"cue_id": source_id, "number": "101", "type": "Light"}
    assert result["affected"] == [{"instrument": "Front", "parameter": "intensity"}]


def test_cue_pull_without_unique_reference_is_invalid(light_patch: dict) -> None:
    result = analyze("Front = cue 404", light_patch)

    assert result["status"] == "invalid"
    assert result["errors"][0]["code"] == "unknown_cue_reference"
    assert result["affected"] == []


@pytest.mark.parametrize(
    ("command", "error_code"),
    [
        ("[Front] = 50", "range_or_list"),
        ("Front = cue", "cue_pull_syntax"),
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
