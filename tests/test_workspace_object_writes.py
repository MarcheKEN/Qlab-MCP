from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from qlab_mcp.errors import OscTimeoutError
from qlab_mcp.models import (
    AudioLevelOperation, VideoBoundsOperation, VideoComponentOperation,
    VideoRouteGuidesOperation, SettingNameOperation,
    AudioOutputPatchOperation, VideoRegionOperation, VideoRouteOperation,
)
from qlab_mcp.settings import object_writes
from qlab_mcp.settings.object_writes import ObjectSettingsWriteMixin
from qlab_mcp.settings.workspace import WorkspaceSettingsMixin
from qlab_mcp.settings.write_operations import WorkspaceSettingsWriteMixin
from qlab_mcp.settings.write_operations import SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_VERSION, _SETTINGS_TOKEN_SECRET
from qlab_mcp.write.tokens import decode_confirm_token, encode_confirm_token


WS = "11111111-1111-4111-8111-111111111111"
ROUTE = "22222222-2222-4222-8222-222222222222"
PATH = f"/workspace/{WS}/settings/video/routeID/{ROUTE.upper()}"


class Reader(WorkspaceSettingsWriteMixin, ObjectSettingsWriteMixin):
    def __init__(self) -> None:
        self.client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))
        self._read_cache = SimpleNamespace(clear=lambda: None)
        self.data = {PATH: {"uniqueID": ROUTE}, PATH + "/enableGuides": False}
        self.setters: list[tuple[str, tuple[object, ...]]] = []
        self.active = False
        self.timeout = False
        self.fail_readback = False

    def get_workspaces(self):
        return {"workspaces": [{"uniqueID": WS}]}

    def get_running_cues(self, *_args, **_kwargs):
        return {"running_cues": [{"uniqueID": "active"}] if self.active else []}

    def _request(self, address, *args, **_kwargs):
        if self.fail_readback and not args and self.setters:
            raise OscTimeoutError("readback unavailable")
        if args:
            self.setters.append((address, args))
            self.data[address] = args[0] if len(args) == 1 else list(args)
            if self.timeout:
                raise OscTimeoutError("uncertain setter")
        return SimpleNamespace(status="ok", data=self.data[address])


@pytest.fixture(autouse=True)
def ready(monkeypatch):
    monkeypatch.setattr(object_writes, "check_write_readiness", lambda *_: {"ok": True})
    monkeypatch.setattr(object_writes, "ensure_write_ready", lambda *_: None)


def call(reader: Reader, *, dry: bool, token: str | None = None):
    return reader.edit_object_setting(WS, "route", {"route_id": ROUTE},
                                      VideoRouteGuidesOperation(kind="enableGuides", value=True), dry, token)


def test_one_setter_token_and_readback():
    reader = Reader()
    plan = call(reader, dry=True)
    assert plan.status == "dry_run" and plan.baseline is False and not reader.setters
    done = call(reader, dry=False, token=plan.confirm_token)
    assert done.status == "updated" and done.readback is True and len(reader.setters) == 1
    restore = reader.edit_object_setting(WS, "route", {"route_id": ROUTE},
                                         VideoRouteGuidesOperation(kind="enableGuides", value=False), True, None)
    assert restore.status == "dry_run"
    reader.edit_object_setting(WS, "route", {"route_id": ROUTE},
                               VideoRouteGuidesOperation(kind="enableGuides", value=False), False, restore.confirm_token)
    replay = call(reader, dry=False, token=plan.confirm_token)
    assert replay.status == "preflight_failed" and len(reader.setters) == 2


def test_stale_baseline_and_active_workspace_block_setter():
    reader = Reader()
    plan = call(reader, dry=True)
    reader.active = True
    assert call(reader, dry=False, token=plan.confirm_token).status == "preflight_failed"
    assert not reader.setters
    reader.active = False
    reader.data[PATH + "/enableGuides"] = True
    assert call(reader, dry=False, token=plan.confirm_token).status == "unchanged"
    assert not reader.setters


def test_timeout_never_retries_setter():
    reader = Reader()
    plan = call(reader, dry=True)
    reader.timeout = True
    result = call(reader, dry=False, token=plan.confirm_token)
    assert result.status == "updated_with_confirmed_timeouts"
    assert len(reader.setters) == 1


@pytest.mark.parametrize("channels", [(0, 0), (1, 0), (0, 1)])
def test_patch_main_and_marginal_gain_timeout_single_setter(channels):
    reader = Reader()
    patch = "33333333-3333-4333-8333-333333333333"
    path = f"/workspace/{WS}/settings/audio/patchID/{patch}"
    suffix = f"/level/{channels[0]}/{channels[1]}"
    reader.data.update({path: {"uniqueID": patch}, path + "/cueOutputChannels": 12,
                        path + suffix: 0})
    op = AudioLevelOperation(kind="level", input_channel=channels[0],
                             output_channel=channels[1], value=-3)
    plan = reader.edit_object_setting(WS, "audio", {"patch_id": patch}, op, True, None)
    assert plan.status == "dry_run" and not reader.setters
    reader.timeout = True
    done = reader.edit_object_setting(WS, "audio", {"patch_id": patch}, op, False, plan.confirm_token)
    assert done.status == "updated_with_confirmed_timeouts" and done.readback == -3
    assert reader.setters == [(path + suffix, (-3,))]


def test_expired_token_and_unavailable_readback():
    reader = Reader()
    plan = call(reader, dry=True)
    payload, error = decode_confirm_token(plan.confirm_token, SETTINGS_TOKEN_FAMILY,
                                          SETTINGS_TOKEN_VERSION, _SETTINGS_TOKEN_SECRET)
    assert error is None
    payload["expires_at"] = 1
    expired = encode_confirm_token(SETTINGS_TOKEN_FAMILY, SETTINGS_TOKEN_VERSION, payload, _SETTINGS_TOKEN_SECRET)
    assert call(reader, dry=False, token=expired).status == "preflight_failed"
    assert not reader.setters
    reader.fail_readback = True
    result = call(reader, dry=False, token=plan.confirm_token)
    assert result.status == "verification_inconclusive" and result.retry_unsafe
    assert len(reader.setters) == 1


def test_changed_string_baseline_blocks_write():
    reader = Reader()
    stage = "33333333-3333-4333-8333-333333333333"
    path = f"/workspace/{WS}/settings/video/stageID/{stage.upper()}"
    reader.data[path] = {"uniqueID": stage}
    reader.data[path + "/name"] = "A"
    op = SettingNameOperation(kind="name", value="C")
    plan = reader.edit_object_setting(WS, "stage", {"stage_id": stage}, op, True, None)
    assert plan.status == "dry_run"
    reader.data[path + "/name"] = "B"
    result = reader.edit_object_setting(WS, "stage", {"stage_id": stage}, op, False, plan.confirm_token)
    assert result.status == "preflight_failed" and not reader.setters


@pytest.mark.parametrize("timeout", [False, True])
def test_negative_infinity_at_numeric_floor_still_plans_and_sends_once(timeout):
    reader = Reader()
    patch = "33333333-3333-4333-8333-333333333333"
    path = f"/workspace/{WS}/settings/audio/patchID/{patch}"
    reader.data.update({path: {"uniqueID": patch}, path + "/cueOutputChannels": 12,
                        path + "/level/1/1": -60, f"/workspace/{WS}/settings/audio/minVolume": -60})
    request = reader._request

    def floor_readback(address, *args, **kwargs):
        try:
            return request(address, *args, **kwargs)
        finally:
            if args:
                reader.data[address] = -60

    reader._request = floor_readback
    op = AudioLevelOperation(kind="level", input_channel=1, output_channel=1, value="-inf")
    plan = reader.edit_object_setting(WS, "audio", {"patch_id": patch}, op, True, None)
    assert plan.status == "dry_run" and plan.confirm_token and not reader.setters
    reader.timeout = timeout
    done = reader.edit_object_setting(WS, "audio", {"patch_id": patch}, op, False, plan.confirm_token)
    assert done.status == ("updated_with_confirmed_timeouts" if timeout else "updated")
    assert done.readback == -60 and done.verification["matched"]
    assert reader.setters == [(path + "/level/1/1", ("-inf",))]
    assert done.warnings
    reader.data[path + "/level/1/1"] = "-inf"
    unchanged = reader.edit_object_setting(WS, "audio", {"patch_id": patch}, op, True, None)
    assert unchanged.status == "unchanged" and unchanged.confirm_token is None
    assert len(reader.setters) == 1


@pytest.fixture
def region_reader():
    reader = Reader()
    stage = "33333333-3333-4333-8333-333333333333"
    region = "44444444-4444-4444-8444-444444444444"
    stage_path = f"/workspace/{WS}/settings/video/stageID/{stage}"
    path = stage_path + "/regionID/" + region
    reader.data.update({stage_path: {"uniqueID": stage},
                        path: {"uniqueID": region, "route": {"uniqueID": ROUTE}},
                        path + "/bounds": {"x": 0, "y": 0, "width": 100, "height": 100},
                        path + "/enableGrid": False, path + "/enableGuide": False,
                        path + "/subregionIndex/0/controlPointIndex/0": [0, 0]})
    reader.data[PATH]["naturalSize"] = {"width": 1920, "height": 1080}
    reader._resolve_workspace_id_strict = lambda value: value
    return reader, {"stage_id": stage, "region_id": region}, path


@pytest.mark.parametrize("point", [{}, [], [None, None], [True, 0], [float("nan"), 2], [float("inf"), 0]])
def test_invalid_point_blocks_get_and_edit(region_reader, point):
    reader, ids, path = region_reader
    reader.data[path + "/subregionIndex/0/controlPointIndex/0"] = point
    op = VideoBoundsOperation(kind="controlPoint", x=1, y=2, subregion_index=0, control_point_index=0)
    plan = reader.edit_object_setting(WS, "region", ids, op, True, None)
    assert plan.status == "dry_run_preflight_failed" and plan.confirm_token is None
    assert not reader.setters
    with pytest.raises(ValueError, match="OSC controlPoint"):
        WorkspaceSettingsMixin.get_video_region(reader, WS, ids["stage_id"], ids["region_id"], 0, 0)


def test_point_is_revalidated_before_setter_and_valid_point_verifies(region_reader):
    reader, ids, path = region_reader
    point_path = path + "/subregionIndex/0/controlPointIndex/0"
    op = VideoBoundsOperation(kind="controlPoint", x=1, y=2, subregion_index=0, control_point_index=0)
    plan = reader.edit_object_setting(WS, "region", ids, op, True, None)
    reader.data[point_path] = [None, None]
    blocked = reader.edit_object_setting(WS, "region", ids, op, False, plan.confirm_token)
    assert blocked.status == "preflight_failed" and not reader.setters
    reader.data[point_path] = [0, 0]
    done = reader.edit_object_setting(WS, "region", ids, op, False, plan.confirm_token)
    assert done.status == "updated" and done.readback == [1, 2]
    assert reader.setters == [(point_path, (1, 2))]


@pytest.mark.parametrize("value", [None, True, 1.0, "1", 2**31])
def test_invalid_bounds_are_rejected_by_get(region_reader, value):
    reader, ids, path = region_reader
    reader.data[path + "/bounds"]["x"] = value
    with pytest.raises(ValueError, match="OSC bounds"):
        WorkspaceSettingsMixin.get_video_region(reader, WS, ids["stage_id"], ids["region_id"])


@pytest.mark.parametrize("operation", [
    {"kind": "level", "input_channel": 1, "output_channel": 1, "value": "silence"},
    {"kind": "level", "input_channel": 1, "output_channel": 1, "value": float("inf")},
])
def test_audio_level_rejects_unrepresentable_values(operation):
    with pytest.raises(ValidationError):
        AudioLevelOperation.model_validate(operation)


def test_region_geometry_schema_rejects_incomplete_or_unrelated_fields():
    with pytest.raises(ValidationError):
        VideoBoundsOperation(kind="bounds", x=0, y=0, width=100)
    with pytest.raises(ValidationError):
        VideoBoundsOperation(kind="origin", x=0, y=0, width=100)
    with pytest.raises(ValidationError):
        VideoComponentOperation(kind="width", value=2**31)


@pytest.mark.parametrize(("operation_type", "payload"), [
    (AudioOutputPatchOperation, {"kind": "audioMap", "value": 1}),
    (AudioOutputPatchOperation, {"kind": "mute", "output_channel": 129, "value": True}),
    (VideoRouteOperation, {"kind": "rotationDegrees", "value": 90}),
    (VideoRegionOperation, {"kind": "controlPoint", "x": 1, "y": 2, "subregion_index": 0}),
])
def test_unsupported_or_incomplete_operations_are_rejected(operation_type, payload):
    with pytest.raises(ValidationError):
        TypeAdapter(operation_type).validate_python(payload)


def test_decimal_control_point_read_plan_and_stale_token(region_reader):
    reader, ids, path = region_reader
    point_path = path + '/subregionIndex/0/controlPointIndex/0'
    reader.data[point_path] = [1.25, 2.75]
    observed = WorkspaceSettingsMixin.get_video_region(reader, WS, ids['stage_id'], ids['region_id'], 0, 0)
    assert observed['data']['control_point'] == [1.25, 2.75]
    op = VideoBoundsOperation(kind='controlPoint', x=1, y=2, subregion_index=0, control_point_index=0)
    plan = reader.edit_object_setting(WS, 'region', ids, op, True, None)
    assert plan.status == 'dry_run' and plan.baseline == [1.25, 2.75]
    reader.data[point_path] = [1.5, 2.75]
    done = reader.edit_object_setting(WS, 'region', ids, op, False, plan.confirm_token)
    assert done.status == 'preflight_failed' and not reader.setters


def test_preparation_failure_reports_no_setter_and_consumes_token():
    from qlab_mcp.errors import OscPreparationError
    reader = Reader()
    plan = call(reader, dry=True)
    original = reader._request
    def request(address, *args, **kwargs):
        if kwargs.get('ensure_always_reply'):
            assert kwargs['allow_empty_data']
            raise OscPreparationError('no setter was sent')
        return original(address, *args, **kwargs)
    reader._request = request
    result = call(reader, dry=False, token=plan.confirm_token)
    assert result.status == 'preflight_failed' and result.executed_operations == []
    assert not reader.setters
    assert call(reader, dry=False, token=plan.confirm_token).status == 'preflight_failed'


def test_decimal_baseline_can_verify_float_reply(region_reader):
    reader, ids, path = region_reader
    point_path = path + '/subregionIndex/0/controlPointIndex/0'
    reader.data[point_path] = [1.25, 2.75]
    op = VideoBoundsOperation(kind='controlPoint', x=1, y=2, subregion_index=0, control_point_index=0)
    plan = reader.edit_object_setting(WS, 'region', ids, op, True, None)
    original = reader._request
    def request(address, *args, **kwargs):
        reply = original(address, *args, **kwargs)
        if address == point_path and args:
            reader.data[point_path] = [float(v) for v in args]
        return reply
    reader._request = request
    done = reader.edit_object_setting(WS, 'region', ids, op, False, plan.confirm_token)
    assert done.status == 'updated' and done.readback == [1.0, 2.0]
    assert len(reader.setters) == 1
