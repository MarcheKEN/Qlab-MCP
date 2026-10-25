"""Graph-preserving QLab 5.5.10 video plans; no document or device side effects."""
from __future__ import annotations
import base64
from copy import deepcopy
import hashlib
import math
import plistlib
import re
from uuid import UUID, uuid5, NAMESPACE_URL
from pydantic import TypeAdapter
from .light_patch.archive import Archive
from .video_settings import inspect_saved_video, _NUMBER
from .video_models import OPERATIONS

_SCALING={'center':0,'stretch':1,'fill':2,'fit':3}
_WARP={'perspective':3,'linear':1,'bezier':2}


class VideoArchive:
    def __init__(self,source,context):
        self.source=source
        self.hash=hashlib.sha256(source).hexdigest()
        self.a=Archive(source)
        self.original=inspect_saved_video(source)
        self.meta=self.a.mapping(self.a.root)
        self.settings=self.a.mapping(self.meta['settings'])
        self.v=self.a.mapping(self.settings['Video'])
        self.c=self.a.mapping(self.settings['Camera']) if 'Camera' in self.settings else {}
        self.refs={k:list(self.a.array(self.v[k])) for k in ('stages','routes','virtualDestinations')}
        self.refs['cameraPatches']=list(self.a.array(self.c['cameraPatches'])) if 'cameraPatches' in self.c else []
        self.created={}
        self.context=context or {}
        self.dirty=False
        self.deleted=[]
        self.changed=set()
        self.serial=0

    def ident(self,value):
        value=self.a.ref(value)
        if isinstance(value,dict) and 'NS.uuidbytes' in value:
            return str(UUID(bytes=value['NS.uuidbytes'])).upper()
        if isinstance(value,str):
            return str(UUID(value)).upper()
        raise ValueError('Invalid archived video UUID.')

    def uuid(self,label):
        return str(uuid5(NAMESPACE_URL,self.hash+':video:'+label)).upper()

    def nsuuid(self,label):
        return self.a.add({'$class':self.a.cls('NSUUID'),'NS.uuidbytes':UUID(self.uuid(label)).bytes})

    def object(self,kind,**fields):
        parents=('F53PasteboardObject',) if kind in {'VideoStage','VideoStageViewport','F53VideoOutputRoute','CameraPatch'} else ()
        return self.a.add({'$class':self.a.cls(kind,parents),**fields})

    def value(self,ref,key,default=None):
        return self.a.ref(self.a.ref(ref).get(key,default))

    def put(self,ref,key,value,*,object_value=None):
        obj=self.a.ref(ref)
        if self.a.ref(obj.get(key))==value:
            return
        if object_value is None:
            object_value=isinstance(obj.get(key),plistlib.UID) or isinstance(value,str)
        obj[key]=self.a.add(value) if object_value else value
        self.dirty=True

    def pointer(self,ref,key,value):
        obj=self.a.ref(ref)
        if obj.get(key)!=value:
            obj[key]=value
            self.dirty=True

    def array(self,ref,key):
        value=self.a.ref(ref).get(key)
        return list(self.a.array(value)) if self.a.ref(value) is not None else []

    def put_array(self,ref,key,values):
        if self.array(ref,key)!=values:
            self.pointer(ref,key,self.a.make_array(values))

    def mapping_put(self,ref,key,value):
        obj=self.a.ref(ref)
        keys=[self.a.ref(k) for k in obj['NS.keys']]
        obj['NS.keys']=list(obj['NS.keys']);obj['NS.objects']=list(obj['NS.objects'])
        if key in keys:
            obj['NS.objects'][keys.index(key)]=value
        else:
            obj['NS.keys'].append(self.a.add(key));obj['NS.objects'].append(value)

    def geometry(self,ref,key,count):
        value=self.value(ref,key)
        if not isinstance(value,str):
            raise ValueError('Unsupported video geometry encoding.')
        result=[float(x) for x in _NUMBER.findall(value)]
        if len(result)!=count or not all(math.isfinite(x) for x in result):
            raise ValueError('Invalid video geometry.')
        return result

    @staticmethod
    def geo(values):
        values=[format(float(v),'.17g') for v in values]
        return '{'+', '.join(values)+'}' if len(values)==2 else '{{'+', '.join(values[:2])+'}, {'+', '.join(values[2:])+'}}'

    def target(self,key,value):
        if value.startswith('@'):
            if value[1:] not in self.created:raise ValueError('Unknown local video reference.')
            value=self.created[value[1:]]
        matches=[]
        for ref in self.refs[key]:
            if key=='virtualDestinations':
                match=value in {f'{self.hash}:{ref.data}','saved-virtual:'+f'{self.hash}:{ref.data}'}
            else:
                match=self.ident(self.a.ref(ref)['uniqueID'])==str(UUID(value)).upper()
            if match:matches.append(ref)
        if len(matches)!=1:raise ValueError('Reference must identify exactly one active video object in this snapshot.')
        ref=matches[0]
        expected={'stages':{'VideoStage'},'routes':{'F53VideoOutputRoute'},'cameraPatches':{'CameraPatch'},'virtualDestinations':{'F53VideoOutputDestinationNDI','F53VideoOutputDestinationSyphon'}}[key]
        if self.a.kind(ref) not in expected:raise ValueError('Unsupported target video object class; its encoding cannot be safely edited.')
        return ref

    def register(self,key,op,ref):
        label=op['client_ref']
        if label.startswith('@') or label in self.created:
            raise ValueError('Creation client_ref must be unique and must not start with @.')
        self.refs[key].append(ref)
        self.created[label]=f'{self.hash}:{ref.data}' if key=='virtualDestinations' else self.ident(self.a.ref(ref)['uniqueID'])
        self.dirty=True
        return ref

    def region(self,stage_id,region_id):
        stage=self.target('stages',stage_id)
        if region_id.startswith('@'):
            region_id=self.created.get(region_id[1:],'')
        matches=[r for r in self.array(stage,'regions') if self.ident(self.a.ref(r)['uniqueID'])==str(UUID(region_id)).upper()]
        if len(matches)!=1:
            raise ValueError('Region UUID must belong to the exact stage.')
        if self.a.kind(matches[0])!='VideoStageRegion':raise ValueError('Unsupported region class.')
        return stage,matches[0]

    def descendants(self,region,seen=None):
        seen=set() if seen is None else seen
        if region.data in seen or len(seen)>4096:
            raise ValueError('Cyclic or oversized video mesh.')
        if self.a.kind(region)!='VideoStageRegion':raise ValueError('Unsupported mesh region class.')
        seen.add(region.data)
        yield region
        for child in self.array(region,'meshSubregions'):
            yield from self.descendants(child,seen)

    def active_regions(self):
        for stage in self.refs['stages']:
            for region in self.array(stage,'regions'):
                yield from self.descendants(region)

    def points(self):
        seen=set()
        for region in self.active_regions():
            for key in ['controlPoints','shadowControlPoints']:
                for point in self.array(region,key):
                    if point.data not in seen:
                        seen.add(point.data);yield point

    def new_point(self,region,x,y,label,link=None):
        return self.object('VideoStageRegionControlPoint',region=region,
            linkID=link or self.nsuuid(label),outputPoint=self.a.add(self.geo([x,y])),pristine=True)

    def new_region(self,stage,route,bounds,label,*,leaf=False,output=None):
        initial=output or (self.geometry(route,'naturalSize',2) if route else bounds[2:])
        ref=self.object('VideoStageRegion',uniqueID=self.nsuuid(label),stage=stage,route=route or plistlib.UID(0),
            boundsOnStage=self.a.add(self.geo(bounds)),initialBoundsOnRoute=self.a.add(self.geo([0,0,*initial])),
            autoEdgeBlends=not leaf,meshWidth=0 if leaf else 1,meshHeight=0 if leaf else 1,warpType=3,
            edgeBlendTopPixels=self.a.add(0.0),edgeBlendBottomPixels=self.a.add(0.0),
            edgeBlendLeftPixels=self.a.add(0.0),edgeBlendRightPixels=self.a.add(0.0),
            edgeBlendCenterLuminance=self.a.add(0.0 if leaf else 0.5),
            edgeBlendPower=self.a.add(0.0 if leaf else 2.0),edgeBlendGamma=self.a.add(0.0 if leaf else 0.8),
            shadowControlPoints=plistlib.UID(0),meshSubregions=self.a.make_array([]),controlPoints=self.a.make_array([]))
        w,h=initial
        corners=[(0,0),(w,0),(0,h),(w,h)]
        self.a.ref(ref)['controlPoints']=self.a.make_array([self.new_point(ref,x,y,f'{label}:p{i}') for i,(x,y) in enumerate(corners)])
        if not leaf:
            self.a.ref(ref)['meshSubregions']=self.a.make_array([self.new_region(stage,route,bounds,label+':mesh',leaf=True,output=initial)])
        return ref

    def route_info(self,device):
        obj=self.a.ref(device);kind=self.a.kind(device).removeprefix('F53VideoOutputDestination')
        if kind not in {'NDI','Syphon'}:
            raise ValueError('Unsupported output device class.')
        name=self.value(device,'name');size=self.value(device,'size');rate=self.value(device,'refreshRate')
        info=dict(destinationType=kind,name=name,videoOutputKeyPath=kind.lower()+'.'+name,
                  pixelSize=size,videoOutputRasterSize=size,videoOutputRefreshRate=rate)
        if kind=='NDI':
            info.update({k:self.a.ref(v) for k,v in obj.items() if k in {'pixelFormat','audioChannels','audioSampleRate','audioBufferSize'}})
        return info

    def encode_dict(self,values):
        return self.a.make_dict({k:self.a.add(v) for k,v in values.items()})

    def destination(self,device_ref):
        if device_ref is None:
            return {}
        if device_ref in self.context.get('devices',{}):
            return deepcopy(self.context['devices'][device_ref])
        return self.route_info(self.target('virtualDestinations',device_ref))

    def cues(self):
        payload=self.a.ref(self.meta.get('cueLists'))
        if isinstance(payload,dict):
            payload=self.a.ref(payload.get('NS.data'))
        if not isinstance(payload,bytes):
            raise ValueError('Cue references cannot be checked in this archive.')
        nested=Archive(payload);visited=set();stack=[nested.data['$top']['root']];result=[]
        while stack:
            ref=stack.pop()
            if not isinstance(ref,plistlib.UID) or ref.data in visited:
                continue
            visited.add(ref.data)
            if len(visited)>100000:
                raise ValueError('Cue dependency analysis exceeds its bound.')
            obj=nested.ref(ref)
            if not isinstance(obj,dict):
                continue
            if 'cues' in obj:
                stack.extend(nested.array(obj['cues']))
            if 'NS.objects' in obj and 'NS.keys' not in obj:
                stack.extend(obj['NS.objects'])
            fields={k:nested.ref(obj.get(k)) for k in ['uniqueID','name','viewportID','cameraPatchID']}
            for key in ('uniqueID','viewportID','cameraPatchID'):
                value=fields[key]
                if isinstance(value,dict) and 'NS.uuidbytes' in value:value=str(UUID(bytes=value['NS.uuidbytes'])).upper()
                if isinstance(value,str) and value:
                    try:value=str(UUID(value)).upper()
                    except ValueError:pass
                fields[key]=value
            if fields['viewportID'] or fields['cameraPatchID']:
                result.append(fields)
        return result

    def apply_route(self,op):
        kind=op['kind']
        if kind=='reorder_routes':
            ordered=[self.target('routes',r) for r in op['route_ids']]
            if len(ordered)!=len(self.refs['routes']) or set(ordered)!=set(self.refs['routes']):raise ValueError('Route order must contain each active route exactly once.')
            if ordered!=self.refs['routes']:self.refs['routes']=ordered;self.dirty=True
            return
        if kind=='create_route':
            ref=self.object('F53VideoOutputRoute',uniqueID=self.a.add(self.uuid(op['client_ref'])),name=self.a.add(op['name']),
                naturalSize=self.a.add(self.geo([op.get('width',1920),op.get('height',1080)])),
                rotationDegrees=0,scalingMode=0,rear=False,layoutWide=1,layoutHigh=1,layoutIndex=0,guidelineMode=0,
                destinationInfo=self.a.make_dict({}))
            self.register('routes',op,ref)
        else:
            ref=self.target('routes',op['route_id'])
            if kind=='delete_route':
                self.refs['routes'].remove(ref);self.deleted.append(('route',ref));self.dirty=True;return
        self.changed.add(('route',self.ident(self.a.ref(ref)['uniqueID'])))
        if 'rotation' in op and not any(k in op for k in ('width','height')) and (op['rotation']//90)%2!=(self.value(ref,'rotationDegrees',0)//90)%2:
            w,h=self.geometry(ref,'naturalSize',2);self.put(ref,'naturalSize',self.geo([h,w]))
        for field,key in [('name','name'),('rotation','rotationDegrees'),('rear','rear'),('layout_wide','layoutWide'),
                          ('layout_high','layoutHigh'),('layout_index','layoutIndex'),('guideline_mode','guidelineMode')]:
            if field in op:self.put(ref,key,op[field])
        if 'scaling' in op:self.put(ref,'scalingMode',_SCALING[op['scaling']])
        if 'width' in op or 'height' in op:
            w,h=self.geometry(ref,'naturalSize',2)
            self.put(ref,'naturalSize',self.geo([op.get('width',w),op.get('height',h)]))
        if 'device_ref' in op:
            info=self.destination(op['device_ref'])
            if {k:self.a.ref(v) for k,v in self.a.mapping(self.a.ref(ref)['destinationInfo']).items()}!=info:
                self.pointer(ref,'destinationInfo',self.encode_dict(info))

    def apply_stage(self,op):
        from .video_geometry import edit_geometry
        kind=op['kind']
        if kind=='reorder_stages':
            ordered=[self.target('stages',r) for r in op['stage_ids']]
            if len(ordered)!=len(self.refs['stages']) or set(ordered)!=set(self.refs['stages']):raise ValueError('Stage order must contain each active stage exactly once.')
            if ordered!=self.refs['stages']:self.refs['stages']=ordered;self.dirty=True
            return
        if kind=='create_stage':
            w,h=op.get('width',1920),op.get('height',1080)
            ref=self.object('VideoStage',uniqueID=self.a.add(self.uuid(op['client_ref'])),name=self.a.add(op['name']),
                width=self.a.add(w),height=self.a.add(h),keepRendering=False,gridIsDark=self.a.add(False),
                gridBypassesEdgeBlends=self.a.add(False),regions=self.a.make_array([]))
            viewport=self.object('VideoStageViewport',uniqueID=self.a.add(self.uuid(op['client_ref']+':viewport')),name=self.a.add('main'),
                stage=ref,boundsOnStage=self.a.add(self.geo([0,0,w,h])),layer=self.a.add(1000),audition=False,maskAlias=plistlib.UID(0))
            self.a.ref(ref)['viewport']=viewport;self.register('stages',op,ref)
        else:
            ref=self.target('stages',op['stage_id'])
        self.changed.add(('stage',self.ident(self.a.ref(ref)['uniqueID'])))
        if kind=='delete_stage':
            self.refs['stages'].remove(ref);self.deleted.append(('stage',ref));self.dirty=True;return
        if kind in {'create_stage','update_stage'}:
            for field,key in [('name','name'),('keep_rendering','keepRendering'),('grid_is_dark','gridIsDark'),('grid_bypasses_edge_blends','gridBypassesEdgeBlends')]:
                if field in op:self.put(ref,key,op[field])
            viewport=self.a.ref(ref)['viewport']
            if 'layer' in op:self.put(viewport,'layer',op['layer'])
            if 'mask_path' in op:
                resource=self.context.get('masks',{}).get(op['mask_path']) if op['mask_path'] is not None else None
                if op['mask_path'] is not None and resource is None:raise ValueError('Mask requires a validated local bookmark dependency.')
                if resource:
                    alias=self.object('F53Alias',bookmark=self.a.add(base64.b64decode(resource['bookmark'],validate=True)),
                        lastKnownPath=self.a.add(resource['path']),relativePath=self.a.add(resource['relative_path']))
                else:alias=plistlib.UID(0)
                self.pointer(viewport,'maskAlias',alias)
            return
        if kind=='create_region':
            route=self.target('routes',op['route_id']) if op.get('route_id') else None
            b=op['bounds'];region=self.new_region(ref,route,[b[k] for k in ('x','y','width','height')],op['client_ref'])
            if op['client_ref'].startswith('@') or op['client_ref'] in self.created:raise ValueError('Creation client_ref must be unique and must not start with @.')
            self.created[op['client_ref']]=self.ident(self.a.ref(region)['uniqueID'])
            self.put_array(ref,'regions',[*self.array(ref,'regions'),region]);return
        if kind=='reorder_regions':
            regions=self.array(ref,'regions');ordered=[self.region(op['stage_id'],r)[1] for r in op['region_ids']]
            if len(ordered)!=len(regions) or set(ordered)!=set(regions):raise ValueError('Region order must contain each active region exactly once.')
            self.put_array(ref,'regions',ordered);return
        if kind=='delete_region':
            _,region=self.region(op['stage_id'],op['region_id']);self.put_array(ref,'regions',[r for r in self.array(ref,'regions') if r!=region]);return
        if kind=='update_region':
            _,region=self.region(op['stage_id'],op['region_id'])
            if 'route_id' in op:
                route=self.target('routes',op['route_id']) if op['route_id'] is not None else plistlib.UID(0)
                for child in self.descendants(region):self.pointer(child,'route',route)
            if 'bounds' in op:
                b=op['bounds'];edit_geometry(self,ref,region,dict(kind='set_bounds',bounds=[b[k] for k in ('x','y','width','height')]))
            for field,key in [('auto_edge_blends','autoEdgeBlends'),('edge_top','edgeBlendTopPixels'),('edge_bottom','edgeBlendBottomPixels'),
                              ('edge_left','edgeBlendLeftPixels'),('edge_right','edgeBlendRightPixels'),('blend_gamma','edgeBlendGamma'),
                              ('blend_power','edgeBlendPower'),('center_luminance','edgeBlendCenterLuminance')]:
                if field in op:self.put(region,key,op[field])
            if 'warp' in op:
                route=self.a.ref(region).get('route')
                for owner in self.refs['stages']:
                    for root in self.array(owner,'regions'):
                        if root==region or self.a.ref(route) is not None and self.a.ref(root).get('route')==route:
                            edit_geometry(self,owner,root,dict(kind='warp',warp=_WARP[op['warp']]))
                            self.changed.add(('stage',self.ident(self.a.ref(owner)['uniqueID'])))
            return
        region=self.region(op['stage_id'],op['region_id'])[1] if 'region_id' in op else None
        edit_geometry(self,ref,region,op)

    def apply_device(self,op):
        kind=op['kind']
        if kind=='create_device':
            typ=op['device_type'];name=op['name']
            if any(self.value(r,'name')==name and self.a.kind(r)=='F53VideoOutputDestination'+typ for r in self.refs['virtualDestinations']):
                raise ValueError('Virtual device name is already in use.')
            ref=self.object('F53VideoOutputDestination'+typ,virtualID=self.v['virtualOutputID'],name=self.a.add(name),
                size=self.a.add(self.geo([op.get('width',1920),op.get('height',1080)])),refreshRate=op.get('frame_rate',30.0))
            if typ=='NDI':self.a.ref(ref).update(pixelFormat=1111970369,audioChannels=0,audioSampleRate=48000.0,audioBufferSize=512)
            self.register('virtualDestinations',op,ref)
        else:ref=self.target('virtualDestinations',op['device_ref'])
        old=self.route_info(ref)
        old_owners=sum(self.route_info(r)['videoOutputKeyPath']==old['videoOutputKeyPath'] for r in self.refs['virtualDestinations'])
        matching=[r for r in self.refs['routes'] if self.a.ref(self.a.mapping(self.a.ref(r)['destinationInfo']).get('videoOutputKeyPath'))==old['videoOutputKeyPath']]
        if kind=='delete_device':
            self.refs['virtualDestinations'].remove(ref);self.deleted.append(('device',ref));self.dirty=True;return
        typ=self.a.kind(ref).removeprefix('F53VideoOutputDestination')
        if typ=='Syphon' and any(k in op for k in ['pixel_format','audio_channels','audio_sample_rate','audio_buffer_size']):
            raise ValueError('Syphon has no NDI pixel/audio settings.')
        for field,key in [('name','name'),('frame_rate','refreshRate'),('audio_channels','audioChannels'),('audio_sample_rate','audioSampleRate'),('audio_buffer_size','audioBufferSize')]:
            if field in op:self.put(ref,key,float(op[field]) if field in {'frame_rate','audio_sample_rate'} else op[field])
        if 'pixel_format' in op:self.put(ref,'pixelFormat',int.from_bytes(op['pixel_format'].encode(),'big'))
        if 'width' in op or 'height' in op:
            w,h=self.geometry(ref,'size',2);self.put(ref,'size',self.geo([op.get('width',w),op.get('height',h)]))
        if any(r!=ref and self.a.kind(r)==self.a.kind(ref) and self.value(r,'name')==self.value(ref,'name') for r in self.refs['virtualDestinations']):
            raise ValueError('Virtual device name is already in use.')
        new=self.route_info(ref)
        if old!=new:
            if matching and old_owners>1:
                raise ValueError('Ambiguous virtual-device route ownership.')
            for route in matching:
                preserved=self.a.mapping(self.a.ref(route)['destinationInfo'])
                preserved.update({k:self.a.add(v) for k,v in new.items()})
                self.pointer(route,'destinationInfo',self.a.make_dict(preserved));self.changed.add(('route',self.ident(self.a.ref(route)['uniqueID'])))

    def apply_input(self,op):
        kind=op['kind']
        if kind=='reorder_inputs':
            ordered=[self.target('cameraPatches',r) for r in op['patch_ids']]
            if len(ordered)!=len(self.refs['cameraPatches']) or set(ordered)!=set(self.refs['cameraPatches']):raise ValueError('Input order must contain each active patch exactly once.')
            if ordered!=self.refs['cameraPatches']:self.refs['cameraPatches']=ordered;self.dirty=True
            return
        if kind=='create_input':
            ref=self.object('CameraPatch',uniqueID=self.a.add(self.uuid(op['client_ref'])),name=self.a.add(op['name']),serializedDescription=plistlib.UID(0))
            self.register('cameraPatches',op,ref)
        else:ref=self.target('cameraPatches',op['patch_id'])
        self.changed.add(('input',self.ident(self.a.ref(ref)['uniqueID'])))
        if kind=='delete_input':
            self.refs['cameraPatches'].remove(ref);self.deleted.append(('input',ref));self.dirty=True;return
        if 'name' in op:self.put(ref,'name',op['name'])
        descriptor=self.a.ref(ref).get('serializedDescription',plistlib.UID(0))
        if 'source_ref' in op:
            source=self.context.get('sources',{}).get(op['source_ref']) if op['source_ref'] is not None else None
            if op['source_ref'] is not None and source is None:raise ValueError('Input source must be an exact current local source reference.')
            current_descriptor=self.a.mapping(descriptor) if self.a.ref(descriptor) is not None else {}
            if source and self.a.ref(current_descriptor.get('uniqueID'))==source['id']:
                pass
            elif source:
                size=source['size'];size_ref=self.object('NSValue',**{'NS.special':2,'NS.sizeval':self.a.add(self.geo(size))})
                descriptor=self.a.make_dict({'uniqueID':self.a.add(source['id']),'name':self.a.add(source['name']),
                    'type':self.a.add('AVCaptureDevice'),'size':size_ref,'config':self.a.make_dict({})})
            else:descriptor=plistlib.UID(0)
            self.pointer(ref,'serializedDescription',descriptor)
        if 'mode' in op:
            if self.a.ref(descriptor) is None:raise ValueError('Cannot set a mode on an unassigned input patch.')
            values=self.a.mapping(descriptor)
            if self.a.ref(values.get('type'))!='AVCaptureDevice':raise ValueError('Only local AVFoundation input modes are supported.')
            mode=op['mode']
            config_values=dict(self.a.mapping(values['config']))
            if mode=='auto':
                config_values.pop('AVCaptureFormat',None);config=self.a.make_dict(config_values)
            elif isinstance(mode,dict):
                uid=self.a.ref(values['uniqueID']);available=self.context.get('formats',{}).get(uid,[])
                # QLab 5.5.10 lists range endpoints, not arbitrary supported FPS.
                if not any(f['width']==mode['width'] and f['height']==mode['height'] and f['pixel_format']==mode['pixel_format'] and
                    any(mode['frame_rate'] in {rate['min'],rate['max']} for rate in f['frame_rates']) for f in available):
                    raise ValueError('Manual input mode is not present in the current source format metadata.')
                fmt=self.object('F53VideoAVCaptureFormat',pixelWidth=mode['width'],pixelHeight=mode['height'],
                    pixelFormat=mode['pixel_format'],framesPerSecond=mode['frame_rate'])
                config_values['AVCaptureFormat']=fmt
                config=self.a.make_dict(config_values)
            else:raise ValueError('Input mode must be auto or an exact supported format.')
            if self.a.mapping(values['config'])!=self.a.mapping(config):
                updated=self.a.replacing_mapping(descriptor,'config',config);self.pointer(ref,'serializedDescription',updated)

    def validate(self):
        cues=self.cues()
        for kind,ref in self.deleted:
            if kind=='route' and any(self.a.ref(r).get('route')==ref for r in self.active_regions()):raise ValueError('Route is in use; reassign its regions first.')
            if kind=='device':
                path=self.route_info(ref)['videoOutputKeyPath']
                if any(self.a.ref(self.a.mapping(self.a.ref(r)['destinationInfo']).get('videoOutputKeyPath'))==path for r in self.refs['routes']):raise ValueError('Device is in use; reassign its routes first.')
            if kind in {'stage','input'}:
                uid=self.ident(self.a.ref(self.a.ref(ref)['viewport'])['uniqueID']) if kind=='stage' else self.ident(self.a.ref(ref)['uniqueID'])
                field='viewportID' if kind=='stage' else 'cameraPatchID'
                if any(c[field]==uid for c in cues):raise ValueError(f'{kind} is in use by cues; reassign them with the cue editor first.')
        for stage in self.refs['stages']:
            if ('stage',self.ident(self.a.ref(stage)['uniqueID'])) not in self.changed:
                continue
            w,h=self.value(stage,'width'),self.value(stage,'height')
            if not (type(w) in {int,float} and type(h) in {int,float} and 0<w<=16384 and 0<h<=16384):raise ValueError('Invalid stage size.')
            for region in self.array(stage,'regions'):
                x,y,rw,rh=self.geometry(region,'boundsOnStage',4)
                if rw<=0 or rh<=0 or x<0 or y<0 or x+rw>w+1e-6 or y+rh>h+1e-6:
                    # Existing broken geometry may be retained, but authoring cannot introduce it.
                    if ('stage',self.ident(self.a.ref(stage)['uniqueID'])) in self.changed:raise ValueError('Region bounds must fit within the final stage.')
            for region in [r for root in self.array(stage,'regions') for r in self.descendants(root)]:
                route=self.a.ref(region).get('route')
                if self.a.ref(route) is not None and route not in self.refs['routes']:raise ValueError('Region references a missing route.')
                children=self.array(region,'meshSubregions')
                if children and len(children)!=self.value(region,'meshWidth')*self.value(region,'meshHeight'):raise ValueError('Mesh topology is inconsistent.')
                count=len(self.array(region,'controlPoints'));warp=self.value(region,'warpType')
                if count not in ({16} if warp==2 else {4}):raise ValueError('Unsupported warp control topology.')
        for route in self.refs['routes']:
            wide,high,index=[self.value(route,k,d) for k,d in [('layoutWide',1),('layoutHigh',1),('layoutIndex',0)]]
            if not 1<=wide<=4 or not 1<=high<=4 or not 0<=index<wide*high:raise ValueError('Partial-output index is outside its layout.')
        affected=[]
        changed_stages={uid for kind,uid in self.changed if kind=='stage'}
        changed_routes={uid for kind,uid in self.changed if kind=='route'}
        for stage in self.refs['stages']:
            if any(self.ident(self.a.ref(self.a.ref(r)['route'])['uniqueID']) in changed_routes for r in self.array(stage,'regions') if self.a.ref(self.a.ref(r).get('route')) is not None):
                changed_stages.add(self.ident(self.a.ref(stage)['uniqueID']))
        viewports={self.ident(self.a.ref(self.a.ref(s)['viewport'])['uniqueID']) for s in self.refs['stages'] if self.ident(self.a.ref(s)['uniqueID']) in changed_stages}
        inputs={uid for kind,uid in self.changed if kind=='input'}
        for cue in cues:
            if cue['viewportID'] in viewports or cue['cameraPatchID'] in inputs:affected.append(cue)
        return affected

    def finish(self):
        for key in ('stages','routes','virtualDestinations'):
            if self.a.array(self.v[key])!=self.refs[key]:self.mapping_put(self.settings['Video'],key,self.a.make_array(self.refs[key]))
        if self.c:
            if self.a.array(self.c['cameraPatches'])!=self.refs['cameraPatches']:self.mapping_put(self.settings['Camera'],'cameraPatches',self.a.make_array(self.refs['cameraPatches']))
        elif self.refs['cameraPatches']:
            self.mapping_put(self.meta['settings'],'Camera',self.a.make_dict({'cameraPatches':self.a.make_array(self.refs['cameraPatches']),'monitorState':self.a.make_dict({})}))
        return self.a.dump() if self.dirty else self.source


def plan_video(source,operations,*,domain,context=None):
    if domain not in OPERATIONS:raise ValueError('Unsupported video authoring domain.')
    ops=[op.model_dump(exclude_unset=True) for op in TypeAdapter(OPERATIONS[domain]).validate_python(operations)] if operations else []
    editor=VideoArchive(source,context)
    general=editor.a.mapping(editor.settings['General']) if 'General' in editor.settings else {}
    if ops:
        hooks=[editor.a.ref(general.get(k)) for k in ('doStartOnOpen','doStartOnClose')]
        if any(type(v) is not bool for v in hooks):raise ValueError('Workspace open/close cue hooks must have known boolean state.')
        if any(hooks):raise ValueError('Workspace open/close cue hooks must be disabled before archive authoring.')
    for i,op in enumerate(ops):
        editor.serial=i
        getattr(editor,'apply_'+{'routes':'route','stages':'stage','devices':'device','inputs':'input'}[domain])(op)
    # Read-only baseline plans must remain usable for partially configured workspaces.
    affected=editor.validate() if ops else []
    output=editor.finish()
    summary=inspect_saved_video(output)
    def semantic(value):
        if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if k!='archive_sha256'}
        if isinstance(value,list):return [semantic(v) for v in value]
        if isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}:\d+',value):return 'archive-object:'+value.split(':')[-1]
        return value
    if semantic(summary)==semantic(editor.original):
        output=source;summary=editor.original;editor.dirty=False;editor.created={}
    return dict(workspace_id=summary['workspace_id'],output_bytes=output,summary=summary,
        changes=ops if editor.dirty else [],warnings=['Configuration acceptance does not verify capture, rendering or physical signal.', 'QLab may retain prior unreferenced virtual-device entries in its process-shared registry after reopen; the saved configuration is distinct.'] if ops else [],
        affected_cues=affected,affected_objects=[dict(kind=k,id=uid) for k,uid in sorted(editor.changed)],created_refs={k:(hashlib.sha256(output).hexdigest()+':'+v.split(':')[-1] if domain=='devices' else v) for k,v in editor.created.items()})
