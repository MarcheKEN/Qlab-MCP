import pytest
import plistlib

from qlab_mcp.write.input_channels import _archived_input_patch, _resolve_device, validate_span


def _saved_workspace():
    objects = ["$null"]

    def add(value):
        objects.append(value)
        return plistlib.UID(len(objects) - 1)

    classes = {}

    def cls(name):
        if name not in classes:
            classes[name] = add({"$classname": name, "$classes": [name, "NSObject"]})
        return classes[name]

    def mapping(values):
        return add({"$class": cls("NSDictionary"),
                    "NS.keys": [add(key) for key in values],
                    "NS.objects": [value if isinstance(value, plistlib.UID) else add(value)
                                   for value in values.values()]})

    device = mapping({"deviceUID": "BuiltInMicrophoneDevice", "inputChannels": 1})
    patch = add({"$class": cls("AudioInputPatch"), "uniqueID": add("A0000000-0000-4000-8000-000000000001"),
                 "useSystemDevice": add(True), "deviceDescription": device})
    patches = add({"$class": cls("NSArray"), "NS.objects": [patch]})
    mic = mapping({"audioInputPatches": patches})
    settings = mapping({"Mic": mic})
    root = mapping({"QLabShortVersionString": "5.5.10", "QLabBuildNumber": 5510,
                    "uniqueID": "95000000-0000-4000-8000-000000000001", "settings": settings})
    return plistlib.dumps({"$archiver": "NSKeyedArchiver", "$version": 100000,
                           "$objects": objects, "$top": {"root": root}}, fmt=plistlib.FMT_BINARY)


@pytest.mark.parametrize("capacity,channels,offset", [(1, 1, 0), (2, 1, 1), (24, 24, 0)])
def test_input_span_fits_device(capacity, channels, offset):
    validate_span(capacity, channels, offset)


@pytest.mark.parametrize("capacity,channels,offset", [
    (1, 2, 0), (2, 2, 1), (0, 1, 0), (2, 0, 0), (2, 1, -1),
    (2, True, 0), (True, 1, 0),
])
def test_input_span_rejects_unknown_or_out_of_range_values(capacity, channels, offset):
    with pytest.raises(ValueError):
        validate_span(capacity, channels, offset)


def test_system_patch_resolves_only_the_current_default_device():
    devices = [{"id": 7, "uid": "mic-A", "input_channels": 2},
               {"id": 8, "uid": "mic-B", "input_channels": 8}]
    assert _resolve_device({"use_system_device": True}, {"default_input_id": 8, "devices": devices}) == devices[1]
    with pytest.raises(ValueError, match="default input"):
        _resolve_device({"use_system_device": True}, {"default_input_id": 0, "devices": devices})


def test_archived_patch_is_selected_by_exact_workspace_and_patch_uuid():
    source = _saved_workspace()
    value = _archived_input_patch(source, "95000000-0000-4000-8000-000000000001",
                                  "A0000000-0000-4000-8000-000000000001")
    assert value["use_system_device"] is True
    assert value["device_uid"] == "BuiltInMicrophoneDevice"
    assert value["saved_input_channels"] == 1
    with pytest.raises(ValueError, match="identity"):
        _archived_input_patch(source, "95000000-0000-4000-8000-000000000001",
                              "A0000000-0000-4000-8000-000000000002")


def test_explicit_patch_uses_device_uid_not_display_name():
    devices = [{"id": 7, "uid": "mic-A", "name": "USB Mic"},
               {"id": 8, "uid": "mic-B", "name": "USB Mic"}]
    assert _resolve_device({"use_system_device": False, "device_uid": "mic-B"}, {"devices": devices}) == devices[1]
    with pytest.raises(ValueError, match="one current"):
        _resolve_device({"use_system_device": False, "device_uid": "USB Mic"}, {"devices": devices})
