"""Synthetic keyed archives, never a user's workspace or vendor fixture library."""
import plistlib
import pytest


def workspace():
    objects = ['$null']
    def add(value):
        objects.append(value)
        return plistlib.UID(len(objects)-1)
    def cls(name):
        return add({'$classname': name, '$classes': [name, 'NSObject']})
    def array(values):
        return add({'$class': cls('NSMutableArray'), 'NS.objects': values})
    def mapping(values):
        return add({'$class': cls('NSMutableDictionary'), 'NS.keys': [add(k) for k in values], 'NS.objects': list(values.values())})
    scalar = add({'$class': cls('LightCueInstrumentDefinitionParameterScalar'), 'name': add('intensity'), 'type': add('scalar'), 'twoBytes': False, 'valueIsPercentage': True, 'homeValue': 0, 'homeValueDouble': 0.0})
    definition = add({'$class': cls('LightCueInstrumentDefinition'), 'name': add('Dimmer'), 'manufacturer': add('Example'), 'definitionVersion': 2, 'defaultParameter': 0, 'parameters': mapping({0:scalar})})
    defs = add({'$class': cls('LightLibrary'), 'library': add({'$class': cls('OrderedDictionary'), 'dictionary': mapping({'Dimmer': definition}), 'array': array([add('Dimmer')])})})
    fixture = add({'$class': cls('LightCueInstrument'), 'name': add('Door'), 'comment': add('Keep'), 'definitionName': add('Dimmer'), 'address': -1, 'lightOutputID': 1, 'dmxUniverse': plistlib.UID(0)})
    root = add({'$class': cls('LightPatch'), 'library': defs, 'itemList': array([fixture]), 'midiTriggers': array([]), 'unknown': add('preserve')})
    inner = plistlib.dumps({'$archiver': 'NSKeyedArchiver', '$version': 100000, '$top': {'root': root}, '$objects': objects},fmt=plistlib.FMT_BINARY,sort_keys=False)
    objects = ['$null']
    patch = add({'$class': cls('NSMutableData'), 'NS.data':inner})
    root = mapping({'uniqueID': add('11111111-1111-4111-8111-111111111111'), 'QLabBuildNumber': 5510, 'QLabShortVersionString': add('5.5.10'), 'settings': mapping({'Light': mapping({'patch': patch}),'General':mapping({'doStartOnOpen':False,'doStartOnClose':False})}), 'unrelated': add('keep cues')})
    return plistlib.dumps({'$archiver': 'NSKeyedArchiver', '$version': 100000, '$top': {'root': root}, '$objects': objects},fmt=plistlib.FMT_BINARY,sort_keys=False)


def test_noop_preserves_exact_bytes():
    from qlab_mcp.light_patch.archive import plan_patch
    source=workspace()
    plan=plan_patch(source, [])
    assert plan['output_bytes'] == source
    assert plan['summary']['instruments'][0]['name']=='Door'
    assert plan['changes']==[]


def test_update_note_preserves_original_and_unrelated_data():
    from qlab_mcp.light_patch.archive import plan_patch, Patch
    source=workspace()
    plan=plan_patch(source,[{'action':'update_instrument','name':'Door','note':'Changed'}])
    assert plan['summary']['instruments'][0]['note']=='Changed'
    assert Patch(source).snapshot()['instruments'][0]['note']=='Keep'
    assert plan_patch(plan['output_bytes'],[])['summary']==plan['summary']
    outer=Patch(plan['output_bytes']).outer
    assert outer.ref(outer.mapping(outer.root)['unrelated'])=='keep cues'


def test_batch_creates_renames_and_deletes_internal_references():
    from qlab_mcp.light_patch.archive import plan_patch
    ops=[{'action':'create_instrument','name':'Roof','definition':'Dimmer','output':{'backend':'artnet','net':1,'subnet':2,'universe':3,'address':512}},
         {'action':'create_group','name':'Front','members':['Door','Roof']},
         {'action':'rename_instrument','name':'Door','new_name':'Entry'},
         {'action':'delete_instrument','name':'Roof'}]
    p=plan_patch(workspace(),ops)
    assert [i['name'] for i in p['summary']['instruments']]==['Entry']
    assert p['summary']['groups'][0]['members']==['Entry']
    assert p['warnings']


def test_final_state_validation_allows_reassignment_then_definition_delete():
    from qlab_mcp.light_patch.archive import plan_patch
    p=plan_patch(workspace(),[
        {'action':'create_definition','name':'Other','manufacturer':'Example','parameters':[{'type':'scalar','name':'intensity'}]},
        {'action':'delete_definition','name':'Dimmer'},
        {'action':'update_instrument','name':'Door','definition':'Other'}])
    assert [d['name'] for d in p['summary']['definitions']]==['Other']


def test_overlap_and_cycles_reject_entire_batch():
    from qlab_mcp.light_patch.archive import plan_patch
    output={'backend':'artnet','net':0,'subnet':0,'universe':0,'address':1}
    with pytest.raises(ValueError,match='overlap'):
        plan_patch(workspace(),[{'action':'update_instrument','name':'Door','output':output},{'action':'create_instrument','name':'Roof','definition':'Dimmer','output':output}])
    with pytest.raises(ValueError,match='cycle'):
        plan_patch(workspace(),[{'action':'create_group','name':'A','members':['B']},{'action':'create_group','name':'B','members':['A']}])


def test_usb_output_preserves_exact_device_identity():
    from qlab_mcp.light_patch.archive import plan_patch
    output={'backend':'usb','device_serial':'SYNTHETIC USB','device_name':'Synthetic device','device_universes':2,'universe':1,'address':512}
    plan=plan_patch(workspace(),[{'action':'update_instrument','name':'Door','output':output}])
    assert plan['summary']['instruments'][0]['output']==output


def test_automatic_open_or_close_cues_block_file_authoring():
    from qlab_mcp.light_patch.archive import Patch,plan_patch
    patch=Patch(workspace());a=patch.outer
    general=a.mapping(a.mapping(a.mapping(a.root)['settings'])['General'])
    value=a.ref(a.mapping(a.mapping(a.root)['settings'])['General'])
    index=[a.ref(k) for k in value['NS.keys']].index('doStartOnOpen')
    value['NS.objects'][index]=True
    with pytest.raises(ValueError,match='automatic'):
        plan_patch(a.dump(),[{'action':'update_instrument','name':'Door','note':'Changed'}])


def test_live_group_membership_mismatch_is_not_verified():
    from qlab_mcp.light_patch.archive import plan_patch,verify_live_patch
    plan=plan_patch(workspace(),[{'action':'create_group','name':'Front','members':['Door']}])
    payload={'instruments':[{'name':'Door','comment':'Keep','definition':{'name':'Dimmer'},'patched':False}], 'groups':[{'name':'Front','members':[]}]}
    assert not verify_live_patch(plan['summary'],payload)


def test_repeated_identical_create_is_noop():
    from qlab_mcp.light_patch.archive import plan_patch
    operation={'action':'create_instrument','name':'Roof','definition':'Dimmer'}
    first=plan_patch(workspace(),[operation])
    second=plan_patch(first['output_bytes'],[operation])
    assert second['changes']==[] and second['output_bytes']==first['output_bytes']


def test_parameter_reorder_preserves_default_by_name():
    from qlab_mcp.light_patch.archive import plan_patch
    p=plan_patch(workspace(),[{'action':'update_definition','name':'Dimmer','parameters':[{'type':'scalar','name':'other'},{'type':'scalar','name':'intensity'}]}])
    assert p['summary']['definitions'][0]['default_parameter']==1


def test_shared_definition_footprint_rechecks_other_instruments():
    from qlab_mcp.light_patch.archive import plan_patch
    output={'backend':'artnet','net':0,'subnet':0,'universe':0,'address':512}
    p=plan_patch(workspace(),[{'action':'update_instrument','name':'Door','output':output}])
    with pytest.raises(ValueError,match='footprint'):
        plan_patch(p['output_bytes'],[{'action':'update_definition','name':'Dimmer','parameters':[{'type':'scalar','name':'intensity','two_bytes':True}]}])


def test_rename_preserves_existing_member_range_objects():
    from qlab_mcp.light_patch.archive import Patch,plan_patch
    created=plan_patch(workspace(),[{'action':'create_group','name':'Front','members':['Door']}])
    p=Patch(created['output_bytes']);a=p.archive;g=a.ref(p.find('Front','group'));member=a.ref(a.array(g['members'])[0]);rng=a.ref(member['nameRange']);rng['NS.rangeval.location']=a.add(2);rng['NS.rangeval.length']=a.add(3)
    source=p.finish()
    out=Patch(plan_patch(source,[{'action':'rename_instrument','name':'Door','new_name':'Entry'}])['output_bytes'])
    group=out.archive.ref(out.find('Front','group'));value=out.archive.ref(out.archive.array(group['members'])[0]);r=out.archive.ref(value['nameRange'])
    assert out.archive.ref(r['NS.rangeval.location'])==2
    assert out.archive.ref(r['NS.rangeval.length'])==3


def test_outer_patch_carrier_alias_outside_light_is_preserved():
    from qlab_mcp.light_patch.archive import Patch,plan_patch
    p=Patch(workspace());a=p.outer;root=a.root
    settings=a.mapping(a.mapping(a.root)['settings']);light=a.mapping(settings['Light']);carrier=light['patch']
    root['NS.keys'].append(a.add('unrelated_patch_copy'));root['NS.objects'].append(carrier)
    original=p.data_object['NS.data'];source=a.dump()
    output=Patch(plan_patch(source,[{'action':'update_instrument','name':'Door','note':'Changed'}])['output_bytes'])
    root=output.outer.mapping(output.outer.root)
    assert output.outer.ref(root['unrelated_patch_copy'])['NS.data']==original
    assert output.snapshot()['instruments'][0]['note']=='Changed'


def test_existing_overlap_can_be_repaired_by_final_batch():
    from qlab_mcp.light_patch.archive import Patch,plan_patch
    out={'backend':'artnet','net':0,'subnet':0,'universe':0,'address':1}
    valid=plan_patch(workspace(),[{'action':'update_instrument','name':'Door','output':out},{'action':'create_instrument','name':'Roof','definition':'Dimmer'}])
    broken=Patch(valid['output_bytes']);broken.set_output(broken.archive.ref(broken.find('Roof','instrument')),out)
    source=broken.finish()
    assert plan_patch(source,[])['summary']
    fixed=plan_patch(source,[{'action':'update_instrument','name':'Roof','output':{**out,'address':2}}])
    assert fixed['summary']['instruments'][1]['output']['address']==2


def test_live_definition_interpretation_must_match():
    from qlab_mcp.light_patch.archive import plan_patch,verify_live_patch
    summary=plan_patch(workspace(),[])['summary']
    definition={'name':'Dimmer','manufacturer':'Example','defaultParameter':0,'parameters':{'0':{'name':'intensity','type':'scalar','twoBytes':False,'valueIsPercentage':True,'homeValue':0}}}
    payload={'instruments':[{'name':'Door','comment':'Keep','definition':definition,'patched':False}],'groups':[]}
    assert verify_live_patch(summary,payload)
    definition['parameters']['0']['homeValue']=50
    assert not verify_live_patch(summary,payload)
