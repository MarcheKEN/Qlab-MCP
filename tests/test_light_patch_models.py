"""Strict typed Light Patch edits preserve omitted fields and reject ambiguity."""
import importlib

import pytest
from pydantic import TypeAdapter, ValidationError


def models():
    try:
        return importlib.import_module("qlab_mcp.light_patch.models")
    except ModuleNotFoundError:
        pytest.fail("Light Patch operation models are not implemented")


def validate(value):
    return TypeAdapter(models().LightPatchOperations).validate_python(value)


def validate_definitions(value):
    return TypeAdapter(models().DefinitionOperations).validate_python(value)


def test_typed_batch_preserves_omitted_update_fields():
    result = validate([{"action": "update_instrument", "name": "Existing + name", "note": "Updated"}])
    assert result[0].model_dump(exclude_unset=True) == {
        "action": "update_instrument", "name": "Existing + name", "note": "Updated"}


@pytest.mark.parametrize("action, fields", [
    ("create_instrument", {"definition": "Generic Dimmer", "name": "New Instrument"}),
    ("update_instrument", {"definition": "Generic Dimmer"}),
    ("rename_instrument", {"new_name": "New Instrument"}),
    ("delete_instrument", {}),
    ("create_group", {"name": "New Group", "members": ["Instrument"]}),
    ("update_group", {"members": []}),
    ("rename_group", {"new_name": "New Group"}),
    ("delete_group", {}),
    ("create_definition", {"manufacturer": "Example", "parameters": [
        {"type": "scalar", "name": "intensity"}]}),
    ("update_definition", {"default_parameter": None}),
    ("rename_definition", {"new_name": "Example RGB+Dimmer (4ch)"}),
    ("delete_definition", {}),
])
def test_all_supported_actions_have_discriminated_models(action, fields):
    operation = {"action": action, "name": "Existing", **fields}
    parsed = (validate_definitions if action.endswith("_definition") else validate)([operation])[0]
    assert parsed.action == action
    assert parsed.model_dump(exclude_unset=True) == operation


@pytest.mark.parametrize("value", [[], [{"action": "delete_group", "name": "G"}] * 101,
    ({"action": "delete_group", "name": "G"},)])
def test_batch_is_a_bounded_strict_list(value):
    with pytest.raises(ValidationError):
        validate(value)


@pytest.mark.parametrize("extra", [
    {"action": "raw_archive", "name": "G"},
    {"action": "delete_group", "name": "G", "arbitrary_key": True},
    {"action": "update_group", "name": "G", "members": None},
    {"action": "update_instrument", "name": "I", "output": None},
    {"action": "update_instrument", "name": "I", "note": None},
    {"action": "rename_group", "name": "G", "new_name": " Group"},
    {"action": "rename_group", "name": "G", "new_name": "Group!"},
    {"action": "update_definition", "name": "a\x85b", "manufacturer": "M"},
])
def test_ambiguous_or_unknown_input_is_rejected(extra):
    with pytest.raises(ValidationError):
        validate([extra])


def artnet(**values):
    return {"backend": "artnet", "net": 0, "subnet": 0, "universe": 0, "address": 1, **values}


@pytest.mark.parametrize("values", [{"address": 0}, {"address": 513}, {"address": True},
    {"address": "1"}, {"net": 128}, {"net": -1}, {"subnet": 16}, {"universe": 16}])
def test_artnet_rejects_out_of_range_and_coerced_numbers(values):
    with pytest.raises(ValidationError):
        validate([{"action": "update_instrument", "name": "I", "output": artnet(**values)}])


def test_outputs_include_explicit_unpatch_and_exact_usb_identity():
    unpatch = validate([{"action": "update_instrument", "name": "I", "output": {"backend": "none"}}])[0]
    assert unpatch.output.backend == "none"
    output = {"backend": "usb", "device_serial": "ABC123", "device_name": "USB DMX",
        "device_universes": 2, "universe": 1, "address": 512}
    usb = validate([{"action": "update_instrument", "name": "I", "output": output}])[0]
    assert usb.output.model_dump() == output
    with pytest.raises(ValidationError):
        validate([{"action": "update_instrument", "name": "I", "output": {**output, "universe": 2}}])


@pytest.mark.parametrize("parameter", [
    {"type": "scalar", "name": "dimmer", "home_value": 256},
    {"type": "scalar", "name": "dimmer", "home_value": True},
    {"type": "scalar", "name": "dimmer", "two_bytes": 1},
    {"type": "scalar", "name": "dimmer", "two_bytes": True, "home_value": 65536},
    {"type": "rgbcolor", "name": "color", "outputs": ["red", "green"]},
    {"type": "rgbcolor", "name": "color", "outputs": ["red", "green", "red"]},
    {"type": "unsupported", "name": "other"},
])
def test_parameter_shapes_and_widths_are_strict(parameter):
    with pytest.raises(ValidationError):
        validate_definitions([{"action": "create_definition", "name": "D", "manufacturer": "M", "parameters": [parameter]}])


def test_definition_parameter_order_and_explicit_default_clear_are_preserved():
    operation = {"action": "create_definition", "name": "RGB+Dimmer (16bit)", "manufacturer": "M",
        "parameters": [{"type": "scalar", "name": "red", "two_bytes": True, "value_is_percentage": False, "home_value": 65535},
                       {"type": "scalar", "name": "green"}, {"type": "scalar", "name": "blue"},
                       {"type": "rgbcolor", "name": "color", "outputs": ["red", "green", "blue"]}],
        "default_parameter": None}
    assert validate_definitions([operation])[0].model_dump(exclude_unset=True) == operation


@pytest.mark.parametrize("value", [0, 12.5, 100])
def test_percentage_home_values_use_displayed_percent_units(value):
    parameter = models().ScalarParameter(type="scalar", name="dimmer", home_value=value)
    assert parameter.home_value == value


@pytest.mark.parametrize("value", [101, 1234, 100.01, float("inf"), float("nan")])
def test_percentage_home_rejects_values_outside_zero_to_one_hundred(value):
    with pytest.raises(ValidationError):
        models().ScalarParameter(type="scalar", name="dimmer", home_value=value)


@pytest.mark.parametrize("value", [1.5, 12.0, True, "12"])
def test_raw_dmx_home_requires_a_strict_integer(value):
    with pytest.raises(ValidationError):
        models().ScalarParameter(type="scalar", name="dimmer", value_is_percentage=False, home_value=value)
