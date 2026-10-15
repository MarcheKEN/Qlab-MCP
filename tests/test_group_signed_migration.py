"""Group/List migration and generic exclusion regressions, with no live QLab."""
import pytest
from test_control_cue_writes import Reader, WS, START, LIST
from qlab_mcp.write import control
from qlab_mcp.write.group import edit_group_cues
from qlab_mcp.write.registry import normalize_update_request, real_write_permission_errors

@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr(control, 'check_write_readiness', lambda *a: {'ok': True})
    monkeypatch.setattr(control, 'ensure_write_ready', lambda *a: None)
    reader = Reader()
    reader.values[START].update(type='Group', mode=6, armed=True, isLoaded=False,
        isOverridden=False, isActionRunning=False, isChildAuditioning=False,
        **{'playlist/doLoop':False,'playlist/doShuffle':False,'playlist/doCrossfade':False,
           'playlist/crossfade/duration':0})
    reader.get_cue_children = lambda *a, **k: {'children':[]}
    return reader

@pytest.mark.parametrize('properties', [{'name':'new'}, {'secondTriggerAction':7}, {'mode':3}])
def test_group_signed_execution_and_replay(reader, properties):
    items = [{'cue_id':START,'properties':properties}]
    planned = edit_group_cues(reader, WS, items, True)
    assert planned['ok'], planned
    items[0]['confirm_gates'] = [op['confirm_token'] for op in planned['results'][0]['planned_operations']]
    assert all(t.startswith('confirm:controlCue:') for t in items[0]['confirm_gates'])
    assert edit_group_cues(reader, WS, items, False)['ok']
    assert not edit_group_cues(reader, WS, items, False)['ok']
    assert len(reader.setters)==1

def test_group_action_requires_playlist(reader):
    reader.values[START]['mode']=3
    result=edit_group_cues(reader,WS,[{'cue_id':START,'properties':{'secondTriggerAction':6}}],True)
    assert not result['ok'] and not reader.setters

@pytest.mark.parametrize('profile,properties', [('script_basic',{'scriptSource':'bad'}),
    ('audio_basic',{'audioMapID':'map'}),('group_basic',{'playheadID':'x'})])
def test_generic_token_cannot_enable_excluded_operation(profile,properties):
    _, operations = normalize_update_request(profile,properties,None)
    assert real_write_permission_errors(profile,operations,[op['confirm_token'] for op in operations])

from qlab_mcp.write.cue_lists import edit_cue_lists

def test_cue_list_signed_basics_and_timecode(reader):
    reader.values[LIST].update(parent='',name='old', number='',isRunning=False,isPaused=False,
        isAuditioning=False,timecodeSyncMode=0,timecodeFreewheelTime=1)
    items=[{'cue_list_id':LIST,'properties':{'name':'main','smpte_format':'25_fps'}}]
    planned=edit_cue_lists(reader,WS,items,True)
    assert planned['ok'],planned
    items[0]['confirm_gates']=[op['confirm_token'] for op in planned['results'][0]['planned_operations']]
    assert edit_cue_lists(reader,WS,items,False)['ok']
    assert len(reader.setters)==2
    assert not edit_cue_lists(reader,WS,items,False)['ok']

def test_group_mode_blocks_playlist_action_until_resolved(reader):
    reader.values[START]['secondTriggerAction']=7
    result=edit_group_cues(reader,WS,[{'cue_id':START,'properties':{'mode':3}}],True)
    assert not result['ok'] and not reader.setters

def test_group_trigger_uses_containing_list_format(reader):
    reader.values[LIST]['timecodeSMPTEFormat']=0
    result=edit_group_cues(reader,WS,[{'cue_id':START,'properties':{'timecodeTrigger/frames':24}}],True)
    assert not result['ok'] and not reader.setters

def test_group_mode_changed_after_batch_preflight_blocks_setter(reader,monkeypatch):
    items=[{'cue_id':START,'properties':{'secondTriggerAction':7}}]
    plan=edit_group_cues(reader,WS,items,True)
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    original=control._scalar
    def scalar(r,ws,uid,key):
        if key=='mode':
            return 3
        return original(r,ws,uid,key)
    monkeypatch.setattr(control,'_scalar',scalar)
    result=edit_group_cues(reader,WS,items,False)
    assert not result['ok'] and not reader.setters

def test_generic_internal_control_profile_remains_blocked():
    _,operations=normalize_update_request('control_basic',{'name':'new'},None)
    assert operations[0]['real_write_enabled']
    assert 'profile' in real_write_permission_errors('control_basic',operations)

from test_control_cue_writes import WAIT

def add_group_child(reader):
    reader.values[WAIT].update(armed=True,continueMode=1,preWait=0,postWait=0,duration=2,
        isLoaded=False,isOverridden=False,isActionRunning=False)
    reader.get_cue_children=lambda *a,**k:{'children':[{'uniqueID':WAIT}]}

def test_group_mode_token_binds_children(reader):
    add_group_child(reader)
    items=[{'cue_id':START,'properties':{'mode':3}}]
    plan=edit_group_cues(reader,WS,items,True)
    assert plan['ok'],plan
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    reader.values[WAIT]['postWait']=1
    assert not edit_group_cues(reader,WS,items,False)['ok']
    assert not reader.setters

@pytest.mark.parametrize('field,value,success',[('continueMode',0,True),('postWait',1,False)])
def test_group_mode_reports_expected_and_unexpected_child_effects(reader,field,value,success):
    add_group_child(reader)
    items=[{'cue_id':START,'properties':{'mode':3}}]
    plan=edit_group_cues(reader,WS,items,True)
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    request=reader._request
    def setter(address,*args,**kwargs):
        response=request(address,*args,**kwargs)
        if args and address.endswith('/mode'):
            reader.values[WAIT][field]=value
        return response
    reader._request=setter
    result=edit_group_cues(reader,WS,items,False)
    assert result['ok'] is success
    assert len(reader.setters)==1
    assert result['results'][0]['planned_operations'][0]['child_side_effects'][0]['field']==field

def test_mode_guard_rechecks_and_preserves_second_trigger(reader,monkeypatch):
    items=[{'cue_id':START,'properties':{'mode':3}}]
    plan=edit_group_cues(reader,WS,items,True)
    assert plan['ok'],plan
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    calls=0
    def ready(*args):
        nonlocal calls
        calls+=1
        if calls==2:
            reader.values[START]['secondTriggerAction']=7
    monkeypatch.setattr(control,'ensure_write_ready',ready)
    assert not edit_group_cues(reader,WS,items,False)['ok']
    assert not reader.setters


def test_mode_readback_rejects_changed_second_trigger(reader):
    items=[{'cue_id':START,'properties':{'mode':3}}]
    plan=edit_group_cues(reader,WS,items,True)
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    original=reader._request
    def setter(address,*args,**kwargs):
        result=original(address,*args,**kwargs)
        if args:
            reader.values[START]['secondTriggerAction']=7
        return result
    reader._request=setter
    result=edit_group_cues(reader,WS,items,False)
    assert not result['ok'] and len(reader.setters)==1
    assert 'source side effects' in str(result['errors']) or 'source side effects' in str(result['results'][0]['errors'])
