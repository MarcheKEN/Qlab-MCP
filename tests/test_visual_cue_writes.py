"""Specialized visual batches retain the shared confirmation and no-retry protocol."""
from uuid import UUID

import pytest
from pydantic import ValidationError

from qlab_mcp.write import control, visual
from test_control_cue_writes import Reader, WS, START, WAIT, MEMO


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr(control, "check_write_readiness", lambda *a: {"ok": True})
    monkeypatch.setattr(control, "ensure_write_ready", lambda *a: None)
    r = Reader()
    for uid, kind in ((START, "Video"), (WAIT, "Camera"), (MEMO, "Text")):
        r.values[uid].update(type=kind, allowsEditingDuration=True, opacity=1, stageID="",
                             translation={"x": 0, "y": 0}, **{"translation/x": 0, "translation/y": 0})
    r.values[MEMO].update(text="hello", **{"text/format": [{"range": [0, 5], "fontSize": 24, "alignment": "left"}]})
    return r


def request(uid, **props):
    return {"cue_id": uid, "properties": props}


def execute(r, fn, items):
    plan = fn(r, WS, items, True)
    assert plan["ok"], plan
    assert not r.setters
    for item, result in zip(items, plan["results"], strict=True):
        item["confirm_gates"] = [op["confirm_token"] for op in result["planned_operations"]]
    return fn(r, WS, items, False)


@pytest.mark.parametrize("fn,uid", [(visual.edit_video_cues, START), (visual.edit_camera_cues, WAIT), (visual.edit_text_cues, MEMO)])
def test_saved_visual_multiple_properties(reader, fn, uid):
    result = execute(reader, fn, [request(uid, opacity=0.5, name="updated", duration=2)])
    assert result["ok"] and len(reader.setters) == 3
    assert reader.values[uid]["opacity"] == 0.5


def test_visual_batch_all_preflight(reader):
    result = visual.edit_video_cues(reader, WS, [request(START, opacity=0.5), request(WAIT, opacity=0.5)], True)
    assert not result["ok"] and not reader.setters


def test_ndi_output_is_an_explicit_supported_patch_reference():
    assert visual.VideoCueEditProperties(audioOutputPatchID="ndi-output").audioOutputPatchID == "ndi-output"
    with pytest.raises(ValueError):
        visual.VideoCueEditProperties(stageID="ndi-output")


def test_camera_audio_input_assignment_uses_workspace_mic_patches(reader):
    from types import SimpleNamespace

    patch_id = str(UUID(int=99)).upper()
    reader.values[WAIT]["audioInputPatchID"] = ""
    original = reader._request

    def request_osc(address, *args, **kwargs):
        if address.endswith("/settings/mic/patchList"):
            return SimpleNamespace(data=[{"uniqueID": patch_id, "name": "Input"}])
        if "/settings/" in address:
            raise ValueError("Unknown settings route")
        return original(address, *args, **kwargs)

    reader._request = request_osc
    result = visual.edit_camera_cues(reader, WS, [request(WAIT, audioInputPatchID=patch_id)], True)
    assert result["ok"], result
    missing = visual.edit_camera_cues(reader, WS, [request(WAIT, audioInputPatchID=str(UUID(int=100)))], True)
    assert not missing["ok"]
    assert not reader.setters


def test_video_without_audio_can_edit_media_timing(reader):
    reader.values[START].update(fileTarget="/tmp/silent.mov", audioTrackFormats={}, numChannelsIn=0,
        levels=[], startTime=0, endTime=8, rate=1, playCount=1)
    result = execute(reader, visual.edit_video_cues, [request(START, startTime=1)])
    assert result["ok"], result
    assert reader.values[START]["startTime"] == 1


def test_unknown_or_still_media_range_does_not_enable_silent_timing(reader):
    reader.values[START].update(fileTarget="/tmp/still.png", audioTrackFormats={}, numChannelsIn=0,
        levels=[], startTime=0, endTime=0, rate=1)
    result = visual.edit_video_cues(reader, WS, [request(START, rate=2)], True)
    assert not result["ok"] and not reader.setters


def test_ndi_assignment_binds_saved_stage_route_and_audio_channels(reader, monkeypatch):
    from types import SimpleNamespace
    from qlab_mcp import video_settings
    stage, route = str(UUID(int=40)).upper(), str(UUID(int=41)).upper()
    info = dict(destinationType="NDI", name="NDI")
    saved = dict(status="ready", document_modified=False, sha256="snapshot",
        stages=[dict(id=stage, regions=[dict(route_id=route)])],
        routes=[dict(id=route, destination_type="NDI", destination_info=info, destination_candidates=["snapshot:10"])],
        destinations=[dict(id="snapshot:10", fields=dict(audioChannels=2))])
    monkeypatch.setattr(video_settings, "_saved", lambda *a: saved)
    reader.values[START].update(stageID=stage, audioOutputPatchID="")
    original = reader._request
    def get(address, *args, **kwargs):
        if address.endswith("/settings/video/routeID/" + route):
            return SimpleNamespace(data=dict(uniqueID=route, destinationInfo=info))
        return original(address, *args, **kwargs)
    reader._request = get
    item = request(START, audioOutputPatchID="ndi-output")
    plan = visual.edit_video_cues(reader, WS, [item], True)
    assert plan["ok"], plan
    item["confirm_gates"] = [op["confirm_token"] for op in plan["results"][0]["planned_operations"]]
    saved["sha256"] = "changed"
    result = visual.edit_video_cues(reader, WS, [item], False)
    assert not result["ok"] and not reader.setters


def test_ndi_assignment_blocks_missing_destination(reader, monkeypatch):
    from qlab_mcp import video_settings
    monkeypatch.setattr(video_settings, "_saved", lambda *a: dict(status="unavailable"))
    reader.values[START]["audioOutputPatchID"] = ""
    result = visual.edit_video_cues(reader, WS, [request(START, audioOutputPatchID="ndi-output")], True)
    assert not result["ok"] and not reader.setters


def test_context_only_read_does_not_repeat_identity_query(reader, monkeypatch):
    original = reader.read_cue_values
    calls = []

    def read_values(ws, uid, keys, **kwargs):
        if calls and calls[-1] == keys:
            raise control.OscTimeoutError("QLab suppressed repeated unchanged query")
        calls.append(keys)
        return original(ws, uid, keys, **kwargs)

    monkeypatch.setattr(reader, "read_cue_values", read_values)
    values = visual.read(reader, WS, MEMO, ["uniqueID", "type"])
    assert values == {"uniqueID": MEMO, "type": "Text"}
    assert calls == [["uniqueID", "type"]] and not reader.setters


def test_visual_timeout_no_retry(reader):
    reader.fail = "timeout"
    result = execute(reader, visual.edit_video_cues, [request(START, opacity=0.5)])
    assert result["ok"] and len(reader.setters) == 1
    assert result["status"] == "updated_with_confirmed_timeouts"


def test_visual_preparation_without_setter(reader):
    reader.fail = "prepare"
    result = execute(reader, visual.edit_camera_cues, [request(WAIT, opacity=0.5)])
    assert not result["ok"] and not reader.setters


def test_file_target_verification_requires_healthy_media(reader):
    reader.values[START]["isBroken"] = True
    assert not visual.matches("fileTarget", "/tmp/video.mp4", "/tmp/video.mp4", {}, reader, WS, START)
    reader.values[START]["isBroken"] = False
    assert visual.matches("fileTarget", "/tmp/video.mp4", "/tmp/video.mp4", {}, reader, WS, START)
    assert not visual.matches("fileTarget", "/tmp/other.mp4", "/tmp/video.mp4", {}, reader, WS, START)


def test_file_assignment_broken_readback_stops_without_retry(reader, tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"not a valid video")
    reader.values[START].update(fileTarget="", isBroken=True)
    result = execute(reader, visual.edit_video_cues, [request(START, fileTarget=str(path))])
    assert not result["ok"]
    assert len(reader.setters) == 1
    assert reader.values[START]["fileTarget"] == str(path)


@pytest.mark.parametrize("props", [{"opacity": True}, {"opacity": float("nan")}, {"layer": 1001},
                                  {"translation": {"x": 1, "y": False}}, {"cueTargetID": str(UUID(int=10))},
                                  {"anchor": {"x": 0, "y": 0}, "anchor/x": 1}, {"unknown": 1},
                                  {"fadeAndStopOthers": 4}, {"secondTriggerAction": 6}, {"name": None}])
def test_strict_visual_schema(props):
    with pytest.raises(ValidationError):
        visual.VideoCueEditInput.model_validate(request(START, **props))


def test_optional_text_missing_or_mixed_blocks(reader):
    for fragments in ([{"range": [0,5]}], [{"range": [0,2], "fontSize": 12}, {"range": [2,3], "fontSize": 24}]):
        reader.values[MEMO]["text/format"] = fragments
        result = visual.edit_text_cues(reader, WS, [request(MEMO, **{"text/format/fontSize": 32})], True)
        assert not result["ok"] and not reader.setters


def test_uniform_text_style_dry_run(reader):
    plan = visual.edit_text_cues(reader, WS, [request(MEMO, **{"text/format/fontSize": 32})], True)
    assert plan["ok"] and plan["results"][0]["before"]["text/format/fontSize"] == 24
    assert not reader.setters


@pytest.mark.parametrize("props", [
    {"text/format/fontName": "HiraginoSans-W3"},
    {"text/format/fontFamilyAndStyle": {"family": "Hiragino Sans", "style": "W3"}},
])
def test_scalar_font_change_blocks_unverified_emoji_fallback(reader, props):
    reader.values[MEMO].update(text="漢🙂", **{"text/format": [{"range": [0, 3],
        "fontName": "HelveticaNeue-Bold", "fontFamily": "Helvetica Neue", "fontStyle": "Bold", "fontSize": 24}]})
    plan = visual.edit_text_cues(reader, WS, [request(MEMO, **props)], True)
    assert not plan["ok"]
    assert not reader.setters


def test_scalar_font_confirmation_rejects_changed_text(reader):
    reader.values[MEMO].update(text="ab", **{"text/format": [{"range": [0, 2],
        "fontName": "HelveticaNeue-Bold", "fontFamily": "Helvetica Neue", "fontStyle": "Bold", "fontSize": 24}]})
    item = request(MEMO, **{"text/format/fontName": "HiraginoSans-W3"})
    plan = visual.edit_text_cues(reader, WS, [item], True)
    assert plan["ok"], plan
    item["confirm_gates"] = [op["confirm_token"] for op in plan["results"][0]["planned_operations"]]
    reader.values[MEMO]["text"] = "🙂"
    result = visual.edit_text_cues(reader, WS, [item], False)
    assert not result["ok"]
    assert not reader.setters


def test_wrong_workspace_reference(reader):
    result = visual.edit_video_cues(reader, WS, [request(START, stageID=str(UUID(int=40)))], True)
    assert not result["ok"] and not reader.setters


def test_token_bound_to_family(reader):
    item = request(START, opacity=0.5)
    plan = visual.edit_video_cues(reader, WS, [item], True)
    item["confirm_gates"] = [plan["results"][0]["planned_operations"][0]["confirm_token"]]
    reader.values[START]["type"] = "Camera"
    result = visual.edit_camera_cues(reader, WS, [item], False)
    assert not result["ok"] and not reader.setters

@pytest.mark.parametrize("props", [{"resetRotation": 1}, {"resetRotation": False},
                                  {"quaternion": [0,0,0,2]}, {"quaternion": [0,0,False,1]},
                                  {"level": {"inChannel": True, "outChannel": 1, "decibel": 0}},
                                  {"sliderLevel": {"channel": 129, "decibel": 0}},
                                  {"mute/channel/clear": 1}])
def test_actions_and_indexed_types_are_strict(props):
    with pytest.raises(ValidationError):
        visual.VideoCueEditInput.model_validate(request(START, **props))


def test_geometry_readback_preserves_decimal_precision(reader):
    original = reader._request
    def request_osc(address, *args, **kwargs):
        if address.endswith('/translation') and args:
            reader.values[START]['translation'] = dict(x=args[0],y=args[1])
            reader.setters.append((START, 'translation', args))
            return type('Reply', (), {'data': None})()
        return original(address,*args,**kwargs)
    reader._request=request_osc
    result=execute(reader, visual.edit_video_cues, [request(START, translation={'x':1.25,'y':-2.5})])
    assert result['ok'] and len(reader.setters)==1
    assert result['results'][0]['after']['translation']=={'x':1.25,'y':-2.5}


def test_reset_rotation_verifies_quaternion(reader):
    reader.values[START]['quaternion']=[0,0,1,0]
    original=reader._request
    def request_osc(address,*args,**kwargs):
        if address.endswith('/resetRotation'):
            assert not args and kwargs['ensure_always_reply'] and kwargs['allow_empty_data']
            reader.values[START]['quaternion']=[0,0,0,1]
            reader.setters.append((START,'resetRotation',args))
            return type('Reply', (), {'data': None})()
        return original(address,*args,**kwargs)
    reader._request=request_osc
    result=execute(reader,visual.edit_video_cues,[request(START,resetRotation=True)])
    assert result['ok'] and len(reader.setters)==1


@pytest.mark.parametrize('fn,uid', [(visual.edit_video_cues, START), (visual.edit_camera_cues, WAIT),
                                  (visual.edit_text_cues, MEMO)])
def test_quaternion_plan_and_verified_write_preserve_all_components(reader, fn, uid):
    reader.values[uid]['quaternion'] = [0, 0, 0, 1]
    requested = [1, 0, 0, 0]
    original = reader._request

    def request_osc(address, *args, **kwargs):
        if address.endswith('/quaternion') and args:
            assert kwargs['ensure_always_reply'] and kwargs['allow_empty_data']
            reader.setters.append((uid, 'quaternion', args))
            reader.values[uid]['quaternion'] = [float(value) for value in args]
            return type('Reply', (), {'data': None})()
        return original(address, *args, **kwargs)

    reader._request = request_osc
    item = request(uid, quaternion=requested)
    plan = fn(reader, WS, [item], True)
    assert plan['ok'] and not reader.setters
    planned = plan['results'][0]
    assert planned['properties']['quaternion'] == requested
    assert planned['before']['quaternion'] == [0, 0, 0, 1]
    operation = planned['planned_operations'][0]
    assert operation['args'] == requested
    item['confirm_gates'] = [operation['confirm_token']]
    result = fn(reader, WS, [item], False)
    assert result['ok'] and len(reader.setters) == 1
    assert result['results'][0]['after']['quaternion'] == requested


def test_bad_visual_baseline_is_rejected(reader):
    reader.values[START]['opacity']=True
    result=visual.edit_video_cues(reader,WS,[request(START,opacity=0.5)],True)
    assert not result['ok'] and not reader.setters


def test_partial_batch_stops_with_pending_operations(reader):
    reader.fail='mismatch'
    result=execute(reader,visual.edit_video_cues,[request(START,opacity=0.5,name='later')])
    assert not result['ok'] and len(reader.setters)==1
    assert result['results'][0]['planned_operations'][1]['status']=='planned'


def test_visual_baseline_changes_invalidate_token(reader):
    item=request(START,opacity=0.5)
    plan=visual.edit_video_cues(reader,WS,[item],True)
    item['confirm_gates']=[plan['results'][0]['planned_operations'][0]['confirm_token']]
    reader.values[START]['opacity']=0.75
    assert not visual.edit_video_cues(reader,WS,[item],False)['ok'] and not reader.setters


def test_visual_identity_read_prepares_always_reply(reader):
    original=reader._request
    identity_calls=[]
    def request_osc(address,*args,**kwargs):
        if address.endswith('/uniqueID'):
            identity_calls.append(kwargs)
        return original(address,*args,**kwargs)
    reader._request=request_osc
    plan=visual.edit_video_cues(reader,WS,[request(START,opacity=0.5)],True)
    assert plan['ok'] and identity_calls
    assert all(call['ensure_always_reply'] is True for call in identity_calls)
    assert all(not call.get('allow_empty_data',False) for call in identity_calls)
    assert not reader.setters


def test_audio_crosspoint_quantization_and_bounds(reader):
    from types import SimpleNamespace
    patch=str(UUID(int=40)).upper()
    reader.values[START].update(numChannelsIn=2,audioOutputPatchID=patch,**{'level/1/1':0})
    original=reader._request
    def request_osc(address,*args,**kwargs):
        if '/settings/audio/patchID/' in address:
            return SimpleNamespace(data={'uniqueID':patch,'cueOutputChannels':2})
        if address.endswith('/level/1/1') and args:
            reader.setters.append((START,'level/1/1',args))
            reader.values[START]['level/1/1']=args[0]+0.000048
            return SimpleNamespace(data=None)
        return original(address,*args,**kwargs)
    reader._request=request_osc
    result=execute(reader,visual.edit_video_cues,[request(START,level={'inChannel':1,'outChannel':1,'decibel':-12})])
    assert result['ok'] and len(reader.setters)==1
    bad=visual.edit_video_cues(reader,WS,[request(START,level={'inChannel':3,'outChannel':1,'decibel':0})],True)
    assert not bad['ok'] and len(reader.setters)==1


def test_content_verifies_inherited_format(reader):
    result=execute(reader,visual.edit_text_cues,[request(MEMO,text='changed')])
    assert result['ok'] and len(reader.setters)==1


def test_content_format_changes_invalidate_confirmation(reader):
    item=request(MEMO,text='changed')
    plan=visual.edit_text_cues(reader,WS,[item],True)
    item['confirm_gates']=[plan['results'][0]['planned_operations'][0]['confirm_token']]
    reader.values[MEMO]['text/format'][0]['fontSize']=32
    result=visual.edit_text_cues(reader,WS,[item],False)
    assert not result['ok'] and not reader.setters


def test_content_verification_reads_format_only_once(reader):
    original=reader._request
    reads=[]
    def request_osc(address,*args,**kwargs):
        if address.endswith('/text/format'):
            reads.append(address)
            assert len(reads)==1, 'Duplicate immediate format read'
        return original(address,*args,**kwargs)
    reader._request=request_osc
    dependency={'text/format':reader.values[MEMO]['text/format']}
    assert visual.matches('text','changed','changed',dependency,reader,WS,MEMO)
    assert len(reads)==1


def test_coordinate_component_pair_becomes_one_setter(reader):
    plan=visual.edit_video_cues(reader,WS,[request(START,**{'translation/x':1.25,'translation/y':-2.5})],True)
    assert plan['ok'] and not reader.setters
    result=plan['results'][0]
    assert result['properties']=={'translation':{'x':1.25,'y':-2.5}}
    assert len(result['planned_operations'])==1
    assert result['planned_operations'][0]['address'].endswith('/translation')


def test_rotation_request_rejects_reset_and_quaternion():
    with pytest.raises(ValidationError):
        visual.VideoCueEditInput.model_validate(request(START,resetRotation=True,quaternion=[0,0,1,0]))


@pytest.mark.parametrize('fn,uid', [(visual.edit_video_cues, START), (visual.edit_camera_cues, WAIT),
                                  (visual.edit_text_cues, MEMO)])
def test_crop_osc_list_baseline_and_readback(reader, fn, uid):
    reader.values[uid]['crop'] = [0, 0, 0, 0]
    original = reader._request
    def request_osc(address, *args, **kwargs):
        if address.endswith('/crop') and args:
            reader.setters.append((uid, 'crop', args))
            reader.values[uid]['crop'] = list(args)
            return type('Reply', (), {'data': None})()
        return original(address, *args, **kwargs)
    reader._request = request_osc
    result = execute(reader, fn, [request(uid, crop=dict(top=12, bottom=8, left=16, right=4))])
    assert result['ok'] and len(reader.setters) == 1
    assert result['results'][0]['before']['crop'] == dict(top=0, bottom=0, left=0, right=0)
    assert result['results'][0]['after']['crop'] == dict(top=12, bottom=8, left=16, right=4)


@pytest.mark.parametrize('value', [0, 1])
def test_preserve_pitch_integer_read_is_boolean(reader, value):
    reader.values[START].update(preservePitch=value, numChannelsIn=2, audioTrackFormats=['AAC'],
                                fileTarget='/fixture.mp4')
    result = execute(reader, visual.edit_video_cues, [request(START, preservePitch=not bool(value))])
    assert result['ok'] and len(reader.setters) == 1
    assert result['results'][0]['before']['preservePitch'] is bool(value)


@pytest.mark.parametrize('baseline', [[0, 0, 0], [0, False, 0, 0], [0, float('nan'), 0, 0]])
def test_invalid_crop_read_blocks_setter(reader, baseline):
    reader.values[START]['crop'] = baseline
    result = visual.edit_video_cues(reader, WS, [request(START, crop=dict(top=1, bottom=1, left=1, right=1))], True)
    assert not result['ok'] and not reader.setters


@pytest.mark.parametrize('value', [0, 1, 'true'])
def test_boolean_request_stays_strict(value):
    with pytest.raises(ValidationError):
        visual.VideoCueEditInput.model_validate(request(START, preservePitch=value))


@pytest.mark.parametrize('props', [{'mute/channel': {'output': 2, 'value': False}},
                                  {'mute/channel/clear': True}, {'solo/channel/clear': True}])
def test_warning_allows_readable_mute_solo_recovery(reader, props):
    from types import SimpleNamespace
    patch = str(UUID(int=40)).upper()
    reader.values[START].update(isWarning=True, numChannelsIn=2, audioOutputPatchID=patch,
                               muteChannels=[2], soloChannels=[2], **{'mute/channel/2': True})
    original = reader._request
    def request_osc(address, *args, **kwargs):
        if '/settings/audio/patchID/' in address:
            return SimpleNamespace(data={'uniqueID': patch, 'cueOutputChannels': 2})
        if address.endswith(('/mute/channel/clear', '/solo/channel/clear')):
            reader.setters.append((START, address, args))
            reader.values[START]['muteChannels' if '/mute/' in address else 'soloChannels'] = []
            return SimpleNamespace(data=None)
        return original(address, *args, **kwargs)
    reader._request = request_osc
    result = execute(reader, visual.edit_video_cues, [request(START, **props)])
    assert result['ok'] and len(reader.setters) == 1


@pytest.mark.parametrize('broken', [True, None])
def test_mute_recovery_never_bypasses_broken_health(reader, broken):
    reader.values[START].update(isWarning=True, isBroken=broken, muteChannels=[2])
    result = visual.edit_video_cues(reader, WS, [request(START, **{'mute/channel/clear': True})], True)
    assert not result['ok'] and not reader.setters


def test_restore_scale_before_enabling_aspect_ratio(reader):
    reader.values[START].update(preserveAspectRatio=False, scale={'x': 1.25, 'y': .75})
    original = reader._request
    def request_osc(address, *args, **kwargs):
        if address.endswith('/scale') and args:
            reader.setters.append((START, 'scale', args))
            reader.values[START]['scale'] = {'x': args[0], 'y': args[1]}
            return type('Reply', (), {'data': None})()
        reply = original(address, *args, **kwargs)
        if address.endswith('/preserveAspectRatio') and args and args[0]:
            x = reader.values[START]['scale']['x']
            reader.values[START]['scale'] = {'x': x, 'y': x}
        return reply
    reader._request = request_osc
    result = execute(reader, visual.edit_video_cues,
                     [request(START, preserveAspectRatio=True, scale={'x': 1, 'y': 1})])
    assert result['ok'] and len(reader.setters) == 2
    assert [x[1] for x in reader.setters] == ['scale', 'preserveAspectRatio']
    assert reader.values[START]['scale'] == {'x': 1, 'y': 1}


def test_nonuniform_scale_with_preserved_aspect_is_rejected(reader):
    reader.values[START].update(preserveAspectRatio=True, scale={'x': 1, 'y': 1})
    result = visual.edit_video_cues(reader, WS, [request(START, scale={'x': 1.25, 'y': .75})], True)
    assert not result['ok'] and not reader.setters


def test_single_scale_component_can_use_existing_aspect_lock(reader):
    reader.values[START].update(preserveAspectRatio=True, scale={'x': 1, 'y': 1}, **{'scale/x': 1})
    result = execute(reader, visual.edit_video_cues, [request(START, **{'scale/x': 1.25})])
    assert result['ok'] and len(reader.setters) == 1


def test_enabling_aspect_and_component_requires_explicit_scale_pair(reader):
    reader.values[START].update(preserveAspectRatio=False, scale={'x': 1, 'y': .75}, **{'scale/y': .75})
    result = visual.edit_video_cues(reader, WS, [request(START, preserveAspectRatio=True, **{'scale/y': 1.25})], True)
    assert not result['ok'] and not reader.setters


def test_visual_dependency_check_does_not_duplicate_shared_timecode_read(reader, monkeypatch):
    def duplicate(*args):
        pytest.fail('Containing list format is checked by the shared writer')
    monkeypatch.setattr(control, '_timecode_format', duplicate)
    visual.check_dependencies(reader, WS, START, {'timecode': {'list_id': START, 'format': 3}})


def test_setter_error_with_matching_readback_is_not_hidden_or_retried(reader):
    from qlab_mcp.errors import QLabReplyError
    original = reader._request
    def request_osc(address, *args, **kwargs):
        result = original(address, *args, **kwargs)
        if args:
            raise QLabReplyError('QLab returned status error')
        return result
    reader._request = request_osc
    result = execute(reader, visual.edit_video_cues, [request(START, opacity=.5, name='pending')])
    assert not result['ok'] and len(reader.setters) == 1
    first = result['results'][0]['planned_operations'][0]['property']
    assert result['results'][0]['after'][first] == result['results'][0]['properties'][first]
    assert 'error despite matching readback' in result['results'][0]['errors'][first]
    assert result['results'][0]['planned_operations'][1]['status'] == 'planned'


def test_explicit_qlab_rejection_with_unchanged_readback_is_verification_failure(reader):
    from qlab_mcp.errors import QLabReplyError

    original = reader._request
    def reject_setter(address, *args, **kwargs):
        if args:
            reader.setters.append((address, args))
            raise QLabReplyError('error', address=address)
        return original(address, *args, **kwargs)

    reader._request = reject_setter
    result = execute(reader, visual.edit_video_cues, [request(START, opacity=0.5)])
    item = result['results'][0]
    assert not result['ok'] and len(reader.setters) == 1
    assert result['status'] == 'verification_failed'
    assert item['after']['opacity'] == item['before']['opacity'] == 1
    assert item['status'] == 'verification_failed'
    assert 'QLab reply status' in item['errors']['opacity']

@pytest.mark.parametrize('value', [0, 1])
def test_infinite_loop_integer_read_and_verification(reader, value):
    reader.values[START].update(infiniteLoop=value, numChannelsIn=2, audioTrackFormats=['AAC'],
                                fileTarget='/video.mp4')
    original = reader._request
    def request_osc(address, *args, **kwargs):
        result = original(address, *args, **kwargs)
        if address.endswith('/infiniteLoop') and args:
            reader.values[START]['infiniteLoop'] = int(args[0])
        return result
    reader._request = request_osc
    result = execute(reader, visual.edit_video_cues, [request(START, infiniteLoop=not bool(value))])
    assert result['ok'] and len(reader.setters) == 1
    assert result['results'][0]['before']['infiniteLoop'] is bool(value)
    assert result['results'][0]['after']['infiniteLoop'] is not bool(value)


@pytest.mark.parametrize('value', [0, 1, 1.0, '1'])
def test_infinite_loop_write_stays_strict_boolean(value):
    with pytest.raises(ValidationError):
        visual.VideoCueEditInput.model_validate(request(START, infiniteLoop=value))

@pytest.mark.parametrize('changed', ['requested', 'baseline'])
def test_quaternion_token_binds_every_component(reader, changed):
    reader.values[START]['quaternion'] = [0, 0, 0, 1]
    item = request(START, quaternion=[1, 0, 0, 0])
    plan = visual.edit_video_cues(reader, WS, [item], True)
    assert plan['ok'] and not reader.setters
    item['confirm_gates'] = [plan['results'][0]['planned_operations'][0]['confirm_token']]
    if changed == 'requested':
        item['properties']['quaternion'] = [1, 0.00001, 0, 0]
    else:
        reader.values[START]['quaternion'] = [0, 1, 0, 0]
    result = visual.edit_video_cues(reader, WS, [item], False)
    assert not result['ok'] and not reader.setters
