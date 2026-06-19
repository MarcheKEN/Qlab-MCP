"""Read-only analysis of a deliberately small Lighting Command Language subset."""

from __future__ import annotations

import re
from typing import Any


_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _line_result(line: int, source: str) -> dict[str, Any]:
    return {
        "line": line,
        "source": source,
        "status": "unsupported",
        "target": {
            "input": None,
            "resolved_name": None,
            "kind": None,
            "exists": False,
            "normalized_match": False,
        },
        "parameter": {"input": None, "exists": False, "defaulted": False},
        "value": {"kind": "unsupported", "raw": None, "number": None},
        "affected": [],
        "skipped_members": [],
        "warnings": [],
        "errors": [],
    }


def _unsupported(result: dict[str, Any], code: str, message: str) -> dict[str, Any]:
    result["errors"].append(_issue(code, message))
    return result


def _parse_value(raw: str) -> dict[str, Any] | None:
    normalized = raw.casefold()
    if normalized in {"home", "pass"}:
        return {"kind": normalized, "raw": raw, "number": None}
    if not _NUMBER.fullmatch(raw):
        return None
    number: int | float = float(raw)
    if "." not in raw:
        number = int(raw)
    return {"kind": "number", "raw": raw, "number": number}


def _unsupported_syntax(result: dict[str, Any], left: str, right: str) -> dict[str, Any] | None:
    if "[" in left or "]" in left:
        return _unsupported(result, "ad_hoc_group", "Ad-hoc groups are outside the MVP grammar.")
    if "," in left or re.fullmatch(r"\d+\s*-\s*\d+", left):
        return _unsupported(result, "range_or_list", "Ranges and target lists are outside the MVP grammar.")
    if right == "cue" or right.startswith("cue "):
        return _unsupported(result, "cue_pull", "Pulling values from another cue is outside the MVP grammar.")
    if "(" in right or ")" in right:
        return _unsupported(result, "compound_value", "Functions and compound values are outside the MVP grammar.")
    if not _NUMBER.fullmatch(right) and (
        any(operator in right for operator in ("+", "*", "/")) or "-" in right[1:]
    ):
        return _unsupported(result, "expression", "Expressions and operators are outside the MVP grammar.")
    return None


def _targets(light_patch: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    targets: list[tuple[str, dict[str, Any]]] = []
    for kind, key in (("instrument", "instruments"), ("group", "groups")):
        for item in light_patch.get(key, []):
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                targets.append((kind, item))
    return targets


def _resolve_target(
    target_name: str,
    targets: list[tuple[str, dict[str, Any]]],
) -> tuple[str | None, dict[str, Any] | None, bool, str | None]:
    exact = [(kind, target) for kind, target in targets if target["name"] == target_name]
    if len(exact) == 1:
        return exact[0][0], exact[0][1], False, None
    if len(exact) > 1:
        return None, None, False, "ambiguous_target"
    normalized = [(kind, target) for kind, target in targets if target["name"].casefold() == target_name.casefold()]
    if len(normalized) == 1:
        return normalized[0][0], normalized[0][1], True, None
    if len(normalized) > 1:
        return None, None, False, "ambiguous_target"
    return None, None, False, "unknown_target"


def _parameter_names(instrument: dict[str, Any]) -> set[str]:
    return {name for name in instrument.get("parameter_names", []) if isinstance(name, str)}


def _default_parameter(instrument: dict[str, Any]) -> str | None:
    definition = instrument.get("definition")
    if not isinstance(definition, dict):
        return None
    name = definition.get("default_parameter_name")
    return name if isinstance(name, str) and name else None


def _analyze_instrument(
    result: dict[str, Any],
    instrument: dict[str, Any],
    explicit_parameter: str | None,
) -> None:
    parameter = explicit_parameter or _default_parameter(instrument)
    if not parameter or parameter not in _parameter_names(instrument):
        code = "unknown_parameter" if explicit_parameter else "default_parameter_unavailable"
        message = (
            f"Instrument {instrument['name']!r} has no parameter {explicit_parameter!r}."
            if explicit_parameter
            else f"Instrument {instrument['name']!r} has no usable default parameter."
        )
        result["status"] = "invalid"
        result["errors"].append(_issue(code, message))
        return
    result["parameter"]["exists"] = True
    result["affected"].append({"instrument": instrument["name"], "parameter": parameter})


def _analyze_group(
    result: dict[str, Any],
    group: dict[str, Any],
    explicit_parameter: str | None,
    instruments: dict[str, dict[str, Any]],
) -> None:
    for member_name in group.get("instrument_names", []):
        instrument = instruments.get(member_name)
        if instrument is None:
            result["skipped_members"].append({"instrument": member_name, "reason": "instrument_unavailable"})
            continue
        parameter = explicit_parameter or _default_parameter(instrument)
        if not parameter or parameter not in _parameter_names(instrument):
            reason = "parameter_unavailable" if explicit_parameter else "default_parameter_unavailable"
            result["skipped_members"].append({"instrument": member_name, "reason": reason})
            continue
        result["affected"].append({"instrument": member_name, "parameter": parameter})

    result["parameter"]["exists"] = bool(result["affected"])
    if not result["affected"]:
        code = "unknown_parameter" if explicit_parameter else "default_parameter_unavailable"
        result["status"] = "invalid"
        result["errors"].append(_issue(code, f"Group {group['name']!r} has no compatible members."))
    elif result["skipped_members"]:
        result["status"] = "warning"
        result["warnings"].append(
            _issue("group_members_skipped", "Some group members do not expose the requested parameter.")
        )


def _analyze_line(
    line_number: int,
    source: str,
    targets: list[tuple[str, dict[str, Any]]],
    instruments: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = _line_result(line_number, source)
    assignment_count = source.count("=")
    if assignment_count != 1:
        code = "multiple_assignments" if assignment_count > 1 else "unsupported_syntax"
        return _unsupported(result, code, "Exactly one assignment is required per line.")

    left, right = (part.strip() for part in source.split("=", 1))
    if not left or not right:
        return _unsupported(result, "unsupported_syntax", "Target and value are required.")
    unsupported = _unsupported_syntax(result, left, right)
    if unsupported is not None:
        return unsupported
    if left.count(".") > 1:
        return _unsupported(result, "unsupported_syntax", "Only one target.parameter separator is supported.")

    if "." in left:
        target_input, parameter_input = (part.strip() for part in left.split(".", 1))
        if not target_input or not parameter_input:
            return _unsupported(result, "unsupported_syntax", "Target and parameter names cannot be empty.")
    else:
        target_input, parameter_input = left, None

    value = _parse_value(right)
    if value is None:
        return _unsupported(result, "unsupported_syntax", "Value is outside the MVP grammar.")

    result["target"]["input"] = target_input
    result["parameter"].update({"input": parameter_input, "defaulted": parameter_input is None})
    result["value"] = value

    kind, target, normalized_match, error = _resolve_target(target_input, targets)
    if error:
        result["status"] = "invalid"
        message = (
            f"Target {target_input!r} matches multiple instruments or groups."
            if error == "ambiguous_target"
            else f"Target {target_input!r} does not exist in the Light Patch."
        )
        result["errors"].append(_issue(error, message))
        return result

    assert kind is not None and target is not None
    result["status"] = "warning" if normalized_match else "valid"
    result["target"].update(
        {
            "resolved_name": target["name"],
            "kind": kind,
            "exists": True,
            "normalized_match": normalized_match,
        }
    )
    if normalized_match:
        result["warnings"].append(
            _issue("normalized_target_match", "Target matched by unique case-insensitive comparison.")
        )

    if kind == "instrument":
        _analyze_instrument(result, target, parameter_input)
    else:
        _analyze_group(result, target, parameter_input, instruments)
    return result


def analyze_light_command_text(command_text: str, light_patch: dict[str, Any]) -> dict[str, Any]:
    """Analyze simple LCL assignments against normalized safe Light Patch details."""

    if not isinstance(command_text, str):
        raise TypeError("command_text must be a string")
    if not isinstance(light_patch, dict):
        raise TypeError("light_patch must be a dictionary")

    lines = command_text.splitlines()
    targets = _targets(light_patch)
    instruments = {
        instrument["name"]: instrument
        for kind, instrument in targets
        if kind == "instrument"
    }
    results = [
        _analyze_line(line_number, source, targets, instruments)
        for line_number, source in enumerate(lines, start=1)
        if source.strip()
    ]
    return {"line_count": len(lines), "analyzed_count": len(results), "results": results}
