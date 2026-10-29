"""Regressions for signed, indexed family editing."""
from types import SimpleNamespace
from uuid import UUID
import pytest
from qlab_mcp.write import remaining, control
from test_control_cue_writes import Reader, WS, START, MEMO

@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr(control, 'check_write_readiness', lambda *a: {'ok': True})
    monkeypatch.setattr(control, 'ensure_write_ready', lambda *a: None)
    r = Reader()
    original = r._request
    patch = str(UUID(int=100)).upper()
    def request(address, *args, **kwargs):
        if address.endswith("settings/audio/patchList"):
            return SimpleNamespace(data=[{"uniqueID": patch}])
        if address.endswith("settings/audio/patchID/" + patch):
            return SimpleNamespace(data={"uniqueID": patch, "cueOutputChannels": 2})
        return original(address, *args, **kwargs)
    r._request = request
    for uid in (START, MEMO):
        r.values[uid].update(type='Audio', rate=1.0, numChannelsIn=2, fileTarget='/tmp/example.wav', audioOutputPatchID=patch,
                             levels=[[0,0,0],[0,0,-60],[0,-60,0]], sliderLevels=[0,0,0],
                             **{'level/1/1': 0, 'level/2/2': 0})
    return r

def test_specific_and_trigger_share_confirmation(reader):
    items=[{'cue_id': START, 'properties': {'rate': 2, 'duckOthers': True}}]
    p=remaining.edit_remaining_cues(reader, WS, items, True, family='audio')
    assert p['ok'], p
    assert len(p['results'][0]['planned_operations'])==2
    items[0]['confirm_gates']=[x['confirm_token'] for x in p['results'][0]['planned_operations']]
    assert remaining.edit_remaining_cues(reader, WS, items, False, family='audio')['ok']
    assert len(reader.setters)==2
    assert not remaining.edit_remaining_cues(reader, WS, items, False, family='audio')['ok']

def test_multiple_indexed_only(reader):
    items=[{'cue_id':START,'operations':[
        {'property':'level','args':{'inChannel':1,'outChannel':1,'decibel':-6}},
        {'property':'level','args':{'inChannel':2,'outChannel':2,'decibel':-3}}]}]
    p=remaining.edit_remaining_cues(reader,WS,items,True,family='audio')
    assert p['ok'],p
    items[0]['confirm_gates']=[x['confirm_token'] for x in p['results'][0]['planned_operations']]
    assert remaining.edit_remaining_cues(reader,WS,items,False,family='audio')['ok']
    assert len(reader.setters)==2

def confirmed(reader, items, family='audio'):
    plan = remaining.edit_remaining_cues(reader, WS, items, True, family=family)
    assert plan['ok'], plan
    for item, result in zip(items, plan['results'], strict=True):
        item['confirm_gates'] = [p['confirm_token'] for p in result['planned_operations']]
    return items

@pytest.mark.parametrize('failure,count,ok', [('prepare',0,False),('timeout',2,True),('mismatch',1,False)])
def test_specific_failure_never_retries_and_stops(reader,failure,count,ok):
    items=confirmed(reader,[{'cue_id':START,'properties':{'rate':2}}, {'cue_id':MEMO,'properties':{'rate':2}}])
    reader.fail=failure
    result=remaining.edit_remaining_cues(reader,WS,items,False,family='audio')
    assert result['ok'] is ok and len(reader.setters)==count
    if not ok:
        assert result['results'][1]['executed_operations']==[]

@pytest.mark.parametrize('change', ['baseline','dependency','expired','forged'])
def test_stale_specific_tokens_block_all_setters(reader,monkeypatch,change):
    items=confirmed(reader,[{'cue_id':START,'properties':{'rate':2}}])
    if change=='baseline':reader.values[START]['rate']=1.5
    elif change=='dependency':reader.values[START]['fileTarget']='/tmp/other.wav'
    elif change=='expired':
        original=control.time.time
        monkeypatch.setattr(control.time,'time',lambda:original()+301)
    else:items[0]['confirm_gates'][0]+='tampered'
    assert not remaining.edit_remaining_cues(reader,WS,items,False,family='audio')['ok']
    assert not reader.setters

@pytest.mark.parametrize('items',[
    [{'cue_id':START,'properties':{'level':{'inChannel':1,'outChannel':1,'decibel':0}},'operations':[{'property':'level','args':{'inChannel':1,'outChannel':1,'decibel':1}}]}],
    [{'cue_id':START,'properties':{'fileTarget':'/tmp/missing.wav','rate':2}}],
    [{'cue_id':START,'operations':[{'property':'level','args':{'inChannel':3,'outChannel':1,'decibel':0}}]}],
])
def test_conflicts_and_missing_bounds_no_writes(reader,items):
    try:result=remaining.edit_remaining_cues(reader,WS,items,False,family='audio')
    except ValueError:result={'ok':False}
    assert not result['ok'] and not reader.setters

def test_fifty_cues_and_budget(reader,monkeypatch):
    items=[]
    for n in range(200,250):
        uid=str(UUID(int=n)).upper()
        reader.values[uid]={**reader.values[START],'uniqueID':uid,'number':str(n)}
        items.append({'cue_id':uid,'properties':{'rate':2}})
    confirmed(reader,items)
    result=remaining.edit_remaining_cues(reader,WS,items,False,family='audio')
    assert result['updated_count']==50 and len(reader.setters)==50
    reader.setters.clear()
    items=confirmed(reader,[{'cue_id':START,'properties':{'rate':2}}])
    ticks=iter([0,0,100])
    monkeypatch.setattr(control.time,'monotonic',lambda:next(ticks,100))
    assert not remaining.edit_remaining_cues(reader,WS,items,False,family='audio')['ok']
    assert not reader.setters

@pytest.mark.parametrize('properties,mode,status,ok',[
    ({'note':61,'velocity':50},1,1,True),({'pitchBend':8192},1,1,False),
    ({'endValue':200},1,3,False),({'byteCombo':8192},1,6,True),
    ({'rawString':'43 10 7f'},3,1,True),({'rawString':'F0 43 F7'},3,1,False),
    ({'command':1},2,1,True),({'command':127},2,1,False),
    ({'controlValue':2},2,1,False)])
def test_midi_modes(reader,properties,mode,status,ok):
    reader.values[START].update(type='MIDI',messageType=mode,status=status,byte1=60,byte2=64,byteCombo=1,endValue=0,rawString='43 10 01',command=2,controlValue=1)
    result=remaining.edit_remaining_cues(reader,WS,[{'cue_id':START,'properties':properties}],True,family='midi')
    assert result['ok'] is ok, result['results']
    assert not reader.setters

@pytest.mark.parametrize('text,fmt,valid', [('0:01:00:00',7,False),('0:10:00:00',7,True),('1:00:00:24',0,False),('1:00:00:23',0,True)])
def test_timecode_format_validation(text,fmt,valid):
    if valid:assert remaining._time_seconds(text,fmt)>=0
    else:
        with pytest.raises(ValueError):remaining._time_seconds(text,fmt)

def test_inspections_are_bounded_and_read_only(reader):
    from qlab_mcp.cues.audio import AudioCueDetailsResult,AudioCueSummary
    result=AudioCueDetailsResult(workspace_id=WS,cue_id=START,identity=AudioCueSummary(uniqueID=START,type='Audio'))
    inspected=remaining.inspect(reader,result,[{'property':'level','args':{'inChannel':1,'outChannel':1}}])
    assert inspected.inspection_values=={'level/1/1':0} and not reader.setters
    with pytest.raises(ValueError):remaining.inspect(reader,result,[{'property':'level','args':{'inChannel':1,'outChannel':1,'decibel':0}}])

def slice_reader(reader):
    reader.values[START].update(startTime=0,endTime=10,sliceMarkers=[{'time':2,'playCount':1},{'time':5,'playCount':1}], **{'sliceMarker/0/playCount':1,'sliceMarker/1/playCount':1})
    original=reader._request
    def request(address,*args,**kwargs):
        response=original(address,*args,**kwargs)
        if args and '/sliceMarker/' in address:
            index=int(address.split('/sliceMarker/')[1].split('/')[0])
            reader.values[START]['sliceMarkers'][index]['playCount']=args[0]
        return response
    reader._request=request
    return reader

def test_multiple_slices_validate_whole_inventory(reader):
    slice_reader(reader)
    items=confirmed(reader,[{'cue_id':START,'operations':[
        {'property':'sliceMarker/playCount','args':{'index':0,'playCount':2}},
        {'property':'sliceMarker/playCount','args':{'index':1,'playCount':3}}]}])
    result=remaining.edit_remaining_cues(reader,WS,items,False,family='audio')
    assert result['ok'],result['results']
    assert reader.values[START]['sliceMarkers']==[{'time':2,'playCount':2},{'time':5,'playCount':3}]

def test_slice_scalar_match_cannot_hide_other_marker_change(reader):
    slice_reader(reader)
    items=confirmed(reader,[{'cue_id':START,'operations':[
        {'property':'sliceMarker/playCount','args':{'index':0,'playCount':2}},
        {'property':'sliceMarker/playCount','args':{'index':1,'playCount':3}}]}])
    original=reader._request
    def corrupt(address,*args,**kwargs):
        response=original(address,*args,**kwargs)
        if args:reader.values[START]['sliceMarkers'][1]['time']=6
        return response
    reader._request=corrupt
    result=remaining.edit_remaining_cues(reader,WS,items,False,family='audio')
    assert not result['ok'] and len(reader.setters)==1

@pytest.mark.parametrize('property_name,value', [('rate',2),('rotation',20),('quaternion',[0,0,0,1])])
def test_fade_invalid_geometry_modes_block(reader,property_name,value):
    from test_control_cue_writes import TARGET
    reader.values[START].update(type='Fade',cueTargetID=TARGET,patchTargetID='',targetMode=0,
        doOpacity=True,doRate=True,doRotation=True,doScale=True,doTranslation=True,geoMode=1,rotationType=0,levelsMode=0,
        rate=1,rotation=0,quaternion=[0,0,0,1])
    reader.values[TARGET].update(type='Video')
    result=remaining.edit_remaining_cues(reader,WS,[{'cue_id':START,'properties':{property_name:value}}],True,family='fade')
    assert not result['ok'] and not reader.setters


def test_level_readback_accepts_qlab_quantization():
    assert remaining.matches('level/1/1', -2.999948263168335, -3, {}, None, WS, START)
    assert not remaining.matches('level/1/1', -2.99, -3, {}, None, WS, START)

def test_timecode_selector_normalizes_end_and_allows_following_basics(reader):
    reader.values[START].update(type='Timecode', outputType=1, framerate=6,
        startTime='1:00:00:00', endTime='2:00:00:00', duration=3603.6, ltcChannel=0)
    original = reader._request
    def request(address, *args, **kwargs):
        response = original(address, *args, **kwargs)
        if address.endswith('/framerate') and args:
            reader.values[START]['endTime'] = '2:00:03:18'
        return response
    reader._request = request
    items = confirmed(reader, [{'cue_id': START, 'properties': {'timecodeFrameRate': 2, 'name': 'new'}}], 'timecode')
    result = remaining.edit_remaining_cues(reader, WS, items, False, family='timecode')
    assert result['ok'], result['results']
    assert len(reader.setters) == 2

@pytest.mark.parametrize('mapped', [None, str(UUID(int=77))])
def test_object_ownership_unknown_or_map_blocks(reader, mapped):
    obj = str(UUID(int=78)).upper()
    reader.values[START].update(objects=[{'uniqueID': obj}], **{'audioMap/uniqueID': mapped, f'objectID/{obj}/name': 'old'})
    result = remaining.edit_remaining_cues(reader, WS, [{'cue_id': START,
        'operations': [{'property': 'objectID/name', 'args': {'objectID': obj, 'name': 'new'}}]}], True, family='audio')
    assert not result['ok'] and not reader.setters


def owned_object(reader):
    obj = str(UUID(int=78)).upper()
    reader.values[START].update(objects=[{'uniqueID': obj, 'name': 'old'}],
        **{'audioMap/uniqueID': '', f'objectID/{obj}/name': 'old', f'objectID/{obj}/spread': 0})
    return obj


@pytest.mark.parametrize('family,kind', [('audio', 'Audio'), ('mic', 'Mic')])
def test_owned_object_signed_edit_uses_exact_uuid_and_fresh_readback(reader, family, kind):
    obj = owned_object(reader)
    reader.values[START]['type'] = kind
    events = []
    original = reader._request
    def request(address, *args, **kwargs):
        events.append((address, args))
        response = original(address, *args, **kwargs)
        if address.endswith(f'/objectID/{obj}/name') and args:
            reader.values[START]['objects'][0]['name'] = args[0]
        return response
    reader._request = request
    items = confirmed(reader, [{'cue_id': START, 'operations': [
        {'property': 'objectID/name', 'args': {'objectID': obj, 'name': 'new'}},
        {'property': 'objectID/spread', 'args': {'objectID': obj, 'spread': 0.5}}]}], family)
    assert not reader.setters
    events.clear()
    result = remaining.edit_remaining_cues(reader, WS, items, False, family=family)
    assert result['ok'], result['results']
    assert reader.setters == [(START, f'objectID/{obj}/name', ('new',)),
                              (START, f'objectID/{obj}/spread', (0.5,))]
    after = result['results'][0]['after']
    assert after['uniqueID'] == START and after['type'] == kind
    for field, value in [('name', 'new'), ('spread', 0.5)]:
        path = f'/workspace/{WS}/cue_id/{START}/objectID/{obj}/{field}'
        sent = events.index((path, (value,)))
        assert (path, ()) in events[sent + 1:]
        assert (f'/workspace/{WS}/cue_id/{START}/uniqueID', ()) in events[sent + 1:]
        assert after[f'objectID/{obj}/{field}'] == value
    assert not remaining.edit_remaining_cues(reader, WS, items, False, family=family)['ok']
    assert len(reader.setters) == 2


@pytest.mark.parametrize('change', ['inventory', 'audio_map', 'unknown_map', 'cue_uuid', 'requested_object'])
def test_owned_object_confirmation_rejects_changed_identity_or_ownership(reader, change):
    obj = owned_object(reader)
    other = str(UUID(int=79)).upper()
    if change == 'requested_object':
        reader.values[START]['objects'].append({'uniqueID': other})
        reader.values[START][f'objectID/{other}/name'] = 'old'
    items = confirmed(reader, [{'cue_id': START, 'operations': [
        {'property': 'objectID/name', 'args': {'objectID': obj, 'name': 'new'}}]}])
    if change == 'inventory':
        reader.values[START]['objects'] = [{'uniqueID': other}]
    elif change in {'audio_map', 'unknown_map'}:
        reader.values[START]['audioMap/uniqueID'] = other if change == 'audio_map' else None
    elif change == 'cue_uuid':
        reader.values[START]['uniqueID'] = MEMO
    else:
        items[0]['operations'][0]['args']['objectID'] = other
    result = remaining.edit_remaining_cues(reader, WS, items, False, family='audio')
    assert not result['ok'] and not reader.setters


def test_owned_object_divergent_readback_stops_remaining_operations_and_cues(reader):
    obj = owned_object(reader)
    items = confirmed(reader, [
        {'cue_id': START, 'operations': [
            {'property': 'objectID/name', 'args': {'objectID': obj, 'name': 'new'}},
            {'property': 'objectID/spread', 'args': {'objectID': obj, 'spread': 0.5}}]},
        {'cue_id': MEMO, 'properties': {'rate': 2}}])
    reader.fail = 'mismatch'
    result = remaining.edit_remaining_cues(reader, WS, items, False, family='audio')
    assert not result['ok']
    assert reader.setters == [(START, f'objectID/{obj}/name', ('new',))]
    assert result['results'][0]['after'][f'objectID/{obj}/name'] == 'different'
    assert result['results'][1]['executed_operations'] == []


@pytest.mark.parametrize('family,kind,properties', [
    ('mic', 'Mic', {'channels': 2}), ('mic', 'Mic', {'channelOffset': 1}),
    ('midi', 'MIDI', {'controlNumber': 1}), ('midi', 'MIDI', {'qNumber': '1'}),
    ('network', 'Network', {'parameterValue': {'parameter': 'gain', 'value': 1}}),
    ('network', 'Network', {'parameterFadeEnabled': {'parameter': 'gain', 'value': True}}),
])
def test_residual_metadata_limits_block_even_with_readable_baseline(reader, family, kind, properties):
    reader.values[START].update(type=kind, messageType=2, command=1,
        **{key: value if not isinstance(value, dict) else value['value'] for key, value in properties.items()})
    result = remaining.edit_remaining_cues(reader, WS, [
        {'cue_id': START, 'properties': properties}], True, family=family)
    assert not result['ok'] and not reader.setters
    if family == 'mic' and set(properties) <= {'channels', 'channelOffset'}:
        assert set(properties) <= remaining.capabilities(family)['conditional_properties'].keys()
    else:
        assert set(properties) <= remaining.capabilities(family)['blocked_properties'].keys()


def test_mic_channel_preflight_binds_the_exact_input_patch_capacity(reader, monkeypatch):
    patch = str(UUID(int=81)).upper()
    reader.values[START].update(type='Mic', audioInputPatchID=patch, channels=1, channelOffset=0)
    original_request = reader._request
    def request(address, *args, **kwargs):
        if address.endswith(f'/cue_id/{START}/audioInputPatchID') and not args:
            return SimpleNamespace(data=None)
        return original_request(address, *args, **kwargs)
    reader._request = request
    snapshot = {'workspace_id': WS, 'patch_id': patch, 'input_channels': 2, 'device_uid': 'mic-test'}
    monkeypatch.setattr(remaining, 'input_channel_snapshot', lambda _reader, _ws, patch_id: snapshot)
    items = [{'cue_id': START, 'properties': {'channels': 2}}]
    plan = remaining.edit_remaining_cues(reader, WS, items, True, family='mic')
    assert plan['ok'], plan['results'][0].get('errors')
    assert not reader.setters
    items[0]['confirm_gates'] = [op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    result = remaining.edit_remaining_cues(reader, WS, items, False, family='mic')
    assert result['ok'], result['results']
    assert reader.setters == [(START, 'channels', (2,))]


@pytest.mark.parametrize('property_name,value', [('channels', 2), ('channelOffset', 1)])
def test_camera_input_capacity_blocks_with_existing_patch_and_baseline(reader, property_name, value):
    from qlab_mcp.write import visual
    reader.values[START].update(type='Camera', audioInputPatchID=str(UUID(int=80)).upper(),
        channels=1, channelOffset=0)
    result = visual.edit_camera_cues(reader, WS, [
        {'cue_id': START, 'properties': {property_name: value}}], True)
    assert not result['ok'] and not reader.setters
    assert property_name in visual.capabilities('Camera', SimpleNamespace(
        basics=SimpleNamespace(allowsEditingDuration=True), triggers=SimpleNamespace(fadeAndStopOthers=1),
        video=None)).get('conditional_properties', {})

def test_midi_type_two_file_rejected(reader, tmp_path, monkeypatch):
    import struct
    path = tmp_path / 'unsupported.mid'
    path.write_bytes(b'MThd' + struct.pack('>IHHH', 6, 2, 1, 480))
    reader.values[START].update(type='MIDI File', startTime=0, endTime=1, playCount=1)
    result = remaining.edit_remaining_cues(reader, WS, [{'cue_id': START,
        'properties': {'fileTarget': str(path)}}], True, family='midi_file')
    assert not result['ok'] and not reader.setters

def test_fade_stale_mode_destination_blocks(reader):
    reader.values[START].update(type='Fade', cueTargetID=str(UUID(int=99)), patchTargetID='', targetMode=1)
    result = remaining.edit_remaining_cues(reader, WS, [{'cue_id': START,
        'properties': {'targetMode': 0}}], True, family='fade')
    assert not result['ok'] and not reader.setters

def test_patch_fade_relative_silence_blocks(reader):
    patch = str(UUID(int=100)).upper()
    reader.values[START].update(type='Fade', cueTargetID='', patchTargetID=patch,
        targetMode=1, levelsMode=1, doLevel=[[True, True, True]],
        **{'sliderLevel/1': 0})
    original = reader._request
    def request(address, *args, **kwargs):
        if address.endswith('settings/audio/minVolume'):
            return SimpleNamespace(data=-60)
        return original(address, *args, **kwargs)
    reader._request = request
    result = remaining.edit_remaining_cues(reader, WS, [{'cue_id': START,
        'operations': [{'property': 'sliderLevel', 'args': {'channel': 1, 'decibel': '-inf'}}]}], True, family='fade')
    assert not result['ok'] and not reader.setters

def test_indexed_operation_limit_is_strict():
    from pydantic import ValidationError
    operation = {'property': 'level', 'args': {'inChannel': 1, 'outChannel': 1, 'decibel': 0}}
    with pytest.raises(ValidationError):
        remaining.FAMILIES['audio'].model_validate({'cue_id': START, 'operations': [operation] * 51})

def test_pending_capabilities_do_not_advertise_writes():
    caps = remaining.capabilities('network')
    assert 'parameterValue' not in caps['allowed_properties']
    assert caps['property_capabilities']['parameterValue']['state'] == 'pending_validation'
    assert caps['property_capabilities']['Trim']['state'] == 'unavailable_via_osc'
    assert caps['max_indexed_operations_per_cue'] == 50
    assert remaining.capabilities('script')['max_indexed_operations_per_cue'] == 0

def test_read_checks_uuid_and_type_again_after_scalar_queries(reader):
    original = reader._request
    def request(address, *args, **kwargs):
        response = original(address, *args, **kwargs)
        if address.endswith('/rate') and not args:
            reader.values[START]['type'] = 'Memo'
        return response
    reader._request = request
    with pytest.raises(ValueError, match='identity changed'):
        remaining.read(reader, WS, START, ['rate'])

def test_bulk_snapshot_retains_reserved_output_columns(reader):
    from qlab_mcp.write.remaining_context import validate
    reader.values[START]['levels'] = [[0] * 129 for _ in range(3)]
    original = reader._request
    def request(address, *args, **kwargs):
        if address.endswith('settings/audio/minVolume'):
            return SimpleNamespace(data=-60)
        return original(address, *args, **kwargs)
    reader._request = request
    op = {'property': 'setSilentLevels', 'key': 'setSilentLevels', 'baseline': reader.values[START]['levels'], 'requested': [], 'arg_values': {}}
    validate(reader, WS, START, 'audio', [op], reader.values[START])
    assert op['requested'] == [[-60] * 129 for _ in range(3)]

def test_file_target_readback_does_not_hide_broken_media(reader):
    reader.values[START]['isBroken'] = True
    assert not remaining.matches('fileTarget', '/tmp/invalid.mid', '/tmp/invalid.mid', {}, reader, WS, START)
    reader.values[START]['isBroken'] = False
    assert remaining.matches('fileTarget', '/tmp/valid.mid', '/tmp/valid.mid', {}, reader, WS, START)

def test_fade_mode_cannot_activate_incompatible_dormant_target(reader):
    reader.values[START].update(type='Fade', cueTargetID=MEMO, patchTargetID=str(UUID(int=100)), targetMode=1,
        doOpacity=False, doRate=False, doRotation=False, doScale=False, doTranslation=False, doLevel=[[True]])
    reader.values[MEMO]['type'] = 'Memo'
    result = remaining.edit_remaining_cues(reader, WS, [{'cue_id': START,
        'properties': {'targetMode': 0}}], True, family='fade')
    assert not result['ok'] and not reader.setters
