"""Video planning, native dependencies and shared same-path transactions."""
from base64 import b64decode
from copy import deepcopy
from functools import lru_cache, partial
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from pydantic import TypeAdapter
from . import workspace_documents as docs
from .workspace_archive import edit_archive, _read
from .runtime.read_cache import shared_read_cache
from .settings.summarizers import _collection_items
from .video_archive import plan_video, VideoArchive
from .video_models import OPERATIONS
from .video_settings import _native_metadata, _device_ref

_BOOKMARK_SCRIPT='''use framework "Foundation"
on run argv
 set u to current application's NSURL's fileURLWithPath:(item 1 of argv)
 set b to u's bookmarkDataWithOptions:0 includingResourceValuesForKeys:(missing value) relativeToURL:(missing value) |error|:(missing value)
 if b is missing value then error "Mask bookmark could not be created."
 return (b's base64EncodedStringWithOptions:0) as text
end run'''


@lru_cache(maxsize=128)
def _bookmark(path,fingerprint):
    result=subprocess.run(['/usr/bin/osascript','-',path],input=_BOOKMARK_SCRIPT,text=True,capture_output=True,timeout=10,check=False)
    if result.returncode or len(result.stdout)>128*1024:
        raise ValueError('Mask bookmark creation failed.')
    value=result.stdout.strip()
    if not b64decode(value,validate=True):raise ValueError('Empty mask bookmark.')
    return value


def _dependencies(reader,workspace_id,domain,operations):
    docs._local(reader)
    context={}
    refs={op['device_ref'] for op in operations if op.get('device_ref')}
    if refs:
        row=docs._document(docs._inventory(reader),workspace_id)
        source,_=_read(Path(row['path']));archive=VideoArchive(source,{})
        devices={}
        for ref in refs:
            if ref.startswith('qlab-route:'):
                route=archive.target('routes',ref.removeprefix('qlab-route:'))
                info={k:archive.a.ref(v) for k,v in archive.a.mapping(archive.a.ref(route)['destinationInfo']).items()}
                if info.get('destinationType')!='Display' or any(info.get(k) is None for k in ('screenVendorNumber','screenModelNumber','screenSerialNumber')):
                    raise ValueError('Route observations do not establish an exact virtual-device identity; select its saved device reference.')
                devices[ref]=info
        physical={ref for ref in refs if ref.startswith('macos_coregraphics:')}
        if physical:
            native=_native_metadata('devices')
            if native.get('status')!='ready':raise ValueError('Current display metadata is unavailable.')
            for display in native['devices']:
                ref=_device_ref('macos_coregraphics',display['screen_id'])
                if ref not in physical:continue
                if any(display.get(k) is None for k in ('vendor','model','serial')):raise ValueError('Display hardware identity is incomplete.')
                w,h=display['width'],display['height'];e=archive
                devices[ref]=dict(destinationType='Display',name=display['name'],screenID=display['screen_id'],
                    screenVendorNumber=display['vendor'],screenModelNumber=display['model'],screenSerialNumber=display['serial'],
                    videoOutputKeyPath='screen.screenID.'+str(display['screen_id']),videoOutputRasterSize=e.geo([w,h]),
                    videoOutputRefreshRate=display.get('refresh_rate'))
                if display.get('screen_frame'):devices[ref]['screenFrame']=e.geo(display['screen_frame'])
            if physical-set(devices):raise ValueError('Requested display identity is no longer available.')
        context['devices']=devices
    needs_inputs=domain=='inputs' and any(op.get('source_ref') or isinstance(op.get('mode'),dict) for op in operations)
    if needs_inputs:
        native=_native_metadata('inputs')
        if native.get('status')!='ready':raise ValueError('Current passive input metadata is unavailable.')
        formats={}
        for fmt in native['formats']:formats.setdefault(fmt['source_id'],[]).append(fmt)
        sources={}
        for source in native['devices']:
            f=source.get('observed_format') or next(iter(formats.get(source['id'],[])),{})
            if f.get('width') and f.get('height'):
                sources[_device_ref('macos_avfoundation',source['id'])]=dict(id=source['id'],name=source['name'],size=[f['width'],f['height']])
        context.update(sources=sources,formats=formats)
    masks={op['mask_path'] for op in operations if op.get('mask_path')}
    if masks:
        row=docs._document(docs._inventory(reader),workspace_id)
        resources={}
        for raw in masks:
            path=Path(raw)
            if not path.is_absolute():raise ValueError('Mask path must be absolute.')
            path=path.resolve(strict=True);before=path.stat()
            if not path.is_file() or before.st_size>32*1024*1024:raise ValueError('Mask must be a readable image file bounded to 32 MiB.')
            fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
            bookmark=_bookmark(str(path),(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,fingerprint))
            after=path.stat()
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Mask file changed during planning.')
            resources[raw]=dict(path=str(path),relative_path=os.path.relpath(path,Path(row['path']).parent),sha256=fingerprint,bookmark=bookmark)
        context['masks']=resources
    return context


def _numeric_equal(expected,actual,label):
    if not isinstance(actual,(int,float)) or isinstance(actual,bool) or not math.isfinite(actual) or not math.isclose(expected,actual,rel_tol=1e-6,abs_tol=1e-4):
        raise ValueError('Native video '+label+' does not match the saved plan.')


def verify_region(saved,current):
    if current.get('uniqueID')!=saved['id']:
        raise ValueError('Native region identity does not match the saved plan.')
    for sk,lk in [('mesh_width','meshWidth'),('mesh_height','meshHeight'),('warp_type','warpType')]:
        if saved[sk]!=current.get(lk):raise ValueError('Native region topology does not match the saved plan.')
    edge=saved.get('edge_blends') or {}
    for sk,lk in [('auto','autoEdgeBlends'),('top_pixels','edgeBlendTopPixels'),('bottom_pixels','edgeBlendBottomPixels'),('left_pixels','edgeBlendLeftPixels'),('right_pixels','edgeBlendRightPixels'),('gamma','edgeBlendGamma'),('power','edgeBlendPower'),('center_luminance','edgeBlendCenterLuminance')]:
        if sk in edge and lk in current:
            if isinstance(edge[sk],bool):
                if edge[sk]!=current[lk]:raise ValueError('Native edge blending does not match the archive.')
            else:_numeric_equal(edge[sk],current[lk],lk)
    bounds=current.get('boundsOnStage') or {}
    for value,key in zip(saved['bounds_on_stage']['components'],('x','y','width','height')):
        _numeric_equal(value,bounds.get(key),'bounds')
    if (current.get('route') or {}).get('uniqueID')!=saved.get('route_id'):
        raise ValueError('Native region route does not match the saved plan.')
    for sk,lk in [('control_points','controlPoints'),('shadow_control_points','shadowControlPoints')]:
        a,b=saved.get(sk,[]),current.get(lk,[])
        if len(a)!=len(b):raise ValueError('Native region control point count does not match the saved plan.')
        for expected,actual in zip(a,b):
            if expected['link_id']!=actual.get('linkID'):raise ValueError('Native point links do not match the saved plan.')
            for value,key in zip(expected['output_point']['components'],('x','y')):
                _numeric_equal(value,(actual.get('outputPoint') or {}).get(key),'control point')
    children=current.get('meshSubregions') or []
    if len(children)!=len(saved.get('mesh_subregions',[])):raise ValueError('Native mesh hierarchy does not match the saved plan.')
    for a,b in zip(saved.get('mesh_subregions',[]),children):verify_region(a,b)


def verify_video(reader,workspace_id,summary):
    shared_read_cache().clear()
    result=reader.get_workspace_settings(workspace_id,sections=['video'],profile='technical')
    if result.get('errors'):raise ValueError('Fresh OSC video settings are incomplete.')
    live=(result.get('sections') or {}).get('video')
    if not isinstance(live,dict):raise ValueError('Fresh OSC video settings are unavailable.')
    for saved_section,live_section in [('stages','stages'),('routes','routes'),('inputs','input_patches')]:
        actual={str(x.get('uniqueID','')).upper():x for x in _collection_items(live.get(live_section))}
        expected={x['id']:x for x in summary[saved_section]}
        if set(actual)!=set(expected):raise ValueError(f'Native video {saved_section} identities do not match the archive.')
        for uid,saved in expected.items():
            current=actual[uid]
            if saved_section!='inputs' and current.get('name')!=saved.get('name'):
                raise ValueError(f'Native video {saved_section} names do not match the archive.')
    for saved in summary['stages']:
        response=reader.get_video_setting(workspace_id,kind='stage',ref=saved['id'],profile='technical')
        details=response.get('details') or {}
        if not response.get('ok') or response.get('partial'):
            raise ValueError('Fresh native stage geometry is unavailable.')
        payload=details.get('technical_payload') or {}
        current=payload.get('stage') or {}
        for key in ('width','height'):_numeric_equal(saved[key],current.get(key),'stage dimensions')
        regions=payload.get('regions')
        if not isinstance(regions,list) or len(regions)!=len(saved['regions']):
            raise ValueError('Native stage region membership does not match the archive.')
        for a,b in zip(saved['regions'],regions):verify_region(a,b)
    # The OSC inventory is compact; exact routes supply their actual saved setters.
    for saved in summary['routes']:
        response=reader.get_video_setting(workspace_id,kind='route',ref=saved['id'],profile='technical')
        if not response.get('ok'):raise ValueError('Fresh native route detail is unavailable.')
        detail=(response.get('details') or {}).get('detail') or {}
        for live_key,saved_key in [('rotationDegrees','rotation_degrees'),('scalingMode','scaling_mode'),('rear','rear')]:
            if live_key not in detail or detail[live_key]!=saved.get(saved_key):raise ValueError(f'Native route {live_key} does not match the archive.')
        payload=(response.get('details') or {}).get('technical_payload') or {}
        size=payload.get('naturalSize') or {}
        for value,key in zip(saved['natural_size']['components'],('width','height')):
            _numeric_equal(value,size.get(key),'route dimensions')
        layout=payload.get('partialScreenLayout') or {}
        for key,lk in [('wide','screensWide'),('high','screensHigh')]:
            if saved['layout'][key]!=layout.get(lk):raise ValueError('Native route partial layout does not match the archive.')
        if saved['layout']['index']!=payload.get('partialScreenIndex'):raise ValueError('Native route tile index does not match the archive.')
        destination=payload.get('destinationInfo') or {}
        for key in ('destinationType','videoOutputKeyPath','name','screenVendorNumber','screenModelNumber','screenSerialNumber'):
            if saved['destination_info'].get(key)!=destination.get(key):raise ValueError('Native route destination does not match the archive.')
    return live


def edit_video(reader,workspace_id,domain,operations,dry_run=True,confirm_token=None):
    try:
        workspace_id=docs._uuid(workspace_id)
        ops=[op.model_dump(exclude_unset=True) for op in TypeAdapter(OPERATIONS[domain]).validate_python(operations)]
        context=_dependencies(reader,workspace_id,domain,ops)
        def recheck():
            if _dependencies(reader,workspace_id,domain,ops)!=context:raise ValueError('Video dependencies changed before execution.')
        result=edit_archive(reader,workspace_id,ops,dry_run,confirm_token,
            planner=partial(plan_video,domain=domain,context=context),token_family='videoSettings.'+domain,
            dependencies=context,dependency_check=recheck,live_verifier=verify_video)
    except Exception as exc:
        result=dict(ok=False,status='blocked',planned_operations=[],executed_operations=[],error=str(exc))
    result['workspace_id']=workspace_id
    result['domain']=domain
    result['native_video_verified']=result.pop('native_patch_verified',False)
    result.pop('native_patch_verification_scope',None)
    result['verification_scope']='Archive bytes and OSC stage/route identities, geometry, mesh controls, route dimensions, layout and destination. Viewport layer/mask, stage rendering flags, configured virtual-device parameters and input modes are verified in the saved archive only. Capture, rendering and physical signal are not verified.'
    return result
