"""Passive video inventories keep native, live and saved sources separate."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from qlab_mcp import video_settings as video
from test_video_settings import WS, video_workspace, live


def state(monkeypatch, *, native=None, saved=None):
    saved = saved or video.inspect_saved_video(video_workspace())
    saved.update(status='ready', sha256='a'*64, document_modified=False, freshness='last_saved')
    monkeypatch.setattr(video, '_saved', lambda *args: deepcopy(saved))
    monkeypatch.setattr(video, '_native_metadata', lambda *args: deepcopy(native or dict(
        status='ready', devices=[dict(id='camera-1', name='Camera', type='AVCaptureDevice')], formats=[])))
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host='127.0.0.1')))
    return reader, saved


def test_devices_keep_distinct_origins_and_unrouted_displays(monkeypatch):
    reader, saved = state(monkeypatch, native=dict(status='ready', devices=[
        dict(screen_id=8, name='Unrouted screen', type='Display', width=1360, height=768)], formats=[]))
    result = video.enrich_video_inventory(reader, WS, live(), 'devices')
    data = result['data']
    assert any(x['name'] == 'Unrouted screen' and x['source'] == 'macos_coregraphics' for x in data['items'])
    assert any(x['source'] == 'saved_archive' and x['type'] == 'NDI' for x in data['items'])
    assert len({x['ref'] for x in data['items']}) == len(data['items'])
    assert data['coverage']['complete_qlab_device_registry'] is False
    assert saved['destinations'][0]['fields']['pixelFormat'] == 1111970369
    ndi = next(x for x in data['items'] if x['source'] == 'saved_archive' and x['type'] == 'NDI')
    assert ndi['parameters']['pixel_format_name'] == 'BGRA'
    detail = video.enrich_video_inventory(reader, WS, live(), 'devices', ndi['ref'])
    assert [x['ref'] for x in detail['data']['items']] == [ndi['ref']]


def test_inputs_join_only_by_exact_identity_and_keep_modes_separate(monkeypatch):
    reader, saved = state(monkeypatch, native=dict(status='ready', devices=[dict(
        id='camera-1', name='Other name', type='AVCaptureDevice')], formats=[dict(
            source_id='camera-1', index=0, width=1920, height=1080, frame_rates=[dict(min=24, max=30)])]))
    saved['inputs'].append(dict(id='99999999-0000-4000-8000-000000000001', name='Empty', descriptor=None))
    result = video.enrich_video_inventory(reader, WS, live(), 'inputs')
    patch = next(x for x in result['data']['items'] if x.get('saved'))
    assert patch['saved']['descriptor']['uniqueID'] == 'camera-1'
    assert patch['available_source_ref'] is not None
    assert patch['effective_capture_format'] is None
    assert patch['configured_mode']['status'] == 'automatic'
    assert result['data']['available_formats'][0]['width'] == 1920
    assert any(x['name'] == 'Empty' and x['saved']['descriptor'] is None for x in result['data']['items'])


def test_remote_never_queries_local_devices(monkeypatch):
    reader, _ = state(monkeypatch)
    reader.client.config.host = '192.0.2.7'
    monkeypatch.setattr(video, '_native_metadata', lambda *args: pytest.fail('remote local metadata query'))
    result = video.enrich_video_inventory(reader, WS, live(), 'devices')
    assert result['data']['local_metadata']['status'] == 'remote_qlab'
    assert not any(x['source'] == 'macos_coregraphics' for x in result['data']['items'])


def test_changed_snapshot_discards_saved_and_derived_records(monkeypatch):
    reader, saved = state(monkeypatch)
    count = 0
    def changing(*args):
        nonlocal count
        count += 1
        return dict(deepcopy(saved), sha256=('a' if count == 1 else 'b')*64)
    monkeypatch.setattr(video, '_saved', changing)
    result = video.enrich_video_inventory(reader, WS, live(), 'devices')
    assert result['data']['saved_video']['status'] == 'changed_during_read'
    assert not any(x['source'] == 'saved_archive' for x in result['data']['items'])


def test_collection_pagination_limits_all_sections_and_has_next_request(monkeypatch):
    reader, _ = state(monkeypatch, native=dict(status='ready', devices=[dict(
        id=f'camera-{i}', name=f'Camera {i}', type='AVCaptureDevice') for i in range(1001)], formats=[]))
    r = video.enrich_video_inventory(reader, WS, live(), 'inputs', limit=10)
    assert len(r['data']['available_sources']) == 10
    p = r['data']['pagination']
    assert p['truncated'] and p['counts']['available_sources'] == 1001
    assert p['next_requests'][0]['arguments']['offset'] == 10
    assert p['next_requests'][0]['tool'] == 'qlab_get_video_input_patches'


def test_route_layout_and_dependencies_are_saved_source_only(monkeypatch):
    reader, saved = state(monkeypatch)
    route = saved['routes'][0]
    route['layout'] = dict(wide=2, high=2, index=3)
    info = video._route_inspection(dict(detail={'scalingMode': 2}), route, saved['stages'])
    assert info['current']['scaling_mode']['name'] == 'Fill'
    assert info['saved']['output_selection']['mode'] == 'partial'
    assert info['saved']['output_selection']['column'] == 1
    assert info['saved']['references'][0]['region_id'] == saved['stages'][0]['regions'][0]['id']
    assert info['saved']['source'] == 'saved_archive'
    assert info['saved']['output_selection']['origin'] == 'not_validated'
    for value, name in [(0, 'Center'), (1, 'Stretch'), (2, 'Fill'), (3, 'Fit'), (99, None)]:
        assert video._scaling_mode(value)['name'] == name


def test_saved_and_native_fail_independently_and_dirty_source_stays_explicit(monkeypatch):
    reader, saved = state(monkeypatch, native=dict(status='unavailable', message='denied', devices=[], formats=[]))
    saved['document_modified'] = True
    saved['freshness'] = 'possibly_stale'
    result = video.enrich_video_inventory(reader, WS, live(ok=False), 'inputs')
    assert result['ok'] and result['partial']
    assert result['data']['items'][0]['saved']
    assert result['data']['saved_video']['document_modified'] is True
    assert result['data']['items'][0]['position']['saved_archive'] == 1
    saved.update(status='unsupported_format', inputs=[], destinations=[])
    result = video.enrich_video_inventory(reader, WS, live(), 'devices')
    assert result['ok']
    assert result['data']['local_metadata']['status'] == 'unavailable'
    assert any(x['source'] == 'live_osc' for x in result['data']['items'])


def test_unknown_ref_is_not_an_absence_claim(monkeypatch):
    reader, _ = state(monkeypatch)
    result = video.enrich_video_inventory(reader, WS, live(), 'devices', 'not-observed')
    assert not result['ok']
    assert result['error_code'] == 'reference_not_observed'


def test_display_matching_requires_hardware_tuple_not_just_screen_id_or_name(monkeypatch):
    native = dict(status='ready', devices=[dict(screen_id=1, name='NDI', type='Display', vendor=1, model=2, serial=3)], formats=[])
    reader, saved = state(monkeypatch, native=native)
    saved['routes'][0]['destination_info'].update(screenID=1, screenVendorNumber=1, screenModelNumber=2, screenSerialNumber=4)
    result = video.enrich_video_inventory(reader, WS, live(), 'devices')
    screen = next(x for x in result['data']['items'] if x['source'] == 'macos_coregraphics')
    assert screen['route_ids'] == []
    saved['routes'][0]['destination_info']['screenSerialNumber'] = 3
    result = video.enrich_video_inventory(reader, WS, live(), 'devices')
    assert next(x for x in result['data']['items'] if x['source'] == 'macos_coregraphics')['route_ids']


def test_inventory_byte_budget_applies_to_all_sections_and_model(monkeypatch):
    from qlab_mcp.models import VideoInventoryResult
    reader, _ = state(monkeypatch, native=dict(status='ready', devices=[dict(
        id=str(i), name='x'*300, type='AVCaptureDevice') for i in range(30)], formats=[]))
    monkeypatch.setattr(video, 'MAX_RESPONSE_BYTES', 8000)
    r = video.enrich_video_inventory(reader, WS, live(), 'inputs')
    assert len(VideoInventoryResult.model_validate(r).model_dump_json().encode()) <= 8000
    assert r['data']['pagination']['byte_truncated']
    assert r['data']['pagination']['next_requests']


def test_native_process_timeout_and_invalid_payload_fail_without_retry(monkeypatch):
    import subprocess
    calls = []
    def timeout(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args[0], 10)
    monkeypatch.setattr(video.subprocess, 'run', timeout)
    assert video._native_metadata('inputs')['status'] == 'unavailable'
    assert len(calls) == 1
    monkeypatch.setattr(video.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='{"devices":{},"formats":[]}'))
    assert video._native_metadata('devices')['status'] == 'unavailable'


@pytest.mark.parametrize('available', [True, False])
def test_native_input_adapter_uses_metadata_getters_without_capture(monkeypatch, available):
    from qlab_mcp import video_native as native
    calls = []
    class Obj:
        def sel(self, name):
            return name
        def cls(self, name):
            assert name == b'AVCaptureDevice'
            return 'device-class'
        def string(self, value):
            return value
        def send(self, obj, selector, *args):
            calls.append(selector)
            return {'authorizationStatusForMediaType:': 0, 'devicesWithMediaType:': 'devices',
                    'uniqueID': 'camera-1', 'localizedName': 'Camera', 'isConnected': True,
                    'respondsToSelector:': available, 'isSuspended': True,
                    'isInUseByAnotherApplication': False, 'activeFormat': 'format',
                    'formats': 'formats', 'formatDescription': 'description',
                    'videoSupportedFrameRateRanges': 'rates', 'minFrameRate': 24, 'maxFrameRate': 30}[selector]
        def array(self, obj):
            return ([{'devices': 'device', 'formats': 'format', 'rates': 'rate'}[obj]], 1)
        def text(self, value):
            return value
    monkeypatch.setattr(native, '_Objects', Obj)
    monkeypatch.setattr(native.C, 'CDLL', lambda *args: object())
    monkeypatch.setattr(native, '_function', lambda lib, name, *args: (
        lambda desc: native.Dimensions(1920, 1080)) if name == 'CMVideoFormatDescriptionGetDimensions' else lambda desc: 1111970369)
    result = native.inputs()
    assert result['status'] == 'ready' and result['authorization_status'] == 0
    assert result['formats'][0]['frame_rates'] == [dict(min=24, max=30)]
    device = result['devices'][0]
    if available:
        assert device['suspended'] is True and device['in_use_by_another_application'] is False
        assert device['observed_format']['width'] == 1920
        assert device['observed_format']['capture_verified'] is False
    else:
        assert device['connected'] is None and device['observed_format'] is None
        assert device['metadata_errors']['in_use_by_another_application'] == 'getter_unavailable'
    assert set(calls) <= {'authorizationStatusForMediaType:', 'devicesWithMediaType:', 'uniqueID',
        'localizedName', 'isConnected', 'isSuspended', 'isInUseByAnotherApplication', 'activeFormat',
        'respondsToSelector:', 'formats', 'formatDescription', 'videoSupportedFrameRateRanges', 'minFrameRate', 'maxFrameRate'}


def test_technical_osc_overview_keeps_route_and_input_observations(monkeypatch):
    reader, _ = state(monkeypatch)
    result = live()
    result['profile'] = 'technical'
    result['data'] = dict(technical_payload=dict(
        routes=[dict(uniqueID='22222222-2222-4222-8222-222222222222', name='Route',
            destinationInfo=dict(name='Destination', destinationType='NDI'), connected=False)],
        input_patches=[dict(uniqueID='99999999-9999-4999-8999-999999999999', name='Live patch')]))
    devices = video.enrich_video_inventory(reader, WS, result, 'devices')
    assert any(x['source'] == 'live_osc' and x['name'] == 'Destination' for x in devices['data']['items'])
    patches = video.enrich_video_inventory(reader, WS, result, 'inputs')
    assert patches['data']['items'][0]['live']['name'] == 'Live patch'


def test_route_reference_counts_and_unknown_layout_do_not_claim_completeness():
    route = dict(id='route', layout=dict(wide=2, high=2, index=4))
    stage = dict(id='stage', name='Stage', regions=[dict(id=str(i), route_id='route') for i in range(1001)])
    result = video._route_inspection({}, route, [stage])['saved']
    assert result['reference_count'] == 1001
    assert len(result['references']) == 1000
    assert result['references_truncated'] and not result['references_complete']
    assert result['output_selection']['mode'] == 'unknown'


def test_fastmcp_inventories_preserve_fields_and_validate_arguments(monkeypatch):
    import asyncio
    from fastmcp import Client
    from fastmcp.exceptions import ToolError
    from qlab_mcp import server
    reader, _ = state(monkeypatch, native=dict(status='ready', observed_at='2026-10-24T12:00:00+00:00',
        devices=[dict(id='camera-1', name='Camera', connected=True, suspended=False,
            in_use_by_another_application=False, observed_format=dict(width=1920, height=1080,
                pixel_format=1111970369))], formats=[]))
    reader.get_workspace_settings = lambda **kwargs: dict(live(), sections=dict(video=live()['data']['overview']))
    monkeypatch.setattr(server, '_reader', lambda: reader)
    async def check():
        async with Client(server.mcp) as client:
            for name in ('qlab_get_video_input_patches', 'qlab_get_video_output_devices'):
                r = await client.call_tool(name, dict(workspace_id=WS))
                data = r.structured_content['data']
                assert data['items'] and data['snapshot_id'] and data['coverage']['passive']
                assert data['local_metadata']['status'] == 'ready'
                assert data['local_metadata']['observed_at'] == '2026-10-24T12:00:00+00:00'
                if name == 'qlab_get_video_input_patches':
                    source = data['available_sources'][0]
                    assert source['in_use_by_another_application'] is False
                    assert source['observed_format']['qlab_attribution'] == 'unverified'
                    assert source['observed_format']['capture_verified'] is False
                for bad in (True, 0, 1001):
                    with pytest.raises(ToolError):
                        await client.call_tool(name, dict(workspace_id=WS, limit=bad))
            with pytest.raises(ToolError):
                await client.call_tool('qlab_get_video_input_patches', dict(workspace_id=WS, patch_id='not-a-uuid'))
    asyncio.run(check())


def test_unassigned_patch_never_inherits_orphan_native_formats(monkeypatch):
    reader, saved = state(monkeypatch, native=dict(status='ready', devices=[], formats=[dict(
        source_id='missing-source', index=0, width=640, height=480)]))
    saved['inputs'][0]['descriptor'] = None
    patch_id = saved['inputs'][0]['id']
    result = video.enrich_video_inventory(reader, WS, live(), 'inputs', patch_id)
    assert result['data']['available_sources'] == []
    assert result['data']['available_formats'] == []


def test_observed_state_shared_sources_and_timestamp_independent_snapshot(monkeypatch):
    from qlab_mcp.models import VideoInventoryResult
    observation = dict(status='ready', observed_at='2026-10-24T10:00:00+00:00', devices=[dict(
        id='camera-1', name='Camera', connected=True, suspended=False,
        in_use_by_another_application=False, observed_format=dict(width=1920, height=1080,
            pixel_format=1111970369, source='macos_avfoundation', qlab_attribution='unverified',
            capture_verified=False))], formats=[dict(source_id='camera-1', index=0)])
    reader, saved = state(monkeypatch, native=observation)
    saved['inputs'].append(dict(deepcopy(saved['inputs'][0]), id='99999999-0000-4000-8000-000000000002'))
    first = video.enrich_video_inventory(reader, WS, live(), 'inputs')
    assert len(first['data']['available_sources']) == len(first['data']['available_formats']) == 1
    assert len({x['available_source_ref'] for x in first['data']['items']}) == 1
    assert all(x['effective_capture_format'] is None for x in first['data']['items'])
    parsed = VideoInventoryResult.model_validate(first).model_dump()
    assert parsed['data']['available_sources'][0]['observed_format']['capture_verified'] is False
    assert parsed['data']['local_metadata']['observed_at'] == observation['observed_at']
    observation['observed_at'] = '2026-10-24T10:01:00+00:00'
    second = video.enrich_video_inventory(reader, WS, live(), 'inputs')
    assert second['data']['snapshot_id'] == first['data']['snapshot_id']
    observation['devices'][0]['in_use_by_another_application'] = True
    third = video.enrich_video_inventory(reader, WS, live(), 'inputs')
    assert third['data']['snapshot_id'] != first['data']['snapshot_id']


def test_optional_getter_error_is_unknown(monkeypatch):
    from qlab_mcp.video_native import _optional_get
    import ctypes
    class Objects:
        def sel(self, value):
            return value
        def send(self, *args):
            raise ValueError('getter failed')
    errors = {}
    assert _optional_get(Objects(), 1, 'isSuspended', ctypes.c_bool, errors, 'suspended') is None
    assert errors == {'suspended': 'getter failed'}


def test_display_flags_and_missing_getter(monkeypatch):
    from qlab_mcp import video_native as native
    monkeypatch.setattr(native.C, 'CDLL', lambda *args: object())
    def function(lib, name, *args):
        if name == 'CGGetOnlineDisplayList':
            def online(count, ids, found):
                found._obj.value = 1
                if ids is not None:
                    ids[0] = 7
                return 0
            return online
        if name == 'CGDisplayIsAsleep':
            raise AttributeError('getter unavailable')
        return lambda *args: 0 if name == 'CGDisplayCopyDisplayMode' else 1
    monkeypatch.setattr(native, '_function', function)
    monkeypatch.setattr(native, '_Objects', lambda: (_ for _ in ()).throw(OSError('No AppKit')))
    row = native.displays()['devices'][0]
    assert row['active'] is True and row['mirrored'] is True
    assert row['asleep'] is None and row['metadata_errors']['asleep'] == 'getter unavailable'
