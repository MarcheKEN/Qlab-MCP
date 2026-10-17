"""Stable normalization contracts shared by workspace and cue reads."""
import pytest

from qlab_mcp.cues.overview import _is_container_cue, _workspace_overview_metadata
from qlab_mcp.cues.query import _parse_bool_filter
from qlab_mcp.settings.summarizers import _first_present_case_insensitive
from qlab_mcp.settings.workspace import WorkspaceSettingsMixin


@pytest.mark.parametrize("value", [True, 1, "true", "T", "yes", " Y ", "1"])
def test_boolean_filter_true_aliases(value):
    assert _parse_bool_filter(value) is True


@pytest.mark.parametrize("value", [False, 0, "false", "F", "no", " N ", "0"])
def test_boolean_filter_false_aliases(value):
    assert _parse_bool_filter(value) is False


@pytest.mark.parametrize("value", [None, 2, -1, 0.0, 1.0, "", "on", "off", [], {}])
def test_boolean_filter_rejects_other_types_and_preserves_error(value):
    with pytest.raises(ValueError) as exc:
        _parse_bool_filter(value)
    assert str(exc.value) == f"Boolean cue query filter value must be true or false: {value!r}"


@pytest.mark.parametrize("fields,name", [
    ({"displayName": "Displayed", "name": "Named", "fileName": "File"}, "Displayed"),
    ({"displayName": "", "name": "Named", "fileName": "File"}, "Named"),
    ({"fileName": "File"}, "File"),
    ({}, None),
])
def test_workspace_metadata_precedence_and_shallow_copy(fields, name):
    source = {"uniqueID": "ws", "qlabVersion": "5.5.10", "version": "fallback", **fields}
    result = _workspace_overview_metadata(source)
    assert result == {"uniqueID": "ws", "name": name, "displayName": source.get("displayName"),
                      "qlab_version": "5.5.10", "metadata": source}
    assert result["metadata"] is not source
    source["later"] = True
    assert "later" not in result["metadata"]


@pytest.mark.parametrize("value", [None, "workspace", []])
def test_workspace_metadata_preserves_nonobject_values(value):
    assert _workspace_overview_metadata(value) == {"value": value}


@pytest.mark.parametrize("kind,expected", [
    ("Cue List", True), ("Cue Cart", True), ("Cart", True), ("Group", True),
    ("Audio", False), ("group", False), (None, False),
])
def test_container_classification_remains_case_sensitive(kind, expected):
    assert _is_container_cue({"type": kind}) is expected


@pytest.mark.parametrize("fields,expected", [
    ({"NAME": "fallback", "name": "exact"}, "exact"),
    ({"NAME": "first", "Name": "second"}, "first"),
    ({"name": "", "NAME": "fallback"}, "fallback"),
    ({"name": False, "NAME": "fallback"}, False),
    ({"name": 0, "NAME": "fallback"}, 0),
    ({"name": [], "NAME": "fallback"}, []),
    ({"name": None}, None),
])
def test_case_insensitive_summary_preserves_priority_and_falsey_values(fields, expected):
    assert _first_present_case_insensitive(fields, ("name",)) == expected


def test_general_detail_rejects_specific_kind_without_reading():
    class Reader(WorkspaceSettingsMixin):
        def _workspace_settings_general(self, *args):
            pytest.fail("A specific General detail kind must not trigger a read")

    with pytest.raises(ValueError, match="^General details support only kind all$"):
        Reader()._get_workspace_setting_details_single("ws", "general", kind="output_patch")


@pytest.mark.parametrize("kind,command,error_key", [
    ("route", "video/routes", "video.routes"),
    ("video_input_patch", "video/inputPatchList", "video.inputPatchList"),
])
def test_video_collection_details_preserve_read_and_summary_arguments(kind, command, error_key):
    class Reader(WorkspaceSettingsMixin):
        def _read_workspace_setting(self, workspace, requested_command, errors, requested_error_key):
            self.calls.append((workspace, requested_command, requested_error_key))
            return [{"uniqueID": "item"}]

        def _setting_details_from_collection(self, *args):
            return args

    reader = Reader()
    reader.calls = []
    result = reader._get_workspace_setting_details_single("ws", "video", kind, "item")
    assert reader.calls == [("ws", command, error_key)]
    assert result == ("ws", "video", kind, "item", "safe", [{"uniqueID": "item"}], [], {})
