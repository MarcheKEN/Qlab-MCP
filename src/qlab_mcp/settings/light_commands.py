"""Read-only analysis of a deliberately small Lighting Command Language subset."""

from __future__ import annotations

import re
import math
from typing import Any

from ..errors import UnsafeWriteOperationError


_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
_CUE_PULL = re.compile(r"cue\s+([^\s*]+)(?:\s*\*\s*(" + _NUMBER.pattern + r"))?", re.IGNORECASE)
_LINE_BREAK = re.compile(r"\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
MAX_LIGHT_COMMAND_TEXT_BYTES = 65_536
MAX_LIGHT_COMMAND_LINES = 2_000
MAX_LIGHT_ANALYSIS_RESULTS = 2_000


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


def _expansion_limit(result: dict[str, Any]) -> None:
    result["affected"].clear()
    result["parameter"]["exists"] = False
    result["status"] = "unsupported"
    result["errors"].append(
        _issue("target_expansion_limit", f"Affected targets exceed the {MAX_LIGHT_ANALYSIS_RESULTS}-item analysis limit.")
    )


def _parse_value(raw: str) -> dict[str, Any] | None:
    normalized = raw.casefold()
    if normalized in {"home", "pass"}:
        return {"kind": normalized, "raw": raw, "number": None}
    compound = re.fullmatch(r"([A-Za-z]+)\(([^()]*)\)", raw)
    if compound:
        parts = [part.strip() for part in compound[2].split(",")]
        if not 1 <= len(parts) <= 16 or any(not _NUMBER.fullmatch(part) for part in parts):
            return None
        components = [float(part) for part in parts]
        if any(not math.isfinite(part) for part in components):
            return None
        return dict(kind="compound", raw=raw, number=None, identifier=compound[1], components=components)
    pull = _CUE_PULL.fullmatch(raw)
    if pull:
        scale = float(pull.group(2)) if pull.group(2) is not None else 1.0
        if not math.isfinite(scale):
            return None
        return {
            "kind": "cue_pull",
            "raw": raw,
            "number": None,
            "cue_number": pull.group(1),
            "scale": scale,
        }
    if not _NUMBER.fullmatch(raw):
        return None
    number: int | float = float(raw)
    if "." not in raw:
        number = int(raw)
    return {"kind": "number", "raw": raw, "number": number}


def _unsupported_syntax(result: dict[str, Any], left: str, right: str) -> dict[str, Any] | None:
    if _parse_value(right) is not None:
        return None
    if re.match(r"cue(?:\s|$)", right, re.IGNORECASE) and _parse_value(right) is None:
        return _unsupported(result, "cue_pull_syntax", "Cue pulls must use 'cue NUMBER' with an optional '* SCALE'.")
    if "(" in right or ")" in right:
        return _unsupported(result, "compound_value", "Functions and compound values are outside the MVP grammar.")
    if not _NUMBER.fullmatch(right) and (
        any(operator in right for operator in ("+", "*", "/")) or "-" in right[1:]
    ):
        return _unsupported(result, "expression", "Expressions and operators are outside the MVP grammar.")
    return None


def _compact_range_parts(expression: str) -> tuple[tuple[str, str, str, str] | None, str | None]:
    """Find one matching-prefix numeric range without backtracking over hyphens."""
    end_digits_start = len(expression)
    while end_digits_start and expression[end_digits_start - 1].isdecimal():
        end_digits_start -= 1
    if end_digits_start == len(expression):
        return None, None

    candidate_found = False
    for separator, character in enumerate(expression):
        if character != "-":
            continue
        start_digits_end = separator
        while start_digits_end and expression[start_digits_end - 1].isspace():
            start_digits_end -= 1
        start_digits_start = start_digits_end
        while start_digits_start and expression[start_digits_start - 1].isdecimal():
            start_digits_start -= 1
        if start_digits_start == start_digits_end:
            continue
        candidate_found = True

        end_prefix_start = separator + 1
        while end_prefix_start < end_digits_start and expression[end_prefix_start].isspace():
            end_prefix_start += 1
        if start_digits_start == end_digits_start - end_prefix_start:
            # Left-prefix length increases while right-prefix length decreases, so this is the only full comparison.
            if expression[:start_digits_start] == expression[end_prefix_start:end_digits_start]:
                return (
                    expression[:start_digits_start],
                    expression[start_digits_start:start_digits_end],
                    expression[end_prefix_start:end_digits_start],
                    expression[end_digits_start:],
                ), None

    if candidate_found:
        return None, "Only ranges with matching names and numeric suffixes are supported."
    return None, None


def _selector(
    left: str,
    targets: list[tuple[str, dict[str, Any]]] | None = None,
) -> tuple[str | None, list[str] | None, str | None, str | None]:
    """Parse documented target lists/ranges using exact instrument names."""
    explicit_parameter = None
    ad_hoc = left.startswith("[")
    if ad_hoc:
        end = left.find("]")
        if end < 0 or "]" in left[end + 1 :]:
            return None, None, None, "Malformed ad-hoc group."
        expression = left[1:end].strip()
        suffix = left[end + 1 :].strip()
        if suffix:
            if not suffix.startswith(".") or not suffix[1:].strip():
                return None, None, None, "Ad-hoc group parameter syntax is invalid."
            explicit_parameter = suffix[1:].strip()
    else:
        if left.count(".") > 1:
            return None, None, None, None
        expression, separator, parameter = left.partition(".")
        if separator:
            explicit_parameter = parameter.strip()
            if not explicit_parameter:
                return None, None, None, "Target and parameter names cannot be empty."
        expression = expression.strip()

    if "," in expression:
        names = [name.strip() for name in expression.split(",")]
        if not names or any(not name for name in names):
            return None, None, None, "Target list contains an empty name."
        kind = "ad_hoc_group" if ad_hoc else "list"
        return kind, names, explicit_parameter, None

    if not ad_hoc and targets is not None:
        _, _, _, target_error = _resolve_target(expression, targets)
        if target_error != "unknown_target":
            return None, None, None, None

    range_parts, range_error = _compact_range_parts(expression)
    if range_error:
        return None, None, None, range_error
    if range_parts is not None:
        start_prefix, start_digits, end_prefix, end_digits = range_parts
        if start_prefix != end_prefix:
            return None, None, None, "Only ranges with matching names and numeric suffixes are supported."
        try:
            first, last = int(start_digits), int(end_digits)
        except ValueError:
            return None, None, None, "Target range indices are outside the supported numeric size."
        padded_start = len(start_digits) > len(str(first))
        padded_end = len(end_digits) > len(str(last))
        if padded_start != padded_end or (padded_start and len(start_digits) != len(end_digits)):
            return None, None, None, "Zero-padded target range endpoints must use the same numeric width."
        if first > last:
            return None, None, None, "Descending target ranges are not supported."
        if last - first + 1 > MAX_LIGHT_ANALYSIS_RESULTS:
            return None, None, None, f"Target expansion exceeds the {MAX_LIGHT_ANALYSIS_RESULTS}-target analysis limit."
        kind = "ad_hoc_group" if ad_hoc else "range"
        width = len(start_digits) if padded_start else 0
        names = [f"{start_prefix}{number:0{width}d}" for number in range(first, last + 1)]
        return kind, names, explicit_parameter, None

    if ad_hoc:
        return None, None, None, "Ad-hoc groups require a range or list."
    return None, None, None, None


def _targets(light_patch: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    targets: list[tuple[str, dict[str, Any]]] = []
    parameters = {}
    for spec in light_patch.get("parameters", []):
        if isinstance(spec, dict) and spec.get("scope") == "instrument":
            key = spec.get("owner_name"), spec.get("name")
            parameters[key] = spec if key not in parameters else {}
    for kind, key in (("instrument", "instruments"), ("group", "groups")):
        for item in light_patch.get(key, []):
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                if kind == "instrument":
                    item = {**item, "_parameter_info": {name:parameters.get((item["name"],name), {})
                             for name in item.get("parameter_names", [])}}
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


def _compound_compatible(result, instrument, parameter):
    value = result["value"]
    if value["kind"] != "compound":
        return True
    spec = instrument.get("_parameter_info", {}).get(parameter, {})
    prefix = {"rgbcolor":"rgb", "cmycolor":"cmy", "hsicolor":"hsi", "pantilt":"pantilt"}.get(spec.get("type"))
    prototype = _parse_value(spec["home_value"]) if isinstance(spec.get("home_value"), str) else None
    if not prefix or not prototype or prototype["kind"] != "compound" or not prototype["identifier"].startswith(prefix):
        _unsupported(result, "compound_value", "Compound parameter type/formatter has no verified native prototype.")
        result["status"] = "unsupported"
        result["target"].update(resolved_name=None, exists=False)
        result["parameter"]["exists"] = False
        result["affected"].clear()
        return False
    if (value["identifier"] != prototype["identifier"] or len(value["components"]) != len(prototype["components"])
            or any(not 0 <= component <= 100 for component in value["components"])):
        result["status"] = "invalid"
        result["errors"].append(_issue("compound_value_mismatch", "Compound identifier, arity or 0–100 components do not match the native parameter."))
        return False
    return True


def _analyze_instrument(
    result: dict[str, Any],
    instrument: dict[str, Any],
    explicit_parameter: str | None,
    expansion_budget: int,
) -> None:
    if explicit_parameter is None and result["value"]["kind"] == "cue_pull":
        parameters = sorted(_parameter_names(instrument))
        if len(result["affected"]) + len(parameters) > expansion_budget:
            _expansion_limit(result)
            return
        result["affected"].extend({"instrument": instrument["name"], "parameter": name} for name in parameters)
        result["parameter"]["exists"] = bool(parameters)
        if not parameters:
            result["status"] = "invalid"
            result["errors"].append(_issue("parameters_unavailable", "Instrument parameters are unavailable."))
        return
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
    if not _compound_compatible(result, instrument, parameter):
        return
    if len(result["affected"]) >= expansion_budget:
        _expansion_limit(result)
        return
    result["affected"].append({"instrument": instrument["name"], "parameter": parameter})


def _analyze_group(
    result: dict[str, Any],
    group: dict[str, Any],
    explicit_parameter: str | None,
    instruments: dict[str, dict[str, Any]],
    *,
    expansion_budget: int,
    all_home: bool = False,
) -> None:
    for member_name in group.get("instrument_names", []):
        instrument = instruments.get(member_name)
        if instrument is None:
            result["skipped_members"].append({"instrument": member_name, "reason": "instrument_unavailable"})
            continue
        parameters = _parameter_names(instrument)
        if all_home or (explicit_parameter is None and result["value"]["kind"] == "cue_pull"):
            if not parameters:
                result["skipped_members"].append({"instrument": member_name, "reason": "parameters_unavailable"})
                continue
            for parameter in sorted(parameters):
                if len(result["affected"]) >= expansion_budget:
                    _expansion_limit(result)
                    return
                result["affected"].append({"instrument": member_name, "parameter": parameter})
            continue
        parameter = explicit_parameter or _default_parameter(instrument)
        if not parameter or parameter not in parameters:
            reason = "parameter_unavailable" if explicit_parameter else "default_parameter_unavailable"
            result["skipped_members"].append({"instrument": member_name, "reason": reason})
            continue
        if not _compound_compatible(result, instrument, parameter):
            return
        if len(result["affected"]) >= expansion_budget:
            _expansion_limit(result)
            return
        result["affected"].append({"instrument": member_name, "parameter": parameter})

    result["parameter"]["exists"] = bool(result["affected"])
    if not result["affected"]:
        code = "unknown_parameter" if explicit_parameter else "default_parameter_unavailable"
        result["status"] = "invalid"
        result["errors"].append(_issue(code, f"Group {group['name']!r} has no compatible members."))
    elif result["skipped_members"] and (
        not explicit_parameter
        or any(member["reason"] != "parameter_unavailable" for member in result["skipped_members"])
    ):
        result["status"] = "warning"
        result["warnings"].append(
            _issue("group_members_skipped", "Some group members do not expose the requested parameter.")
        )


def _analyze_line(
    line_number: int,
    source: str,
    targets: list[tuple[str, dict[str, Any]]],
    instruments: dict[str, dict[str, Any]],
    expansion_budget: int,
    cue_references: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = _line_result(line_number, source)
    assignment_count = source.count("=")
    if assignment_count != 1:
        code = "multiple_assignments" if assignment_count > 1 else "unsupported_syntax"
        return _unsupported(result, code, "Exactly one assignment is required per line.")

    left, right = (part.strip() for part in source.split("=", 1))
    if not left or not right:
        return _unsupported(result, "unsupported_syntax", "Target and value are required.")
    selector_kind, selector_names, selector_parameter, selector_error = _selector(left, targets)
    if selector_error:
        code = "target_expansion_limit" if selector_error.startswith("Target expansion exceeds") else "range_or_list"
        return _unsupported(result, code, selector_error)
    unsupported = _unsupported_syntax(result, left, right)
    if unsupported is not None:
        return unsupported
    if selector_kind is None and left.count(".") > 1:
        return _unsupported(result, "unsupported_syntax", "Only one target.parameter separator is supported.")

    if selector_kind is not None:
        target_input, parameter_input = left, selector_parameter
    elif "." in left:
        target_input, parameter_input = (part.strip() for part in left.split(".", 1))
        if not target_input or not parameter_input:
            return _unsupported(result, "unsupported_syntax", "Target and parameter names cannot be empty.")
    else:
        target_input, parameter_input = left, None

    value = _parse_value(right)
    if value is None:
        return _unsupported(result, "unsupported_syntax", "Value is outside the MVP grammar.")
    if value["kind"] == "cue_pull":
        reference = (cue_references or {}).get(value["cue_number"])
        if reference is None:
            result["status"] = "invalid"
            return _unsupported(result, "unknown_cue_reference", f"Cue {value['cue_number']!r} could not be resolved uniquely.")
        if reference.get("type") != "Light":
            result["status"] = "invalid"
            return _unsupported(result, "cue_reference_type", "A Light command may pull only from another Light cue.")
        value["source"] = {
            "cue_id": reference["uniqueID"],
            "number": reference["number"],
            "type": reference["type"],
        }
        value["dynamic"] = True

    result["target"]["input"] = target_input
    result["parameter"].update({"input": parameter_input, "defaulted": parameter_input is None and value["kind"] != "cue_pull"})
    result["value"] = value

    if selector_kind is not None and selector_names is not None:
        if len(selector_names) > expansion_budget:
            return _unsupported(
                result,
                "target_expansion_limit",
                f"Target expansion exceeds the {MAX_LIGHT_ANALYSIS_RESULTS}-target analysis limit.",
            )
        resolved_targets = []
        normalized_matches = []
        for name in selector_names:
            member_kind, member, normalized, error = _resolve_target(name, targets)
            if error:
                result["status"] = "invalid"
                result["errors"].append(_issue(error, f"Selector target {name!r} could not be resolved."))
                return result
            if member_kind != "instrument" or member is None:
                result["status"] = "unsupported"
                result["errors"].append(
                    _issue("selector_requires_instruments", "Selectors may contain only exact instrument targets.")
                )
                return result
            resolved_targets.append(member)
            normalized_matches.append(normalized)
        result["status"] = "warning" if any(normalized_matches) else "valid"
        result["target"].update(
            {
                "resolved_name": ", ".join(item["name"] for item in resolved_targets),
                "kind": selector_kind,
                "exists": True,
                "normalized_match": any(normalized_matches),
            }
        )
        if any(normalized_matches):
            result["warnings"].append(
                _issue("normalized_target_match", "Selector target matched by case-insensitive comparison.")
            )
        for instrument in resolved_targets:
            _analyze_instrument(result, instrument, parameter_input, expansion_budget)
            if result["status"] == "unsupported":
                return result
        return result

    all_group = None
    if target_input.casefold() == "all":
        all_group = {
            "name": "all",
            "instrument_names": list(instruments),
        }
    kind, target, normalized_match, error = _resolve_target(target_input, targets)
    if all_group is not None:
        kind, target, normalized_match, error = "group", all_group, target_input != "all", None
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
        _analyze_instrument(result, target, parameter_input, expansion_budget)
    else:
        _analyze_group(
            result,
            target,
            parameter_input,
            instruments,
            expansion_budget=expansion_budget,
            all_home=target["name"] == "all" and parameter_input is None and value["kind"] == "home",
        )
    return result


def _light_command_line_count(command_text: str) -> int:
    if not command_text:
        return 0
    break_count = 0
    last_break_end = 0
    for match in _LINE_BREAK.finditer(command_text):
        break_count += 1
        last_break_end = match.end()
    return break_count if break_count and last_break_end == len(command_text) else break_count + 1


def validate_light_command_text_limits(command_text: str) -> None:
    if not isinstance(command_text, str):
        raise TypeError("command_text must be a string")
    encoded_size = len(command_text.encode("utf-8"))
    if encoded_size > MAX_LIGHT_COMMAND_TEXT_BYTES:
        raise UnsafeWriteOperationError(
            f"lightCommandText exceeds {MAX_LIGHT_COMMAND_TEXT_BYTES} UTF-8 bytes",
            error_code="light_command_input_too_large",
        )
    line_count = _light_command_line_count(command_text)
    if line_count > MAX_LIGHT_COMMAND_LINES:
        raise UnsafeWriteOperationError(
            f"lightCommandText exceeds {MAX_LIGHT_COMMAND_LINES} lines",
            error_code="light_command_input_too_large",
        )


def analyze_light_command_text(
    command_text: str,
    light_patch: dict[str, Any],
    *,
    cue_references: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze the MVP LCL subset; ``valid`` means MVP-subset-valid, not QLab execution validity."""

    if not isinstance(command_text, str):
        raise TypeError("command_text must be a string")
    if not isinstance(light_patch, dict):
        raise TypeError("light_patch must be a dictionary")

    validate_light_command_text_limits(command_text)
    lines = command_text.splitlines()
    if sum(1 for source in lines if source.strip()) > MAX_LIGHT_ANALYSIS_RESULTS:
        raise UnsafeWriteOperationError(
            f"lightCommandText analysis exceeds {MAX_LIGHT_ANALYSIS_RESULTS} results",
            error_code="light_command_input_too_large",
        )
    targets = _targets(light_patch)
    instruments = {
        instrument["name"]: instrument
        for kind, instrument in targets
        if kind == "instrument"
    }
    results = []
    expansion_budget = MAX_LIGHT_ANALYSIS_RESULTS
    for line_number, source in enumerate(lines, start=1):
        if not source.strip():
            continue
        result = _analyze_line(line_number, source, targets, instruments, expansion_budget, cue_references)
        results.append(result)
        if result["status"] in {"valid", "warning"}:
            expansion_budget -= len(result["affected"])
    has_dynamic_pull = any(result["value"].get("kind") == "cue_pull" for result in results)
    return {
        "line_count": len(lines),
        "analyzed_count": len(results),
        "results": results,
        "dynamic_references_present": has_dynamic_pull,
        "dynamic_look_computed": False if has_dynamic_pull else None,
    }


def light_cue_references(command_text: str) -> list[str]:
    """Return cue numbers used by the supported pull syntax, preserving spelling."""
    validate_light_command_text_limits(command_text)
    references = []
    for source in command_text.splitlines():
        if not source.strip():
            continue
        if source.count("=") != 1:
            if re.search(r"\bcue\b", source, re.IGNORECASE):
                raise UnsafeWriteOperationError("Cue pull syntax must use one assignment per line.")
            continue
        _, right = (part.strip() for part in source.split("=", 1))
        if not re.search(r"\bcue\b", right, re.IGNORECASE):
            continue
        value = _parse_value(right)
        if value is None or value.get("kind") != "cue_pull":
            raise UnsafeWriteOperationError("Cue pulls must use 'cue NUMBER' with an optional '* SCALE'.")
        references.append(value["cue_number"])
    return references
