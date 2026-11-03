"""Graph-preserving video authoring and compatibility checks."""
from copy import deepcopy
import pytest
from qlab_mcp.light_patch.archive import Archive
from test_video_settings import video_workspace as _video_workspace
import plistlib

def video_workspace():
    a=Archive(_video_workspace()); root=a.ref(a.data["$top"]["root"])
    nested=plistlib.dumps({"$archiver":"NSKeyedArchiver","$version":100000,"$top":{"root":plistlib.UID(1)},"$objects":["$null",{"NS.objects":[],"$class":plistlib.UID(2)},{"$classname":"NSMutableArray","$classes":["NSMutableArray","NSArray","NSObject"]}]},fmt=plistlib.FMT_BINARY)
    root["NS.keys"].append(a.add("cueLists"));root["NS.objects"].append(a.add({"$class":a.cls("NSMutableData"),"NS.data":nested}))
    region=next(x for x in a.objects if isinstance(x,dict) and x.get('warpType')==3)
    original=a.array(region['controlPoints'])[0]
    points=[]
    for index,xy in enumerate(((0,0),(1920,0),(0,1080),(1920,1080))):
        obj=deepcopy(a.ref(original));obj['outputPoint']=a.add('{%s, %s}'%xy)
        obj['pristine']=True
        obj['linkID']=a.add({'$class':a.cls('NSUUID'),'NS.uuidbytes':__import__('uuid').UUID(int=index+100).bytes})
        points.append(a.add(obj))
    region['controlPoints']=a.make_array(points)
    return a.dump()

ROUTE='22222222-2222-4222-8222-222222222222'


def test_route_plan_updates_only_requested_fields_and_preserves_other_objects():
    from qlab_mcp.video_archive import plan_video
    source=video_workspace()
    before=Archive(source)
    plan=plan_video(source,[{'kind':'update_route','route_id':ROUTE,'name':'Tour'}],domain='routes')
    after=Archive(plan['output_bytes'])
    old=next(x for x in before.objects if isinstance(x,dict) and x.get('uniqueID')==ROUTE)
    new=next(x for x in after.objects if isinstance(x,dict) and x.get('uniqueID')==ROUTE)
    assert after.ref(new['name'])=='Tour'
    assert {k:v for k,v in new.items() if k!='name'}=={k:v for k,v in old.items() if k!='name'}
    assert plan['changes'] and plan['workspace_id']
    assert plan_video(source,[],domain='routes')['output_bytes']==source
    assert plan_video(source,[{'kind':'update_route','route_id':ROUTE,'name':'Output 1'}],domain='routes')['changes']==[]


def test_route_invalid_values_and_deletion_in_use_are_blocked():
    from qlab_mcp.video_archive import plan_video
    for op in [dict(kind='update_route',route_id=ROUTE,rotation=13),dict(kind='delete_route',route_id=ROUTE)]:
        with pytest.raises(ValueError):
            plan_video(video_workspace(),[op],domain='routes')


def test_stage_and_region_batch_uses_local_refs_and_preserves_cues():
    from qlab_mcp.video_archive import plan_video
    b=video_workspace(); before=Archive(b)
    p=plan_video(b,[dict(kind='create_stage',client_ref='s',name='Tour',width=800,height=600),
      dict(kind='create_region',stage_id='@s',client_ref='r',route_id=ROUTE,
           bounds=dict(x=0,y=0,width=800,height=600))],domain='stages')
    stage=p['summary']['stages'][-1]
    assert stage['name']=='Tour' and len(stage['regions'])==1
    assert stage['regions'][0]['stage_id']==stage['id']
    after=Archive(p['output_bytes'])
    assert after.ref(after.mapping(after.root)['cueLists'])==before.ref(before.mapping(before.root)['cueLists'])
    assert p['created_refs']['s']==stage['id']
    assert plan_video(b,[dict(kind='create_stage',client_ref='s',name='Tour',width=800,height=600)],domain='stages')['created_refs']['s']==p['created_refs']['s']


def test_input_and_device_creation_are_separate_domains_and_duplicate_names_block():
    from qlab_mcp.video_archive import plan_video
    b=video_workspace()
    p=plan_video(b,[dict(kind='create_input',client_ref='p',name='Empty')],domain='inputs')
    assert p['summary']['inputs'][-1]['descriptor'] is None
    p=plan_video(b,[dict(kind='create_device',client_ref='d',name='New',device_type='Syphon',width=800,height=600)],domain='devices')
    assert p['summary']['destinations'][-1]['destination_type']=='Syphon'
    with pytest.raises(ValueError,match='name'):
        plan_video(b,[dict(kind='create_device',client_ref='d',name='NDI',device_type='NDI')],domain='devices')


def test_native_start_close_hooks_are_rejected_without_changing_bytes():
    from qlab_mcp.video_archive import plan_video
    a=Archive(video_workspace()); meta=a.mapping(a.root); settings=a.mapping(meta['settings'])
    if 'General' in settings:
        obj=a.ref(settings['General']); keys=[a.ref(k) for k in obj['NS.keys']];obj['NS.objects'][keys.index('doStartOnOpen')]=a.add(True)
    else:
        obj=a.ref(meta['settings']);obj['NS.keys'].append(a.add('General'));obj['NS.objects'].append(a.make_dict({'doStartOnOpen':a.add(True)}))
    with pytest.raises(ValueError,match='hooks'):
        plan_video(a.dump(),[dict(kind='update_route',route_id=ROUTE,name='No')],domain='routes')


def test_manual_camera_format_is_read_and_auto_removes_only_mode():
    from qlab_mcp.video_archive import plan_video
    b=video_workspace(); uid='camera-1'
    ctx={'formats':{uid:[dict(width=1280,height=720,pixel_format=875704438,frame_rates=[dict(min=15,max=30)])]}}
    patch='99999999-9999-4999-8999-999999999999'
    p=plan_video(b,[dict(kind='update_input',patch_id=patch,mode=dict(width=1280,height=720,pixel_format=875704438,frame_rate=30))],domain='inputs',context=ctx)
    config=p['summary']['inputs'][0]['descriptor']['config']['AVCaptureFormat']
    assert config['pixelWidth']==1280 and config['framesPerSecond']==30
    auto=plan_video(p['output_bytes'],[dict(kind='update_input',patch_id=patch,mode='auto')],domain='inputs')
    assert auto['summary']['inputs'][0]['descriptor']['config']=={}


def test_new_region_warp_mesh_and_linked_point_batch():
    from qlab_mcp.video_archive import plan_video
    ops=[dict(kind='create_stage',client_ref='s',name='Tour',width=800,height=600),
         dict(kind='create_region',client_ref='r',stage_id='@s',route_id=ROUTE,bounds=dict(x=0,y=0,width=800,height=600)),
         dict(kind='update_region',stage_id='@s',region_id='@r',warp='bezier'),
         dict(kind='split_region',stage_id='@s',region_id='@r',width=2,height=2),
         dict(kind='edit_point',stage_id='@s',point=dict(region_id='@r',subregions=[0],index=5),x=90,y=95)]
    p=plan_video(video_workspace(),ops,domain='stages')
    r=p['summary']['stages'][-1]['regions'][0]
    assert r['warp_type']==2 and len(r['mesh_subregions'])==4
    assert r['mesh_subregions'][0]['control_points'][5]['output_point']['components']==[90,95]


def test_public_video_batch_and_legacy_are_exclusive_before_reader(monkeypatch):
    import asyncio
    from fastmcp import Client
    from qlab_mcp import server
    def fail_reader():raise AssertionError('invalid arguments must not create a reader')
    monkeypatch.setattr(server,'_reader',fail_reader)
    async def check():
        async with Client(server.mcp) as client:
            tools={t.name for t in await client.list_tools()}
            assert {'qlab_edit_video_output_devices','qlab_edit_video_input_patches'}<=tools
            for name,target in [('qlab_edit_video_stage','stage_id'),('qlab_edit_video_output_route','route_id')]:
                args={'workspace_id':'11111111-1111-4111-8111-111111111111',target:ROUTE,'operation':{'kind':'name','value':'X'} if target=='stage_id' else {'kind':'enableGuides','value':False},'operations':[{'kind':'delete_stage','stage_id':ROUTE}] if target=='stage_id' else [{'kind':'delete_route','route_id':ROUTE}]}
                r=await client.call_tool(name,args,raise_on_error=False)
                assert r.is_error
    asyncio.run(check())


def test_batch_final_noop_preserves_exact_bytes_and_rotation_swaps_raster():
    from qlab_mcp.video_archive import plan_video
    b=video_workspace()
    p=plan_video(b,[dict(kind='update_route',route_id=ROUTE,name='Temporary'),dict(kind='update_route',route_id=ROUTE,name='Output 1')],domain='routes')
    assert p['output_bytes']==b and p['changes']==[]
    p=plan_video(b,[dict(kind='update_route',route_id=ROUTE,rotation=90)],domain='routes')
    assert p['summary']['routes'][0]['natural_size']['components']==[1080,1920]


def test_deleting_used_device_and_wrong_domain_are_rejected():
    from qlab_mcp.video_archive import plan_video
    from qlab_mcp.video_settings import inspect_saved_video
    b=video_workspace();device=inspect_saved_video(b)['destinations'][0]['id']
    with pytest.raises(ValueError,match='in use'):
        plan_video(b,[dict(kind='delete_device',device_ref='saved-virtual:'+device)],domain='devices')
    with pytest.raises(ValueError):plan_video(b,[dict(kind='delete_device',device_ref=device)],domain='routes')


def test_native_region_verifier_detects_changed_points_and_accepts_float_rounding():
    from qlab_mcp.video_editing import verify_region
    saved=dict(id='r',bounds_on_stage=dict(components=[0,0,10,20]),mesh_width=0,mesh_height=0,warp_type=3,
        control_points=[dict(link_id='l',output_point=dict(components=[1.25,2.5]))],shadow_control_points=[],mesh_subregions=[],route_id=None)
    current=dict(uniqueID='r',boundsOnStage=dict(x=0,y=0,width=10,height=20),meshWidth=0,meshHeight=0,warpType=3,
        controlPoints=[dict(linkID='l',outputPoint=dict(x=1.25000001,y=2.5))],shadowControlPoints=[],meshSubregions=[])
    verify_region(saved,current)
    current['controlPoints'][0]['outputPoint']['x']=9
    with pytest.raises(ValueError,match='point'):verify_region(saved,current)


def test_setting_auto_preserves_unknown_input_configuration():
    from qlab_mcp.video_archive import plan_video
    a=Archive(video_workspace());m=a.mapping(a.root);settings=a.mapping(m['settings']);camera=a.mapping(settings['Camera'])
    patch=a.ref(a.array(camera['cameraPatches'])[0]);descriptor=a.mapping(patch['serializedDescription'])
    a.ref(descriptor['config']).update({'NS.keys':[a.add('vendorSetting')],'NS.objects':[a.add('preserve-me')]})
    p=plan_video(a.dump(),[dict(kind='update_input',patch_id='99999999-9999-4999-8999-999999999999',mode='auto')],domain='inputs')
    assert p['summary']['inputs'][0]['descriptor']['config']=={'vendorSetting':'preserve-me'}


def test_crop_pad_matches_native_pristine_and_deformed_mesh_behavior():
    from qlab_mcp.video_archive import plan_video
    setup=[dict(kind='create_stage',client_ref='s',name='Crop',width=400,height=300),
      dict(kind='create_region',client_ref='r',stage_id='@s',route_id=ROUTE,bounds=dict(x=0,y=0,width=400,height=300)),
      dict(kind='update_region',stage_id='@s',region_id='@r',warp='bezier'),
      dict(kind='split_region',stage_id='@s',region_id='@r',width=2,height=2),
      dict(kind='edit_point',stage_id='@s',point=dict(region_id='@r',subregions=[0],index=5),x=100,y=50)]
    p=plan_video(video_workspace(),setup,domain='stages')
    q=plan_video(p['output_bytes'],[dict(kind='resize_stage',stage_id=p['created_refs']['s'],width=300,height=200,mode='crop_pad',anchor='center')],domain='stages')
    r=q['summary']['stages'][-1]['regions'][0]
    assert r['mesh_width']==2 and len(r['mesh_subregions'])==4
    assert r['mesh_subregions'][0]['control_points'][5]['output_point']['components']==[100,50]
    assert r['mesh_subregions'][1]['control_points'][0]['output_point']['components']==[720,0]
    assert r['mesh_subregions'][1]['initial_bounds_on_route']['components']==[720,0,720,360]


def test_new_mesh_links_shared_vertices_and_reset_distributes_route():
    from qlab_mcp.video_archive import plan_video
    ops=[dict(kind='create_stage',client_ref='s',name='Mesh',width=400,height=300),dict(kind='create_region',client_ref='r',stage_id='@s',route_id=ROUTE,bounds=dict(x=0,y=0,width=400,height=300)),dict(kind='split_region',stage_id='@s',region_id='@r',width=2,height=2,reset=True)]
    p=plan_video(video_workspace(),ops,domain='stages');r=p['summary']['stages'][-1]['regions'][0];a,b=r['mesh_subregions'][:2]
    assert a['control_points'][1]['link_id']==b['control_points'][0]['link_id']
    assert a['control_points'][1]['output_point']['components']==[960,0]
    assert b['control_points'][1]['output_point']['components']==[1920,0]


def test_warp_type_applies_to_all_regions_sharing_exact_route():
    from qlab_mcp.video_archive import plan_video
    ops=[dict(kind='create_stage',client_ref='s',name='Shared',width=800,height=600),
         dict(kind='create_region',client_ref='a',stage_id='@s',route_id=ROUTE,bounds=dict(x=0,y=0,width=400,height=600)),
         dict(kind='create_region',client_ref='b',stage_id='@s',route_id=ROUTE,bounds=dict(x=400,y=0,width=400,height=600)),
         dict(kind='update_region',stage_id='@s',region_id='@a',warp='bezier')]
    result=plan_video(video_workspace(),ops,domain='stages')
    assert all(r['warp_type']==2 for r in result['summary']['stages'][-1]['regions'])


def test_link_merges_existing_groups_without_detaching_unselected_peers():
    from qlab_mcp.video_archive import plan_video
    setup=[dict(kind='create_stage',client_ref='s',name='Links',width=800,height=600),
           dict(kind='create_region',client_ref='r',stage_id='@s',route_id=ROUTE,bounds=dict(x=0,y=0,width=800,height=600)),
           dict(kind='create_region',client_ref='q',stage_id='@s',route_id=ROUTE,bounds=dict(x=0,y=0,width=800,height=600)),
           dict(kind='split_region',stage_id='@s',region_id='@r',width=2,height=1),
           dict(kind='edit_point',stage_id='@s',point=dict(region_id='@q',subregions=[0],index=0),x=960,y=0),
           dict(kind='link_points',stage_id='@s',points=[dict(region_id='@r',subregions=[0],index=1),dict(region_id='@q',subregions=[0],index=0)])]
    p=plan_video(video_workspace(),setup,domain='stages')
    first,second=p['summary']['stages'][-1]['regions']
    a=first['mesh_subregions'][0]['control_points'][1]['link_id']
    assert a==first['mesh_subregions'][1]['control_points'][0]['link_id']
    assert a==second['mesh_subregions'][0]['control_points'][0]['link_id']


def test_manual_input_rejects_interior_rate_not_listed_by_qlab():
    from qlab_mcp.video_archive import plan_video
    with pytest.raises(ValueError,match='not present'):
        plan_video(video_workspace(),[dict(kind='update_input',patch_id='99999999-9999-4999-8999-999999999999',
            mode=dict(width=1280,height=720,pixel_format=875704438,frame_rate=24))],domain='inputs',context={
            'formats':{'camera-1':[dict(width=1280,height=720,pixel_format=875704438,frame_rates=[dict(min=15,max=30)])]}})


def test_stale_virtual_reference_and_unknown_replaced_mesh_data_block():
    from qlab_mcp.video_archive import plan_video,VideoArchive
    source=video_workspace();a=VideoArchive(source,{})
    device=f'{a.hash}:{a.refs["virtualDestinations"][0].data}'
    changed=plan_video(source,[dict(kind='update_route',route_id=ROUTE,name='Changed')],domain='routes')['output_bytes']
    with pytest.raises(ValueError,match='snapshot'):
        plan_video(changed,[dict(kind='update_device',device_ref=device,name='Wrong')],domain='devices')
    p=plan_video(source,[dict(kind='create_stage',client_ref='s',name='Unknown'),dict(kind='create_region',stage_id='@s',client_ref='r',route_id=ROUTE,bounds=dict(x=0,y=0,width=800,height=600))],domain='stages')
    a=VideoArchive(p['output_bytes'],{});stage,region=a.region(p['created_refs']['s'],p['created_refs']['r'])
    a.a.ref(a.array(region,'meshSubregions')[0])['futureField']=a.a.add('preserve')
    with pytest.raises(ValueError,match='Unknown mesh'):
        plan_video(a.a.dump(),[dict(kind='split_region',stage_id=p['created_refs']['s'],region_id=p['created_refs']['r'],width=2,height=2)],domain='stages')


def test_strict_batch_limits_dimensions_and_explicit_null():
    from pydantic import TypeAdapter,ValidationError
    from qlab_mcp.video_models import StageOperations,RouteOperations
    valid=dict(kind='update_route',route_id=ROUTE,width=30000)
    assert TypeAdapter(RouteOperations).validate_python([valid])
    for ops,adapter in [([dict(valid,width=30001)],RouteOperations),([valid]*51,RouteOperations),
                        ([dict(kind='update_stage',stage_id=ROUTE,name=None)],StageOperations),
                        ([dict(kind='split_region',stage_id=ROUTE,region_id=ROUTE,width=3,height=1)],StageOperations)]:
        with pytest.raises(ValidationError):TypeAdapter(adapter).validate_python(ops)


@pytest.mark.parametrize('rate',[22050,44100,48000,88200,96000])
def test_ndi_audio_sample_rate_accepts_qlab_values(rate):
    from qlab_mcp.video_archive import plan_video
    from qlab_mcp.video_settings import inspect_saved_video
    source=video_workspace()
    existing=inspect_saved_video(source)['destinations'][0]
    result=plan_video(source,[dict(kind='create_device',client_ref='ndi',name='Rate',device_type='NDI',audio_sample_rate=rate)],domain='devices')
    device=next(d for d in result['summary']['destinations'] if d['name']=='Rate')
    assert device['fields']['audioSampleRate']==rate
    assert type(device['fields']['audioSampleRate']) is float
    updated=plan_video(source,[dict(kind='update_device',device_ref='saved-virtual:'+existing['id'],audio_sample_rate=rate)],domain='devices')
    assert next(d for d in updated['summary']['destinations'] if d['name']=='NDI')['fields']['audioSampleRate']==rate
    assert type(next(d for d in updated['summary']['destinations'] if d['name']=='NDI')['fields']['audioSampleRate']) is float
    with pytest.raises(ValueError):
        plan_video(source,[dict(kind='create_device',client_ref='bad',name='Bad',device_type='NDI',audio_sample_rate=32000)],domain='devices')


def test_root_route_order_is_exact_and_preserves_route_dependencies():
    from qlab_mcp.video_archive import VideoArchive,plan_video
    source=video_workspace();before=Archive(source);before_editor=VideoArchive(source,{})
    result=plan_video(source,[dict(kind='create_route',client_ref='extra',name='Extra'),
        dict(kind='reorder_routes',route_ids=['@extra',ROUTE])],domain='routes')
    assert [route['id'] for route in result['summary']['routes']]==[result['created_refs']['extra'],ROUTE]
    after=Archive(result['output_bytes']);after_editor=VideoArchive(result['output_bytes'],{})
    before_video=before.mapping(before.mapping(before.mapping(before.root)['settings'])['Video'])
    after_video=after.mapping(after.mapping(after.mapping(after.root)['settings'])['Video'])
    assert [before_editor.ident(before.ref(r)['uniqueID']) for r in before.array(before_video['routes'])]==[ROUTE]
    assert [after_editor.ident(after.ref(r)['uniqueID']) for r in after.array(after_video['routes'])]==[result['created_refs']['extra'],ROUTE]
    old=next(r for r in before.array(before_video['routes']) if before_editor.ident(before.ref(r)['uniqueID'])==ROUTE)
    same=next(r for r in after.array(after_video['routes']) if after_editor.ident(after.ref(r)['uniqueID'])==ROUTE)
    assert before.ref(old)==after.ref(same)
    before_stage=before.array(before_video['stages'])[0]
    after_stage=next(r for r in after.array(after_video['stages']) if after_editor.ident(after.ref(r)['uniqueID'])=='33333333-3333-4333-8333-333333333333')
    assert before.ref(before.array(before.ref(before_stage)['regions'])[0])==after.ref(after.array(after.ref(after_stage)['regions'])[0])
    for order in [['@extra'],[ROUTE,ROUTE]]:
        with pytest.raises(ValueError,match='Route order'):
            plan_video(source,[dict(kind='create_route',client_ref='extra',name='Extra'),
                dict(kind='reorder_routes',route_ids=order)],domain='routes')


def test_root_stage_order_is_exact_and_does_not_change_viewport_layers():
    from qlab_mcp.video_archive import VideoArchive,plan_video
    source=video_workspace();before=Archive(source)
    result=plan_video(source,[dict(kind='create_stage',client_ref='extra',name='Extra'),
        dict(kind='reorder_stages',stage_ids=['@extra','33333333-3333-4333-8333-333333333333'])],domain='stages')
    assert [stage['id'] for stage in result['summary']['stages']]==[result['created_refs']['extra'],'33333333-3333-4333-8333-333333333333']
    after=Archive(result['output_bytes']);after_editor=VideoArchive(result['output_bytes'],{})
    before_video=before.mapping(before.mapping(before.mapping(before.root)['settings'])['Video'])
    after_video=after.mapping(after.mapping(after.mapping(after.root)['settings'])['Video'])
    old=before.array(before_video['stages'])[0]
    same=next(r for r in after.array(after_video['stages']) if after_editor.ident(after.ref(r)['uniqueID'])=='33333333-3333-4333-8333-333333333333')
    assert before.ref(old)==after.ref(same)
    assert after.ref(after.ref(same)['viewport'])['layer']==1000
    for order in [['@extra'],['33333333-3333-4333-8333-333333333333','33333333-3333-4333-8333-333333333333']]:
        with pytest.raises(ValueError,match='Stage order'):
            plan_video(source,[dict(kind='create_stage',client_ref='extra',name='Extra'),
                dict(kind='reorder_stages',stage_ids=order)],domain='stages')


def test_empty_input_name_is_allowed_without_relaxing_other_names():
    from qlab_mcp.video_archive import plan_video
    from qlab_mcp.video_models import InputOperations,RouteOperations
    from pydantic import TypeAdapter,ValidationError
    assert TypeAdapter(InputOperations).validate_python([dict(kind='create_input',client_ref='empty',name='')])
    result=plan_video(video_workspace(),[dict(kind='create_input',client_ref='empty',name='')],domain='inputs')
    assert result['summary']['inputs'][-1]['name']==''
    updated=plan_video(video_workspace(),[dict(kind='update_input',patch_id='99999999-9999-4999-8999-999999999999',name='')],domain='inputs')
    assert updated['summary']['inputs'][0]['name']==''
    with pytest.raises(ValidationError):
        TypeAdapter(RouteOperations).validate_python([dict(kind='create_route',client_ref='bad',name='')])
    with pytest.raises(ValidationError):
        TypeAdapter(InputOperations).validate_python([dict(kind='create_input',client_ref='bad',name='x'*256)])


def test_video_schema_only_advertises_null_for_removable_assignments():
    from qlab_mcp.video_models import StageUpdate,VideoRouteUpdate,InputUpdate,DeviceUpdate
    for model in [StageUpdate,VideoRouteUpdate,InputUpdate,DeviceUpdate]:
        contract=model.model_json_schema()
        schema=contract['properties']
        for name,field in schema.items():
            nullable=any(branch.get('type')=='null' for branch in field.get('anyOf',[]))
            if name in {'mask_path','device_ref','source_ref','route_id'} and name not in contract.get('required',[]):
                assert nullable
            else:
                assert not nullable,(model.__name__,name)
