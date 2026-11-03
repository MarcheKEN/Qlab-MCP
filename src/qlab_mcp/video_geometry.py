"""Finite stage/region transforms and graph-preserving warp controls."""
from .video_settings import _warp_point
from fractions import Fraction


def record(e,ref):
    return dict(warp_type=e.value(ref,'warpType'),mesh_width=e.value(ref,'meshWidth'),mesh_height=e.value(ref,'meshHeight'),
        control_points=[dict(output_point=dict(components=e.geometry(p,'outputPoint',2))) for p in e.array(ref,'controlPoints')],
        shadow_control_points=[dict(output_point=dict(components=e.geometry(p,'outputPoint',2))) for p in e.array(ref,'shadowControlPoints')],
        mesh_subregions=[record(e,c) for c in e.array(ref,'meshSubregions')])


def lattice(corners):
    p0,p1,p2,p3=corners
    return [[(1-u)*(1-v)*p0[k]+u*(1-v)*p1[k]+(1-u)*v*p2[k]+u*v*p3[k] for k in (0,1)]
            for v in (0,1/3,2/3,1) for u in (0,1/3,2/3,1)]


def controls(e,region,values,key='controlPoints'):
    old=e.array(region,key)
    if len(old)==len(values):
        for p,xy in zip(old,values):
            if e.geometry(p,'outputPoint',2)!=list(xy):
                e.put(p,'outputPoint',e.geo(xy));e.put(p,'pristine',False)
        return
    for p in old:
        if e.a.kind(p)!='VideoStageRegionControlPoint' or set(e.a.ref(p))-{'$class','region','linkID','outputPoint','pristine'}:
            raise ValueError('Unknown point data cannot be replaced safely.')
    points=[e.new_point(region,*xy,f'{e.serial}:{region.data}:{key}:{i}') for i,xy in enumerate(values)]
    e.put_array(region,key,points)


def warp(e,region,kind):
    for child in e.descendants(region):
        current=e.value(child,'warpType')
        if current==kind:continue
        pts=[e.geometry(p,'outputPoint',2) for p in e.array(child,'controlPoints')]
        shadow=e.array(child,'shadowControlPoints')
        if kind==2:
            if len(shadow)==16:
                e.put_array(child,'controlPoints',shadow);e.put_array(child,'shadowControlPoints',[])
            elif len(pts)==4:controls(e,child,lattice(pts))
            else:raise ValueError('Unsupported warp conversion topology.')
        elif len(pts)==16:
            old=e.array(child,'controlPoints');e.put_array(child,'shadowControlPoints',old)
            e.put_array(child,'controlPoints',[old[i] for i in (0,3,12,15)])
        elif len(pts)!=4:raise ValueError('Unsupported warp conversion topology.')
        e.put(child,'warpType',kind)


def split_curve(points,t):
    levels=[points]
    while len(levels[-1])>1:
        p=levels[-1];levels.append([[(1-t)*a[k]+t*b[k] for k in (0,1)] for a,b in zip(p,p[1:])])
    return [l[0] for l in levels],[l[-1] for l in reversed(levels)]


def interval(points,a,b):
    left,_=split_curve(points,b)
    _,middle=split_curve(left,a/b if b else 0)
    return middle


def restrict(data,u0,u1,v0,v1):
    children=data['mesh_subregions']
    if children:
        w,h=data['mesh_width'],data['mesh_height']
        col=min(int((u0+1e-10)*w),w-1);row=min(int((v0+1e-10)*h),h-1)
        if u1*w>col+1+1e-8 or v1*h>row+1+1e-8:
            raise ValueError('Mesh cells cross existing subdivisions; use reset=true to replace that topology.')
        return restrict(children[row*w+col],u0*w-col,u1*w-col,v0*h-row,v1*h-row)
    shadow=data['shadow_control_points'];points=shadow if data['warp_type']==3 and len(shadow)==16 else data['control_points']
    pts=[p['output_point']['components'] for p in points]
    cubic=data['warp_type']==2 or data['warp_type']==3 and len(shadow)==16
    if not cubic:return [_warp_point(data,u,v) for u,v in [(u0,v0),(u1,v0),(u0,v1),(u1,v1)]],False
    rows=[interval(pts[i*4:i*4+4],u0,u1) for i in range(4)]
    cols=[interval([rows[y][x] for y in range(4)],v0,v1) for x in range(4)]
    return [cols[x][y] for y in range(4) for x in range(4)],True


def mesh(e,stage,region,w,h,reset=False):
    if not reset and (e.value(region,'meshWidth'),e.value(region,'meshHeight'))==(w,h):return
    known={'$class','uniqueID','stage','route','boundsOnStage','initialBoundsOnRoute','autoEdgeBlends','meshWidth','meshHeight','warpType','edgeBlendTopPixels','edgeBlendBottomPixels','edgeBlendLeftPixels','edgeBlendRightPixels','edgeBlendCenterLuminance','edgeBlendPower','edgeBlendGamma','shadowControlPoints','meshSubregions','controlPoints'}
    for child in e.descendants(region):
        if e.a.kind(child)!='VideoStageRegion' or child!=region and set(e.a.ref(child))-known:
            raise ValueError('Unknown mesh data cannot be replaced safely.')
        for key in ('controlPoints','shadowControlPoints'):
            for p in e.array(child,key):
                if e.a.kind(p)!='VideoStageRegionControlPoint' or set(e.a.ref(p))-{'$class','region','linkID','outputPoint','pristine'}:
                    raise ValueError('Unknown point data cannot be replaced safely.')
    owned={p.data for r in e.descendants(region) for key in ('controlPoints','shadowControlPoints') for p in e.array(r,key)}
    links={e.ident(e.a.ref(p)['linkID']) for r in e.descendants(region) for key in ('controlPoints','shadowControlPoints') for p in e.array(r,key)}
    if any(p.data not in owned and e.ident(e.a.ref(p)['linkID']) in links for p in e.points()):
        raise ValueError('Mesh replacement has external point links; unlink them explicitly first.')
    if not reset:
        by_uv={};by_link={}
        def linked_lattice(node,u=Fraction(0),v=Fraction(0),du=Fraction(1),dv=Fraction(1)):
            children=e.array(node,'meshSubregions')
            if children:
                columns,rows=e.value(node,'meshWidth'),e.value(node,'meshHeight')
                for index,child in enumerate(children):
                    linked_lattice(child,u+du*(index%columns)/columns,v+dv*(index//columns)/rows,du/columns,dv/rows)
            else:
                pts=e.array(node,'controlPoints');columns=4 if len(pts)==16 else 2
                for index,p in enumerate(pts):
                    uv=(u+du*(index%columns)/(columns-1),v+dv*(index//columns)/(columns-1))
                    link=e.ident(e.a.ref(p)['linkID'])
                    by_uv.setdefault(uv,set()).add(link);by_link.setdefault(link,set()).add(uv)
        linked_lattice(region)
        if any(len(values)>1 for values in (*by_uv.values(),*by_link.values())):
            raise ValueError('Mesh has custom links or unlinked seams; use reset=true explicitly to replace them.')
    data=record(e,region);bounds=e.geometry(region,'boundsOnStage',4);route=e.a.ref(region).get('route')
    children=[];kind=e.value(region,'warpType')
    for row in range(h):
        for col in range(w):
            x,y,rw,rh=bounds;b=[x+rw*col/w,y+rh*row/h,rw/w,rh/h]
            child=e.new_region(stage,route if e.a.ref(route) is not None else None,b,f'{e.serial}:mesh:{region.data}:{col}:{row}',leaf=True)
            ix,iy,iw,ih=e.geometry(region,'initialBoundsOnRoute',4)
            rect=[ix+iw*col/w,iy+ih*row/h,iw/w,ih/h]
            if reset:
                x0,y0,cw,ch=rect;corners=[[x0,y0],[x0+cw,y0],[x0,y0+ch],[x0+cw,y0+ch]]
                controls(e,child,lattice(corners) if kind==2 else corners)
            else:
                values,cubic=restrict(data,col/w,(col+1)/w,row/h,(row+1)/h)
                if kind==2:
                    controls(e,child,values if cubic else lattice(values))
                elif cubic:
                    controls(e,child,[values[i] for i in (0,3,12,15)]);controls(e,child,values,'shadowControlPoints')
                else:controls(e,child,values)
            e.put(child,'initialBoundsOnRoute',e.geo(rect))
            e.put(child,'warpType',kind)
            children.append(child)
    for cell_index,child in enumerate(children):
        col,row=cell_index%w,cell_index//w
        for key in ('controlPoints','shadowControlPoints'):
            pts=e.array(child,key)
            for index,p in enumerate(pts):
                columns=4 if len(pts)==16 else 2
                u=Fraction(col*(columns-1)+index%columns,w*(columns-1))
                v=Fraction(row*(columns-1)+index//columns,h*(columns-1))
                xy=tuple(round(x,9) for x in e.geometry(p,'outputPoint',2))
                e.pointer(p,'linkID',e.nsuuid(f'{e.serial}:meshlink:{region.data}:{u}:{v}:{xy}'))
    if reset:
        x,y,rw,rh=e.geometry(region,'initialBoundsOnRoute',4)
        corners=[[x,y],[x+rw,y],[x,y+rh],[x+rw,y+rh]]
        controls(e,region,lattice(corners) if kind==2 else corners)
    e.put_array(region,'meshSubregions',children);e.put(region,'meshWidth',w);e.put(region,'meshHeight',h)


def set_bounds(e,region,new,parent_bounds=None,parent_initial=None):
    old=e.geometry(region,'boundsOnStage',4)
    initial=e.geometry(region,'initialBoundsOnRoute',4)
    children=e.array(region,'meshSubregions')
    if children:
        columns,rows=e.value(region,'meshWidth'),e.value(region,'meshHeight')
        if len(children)!=columns*rows:raise ValueError('Invalid mesh topology during bounds change.')
        for index,child in enumerate(children):
            col,row=index%columns,index//columns
            cell=[new[0]+new[2]*col/columns,new[1]+new[3]*row/rows,new[2]/columns,new[3]/rows]
            set_bounds(e,child,cell,old,initial)
    elif old[2:]!=new[2:] and all(e.value(p,'pristine') is True for p in e.array(region,'controlPoints')):
        # QLab 5.5.10 resets pristine leaves on size changes, preserving edited
        # leaves and shadow controls (native resize/crop acceptance fixtures).
        bx,by,bw,bh=parent_bounds or old
        ix,iy,iw,ih=parent_initial or initial
        rect=[ix+(new[0]-bx)*iw/bw,iy+(new[1]-by)*ih/bh,new[2]*iw/bw,new[3]*ih/bh]
        x,y,w,h=rect;corners=[[x,y],[x+w,y],[x,y+h],[x+w,y+h]]
        values=lattice(corners) if e.value(region,'warpType')==2 else corners
        points=e.array(region,'controlPoints')
        if len(points)!=len(values):raise ValueError('Unknown pristine control topology.')
        for point,xy in zip(points,values):
            e.put(point,'outputPoint',e.geo(xy));e.put(point,'pristine',True)
        e.put(region,'initialBoundsOnRoute',e.geo(rect))
    e.put(region,'boundsOnStage',e.geo(new))


def point(e,stage,selector):
    _,region=e.region(e.ident(e.a.ref(stage)['uniqueID']),selector['region_id'])
    for index in selector.get('subregions',[]):
        children=e.array(region,'meshSubregions')
        if index>=len(children):raise ValueError('Subregion index is outside the exact mesh.')
        region=children[index]
    values=e.array(region,'shadowControlPoints' if selector.get('shadow') else 'controlPoints')
    if selector['index']>=len(values):raise ValueError('Point index is outside the exact control array.')
    return values[selector['index']]


def edit_geometry(e,stage,region,op):
    kind=op['kind']
    if kind=='set_bounds':set_bounds(e,region,op['bounds'])
    elif kind=='warp':warp(e,region,op['warp'])
    elif kind=='split_region':mesh(e,stage,region,op['width'],op['height'],op.get('reset',False))
    elif kind=='edit_point':
        p=point(e,stage,op['point']);link=e.ident(e.a.ref(p)['linkID'])
        for other in e.points():
            if e.ident(e.a.ref(other)['linkID'])==link:
                e.put(other,'outputPoint',e.geo([op['x'],op['y']]));e.put(other,'pristine',False)
                owner=e.a.ref(e.a.ref(other)['region']).get('stage')
                if e.a.ref(owner) is not None:e.changed.add(('stage',e.ident(e.a.ref(owner)['uniqueID'])))
    elif kind in {'link_points','unlink_points'}:
        points=[point(e,stage,p) for p in op['points']]
        first=e.geometry(points[0],'outputPoint',2)
        if kind=='link_points':
            route=e.a.ref(e.a.ref(points[0])['region']).get('route')
            if any(e.a.ref(e.a.ref(p)['region']).get('route')!=route or any(abs(a-b)>1e-5 for a,b in zip(e.geometry(p,'outputPoint',2),first)) for p in points):
                raise ValueError('Link points must already coincide on the same route; move them explicitly first.')
            if len({e.ident(e.a.ref(p)['linkID']) for p in points})==1:return
            old_links={e.ident(e.a.ref(p)['linkID']) for p in points}
            peers=[p for p in e.points() if e.ident(e.a.ref(p)['linkID']) in old_links]
            if any(e.a.ref(e.a.ref(p)['region']).get('route')!=route or any(abs(a-b)>1e-5 for a,b in zip(e.geometry(p,'outputPoint',2),first)) for p in peers):
                raise ValueError('Existing linked peers do not coincide; unlink explicitly first.')
            points=peers
        for i,p in enumerate(points):
            e.pointer(p,'linkID',e.nsuuid(f'{e.serial}:link:{0 if kind=="link_points" else i}'))
            if kind=='link_points':e.put(p,'pristine',False)
    elif kind=='reset_region':
        route=e.a.ref(region).get('route')
        rw,rh=e.geometry(route,'naturalSize',2) if e.a.ref(route) is not None else [e.value(stage,'width'),e.value(stage,'height')]
        x,y,w,h=e.geometry(region,'boundsOnStage',4)
        sw,sh=e.value(stage,'width'),e.value(stage,'height')
        def output(px,py):
            if op.get('size_from','stage')=='route':return [(px-x)*rw/w,(py-y)*rh/h]
            return [px-sw/2+rw/2,py-sh/2+rh/2]
        origin=output(x,y)
        rect=[*origin,rw if op.get('size_from','stage')=='route' else w,rh if op.get('size_from','stage')=='route' else h]
        e.put(region,'initialBoundsOnRoute',e.geo(rect))
        mesh(e,stage,region,1,1,True)
        for child in e.descendants(region):e.put_array(child,'shadowControlPoints',[])
    elif kind=='resize_stage':
        oldw,oldh=e.value(stage,'width'),e.value(stage,'height');nw,nh=op['width'],op['height']
        if (oldw,oldh)==(nw,nh):return
        roots=e.array(stage,'regions');kept=[]
        for root in roots:
            x,y,w,h=e.geometry(root,'boundsOnStage',4)
            if op['mode']=='scale':
                sx,sy=nw/oldw,nh/oldh
                if op.get('preserve_region_aspect'):sx=sy=min(sx,sy)
                left,bottom=(x-oldw/2)*sx+nw/2,(y-oldh/2)*sy+nh/2
                right,top=left+w*sx,bottom+h*sy
            else:
                anchor=op.get('anchor','center')
                ax=0 if 'left' in anchor else 1 if 'right' in anchor else 0.5
                ay=0 if 'bottom' in anchor else 1 if 'top' in anchor else 0.5
                left,bottom=x+(nw-oldw)*ax,y+(nh-oldh)*ay
                right,top=left+w,bottom+h
            left,bottom,right,top=max(0,left),max(0,bottom),min(nw,right),min(nh,top)
            if right>left and top>bottom:
                set_bounds(e,root,[left,bottom,right-left,top-bottom]);kept.append(root)
        e.put_array(stage,'regions',kept)
        e.put(stage,'width',nw);e.put(stage,'height',nh)
        e.put(e.a.ref(stage)['viewport'],'boundsOnStage',e.geo([0,0,nw,nh]))
    else:raise ValueError('Unsupported video geometry operation.')
