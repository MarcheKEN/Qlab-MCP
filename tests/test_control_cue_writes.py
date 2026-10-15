"""The control writer validates the whole batch and never retries setters."""
import re
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscPreparationError, OscTimeoutError
from qlab_mcp.models import UpdateCuesResult
from qlab_mcp.write import control as writes

WS, START, WAIT, MEMO, TARGET, LIST = [str(UUID(int=n)).upper() for n in range(1, 7)]


class Reader:
    def __init__(self):
        self.client = SimpleNamespace(config=QLabConfig(enable_write=True, passcode="test"))
        self.values = {
            uid: {"uniqueID": uid, "type": kind, "parent": LIST, "name": "old", "number": str(i),
                  "duration": 1, "allowsEditingDuration": kind == "Wait", "hasCueTargets": kind == "Start",
                  "cueTargetID": "", "targetMode": 0, "isRunning": False, "isPaused": False,
                  "isAuditioning": False, "isBroken": False, "isWarning": False,
                  "duckLevel": 0, "duckOthers": False, "duckTime": 1,
                  "secondTriggerAction": 0, "secondTriggerOnRelease": False,
                  "fadeAndStopOthers": False, "fadeAndStopOthersTime": 1,
                  "timecodeTrigger/hours": 1, "timecodeTrigger/minutes": 0,
                  "timecodeTrigger/seconds": 0, "timecodeTrigger/frames": 0,
                  "timecodeTrigger/bits": 0, "timecodeTrigger/text": "1:00:00:00"}
            for i, (uid, kind) in enumerate([(START, "Start"), (WAIT, "Wait"), (MEMO, "Memo"), (TARGET, "Audio")])
        }
        self.values[LIST] = {"uniqueID": LIST, "type": "Cue List", "timecodeSMPTEFormat": 3}
        for uid in (START, WAIT, MEMO, TARGET):
            self.values[uid]["timecodeTrigger"] = dict(hours=1, minutes=0, seconds=0, frames=0, bits=0)
        self.setters = []
        self.fail = None
        self.active = False

    def _resolve_workspace_id_strict(self, workspace):
        assert workspace == WS
        return workspace

    def get_running_cues(self, *args, **kwargs):
        return {"running_cues": [START] if self.active else []}

    def get_cue_lists(self, *args, **kwargs):
        return {"cue_lists": [{"uniqueID": LIST, "type": "Cue List"}]}

    def read_cue_values(self, ws, uid, keys, **kwargs):
        value = self.values.get(uid, {})
        return {"values": {key: value[key] for key in keys if key in value}}

    def _request(self, address, *args, **kwargs):
        uid, field = address.split("/cue_id/")[1].split("/", 1)
        if args:
            assert kwargs["ensure_always_reply"] and kwargs["allow_empty_data"]
            if self.fail == "prepare":
                raise OscPreparationError("preparation failed")
            self.setters.append((uid, field, args))
            self.values[uid][field] = args[0]
            if field.startswith("timecodeTrigger/"):
                component = field.split("/")[1]
                if component == "text":
                    match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})[:;](\d{2})(?:\.(\d{2}))?", args[0])
                    self.values[uid]["timecodeTrigger"].update(zip(
                        ("hours", "minutes", "seconds", "frames", "bits"),
                        [int(value or 0) for value in match.groups()], strict=True))
                else:
                    self.values[uid]["timecodeTrigger"][component] = args[0]
            if self.fail == "timeout":
                raise OscTimeoutError("timeout")
            if self.fail == "mismatch":
                self.values[uid][field] = "different"
        return SimpleNamespace(data=self.values[uid].get(field))


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr(writes, "check_write_readiness", lambda *a: {"ok": True})
    monkeypatch.setattr(writes, "ensure_write_ready", lambda *a: None)
    return Reader()


def request(uid=START, **properties):
    return {"cue_id": uid, "properties": properties}


def execute(reader, items):
    plan = writes.edit_control_cues(reader, WS, items, True)
    assert plan["ok"], plan
    for item, result in zip(items, plan["results"], strict=True):
        item["confirm_gates"] = [op["confirm_token"] for op in result["planned_operations"]]
    return writes.edit_control_cues(reader, WS, items, False)


def test_mixed_batch_and_targets(reader):
    items = [request(START, cueTargetID=TARGET, name="start"), request(WAIT, duration=2), request(MEMO, name="memo")]
    plan = writes.edit_control_cues(reader, WS, items, True)
    assert plan["ok"] and not reader.setters
    assert all(not x["executed_operations"] for x in plan["results"])
    result = execute(reader, items)
    assert result["updated_count"] == 3
    UpdateCuesResult.model_validate(result)


@pytest.mark.parametrize("item", [request(WAIT, cueTargetID=TARGET), request(MEMO, duration=2),
                                  request(TARGET, name="wrong"), request(START, cueTargetID=START),
                                  request(START, cueTargetID=str(UUID(int=99))), request(START, fadeAndStopOthers=1)])
def test_bad_item_blocks_entire_batch(reader, item):
    good = WAIT if item["cue_id"] != WAIT else MEMO
    result = writes.edit_control_cues(reader, WS, [request(good, name="good"), item], True)
    assert not result["ok"] and not reader.setters


@pytest.mark.parametrize("properties", [{"duration": True}, {"name": None}, {"unknown": 1},
                                        {"fadeAndStopOthers": 4}, {"secondTriggerAction": 6},
                                        {"duckLevel": float("nan")}, {"timecodeTrigger": {}}])
def test_strict_properties(properties):
    with pytest.raises(ValidationError):
        writes.ControlCueEditInput.model_validate(request(**properties))


def test_timecode_format_uses_identity_checked_values(reader):
    original = reader._request
    def request_osc(address, *args, **kwargs):
        assert not address.endswith('/timecodeSMPTEFormat'), 'Use the fresh list valuesForKeys payload'
        return original(address, *args, **kwargs)
    reader._request = request_osc
    result = execute(reader, [request(START, **{'timecodeTrigger/text': '1:02:03:04'})])
    assert result['ok'] and len(reader.setters) == 1


def test_timecode_format_accepts_qlab_cart_type(reader):
    reader.values[LIST]['type'] = 'Cart'
    assert writes._timecode_format(reader, WS, LIST) == 3


def test_duplicates_and_bounds(reader):
    for items in ([], [request()] * 2, [request()] * 51):
        with pytest.raises(ValueError):
            writes.edit_control_cues(reader, WS, items, True)


def test_token_replay_and_stale_baseline(reader):
    items = [request(name="changed")]
    result = execute(reader, items)
    assert result["ok"]
    assert not writes.edit_control_cues(reader, WS, items, False)["ok"]
    plan = writes.edit_control_cues(reader, WS, [request(name="next")], True)
    token = plan["results"][0]["planned_operations"][0]["confirm_token"]
    reader.values[START]["name"] = "external"
    assert not writes.edit_control_cues(reader, WS, [{**request(name="next"), "confirm_gates": [token]}], False)["ok"]
    assert len(reader.setters) == 1


def test_expiry(reader, monkeypatch):
    items = [request(name="changed")]
    plan = writes.edit_control_cues(reader, WS, items, True)
    items[0]["confirm_gates"] = [plan["results"][0]["planned_operations"][0]["confirm_token"]]
    monkeypatch.setattr(writes.time, "time", lambda: 10**12)
    assert not writes.edit_control_cues(reader, WS, items, False)["ok"]
    assert not reader.setters


@pytest.mark.parametrize("failure,expected", [("prepare", 0), ("timeout", 1), ("mismatch", 1)])
def test_preparation_timeout_and_stop(reader, failure, expected):
    reader.fail = failure
    result = execute(reader, [request(name="changed"), request(MEMO, name="pending")])
    if failure == "timeout":
        assert result["ok"] and len(reader.setters) == 2
        assert result["timeout_confirmed_count"] == 2
    else:
        assert not result["ok"] and len(reader.setters) == expected
        assert result["results"][1]["status"] == "planned"


def test_activity_and_readiness(reader, monkeypatch):
    reader.active = True
    assert not writes.edit_control_cues(reader, WS, [request(name="x")], True)["ok"]
    reader.active = False
    monkeypatch.setattr(writes, "check_write_readiness", lambda *a: {"ok": False, "message": "Edit required"})
    assert not writes.edit_control_cues(reader, WS, [request(name="x")], True)["ok"]


@pytest.mark.parametrize("value", ["garbage", "00:61:00:00", "00:00:00:30"])
def test_timecode_format(reader, value):
    assert not writes.edit_control_cues(reader, WS, [request(**{"timecodeTrigger/text": value})], True)["ok"]


def test_drop_frame(reader):
    reader.values[LIST]["timecodeSMPTEFormat"] = 2
    assert not writes.edit_control_cues(reader, WS, [request(**{"timecodeTrigger/text": "00:01:00;00"})], True)["ok"]
    assert writes.edit_control_cues(reader, WS, [request(**{"timecodeTrigger/text": "00:10:00;00"})], True)["ok"]


def test_reset_patch_and_mode(reader, monkeypatch):
    patch = str(UUID(int=70)).upper()
    reader.values[START].update(type="Reset", canHavePatchTargets=True, patchTargetID="")
    original = reader._request
    def patch_requests(address, *args, **kwargs):
        if address.endswith('/settings/audio/patchList'):
            return SimpleNamespace(data=[{"uniqueID": patch}])
        if '/settings/audio/patchID/' in address:
            return SimpleNamespace(data={"uniqueID": patch, "name": "test", "deviceID": "device"})
        return original(address, *args, **kwargs)
    monkeypatch.setattr(reader, '_request', patch_requests)
    result = execute(reader, [request(patchTargetID=patch)])
    assert result['ok']
    assert [(field, args) for _, field, args in reader.setters] == [('targetMode', (1,)), ('patchTargetID', (patch,))]
    result = execute(reader, [request(cueTargetID=TARGET)])
    assert result['ok'] and reader.values[START]['targetMode'] == 0
    assert not writes.edit_control_cues(reader, WS, [request(cueTargetID=TARGET, targetMode=1)], True)['ok']
    assert not writes.edit_control_cues(reader, WS, [request(patchTargetID=str(UUID(int=71)))], True)['ok']


def test_target_or_format_changes_invalidate_confirmation(reader):
    for properties, object_id, key, changed in [(dict(cueTargetID=TARGET), TARGET, 'isWarning', True),
          ({'timecodeTrigger/frames': 3}, LIST, 'timecodeSMPTEFormat', 0)]:
        item=request(**properties)
        plan=writes.edit_control_cues(reader, WS, [item], True)
        item['confirm_gates']=[x['confirm_token'] for x in plan['results'][0]['planned_operations']]
        reader.values[object_id][key]=changed
        assert not writes.edit_control_cues(reader, WS, [item], False)['ok']
        assert not reader.setters


def test_unknown_activity_blocks(reader):
    reader.values[START].pop('isPaused')
    assert not writes.edit_control_cues(reader, WS, [request(name='x')], True)['ok']


def test_all_ten_types_and_fifty_items(reader):
    items=[]
    for index in range(50):
        uid=str(UUID(int=index+100)).upper()
        reader.values[uid]={**reader.values[START], 'uniqueID':uid, 'type':writes.CONTROL_EDIT_TYPES[index % 10]}
        items.append(request(uid, name='new'))
    result=execute(reader, items)
    assert result['updated_count']==50 and len(reader.setters)==50


def test_timecode_text_zero_padding_verification(reader):
    original=reader._request
    def canonical(address, *args, **kwargs):
        reply=original(address,*args,**kwargs)
        if args and address.endswith('/timecodeTrigger/text'):
            reader.values[START]['timecodeTrigger/text']='1:00:01:00'
        return reply
    reader._request=canonical
    assert execute(reader, [request(**{'timecodeTrigger/text':'01:00:01:00'})])['ok']


def test_scalar_fade_scope_overrides_bulk_boolean(reader):
    original=reader._request
    def scalar_scope(address, *args, **kwargs):
        reply=original(address,*args,**kwargs)
        if address.endswith('/fadeAndStopOthers') and not args:
            return SimpleNamespace(data=getattr(reader, 'scope', 2))
        if address.endswith('/fadeAndStopOthers') and args:
            reader.scope=args[0]
            reader.values[START]['fadeAndStopOthers']=bool(args[0])
        return reply
    reader._request=scalar_scope
    result=execute(reader, [request(fadeAndStopOthers=3)])
    assert result['ok'] and result['results'][0]['before']['fadeAndStopOthers']==2
    assert result['results'][0]['after']['fadeAndStopOthers']==3


def test_new_number_and_collision(reader, monkeypatch):
    monkeypatch.setattr(writes, '_read_snapshot', lambda *a: {'nodes':reader.values})
    assert execute(reader, [request(number='CONTROL_NEW')])['ok']
    assert not writes.edit_control_cues(reader, WS, [request(number=reader.values[WAIT]['number'])], True)['ok']


@pytest.mark.parametrize('family,kind', [('devamp','Devamp'), ('target','Target')])
def test_specialized_basics_and_target(reader, family, kind):
    reader.values[MEMO].update(type=kind, hasCueTargets=True, cueTargetID='')
    if family=='devamp': reader.values[MEMO].update(devampType=1, startNextCueWhenSliceEnds=False, stopTargetWhenSliceEnds=False)
    uid=TARGET if family=='devamp' else START
    items=[request(MEMO, name='special', cueTargetID=uid)]
    plan=writes.edit_control_cues(reader, WS, items, True, _family=family)
    assert plan['ok'] and not reader.setters
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    result=writes.edit_control_cues(reader, WS, items, False, _family=family)
    assert result['ok']
    assert writes.control_edit_capabilities(kind)['tool']==f'qlab_edit_{family}_cues'
    # Exact family guard; cannot submit these confirmations through Control.
    assert not writes.edit_control_cues(reader, WS, items, False)['ok']
    items=[request(MEMO, cueTargetID='')]
    plan=writes.edit_control_cues(reader, WS, items, True, _family=family)
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    assert writes.edit_control_cues(reader, WS, items, False, _family=family)['ok']


@pytest.mark.parametrize('properties', [{'devampType':0},{'devampType':3},{'devampType':True}, {'startNextCueWhenSliceEnds':1}, {'duration':1},{'targetMode':0}])
def test_devamp_schema_rejects_invalid(properties):
    with pytest.raises(ValidationError): writes.DevampCueEditInput.model_validate(request(**properties))


@pytest.mark.parametrize('properties', [{'assignedNumber':2}, {'devampType':1},{'duration':1},{'patchTargetID':TARGET}])
def test_target_schema_excludes_undocumented_or_inapplicable(properties):
    with pytest.raises(ValidationError): writes.TargetCueEditInput.model_validate(request(**properties))


def test_devamp_settings_dependencies(reader):
    reader.values[MEMO].update(type='Devamp', hasCueTargets=True, cueTargetID=TARGET, devampType=1,
                               startNextCueWhenSliceEnds=False, stopTargetWhenSliceEnds=False)
    items=[request(MEMO, devampType=2, startNextCueWhenSliceEnds=True, stopTargetWhenSliceEnds=True)]
    plan=writes.edit_devamp_cues(reader, WS, items, True)
    assert plan['ok']
    items[0]['confirm_gates']=[x['confirm_token'] for x in plan['results'][0]['planned_operations']]
    assert writes.edit_devamp_cues(reader, WS, items, False)['ok']
    reader.values[MEMO]['startNextCueWhenSliceEnds']=False
    assert not writes.edit_devamp_cues(reader, WS, [request(MEMO, stopTargetWhenSliceEnds=True)], True)['ok']
    assert not writes.edit_devamp_cues(reader, WS, [request(MEMO, cueTargetID=START)], True)['ok']
    reader.values[MEMO]['cueTargetID']=''
    assert not writes.edit_devamp_cues(reader, WS, [request(MEMO, devampType=1)], True)['ok']


def test_devamp_cannot_disable_start_next_while_stop_target_remains_enabled(reader):
    reader.values[MEMO].update(type='Devamp', hasCueTargets=True, cueTargetID=TARGET,
                               devampType=1, startNextCueWhenSliceEnds=True,
                               stopTargetWhenSliceEnds=True)
    result = writes.edit_devamp_cues(
        reader, WS, [request(MEMO, startNextCueWhenSliceEnds=False)], True
    )
    assert not result['ok']
    assert not reader.setters


@pytest.mark.parametrize('kind,accepts', [('Fade',True),('Audio',False),('Wait',False)])
def test_target_requires_retargetable_nonfade_cue(reader, kind, accepts):
    reader.values[MEMO].update(type='Target', hasCueTargets=True)
    reader.values[START].update(type=kind, hasCueTargets=accepts)
    assert not writes.edit_target_cues(reader, WS, [request(MEMO, cueTargetID=START)], True)['ok']
    assert not reader.setters


def test_fastmcp_specialized_calls(reader, monkeypatch):
    import asyncio
    from fastmcp import Client
    import qlab_mcp.server as server
    monkeypatch.setattr(server, '_run_tool', lambda fn, **kwargs: fn(reader))
    async def run():
        async with Client(server.mcp) as client:
            for family, kind in [('devamp','Devamp'),('target','Target')]:
                reader.values[MEMO].update(type=kind)
                response=await client.call_tool(f'qlab_edit_{family}_cues', {'workspace_id':WS,'updates':[request(MEMO, name='test')],'dry_run':True})
                assert not response.is_error and response.structured_content['ok']
    asyncio.run(run())


def test_timecode_unrequested_component_race_blocks_setter(reader,monkeypatch):
    items=[request(**{'timecodeTrigger/frames':5})]
    plan=writes.edit_control_cues(reader,WS,items,True)
    items[0]['confirm_gates']=[op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    calls=0
    def ready(*args):
        nonlocal calls
        calls+=1
        if calls==2:
            reader.values[START]['timecodeTrigger']['hours']=2
    monkeypatch.setattr(writes,'ensure_write_ready',ready)
    result=writes.edit_control_cues(reader,WS,items,False)
    assert not result['ok'] and not reader.setters


def test_timecode_cumulative_component_setters_advance_baseline(reader):
    result=execute(reader,[request(**{'timecodeTrigger/hours':2,'timecodeTrigger/frames':5})])
    assert result['ok'] and len(reader.setters)==2
    assert reader.values[START]['timecodeTrigger']['hours']==2
    assert reader.values[START]['timecodeTrigger']['frames']==5
