"""Strict operations for version-gated video document authoring."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, JsonValue, model_validator

Name=Annotated[StrictStr,Field(min_length=1,max_length=255)]
Reference=Annotated[StrictStr,Field(min_length=1,max_length=512)]
Dimension=Annotated[StrictInt,Field(ge=1,le=16384)]
RouteDimension=Annotated[StrictInt,Field(ge=1,le=30000)]
Coordinate=Annotated[float,Field(strict=True,allow_inf_nan=False,ge=-1e7,le=1e7)]
Positive=Annotated[float,Field(strict=True,allow_inf_nan=False,gt=0,le=16384)]


class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

    @model_validator(mode='before')
    @classmethod
    def explicit_values(cls,value):
        if isinstance(value,dict):
            if any(v is None and k not in {'mask_path','device_ref','source_ref','route_id'} for k,v in value.items()):
                raise ValueError('Only assignment fields accept explicit null; omit other fields to preserve them.')
            if 'rotation' in value and type(value['rotation']) is not int:
                raise ValueError('Rotation must be an integer.')
        return value


class Bounds(StrictModel):
    x: Coordinate
    y: Coordinate
    width: Positive
    height: Positive


class RouteFields(StrictModel):
    name: Name|None=None
    width: RouteDimension|None=None
    height: RouteDimension|None=None
    rotation: Literal[0,90,180,270]|None=None
    scaling: Literal['center','fit','stretch','fill']|None=None
    rear: StrictBool|None=None
    device_ref: Reference|None=None
    layout_wide: Annotated[StrictInt,Field(ge=1,le=4)]|None=None
    layout_high: Annotated[StrictInt,Field(ge=1,le=4)]|None=None
    layout_index: Annotated[StrictInt,Field(ge=0,le=15)]|None=None
    guideline_mode: Annotated[StrictInt,Field(ge=0,le=15)]|None=None


class VideoRouteUpdate(RouteFields):
    kind: Literal['update_route']
    route_id: Reference


class VideoRouteCreate(RouteFields):
    kind: Literal['create_route']
    client_ref: Name
    name: Name
    width: RouteDimension=1920
    height: RouteDimension=1080


class VideoRouteDelete(StrictModel):
    kind: Literal['delete_route']
    route_id: Reference


class StageFields(StrictModel):
    name: Name|None=None
    layer: Annotated[StrictInt,Field(ge=0,le=1000)]|None=None
    keep_rendering: StrictBool|None=None
    mask_path: Reference|None=None
    grid_is_dark: StrictBool|None=None
    grid_bypasses_edge_blends: StrictBool|None=None


class StageCreate(StageFields):
    kind: Literal['create_stage']
    client_ref: Name
    name: Name
    width: Dimension=1920
    height: Dimension=1080


class StageUpdate(StageFields):
    kind: Literal['update_stage']
    stage_id: Reference


class StageDelete(StrictModel):
    kind: Literal['delete_stage']
    stage_id: Reference


class StageResize(StrictModel):
    kind: Literal['resize_stage']
    stage_id: Reference
    width: Dimension
    height: Dimension
    mode: Literal['scale','crop_pad']
    preserve_region_aspect: StrictBool=False
    anchor: Literal['bottom_left','bottom','bottom_right','left','center','right','top_left','top','top_right']='center'


class RegionCreate(StrictModel):
    kind: Literal['create_region']
    stage_id: Reference
    client_ref: Name
    route_id: Reference|None=None
    bounds: Bounds


class RegionUpdate(StrictModel):
    kind: Literal['update_region']
    stage_id: Reference
    region_id: Reference
    route_id: Reference|None=None
    bounds: Bounds|None=None
    warp: Literal['perspective','linear','bezier']|None=None
    auto_edge_blends: StrictBool|None=None
    edge_top: Annotated[float,Field(ge=0,le=16384,allow_inf_nan=False)]|None=None
    edge_bottom: Annotated[float,Field(ge=0,le=16384,allow_inf_nan=False)]|None=None
    edge_left: Annotated[float,Field(ge=0,le=16384,allow_inf_nan=False)]|None=None
    edge_right: Annotated[float,Field(ge=0,le=16384,allow_inf_nan=False)]|None=None
    blend_gamma: Annotated[float,Field(gt=0,le=10,allow_inf_nan=False)]|None=None
    blend_power: Annotated[float,Field(gt=0,le=10,allow_inf_nan=False)]|None=None
    center_luminance: Annotated[float,Field(ge=0,le=1,allow_inf_nan=False)]|None=None


class RegionDelete(StrictModel):
    kind: Literal['delete_region']
    stage_id: Reference
    region_id: Reference


class RegionOrder(StrictModel):
    kind: Literal['reorder_regions']
    stage_id: Reference
    region_ids: Annotated[list[Reference],Field(min_length=1,max_length=1000)]


class RegionMesh(StrictModel):
    kind: Literal['split_region']
    stage_id: Reference
    region_id: Reference
    width: Literal[1,2,4,8,16,32]
    height: Literal[1,2,4,8,16,32]
    reset: StrictBool=False


class RegionReset(StrictModel):
    kind: Literal['reset_region']
    stage_id: Reference
    region_id: Reference
    size_from: Literal['stage','route']='stage'


class PointRef(StrictModel):
    region_id: Reference
    subregions: Annotated[list[Annotated[StrictInt,Field(ge=0,le=1023)]],Field(max_length=16)]=Field(default_factory=list)
    index: Annotated[StrictInt,Field(ge=0,le=15)]
    shadow: StrictBool=False


class PointEdit(StrictModel):
    kind: Literal['edit_point']
    stage_id: Reference
    point: PointRef
    x: Coordinate
    y: Coordinate


class PointLinks(StrictModel):
    kind: Literal['link_points','unlink_points']
    stage_id: Reference
    points: Annotated[list[PointRef],Field(min_length=1,max_length=128)]


class DeviceFields(StrictModel):
    name: Name|None=None
    width: Dimension|None=None
    height: Dimension|None=None
    frame_rate: Annotated[float,Field(gt=0,le=240,allow_inf_nan=False)]|None=None
    pixel_format: Literal['BGRA','2vuy']|None=None
    audio_channels: Annotated[StrictInt,Field(ge=0,le=64)]|None=None
    audio_sample_rate: Literal[44100,48000]|None=None
    audio_buffer_size: Literal[128,256,512,1024,2048]|None=None


class DeviceCreate(DeviceFields):
    kind: Literal['create_device']
    client_ref: Name
    device_type: Literal['NDI','Syphon']
    name: Name
    width: Dimension=1920
    height: Dimension=1080
    frame_rate: Annotated[float,Field(gt=0,le=240,allow_inf_nan=False)]=30


class DeviceUpdate(DeviceFields):
    kind: Literal['update_device']
    device_ref: Reference


class DeviceDelete(StrictModel):
    kind: Literal['delete_device']
    device_ref: Reference


class InputFormat(StrictModel):
    width: Dimension
    height: Dimension
    pixel_format: Annotated[StrictInt,Field(ge=0,le=2**32-1)]
    frame_rate: Annotated[float,Field(gt=0,le=240,allow_inf_nan=False)]


class InputFields(StrictModel):
    name: Name|None=None
    source_ref: Reference|None=None
    mode: Literal['auto']|InputFormat|None=None


class InputCreate(InputFields):
    kind: Literal['create_input']
    client_ref: Name
    name: Name


class InputUpdate(InputFields):
    kind: Literal['update_input']
    patch_id: Reference


class InputDelete(StrictModel):
    kind: Literal['delete_input']
    patch_id: Reference


class InputOrder(StrictModel):
    kind: Literal['reorder_inputs']
    patch_ids: Annotated[list[Reference],Field(min_length=1,max_length=1000)]


def batch(union):
    return Annotated[list[Annotated[union,Field(discriminator='kind')]],Field(min_length=1,max_length=50)]


RouteOperations=batch(VideoRouteCreate|VideoRouteUpdate|VideoRouteDelete)
StageOperations=batch(StageCreate|StageUpdate|StageDelete|StageResize|RegionCreate|RegionUpdate|RegionDelete|RegionOrder|RegionMesh|RegionReset|PointEdit|PointLinks)
DeviceOperations=batch(DeviceCreate|DeviceUpdate|DeviceDelete)
InputOperations=batch(InputCreate|InputUpdate|InputDelete|InputOrder)
OPERATIONS={'routes':RouteOperations,'stages':StageOperations,'devices':DeviceOperations,'inputs':InputOperations}


class VideoArchiveEditResult(BaseModel):
    model_config=ConfigDict(extra='allow')
    ok: bool
    status: str
    domain: str="video"
    planned_operations: list[dict]=Field(default_factory=list)
    executed_operations: list[dict]=Field(default_factory=list)
    created_refs: dict[str,str]=Field(default_factory=dict)
    affected_cues: list[dict]=Field(default_factory=list)
    affected_objects: list[dict]=Field(default_factory=list)
    native_video_verified: bool=False
    confirm_token: str|None=None
    error: str|None=None
    workspace_id: str|None=None
    dry_run: bool|None=None
    phase: str|None=None
    path: str|None=None
    recovery_path: str|None=None
    source_sha256: str|None=None
    output_sha256: str|None=None
    file_replaced: bool=False
    document_reopened: bool=False
    document_modified_after_reopen: bool|None=None
    summary: dict|None=None
    changes: list[dict]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)
    verification_scope: str|None=None
    # Preserve the legacy single-setter output contract in the generated schema.
    operation: str|None=None
    requested_value: JsonValue|None=None
    baseline: JsonValue|None=None
    readback: JsonValue|None=None
    readiness: dict|None=None
    activity: dict|None=None
    verification: dict|None=None
    timeout_confirmation: dict|None=None
    retry_unsafe: bool|None=None
    errors: dict[str,str]|None=None
    error_code: str|None=None
    suggested_action: str|None=None
    message: str|None=None
