"""Read bounded, last-saved QLab video configuration from a local workspace."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import math
import plistlib
from pathlib import Path
import re
import subprocess
import time
from uuid import UUID

from . import workspace_documents as docs
from .light_patch.archive import Archive
from .light_patch.reader import _read_file
from .sanitizer import sanitize_exception_message

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_SECTIONS = {
    "stages": "stages",
    "routes": "routes",
    "inputs": "input_patches",
}
_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")


def _warp_name(value):
    return {1: "Linear", 2: "Bézier", 3: "Perspective"}.get(value, "unknown") if type(value) is int else "unknown"


def _guideline_grid(value):
    """QLab 5.5.10 VideoStageEditor.nib menu tags, independently of visibility."""
    if type(value) is int and 0 <= value <= 15:
        width, height = value % 4 + 1, value // 4 + 1
        return dict(width=width, height=height, label=f"{width}×{height}")
    return None


def _warp_point(region, u, v, depth=0):
    """Evaluate the native forward-warp branches; reject unsupported geometry."""
    if depth > 32:
        raise ValueError("Warp mesh nesting exceeds the inspection limit.")
    children = region.get("mesh_subregions") or []
    if children:
        width, height = region.get("mesh_width"), region.get("mesh_height")
        if (type(width) is not int or type(height) is not int
                or min(width, height) < 1 or len(children) != width * height):
            raise ValueError("Invalid warp mesh dimensions.")
        col, row = min(int(u * width), width - 1), min(int(v * height), height - 1)
        return _warp_point(children[row * width + col], u * width - col,
                           v * height - row, depth + 1)
    kind = region.get("warp_type")
    if type(kind) is not int or kind not in (0, 1, 2, 3):
        raise ValueError("Unknown warp type.")
    shadow = region.get("shadow_control_points") or []
    controls = shadow if kind == 3 and len(shadow) == 16 else region.get("control_points", [])
    points = [(p.get("output_point") or {}).get("components") for p in controls]
    bezier = kind == 2 or kind == 3 and len(shadow) == 16
    if (len(points) != (16 if bezier else 4)
            or any(not isinstance(p, list) or len(p) != 2 for p in points)
            or not all(type(x) in (int, float) and math.isfinite(x) for p in points for x in p)):
        raise ValueError("Invalid warp control points.")
    if bezier:
        def weights(t):
            return [(1-t)**3, 3*t*(1-t)**2, 3*t*t*(1-t), t**3]
        a, b = weights(u), weights(v)
        return [sum(a[x] * b[y] * points[y*4+x][axis] for y in range(4) for x in range(4)) for axis in (0, 1)]
    if kind == 1:
        weights = [(1-u)*(1-v), u*(1-v), (1-u)*v, u*v]
        return [sum(w*p[axis] for w, p in zip(weights, points)) for axis in (0, 1)]
    # Projective unit-square map, with native corner order 0, 1, 3, 2.
    p0, p1, p3, p2 = points
    dx1, dy1 = p1[0]-p2[0], p1[1]-p2[1]
    dx2, dy2 = p3[0]-p2[0], p3[1]-p2[1]
    dx3, dy3 = p0[0]-p1[0]+p2[0]-p3[0], p0[1]-p1[1]+p2[1]-p3[1]
    determinant = dx1*dy2-dx2*dy1
    if determinant == 0:
        raise ValueError("Singular projective warp.")
    g, h = (dx3*dy2-dx2*dy3)/determinant, (dx1*dy3-dx3*dy1)/determinant
    denominator = g*u+h*v+1
    if denominator == 0:
        raise ValueError("Projective point is at infinity.")
    result = [((p1[i]-p0[i]+g*p1[i])*u + (p3[i]-p0[i]+h*p3[i])*v + p0[i])/denominator for i in (0, 1)]
    if not all(math.isfinite(x) for x in result):
        raise ValueError("Non-finite projective point.")
    return result


def _region_center(region, route):
    """Derive the functional midpoint; keep native acceptance limits explicit."""
    result = dict(source="saved_archive", derived=True, origin="output_route_center",
                  units="pixels", status="unavailable", value=None)
    size = (route or {}).get("natural_size") or {}
    dimensions = size.get("components") or []
    if (len(dimensions) != 2 or not all(type(x) in (int, float) and math.isfinite(x)
            and x > 0 for x in dimensions)):
        result["reason"] = "Invalid or missing output-route dimensions."
        return result
    try:
        point = _warp_point(region, .5, .5)
        if not all(math.isfinite(x) for x in point):
            raise ValueError("Non-finite warped midpoint.")
    except (ValueError, OverflowError) as exc:
        result["reason"] = str(exc)
        return result
    result.update(status="available", method="forward_warp_at_region_midpoint",
                  value=[point[i] - dimensions[i] / 2 for i in (0, 1)],
                  native_validation="sampled_linear_perspective_bezier_and_divided_meshes")
    return result


def inspect_saved_video(source: bytes) -> dict:
    """Decode known Video and Camera settings without instantiating archived classes."""
    outer = Archive(source)
    meta = outer.mapping(outer.root)
    version = outer.ref(meta.get("QLabShortVersionString"))
    build = outer.ref(meta.get("QLabBuildNumber"))
    if version != "5.5.10" or build != 5510:
        raise ValueError("Saved video inspection supports QLab 5.5.10/build 5510.")
    workspace_id = str(UUID(outer.ref(meta["uniqueID"]))).upper()
    settings = outer.mapping(meta["settings"])
    video = outer.mapping(settings["Video"])
    camera = outer.mapping(settings["Camera"]) if "Camera" in settings else {}
    result = dict(workspace_id=workspace_id, version=version, build=build,
                  stages=[], routes=[], inputs=[], destinations=[], diagnostics=[],
                  coverage="complete", process_inventory="not_in_saved_workspace_archive")

    def diagnostic(section: str, code: str, message: str, **identity) -> None:
        result["coverage"] = "partial"
        result["diagnostics"].append(dict(section=section, code=code, message=message, **identity))

    def resolved(value):
        return outer.ref(value)

    def class_name(value) -> str | None:
        value = resolved(value)
        try:
            return outer.kind(value) if isinstance(value, dict) and "$class" in value else None
        except (KeyError, TypeError, ValueError):
            return None

    def uid_ref(value):
        from plistlib import UID
        return value.data if isinstance(value, UID) else None

    def identity(value) -> str | None:
        value = resolved(value)
        if isinstance(value, str):
            try:
                return str(UUID(value)).upper()
            except (ValueError, AttributeError):
                return value
        if isinstance(value, dict):
            if class_name(value) == "NSUUID":
                raw = resolved(value.get("NS.uuidbytes"))
                if isinstance(raw, bytes) and len(raw) == 16:
                    return str(UUID(bytes=raw)).upper()
            for key in ("uniqueID", "virtualID"):
                if key in value:
                    return identity(value[key])
        return None

    def plain(value, *, section: str, owner: str | None = None, depth: int = 0,
              ancestors: frozenset[int] = frozenset()):
        """Convert only JSON-safe Foundation containers and scalar value objects."""
        from plistlib import UID
        ref_id = uid_ref(value)
        if ref_id is not None and ref_id in ancestors:
            diagnostic(section, "cyclic_reference", "A cyclic archived reference was summarized.", id=owner)
            return {"reference_uid": ref_id}
        if depth > 24:
            diagnostic(section, "nested_value_limit", "An archived value exceeded the interpretation depth limit.", id=owner)
            return {"omitted": "maximum nesting depth"}
        next_ancestors = ancestors | ({ref_id} if ref_id is not None else set())
        item = resolved(value)
        if item is None or type(item) in (str, bool, int):
            return item
        if type(item) is float:
            if math.isfinite(item):
                return item
            diagnostic(section, "non_finite_value", "A non-finite numeric value was omitted.", id=owner)
            return None
        if isinstance(item, bytes):
            diagnostic(section, "binary_value_omitted", "Opaque binary data was omitted.", id=owner)
            return {"present": True, "bytes_omitted": True}
        if isinstance(item, list):
            if len(item) > 1000:
                diagnostic(section, "nested_array_truncated", "A nested archived array exceeded the 1,000-entry interpretation limit.", id=owner)
            return [plain(v, section=section, owner=owner, depth=depth + 1,
                          ancestors=frozenset(next_ancestors)) for v in item[:1000]]
        if not isinstance(item, dict):
            return None
        kind = class_name(item)
        if kind == "NSUUID":
            return identity(item)
        if kind == "F53VideoAVCaptureFormat":
            fields = {key: resolved(item.get(key)) for key in
                      ("framesPerSecond", "pixelWidth", "pixelHeight", "pixelFormat")}
            unknown = sorted(set(item) - set(fields) - {"$class"})
            if unknown:
                diagnostic(section, "unknown_input_format_fields", "Uninterpreted camera format fields: " + ", ".join(unknown[:20]), id=owner)
            return {"class_name": kind, **fields}
        if kind in {"NSArray", "NSMutableArray"}:
            try:
                refs = outer.array(item)
                if len(refs) > 1000:
                    diagnostic(section, "nested_array_truncated", "A nested archived array exceeded the 1,000-entry interpretation limit.", id=owner)
                return [plain(v, section=section, owner=owner, depth=depth + 1,
                              ancestors=frozenset(next_ancestors)) for v in refs[:1000]]
            except (KeyError, TypeError, ValueError):
                diagnostic(section, "invalid_array", "An archived array could not be interpreted.", id=owner)
                return []
        if kind in {"NSDictionary", "NSMutableDictionary"}:
            try:
                values = outer.mapping(item)
            except (KeyError, TypeError, ValueError):
                diagnostic(section, "invalid_dictionary", "An archived dictionary could not be interpreted.", id=owner)
                return {}
            output = {}
            for key, entry in values.items():
                if not isinstance(key, str):
                    diagnostic(section, "non_string_dictionary_key", "A dictionary entry with a non-string key was omitted.", id=owner)
                    continue
                output[key] = plain(entry, section=section, owner=owner, depth=depth + 1,
                                    ancestors=frozenset(next_ancestors))
            return output
        if kind == "NSValue":
            fields = {key: plain(entry, section=section, owner=owner, depth=depth + 1,
                                 ancestors=frozenset(next_ancestors))
                      for key, entry in item.items() if key != "$class" and key != "NS.special"}
            return fields
        if kind == "F53Alias":
            fields = {key: entry for key, entry in item.items() if key != "$class"}
            path = next((resolved(entry) for key, entry in fields.items()
                         if "path" in key.casefold() and "relative" not in key.casefold()
                         and isinstance(resolved(entry), str)), None)
            relative = next((resolved(entry) for key, entry in fields.items()
                             if ("relative" in key.casefold() or "filename" in key.casefold())
                             and isinstance(resolved(entry), str)), None)
            bookmark = next((resolved(entry) for key, entry in fields.items()
                             if "bookmark" in key.casefold()), None)
            return {"class_name": kind, "last_known_path": path if isinstance(path, str) else None,
                    "relative_path": relative if isinstance(relative, str) else None,
                    "bookmark_present": bookmark is not None}
        # Do not serialize arbitrary archived object graphs or unknown class payloads.
        diagnostic(section, "unknown_object_class", "An archived object class was not expanded.", id=owner, class_name=kind or "unknown")
        return {"class_name": kind or "unknown", "id": identity(item)}

    def plain_dict(value, section: str, owner: str | None = None) -> dict:
        try:
            return plain(value, section=section, owner=owner) or {}
        except (KeyError, TypeError, ValueError, AttributeError):
            diagnostic(section, "invalid_dictionary", "An archived dictionary could not be interpreted.", id=owner)
            return {}

    def array(value, section: str) -> list:
        try:
            return outer.array(value)
        except (KeyError, TypeError, ValueError, AttributeError):
            diagnostic(section, "invalid_collection", "An archived collection could not be interpreted.")
            return []

    def number_or_text(value, section: str, owner: str | None = None):
        value = resolved(value)
        if value is None or type(value) in (str, bool, int):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        diagnostic(section, "unsupported_scalar", "A field has an unsupported value type.", id=owner)
        return None

    def geometry(value, section: str, owner: str, expected: int | None = None):
        raw = resolved(value)
        if not isinstance(raw, str):
            diagnostic(section, "invalid_geometry", "A geometry value was not a string.", id=owner)
            return {"raw": None, "components": None}
        components = [float(match.group()) for match in _NUMBER.finditer(raw)]
        if any(not math.isfinite(part) for part in components) or (expected and len(components) != expected):
            diagnostic(section, "invalid_geometry", "A geometry value could not be interpreted.", id=owner)
            components = None
        return {"raw": raw, "components": components}

    def unknown_fields(item: dict, allowed: set[str], section: str, owner: str | None):
        unknown = sorted(set(item) - allowed - {"$class"})
        if unknown:
            diagnostic(section, "unknown_fields", "Uninterpreted fields: " + ", ".join(name[:64] for name in unknown[:20]), id=owner)

    routes_by_id: dict[str, dict] = {}
    for ref in array(video.get("routes"), "routes"):
        item = resolved(ref)
        if not isinstance(item, dict):
            diagnostic("routes", "invalid_route", "A route entry could not be interpreted.")
            continue
        route_id = identity(item.get("uniqueID"))
        try:
            kind = class_name(item)
            if kind != "F53VideoOutputRoute" or not route_id:
                raise ValueError("unsupported route identity")
            name = resolved(item.get("name"))
            info = plain_dict(item.get("destinationInfo"), "routes", route_id)
            record = dict(id=route_id, class_name=kind, name=name,
                          destination_type=info.get("destinationType"),
                          destination_name=info.get("name"),
                          destination_key_path=info.get("videoOutputKeyPath"),
                          destination_raster=geometry(info.get("videoOutputRasterSize"), "routes", route_id, 2)
                          if info.get("videoOutputRasterSize") is not None else None,
                          destination_info=info,
                          natural_size=geometry(item.get("naturalSize"), "routes", route_id, 2),
                          rotation_degrees=number_or_text(item.get("rotationDegrees"), "routes", route_id),
                          scaling_mode=number_or_text(item.get("scalingMode"), "routes", route_id),
                          rear=number_or_text(item.get("rear"), "routes", route_id),
                          layout=dict(wide=number_or_text(item.get("layoutWide"), "routes", route_id),
                                      high=number_or_text(item.get("layoutHigh"), "routes", route_id),
                                      index=number_or_text(item.get("layoutIndex"), "routes", route_id)),
                          guideline_mode=number_or_text(item.get("guidelineMode"), "routes", route_id),
                          guideline_grid=_guideline_grid(resolved(item.get("guidelineMode"))),
                          destination_ids=[], destination_candidates=[], destination_match="unmatched")
            unknown_fields(item, {"destinationInfo", "layoutWide", "guidelineMode", "rotationDegrees", "scalingMode", "rear", "layoutIndex", "uniqueID", "naturalSize", "name", "layoutHigh"}, "routes", route_id)
            result["routes"].append(record)
            routes_by_id[route_id] = record
        except (KeyError, TypeError, ValueError, AttributeError):
            diagnostic("routes", "invalid_route", "A saved output route could not be interpreted.", id=route_id)

    destination_records = []
    for ref in array(video.get("virtualDestinations"), "destinations"):
        item = resolved(ref)
        if not isinstance(item, dict):
            diagnostic("destinations", "invalid_destination", "A virtual destination could not be interpreted.")
            continue
        kind = class_name(item) or "unknown"
        registry_scope_id = identity(item.get("virtualID"))
        object_uid = ref.data if isinstance(ref, plistlib.UID) else None
        archive_hash = hashlib.sha256(source).hexdigest()
        dest_id = f"{archive_hash}:{object_uid}" if object_uid is not None else None
        if not registry_scope_id or not dest_id:
            diagnostic("destinations", "missing_destination_id", "A configured destination has no recognizable identifier.", class_name=kind)
        fields = {key: plain(value, section="destinations", owner=dest_id)
                  for key, value in item.items() if key != "$class"}
        record = dict(id=dest_id, registry_scope_id=registry_scope_id,
                      archive_sha256=archive_hash, archive_object_uid=object_uid,
                      class_name=kind, name=fields.get("name"),
                      destination_type=kind.removeprefix("F53VideoOutputDestination"),
                      scope="workspace_configured_virtual_destination", fields=fields)
        result["destinations"].append(record)
        destination_records.append(record)
        if kind not in {"F53VideoOutputDestinationNDI", "F53VideoOutputDestinationSyphon"}:
            diagnostic("destinations", "unknown_destination_class", "A virtual destination class is not specifically interpreted.", id=dest_id, class_name=kind)

    # The archive route has no destination UUID link; type/name matches are candidates only.
    for route in result["routes"]:
        candidates = [d for d in destination_records
                      if d.get("name") == route.get("destination_name")
                      and str(d.get("destination_type", "")).casefold() == str(route.get("destination_type", "")).casefold()]
        route["destination_candidates"] = [d["id"] for d in candidates if d.get("id")]
        route["destination_match"] = "type_name_candidate_not_identity_verified" if candidates else "unmatched"
        if len(candidates) > 1:
            diagnostic("routes", "ambiguous_destination_reference", "The route name and type match multiple saved virtual destinations.", id=route["id"])

    def point_records(value, section: str, owner: str):
        refs = array(value, section)
        points = []
        for index, ref in enumerate(refs[:10000]):
            point = resolved(ref)
            if not isinstance(point, dict):
                diagnostic(section, "invalid_control_point", "A control point could not be interpreted.", id=owner, index=index)
                continue
            point_kind = class_name(point)
            link = identity(point.get("linkID"))
            output_point = resolved(point.get("outputPoint"))
            record = dict(index=index, class_name=point_kind, link_id=link,
                          output_point=geometry(point.get("outputPoint"), section, owner, 2) if isinstance(output_point, str) else None,
                          pristine=number_or_text(point.get("pristine"), section, owner))
            unknown_fields(point, {"region", "linkID", "outputPoint", "pristine"}, section, owner)
            if point_kind != "VideoStageRegionControlPoint":
                diagnostic(section, "unknown_control_point_class", "A control point class is unknown.", id=owner, index=index, class_name=point_kind or "unknown")
            points.append(record)
        if len(refs) > 10000:
            diagnostic(section, "control_point_limit", "Control points exceed the bounded interpretation limit.", id=owner)
        return points

    def region_record(ref, stage_id: str, ancestry: frozenset[int], depth: int = 0) -> dict | None:
        from plistlib import UID
        ref_id = uid_ref(ref)
        if ref_id is not None and ref_id in ancestry:
            diagnostic("stages", "mesh_cycle", "The mesh region hierarchy contains a cycle.", id=stage_id)
            return None
        if depth > 24:
            diagnostic("stages", "mesh_depth_limit", "The mesh region hierarchy exceeded the interpretation depth limit.", id=stage_id)
            return None
        item = resolved(ref)
        if not isinstance(item, dict):
            diagnostic("stages", "invalid_region", "A region entry could not be interpreted.", id=stage_id)
            return None
        region_id = identity(item.get("uniqueID"))
        if not region_id:
            diagnostic("stages", "missing_region_id", "A region has no recognizable UUID.", id=stage_id)
        kind = class_name(item)
        if kind != "VideoStageRegion":
            diagnostic("stages", "unknown_region_class", "A region class is not recognized.", id=region_id or stage_id, class_name=kind or "unknown")
        linked_stage = identity(resolved(item.get("stage"))) if item.get("stage") is not None else None
        route_id = identity(resolved(item.get("route"))) if item.get("route") is not None else None
        if linked_stage and linked_stage != stage_id:
            diagnostic("stages", "broken_stage_reference", "A region references a different stage UUID.", id=region_id)
        if route_id and route_id not in routes_by_id:
            diagnostic("stages", "broken_route_reference", "A region references a route not present in the saved route list.", id=region_id, route_id=route_id)
        edge = {public: number_or_text(item.get(saved), "stages", region_id or stage_id)
                for saved, public in (("autoEdgeBlends", "auto"), ("edgeBlendTopPixels", "top_pixels"),
                                      ("edgeBlendRightPixels", "right_pixels"), ("edgeBlendBottomPixels", "bottom_pixels"),
                                      ("edgeBlendLeftPixels", "left_pixels"), ("edgeBlendCenterLuminance", "center_luminance"),
                                      ("edgeBlendPower", "power"), ("edgeBlendGamma", "gamma"))}
        record = dict(id=region_id, class_name=kind, stage_id=linked_stage or stage_id, route_id=route_id,
                      bounds_on_stage=geometry(item.get("boundsOnStage"), "stages", region_id or stage_id, 4),
                      initial_bounds_on_route=geometry(item.get("initialBoundsOnRoute"), "stages", region_id or stage_id, 4),
                      warp_type=number_or_text(item.get("warpType"), "stages", region_id or stage_id),
                      mesh_width=number_or_text(item.get("meshWidth"), "stages", region_id or stage_id),
                      mesh_height=number_or_text(item.get("meshHeight"), "stages", region_id or stage_id),
                      warp_type_name=_warp_name(resolved(item.get("warpType"))),
                      edge_blends=edge,
                      control_points=point_records(item.get("controlPoints"), "stages", region_id or stage_id),
                      shadow_control_points=point_records(item.get("shadowControlPoints"), "stages", region_id or stage_id)
                      if resolved(item.get("shadowControlPoints")) is not None else [],
                      mesh_subregions=[])
        if record["warp_type_name"] == "unknown":
            diagnostic("stages", "unmapped_warp_type", "Warp code has no validated UI label.", id=region_id)
        unknown_fields(item, {"autoEdgeBlends", "meshWidth", "edgeBlendTopPixels", "shadowControlPoints", "controlPoints", "uniqueID", "edgeBlendBottomPixels", "edgeBlendRightPixels", "initialBoundsOnRoute", "stage", "meshSubregions", "boundsOnStage", "edgeBlendCenterLuminance", "route", "meshHeight", "edgeBlendLeftPixels", "edgeBlendPower", "warpType", "edgeBlendGamma"}, "stages", region_id or stage_id)
        next_ancestry = ancestry | ({ref_id} if ref_id is not None else set())
        record["mesh_subregions"] = [child for child in
            (region_record(child_ref, stage_id, frozenset(next_ancestry), depth + 1)
             for child_ref in array(item.get("meshSubregions"), "stages")) if child is not None]
        return record

    stage_refs = array(video.get("stages"), "stages")
    for ref in stage_refs:
        item = resolved(ref)
        if not isinstance(item, dict):
            diagnostic("stages", "invalid_stage", "A stage entry could not be interpreted.")
            continue
        stage_id = identity(item.get("uniqueID"))
        try:
            kind = class_name(item)
            if kind != "VideoStage" or not stage_id:
                raise ValueError("unsupported stage")
            viewport = resolved(item.get("viewport"))
            viewport_record = None
            if isinstance(viewport, dict):
                viewport_id = identity(viewport.get("uniqueID"))
                mask_ref = viewport.get("maskAlias")
                viewport_record = dict(id=viewport_id, class_name=class_name(viewport),
                    name=resolved(viewport.get("name")), layer=number_or_text(viewport.get("layer"), "stages", stage_id),
                    layer_label="top" if resolved(viewport.get("layer")) == 1000 else None,
                    bounds_on_stage=geometry(viewport.get("boundsOnStage"), "stages", stage_id, 4),
                    audition=number_or_text(viewport.get("audition"), "stages", stage_id),
                    mask_alias=plain(mask_ref, section="stages", owner=stage_id) if resolved(mask_ref) is not None else None)
                if identity(resolved(viewport.get("stage"))) not in (None, stage_id):
                    diagnostic("stages", "broken_viewport_reference", "The viewport references a different stage UUID.", id=stage_id)
                unknown_fields(viewport, {"stage", "boundsOnStage", "maskAlias", "layer", "uniqueID", "name", "audition"}, "stages", viewport_id or stage_id)
            else:
                diagnostic("stages", "missing_viewport", "A stage has no interpretable viewport.", id=stage_id)
            regions = [region for region in
                       (region_record(region_ref, stage_id, frozenset()) for region_ref in array(item.get("regions"), "stages"))
                       if region is not None]
            record = dict(id=stage_id, class_name=kind, name=resolved(item.get("name")),
                          width=number_or_text(item.get("width"), "stages", stage_id),
                          height=number_or_text(item.get("height"), "stages", stage_id),
                          keep_rendering=number_or_text(item.get("keepRendering"), "stages", stage_id),
                          grid_is_dark=number_or_text(item.get("gridIsDark"), "stages", stage_id),
                          grid_bypasses_edge_blends=number_or_text(item.get("gridBypassesEdgeBlends"), "stages", stage_id),
                          viewport=viewport_record, regions=regions)
            unknown_fields(item, {"height", "gridIsDark", "gridBypassesEdgeBlends", "uniqueID", "viewport", "width", "keepRendering", "name", "regions"}, "stages", stage_id)
            def ui_coordinates(region):
                route = next((r for r in result["routes"] if r["id"] == region.get("route_id")), None)
                region["warping_center"] = _region_center(region, route)
                bounds = region["bounds_on_stage"]["components"]
                width, height = record["width"], record["height"]
                if bounds and type(width) in (int, float) and type(height) in (int, float):
                    x, y, w, h = bounds
                    region["ui_coordinates"] = dict(source="saved_archive", origin="stage_center", units="pixels",
                        lower_left=[x - width / 2, y - height / 2],
                        upper_right=[x + w - width / 2, y + h - height / 2], size=[w, h])
                for child in region["mesh_subregions"]:
                    ui_coordinates(child)
            for region in regions:
                ui_coordinates(region)
            result["stages"].append(record)
        except (KeyError, TypeError, ValueError, AttributeError):
            diagnostic("stages", "invalid_stage", "A saved stage could not be interpreted.", id=stage_id)

    for ref in array(camera.get("cameraPatches"), "inputs"):
        item = resolved(ref)
        if not isinstance(item, dict):
            diagnostic("inputs", "invalid_input_patch", "An input patch could not be interpreted.")
            continue
        patch_id = identity(item.get("uniqueID"))
        description = resolved(item.get("serializedDescription"))
        descriptor = plain_dict(description, "inputs", patch_id) if description is not None else None
        kind = class_name(item)
        if kind != "CameraPatch":
            diagnostic("inputs", "unknown_input_class", "An input patch class is not recognized.", id=patch_id, class_name=kind or "unknown")
        unknown_fields(item, {"serializedDescription", "name", "uniqueID"}, "inputs", patch_id)
        result["inputs"].append(dict(id=patch_id, class_name=kind, name=resolved(item.get("name")),
                                     descriptor=descriptor, descriptor_status="configured" if descriptor is not None else "unconfigured"))

    if not result["stages"] and stage_refs:
        diagnostic("stages", "no_stages_interpreted", "No saved stages could be interpreted.")
    return result


def _saved(reader, workspace_id: str) -> dict:
    saved = dict(status="unavailable", source="saved_archive", freshness="unavailable",
                 document_modified=None, coverage="partial", stages=[], routes=[], inputs=[],
                 destinations=[], diagnostics=[], process_inventory="not_in_saved_workspace_archive")
    try:
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader, running_bundle=True), workspace_id)
            saved["document_modified"] = before["modified"]
            if not before["path"]:
                raise ValueError("Workspace has no saved document path.")
            path = Path(before["path"])
            source, file_identity = _read_file(path)
            try:
                decoded = inspect_saved_video(source)
            except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
                saved.update(status="unsupported_format", message=sanitize_exception_message(exc))
                return saved
            if decoded["workspace_id"] != workspace_id:
                raise ValueError("Saved workspace UUID does not match the requested workspace.")
            after = docs._document(docs._inventory(reader, running_bundle=True), workspace_id)
            current, current_identity = _read_file(path)
            state_keys = ("workspace_id", "path", "modified", "edit_mode", "show_mode", "active_cue_ids")
            if any(before.get(key) != after.get(key) for key in state_keys) or file_identity != current_identity or source != current:
                saved.update(status="changed_during_read", message="Document or saved file changed during the read; saved video data was discarded.")
                return saved
            saved.update(decoded, status="ready" if decoded["coverage"] == "complete" else "partial",
                         sha256=hashlib.sha256(source).hexdigest(),
                         freshness="possibly_stale" if before["modified"] else "last_saved")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        saved["message"] = sanitize_exception_message(exc)
        if "changed during" in str(exc):
            saved["status"] = "changed_during_read"
    return saved


def _comparison(data: dict, saved: dict) -> dict:
    overview = data.get("overview") if isinstance(data.get("overview"), dict) else {}
    result = dict(comparison="not_comparable", comparison_scope=["stage UUID/name/dimensions", "route UUID/name/type", "input UUID"], differences=[])
    if saved.get("status") not in {"ready", "partial"}:
        return result
    pairs = (("stages", "stages", "stage"), ("routes", "routes", "route"), ("input_patches", "inputs", "input"))
    differences = []
    comparable = False
    for live_key, saved_key, label in pairs:
        live = overview.get(live_key)
        stored = saved.get(saved_key)
        if not isinstance(live, list) or not isinstance(stored, list):
            continue
        comparable = True
        live_by_id = {str(row.get("uniqueID")): row for row in live if isinstance(row, dict) and row.get("uniqueID")}
        saved_by_id = {str(row.get("id")): row for row in stored if isinstance(row, dict) and row.get("id")}
        if set(live_by_id) != set(saved_by_id):
            differences.append(f"{label.capitalize()} identities differ between OSC and the saved archive.")
        for uid in live_by_id.keys() & saved_by_id.keys():
            current, archived = live_by_id[uid], saved_by_id[uid]
            if label != "input" and current.get("name") != archived.get("name"):
                differences.append(f"{label.capitalize()} {uid} has a different name.")
            if label == "stage":
                size = current.get("size") or {}
                if isinstance(size, dict) and any(size.get(k) != archived.get(k) for k in ("width", "height") if k in size):
                    differences.append(f"Stage {uid} has different dimensions.")
            elif label == "route" and current.get("destination_type") and current.get("destination_type") != archived.get("destination_type"):
                differences.append(f"Route {uid} has a different destination type.")
    if comparable:
        result.update(comparison="differs" if differences else "matches_observable_fields", differences=differences)
    return result


def _size(result: dict) -> int:
    from .models import WorkspaceVideoSettingsResult
    return len(WorkspaceVideoSettingsResult.model_validate(result).model_dump_json().encode())


def _page(data: dict, saved: dict, section: str, offset: int, limit: int) -> dict:
    overview = data.get("overview")
    if not isinstance(overview, dict):
        overview = {}
        data["overview"] = overview
    count_map = {}
    for key, live_key in _SECTIONS.items():
        values = overview.get(live_key)
        live_available = isinstance(values, list)
        if not live_available:
            values = []
        archived = saved.get(key, [])
        selected = section in {"all", key}
        if live_available:
            overview[live_key] = values[offset:offset + limit] if selected else []
        saved[key] = archived[offset:offset + limit] if selected else []
        live_total, saved_total = len(values) if live_available else None, len(archived)
        count_map[key] = dict(live_total=live_total, saved_total=saved_total,
                              live_returned=len(overview[live_key]) if live_available else None,
                              saved_returned=len(saved[key]),
                              truncated=selected and offset + limit < max(live_total or 0, saved_total))
    destinations = saved.get("destinations", [])
    selected = section in {"all", "destinations"}
    saved["destinations"] = destinations[offset:offset + limit] if selected else []
    count_map["destinations"] = dict(live_total=None, saved_total=len(destinations), live_returned=None,
        saved_returned=len(saved["destinations"]), truncated=selected and offset + limit < len(destinations))
    return count_map


def enrich_video_settings(reader, workspace_id: str, result: dict, section: str = "all",
                          offset: int = 0, limit: int = 1000) -> dict:
    """Add saved archive details and bounded pages while preserving current OSC data."""
    allowed = {"all", "stages", "routes", "inputs", "destinations"}
    if section not in allowed or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("section must be all/stages/routes/inputs/destinations, offset >= 0 and limit 1–1000.")
    result = deepcopy(result)
    live_ok = result.get("ok") is True
    try:
        workspace_id = docs._uuid(result.get("workspace_id", workspace_id))
    except (ValueError, TypeError, AttributeError):
        workspace_id = str(workspace_id).upper()
    data = result.get("data") or {}
    result["data"] = data
    saved = _saved(reader, workspace_id)
    saved["preparation"] = dict(status="needs_save" if saved.get("document_modified") else "ready" if saved.get("status") == "ready" else "unavailable",
        save_requires_preview_and_confirmation=True)
    data["saved_video"] = saved
    comparison = _comparison(data, saved)
    if not live_ok:
        comparison.update(comparison="not_comparable", differences=[])
    data["source_status"] = dict(live_osc=result.get("status", "error"), saved_archive=saved["status"], **comparison)
    if saved["status"] in {"ready", "partial"}:
        result["ok"] = True
    if saved["status"] != "ready" or not live_ok or result.get("partial"):
        result.update(partial=True, status="partial" if result.get("ok") else "error")
    if saved.get("message"):
        result.setdefault("warnings", []).append(saved["message"])

    base = deepcopy(result)
    effective = limit
    omitted = []
    while True:
        page = deepcopy(base)
        current_saved = page["data"]["saved_video"]
        counts = _page(page["data"], current_saved, section, offset, effective)
        truncated = any(row["truncated"] for row in counts.values())
        next_requests = [dict(workspace_id=workspace_id, section=key, offset=offset + effective, limit=effective)
                         for key, row in counts.items() if row["truncated"] and effective]
        if effective == 0 and section == "all":
            # Split an oversized combined response into exact one-section calls at the same offset.
            next_requests = [dict(workspace_id=workspace_id, section=key, offset=offset, limit=1)
                             for key, row in counts.items()
                             if row["truncated"] and row["saved_total"] > offset]
        elif effective == 0:
            for key, row in counts.items():
                if section in {"all", key} and row["truncated"]:
                    next_requests.append(dict(workspace_id=workspace_id, section=key, offset=offset + 1, limit=1))
            for key in ("stages", "routes", "inputs", "destinations"):
                records = base["data"]["saved_video"].get(key, [])
                if section in {"all", key} and offset < len(records):
                    record = records[offset]
                    if key == "stages" and record.get("id"):
                        header = {field: value for field, value in record.items() if field != "regions"}
                        omitted.append(dict(section=key, id=record["id"], stage_header=header,
                            recover_with=dict(tool="qlab_get_video_stage", arguments=dict(workspace_id=workspace_id, stage_id=record["id"], profile="technical")),
                            reason="complete nested stage exceeds the response byte budget"))
                    else:
                        omitted.append(dict(section=key, id=record.get("id"), reason="record exceeds the response byte budget and has no detail reader"))
                    if key == "stages" and omitted:
                        omitted[-1]["recovery_limit"] = "The stage detail tool reads a fresh saved snapshot; compare sha256 before continuing its geometry pages."
        pagination = dict(section=section, offset=offset, limit=limit, effective_limit=effective,
                          byte_limit=MAX_RESPONSE_BYTES, truncated=truncated or bool(omitted) or bool(next_requests),
                          byte_truncated=effective < limit, sections=counts,
                          next_requests=next_requests, omitted_records=omitted)
        page["data"]["pagination"] = pagination
        if truncated or effective < limit or omitted:
            page.update(partial=True, status="partial" if page.get("ok") else "error")
        if _size(page) <= MAX_RESPONSE_BYTES:
            return page
        if effective > 1:
            effective = max(1, effective // 2)
        elif effective:
            effective = 0
        else:
            return dict(ok=False, status="error", partial=True, workspace_id=workspace_id,
                        domain="video", coverage="partial", profile="safe", view="overview",
                        warnings=["Video settings metadata exceeds the response byte budget."],
                        errors={"video": "response_too_large"}, data={"saved_video": dict(status=saved["status"],
                        source="saved_archive", coverage="partial", freshness="unavailable",
                        message="Response too large; no complete inventory returned."),
                        "pagination": dict(section=section, offset=offset, limit=limit, effective_limit=0,
                        byte_limit=MAX_RESPONSE_BYTES, truncated=True, byte_truncated=True,
                        sections=counts, next_requests=[], omitted_records=[])})



def _stage_inspection(reader, workspace_id, stage_id, detail, saved):
    """Explain provenance and bound supplemental OSC reads to sixteen regions/routes."""
    stage_id = str(UUID(stage_id)).upper()
    errors = {}
    visibility = []
    geometry = []
    routes = {}
    regions = detail.get("regions") or []
    read = getattr(reader, "_read_workspace_setting", None)
    deadline = time.monotonic() + 8
    def bounded_read(command):
        if read is None or time.monotonic() >= deadline:
            errors[command] = "Supplemental visibility read unavailable or time budget exhausted."
            return None
        return read(workspace_id, command, errors, command)
    for region in regions[:16]:
        region_id = region.get("uniqueID")
        try:
            region_id = str(UUID(region_id)).upper()
        except (ValueError, TypeError, AttributeError):
            errors["region_identity"] = "A current region has no valid UUID."
            continue
        bounds = region.get("boundsOnStage") or {}
        size = detail.get("size") or {}
        parts = [bounds.get(k) for k in ("x", "y", "width", "height")]
        dimensions = [size.get(k) for k in ("width", "height")]
        coordinates = None
        if all(type(v) in (int, float) and math.isfinite(v) for v in parts + dimensions):
            x, y, w, h = parts
            sw, sh = dimensions
            coordinates = dict(origin="stage_center", units="pixels",
                lower_left=[x - sw / 2, y - sh / 2], upper_right=[x + w - sw / 2, y + h - sh / 2], size=[w, h])
        geometry.append(dict(region_id=region_id, source="live_osc", ui_coordinates=coordinates,
            warp_type=region.get("warpType"),
            warp_type_name=_warp_name(region.get("warpType"))))
        values = dict(region_id=region_id, source="live_osc")
        for field in ("enableGrid", "enableGuide"):
            command = f"video/stageID/{stage_id}/regionID/{region_id}/{field}"
            value = bounded_read(command)
            values[field] = value if isinstance(value, bool) else None
        visibility.append(values)
        route = region.get("route") or {}
        route_id = route.get("uniqueID")
        if route_id:
            try:
                route_id = str(UUID(route_id)).upper()
            except (ValueError, TypeError, AttributeError):
                errors["route_identity"] = "A current route has no valid UUID."
                continue
            if route_id in routes:
                continue
            command = f"video/routeID/{route_id}/enableGuides"
            value = bounded_read(command)
            routes[route_id] = dict(route_id=route_id, source="live_osc",
                enableGuides=value if isinstance(value, bool) else None,
                detail_request=dict(tool="qlab_get_video_output_route",
                    arguments=dict(workspace_id=workspace_id, route_id=route_id)))
    complete = (detail.get("regions") is not None and len(regions) <= 16
                and len(visibility) == len(regions) and not errors
                and all(isinstance(v.get(k), bool) for v in visibility for k in ("enableGrid", "enableGuide"))
                and all(isinstance(v.get("enableGuides"), bool) for v in routes.values()))
    pending_ids = [v["region_id"] for v in visibility
                   if any(v.get(k) is None for k in ("enableGrid", "enableGuide"))]
    pending_ids.extend(r["uniqueID"] for r in regions[16:] if r.get("uniqueID"))
    return dict(atomic_snapshot=False,
        sources=dict(current=dict(source="live_osc", fields=["identity", "size", "region_summary", "visibility"]),
            saved=dict(source="saved_archive", sha256=saved.get("sha256"),
                freshness=saved.get("freshness"), document_modified=saved.get("document_modified"),
                fields=["layer", "mask", "keep_rendering", "grid_options", "geometry"])),
        geometry=geometry,
        visibility=dict(status="complete" if complete else "partial", region_limit=16,
            regions=visibility, routes=list(routes.values()), errors=errors,
            next_requests=[dict(tool="qlab_get_video_region", arguments=dict(
                workspace_id=workspace_id, stage_id=stage_id, region_id=region_id))
                for region_id in pending_ids]),
        coverage=dict(saved_status=saved.get("status"), saved_coverage=saved.get("coverage"),
            unknown_fields=saved.get("diagnostics", []),
            geometry_requires_all_pages=True,
            ui_equivalent=False,
            unavailable=["rendered_pixels", "monitor_image", "mask_image_contents", "complete_live_device_inventory"],
            unverified=["functional_center_for_complex_warps"],
            ui_only=["selection", "canvas_zoom", "resize_dialog_choices", "move_or_draw_interaction_mode", "layout_aspect_lock_state"],
            actions=dict(
                resize=["new_pixel_dimensions", "scale", "crop_pad", "preserve_stage_aspect_ratio", "preserve_region_aspect_ratios"],
                regions=["new_region_with_output", "draw_region_without_output", "move_region", "delete_region"],
                warping=["size_on_stage", "size_of_route", "link_identical_control_points", "unlink_control_points"],
                grids=["show_all_grids", "hide_all_grids", "export_grid_image"]),
            actions_are_saved_properties=False,
            reader_executes_actions=False),
        preparation=dict(status="needs_save" if saved.get("document_modified") else
            "ready" if saved.get("status") == "ready" else "saved_source_unavailable",
            save_request=dict(tool="qlab_save_workspace", arguments=dict(workspace_id=workspace_id, dry_run=True)),
            save_includes_all_pending_changes=True))

def enrich_video_detail(reader, workspace_id: str, result: dict, object_id: str,
                        kind: str, offset: int = 0, limit: int = 1000,
                        expected_sha256: str | None = None) -> dict:
    """Read one saved object; page stage geometry as reconstructable JSON paths."""
    from .models import VideoStageResult, VideoOutputRouteResult
    result = deepcopy(result)
    data = result.setdefault("data", None) or {}
    result["data"] = data
    workspace_id = str(result.get("workspace_id", workspace_id))
    try:
        resolved_id = docs._uuid(workspace_id)
    except (ValueError, TypeError, AttributeError):
        result.setdefault("warnings", []).append("Saved detail unavailable: exact resolved workspace UUID required.")
        result["data"] = result.get("data") or None
        return result
    saved = _saved(reader, resolved_id)
    if expected_sha256 is not None and saved.get("sha256") != expected_sha256:
        for section in ("stages", "routes", "inputs", "destinations"):
            saved[section] = []
        saved.update(status="changed_between_pages", coverage="partial",
                     message="Saved snapshot changed; restart the stage read at offset zero.")
    key = "stages" if kind == "stage" else "routes"
    record = next((item for item in saved.get(key, [])
                   if str(item.get("id", "")).casefold() == object_id.casefold()), None)
    if kind == 'route':
        data['inspection'] = _route_inspection(data, record, saved.get('stages', []))
        data['inspection']['saved'].update(sha256=saved.get('sha256'),
            document_modified=saved.get('document_modified'), freshness=saved.get('freshness'),
            references_complete=bool(record) and saved.get('coverage') == 'complete'
                and not data['inspection']['saved'].get('references_truncated'))
        if data['inspection']['saved'].get('references_truncated'):
            result.update(partial=True, status='partial' if result.get('ok') else 'error')
            data['inspection']['saved']['next_requests'] = [dict(tool='qlab_get_workspace_video_settings',
                arguments=dict(workspace_id=workspace_id, section='stages', offset=0, limit=1000))]
    route_ids = set()
    pending = list(record.get("regions", [])) if kind == "stage" and record else []
    while pending:
        region = pending.pop()
        if region.get("route_id"):
            route_ids.add(region["route_id"])
        pending.extend(region.get("mesh_subregions", []))
    associated_routes = [route for route in saved.get("routes", []) if route.get("id") in route_ids]
    saved = deepcopy(saved)
    for section in ("stages", "routes", "inputs", "destinations"):
        saved[section] = []
    if kind == "stage":
        saved["routes"] = deepcopy(associated_routes)
    saved["preparation"] = dict(status="needs_save" if saved.get("document_modified") else "ready" if saved.get("status") == "ready" else "unavailable",
        save_requires_preview_and_confirmation=True)
    data["saved_video"] = saved
    if record is not None:
        saved[key] = [deepcopy(record)]
        if not result.get("ok"):
            result.update(ok=True, partial=True, status="partial", error_code=None,
                          message="Current OSC detail unavailable; returning saved configuration only.")
    elif saved["status"] in {"ready", "partial"}:
        saved.update(status="object_not_in_saved_archive", coverage="partial",
                     message="The exact object is absent from the saved snapshot; current OSC remains separate.")
    if saved.get("document_modified"):
        result.update(partial=True, status="partial" if result.get("ok") else "error")
        result.setdefault("warnings", []).append(
            "Unsaved changes: saved geometry may be outdated. Explicitly save all workspace changes "
            "using qlab_save_workspace preview and confirmation, then read again before planning file edits.")
    if saved["status"] != "ready":
        result.update(partial=True, status="partial" if result.get("ok") else "error")
    if kind == "stage":
        data["inspection"] = _stage_inspection(reader, workspace_id, object_id,
            data.get("detail") or {}, saved)
        if data["inspection"]["visibility"]["status"] != "complete" or saved.get("document_modified"):
            result.update(partial=True, status="partial" if result.get("ok") else "error")
    entries = []
    if kind == "stage" and record is not None:
        def visit(value, path):
            if isinstance(value, dict) and value:
                for name, child in value.items():
                    visit(child, path + [name])
            elif isinstance(value, list) and value:
                for index, child in enumerate(value):
                    visit(child, path + [index])
            else:
                entries.append(dict(path=path, value=value))
        visit(record.get("regions", []), ["regions"])
        saved[key][0].pop("regions", None)
    model = VideoStageResult if kind == "stage" else VideoOutputRouteResult
    effective = limit
    while True:
        if kind == "stage":
            if record is not None:
                saved[key][0]["geometry_entries"] = entries[offset:offset + effective]
            more = offset + effective < len(entries)
            data["pagination"] = dict(section="stage_geometry", offset=offset, limit=limit,
                effective_limit=effective, total=len(entries), truncated=more,
                byte_limit=MAX_RESPONSE_BYTES, byte_truncated=effective < limit,
                next_requests=[dict(workspace_id=workspace_id, stage_id=object_id,
                    profile=result.get("profile", "safe"), offset=offset + effective,
                    limit=effective, expected_sha256=saved.get("sha256"))] if more and effective else [])
            if more or effective < limit:
                result.update(partial=True, status="partial" if result.get("ok") else "error")
        if len(model.model_validate(result).model_dump_json().encode()) <= MAX_RESPONSE_BYTES:
            return result
        if data.get("technical_payload") is not None:
            data["technical_payload"] = None
            result.setdefault("warnings", []).append("Live technical payload omitted: response byte budget.")
            result.update(partial=True, status="partial" if result.get("ok") else "error")
        elif kind == "stage" and isinstance(data.get("detail"), dict) and data["detail"].get("regions"):
            data["detail"]["regions"] = None
            result.setdefault("warnings", []).append("Live regions omitted: response byte budget; saved geometry is a separate snapshot.")
            result.update(partial=True, status="partial" if result.get("ok") else "error")
        elif kind == "stage" and effective > 1:
            effective = max(1, effective // 2)
        else:
            result.update(ok=False, status="error", partial=True, error_code="response_too_large",
                          message="One detail record exceeds the response byte budget.")
            result["data"] = None
            return result


def _scaling_mode(value):
    """QLab 5.5.10 route-editor native tags; retain unknown codes."""
    return dict(code=value, name={0: 'Center', 1: 'Stretch', 2: 'Fill', 3: 'Fit'}.get(value)
                if type(value) is int else None)


def _output_selection(layout, raster):
    width, height, index = (layout or {}).get('wide'), (layout or {}).get('high'), (layout or {}).get('index')
    result = dict(mode='unknown', layout=layout, origin='not_validated')
    if (any(type(x) is not int for x in (width, height, index)) or min(width, height) < 1
            or not 0 <= index < width * height):
        return result
    col, row = index % width, index // width
    result.update(mode='full' if (width, height) == (1, 1) else 'partial', column=col, row=row,
                  display_number=index + 1, normalized_scale=[1 / width, 1 / height],
                  clip_center=[(2*col+1-width)/width, (height-2*row-1)/height])
    if isinstance(raster, list) and len(raster) == 2 and all(type(x) in (int, float) and math.isfinite(x) and x > 0 for x in raster):
        result['tile_size'] = [raster[0]/width, raster[1]/height]
    return result


def _route_inspection(data, route, stages):
    detail = data.get('detail') or {}
    current = dict(source='live_osc', scaling_mode=_scaling_mode(detail.get('scalingMode')),
                   assigned_device=detail.get('device'), connected=detail.get('connected'),
                   assignment_is_availability=False)
    technical = data.get('technical_payload') or {}
    if isinstance(technical, dict) and isinstance(technical.get('partialScreenLayout'), dict):
        layout = technical['partialScreenLayout']
        raster = (technical.get('destinationInfo') or {}).get('videoOutputRasterSize')
        dimensions = [float(x) for x in _NUMBER.findall(raster)] if isinstance(raster, str) else None
        current['output_selection'] = _output_selection(dict(wide=layout.get('screensWide'),
            high=layout.get('screensHigh'), index=technical.get('partialScreenIndex')), dimensions)
    saved = dict(source='saved_archive', references=[], reference_count=0,
                 references_truncated=False, references_complete=False)
    if route:
        saved.update(scaling_mode=_scaling_mode(route.get('scaling_mode')),
            output_selection=_output_selection(route.get('layout'),
                (route.get('destination_raster') or {}).get('components')),
            assigned_destination=route.get('destination_info'), references_complete=True)
        def visit(regions, stage, path):
            for i, region in enumerate(regions):
                here = path + [i]
                if region.get('route_id') == route.get('id'):
                    saved['reference_count'] += 1
                    if len(saved['references']) < 1000:
                        saved['references'].append(dict(stage_id=stage.get('id'), stage_name=stage.get('name'),
                            region_id=region.get('id'), path=here, source='saved_archive'))
                visit(region.get('mesh_subregions', []), stage, here + ['mesh_subregions'])
        for stage in stages:
            visit(stage.get('regions', []), stage, ['regions'])
        saved['references_truncated'] = saved['reference_count'] > len(saved['references'])
        saved['references_complete'] = not saved['references_truncated']
    return dict(atomic_snapshot=False, current=current, saved=saved,
                rendered_output_verified=False)


def _native_metadata(kind):
    """Run only fixed metadata getters; timeout/failure must not trigger fallback capture."""
    import json
    import sys
    try:
        response = subprocess.run([sys.executable, '-m', 'qlab_mcp.video_native', kind],
            capture_output=True, text=True, timeout=10, check=False)
        if response.returncode or len(response.stdout.encode()) > MAX_RESPONSE_BYTES:
            raise ValueError('Native video metadata process failed or exceeded its byte budget.')
        def invalid_constant(value):
            raise ValueError('Non-finite native metadata.')
        value = json.loads(response.stdout, parse_constant=invalid_constant)
        if (not isinstance(value, dict) or not isinstance(value.get('devices'), list)
                or not isinstance(value.get('formats'), list)
                or any(not isinstance(row, dict) for key in ('devices', 'formats') for row in value[key])):
            raise ValueError('Invalid native video metadata shape.')
        return value
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return dict(status='unavailable', devices=[], formats=[], message=sanitize_exception_message(exc))


def _device_ref(scope, identity):
    return scope + ':' + hashlib.sha256(str(identity).encode()).hexdigest()


def _pixel_format(value):
    if type(value) is int and 0 <= value <= 0xffffffff:
        label = value.to_bytes(4, 'big')
        if all(32 <= x <= 126 for x in label):
            return label.decode('ascii')
    return None


def enrich_video_inventory(reader, workspace_id, result, kind, ref=None, offset=0, limit=1000):
    """Join by identity only; preserve separate live, saved and local observations."""
    from .models import VideoInventoryResult
    if kind not in {'devices', 'inputs'} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Video inventory requires devices/inputs, offset >= 0 and limit 1–1000.')
    result = deepcopy(result)
    workspace_id = docs._uuid(result.get('workspace_id') or workspace_id)
    overview = (result.get('data') or {}).get('overview') or {}
    technical = (result.get('data') or {}).get('technical_payload') or {}
    if not overview and isinstance(technical, dict) and technical:
        from .settings.summarizers import _collection_items, _summarize_video_route, _summarize_video_input_patch
        overview = dict(routes=[_summarize_video_route(r) for r in _collection_items(technical.get('routes'))],
            input_patches=[_summarize_video_input_patch(p, i) for i, p in enumerate(
                _collection_items(technical.get('input_patches')), start=1)])
    saved = _saved(reader, workspace_id)
    usable = saved.get('status') in {'ready', 'partial'}
    native = dict(status='workspace_not_verified', devices=[], formats=[])
    try:
        docs._local(reader)
    except ValueError:
        native['status'] = 'remote_qlab'
    else:
        if result.get('ok') or usable:
            native = _native_metadata(kind)
    if usable:
        after = _saved(reader, workspace_id)
        if (after.get('status') not in {'ready', 'partial'} or any(
                saved.get(k) != after.get(k) for k in ('workspace_id', 'sha256', 'document_modified', 'freshness'))):
            saved.update(status='changed_during_read', coverage='partial',
                         message='Document or saved file changed during metadata inspection; saved enrichment discarded.')
            for key in ('stages', 'routes', 'inputs', 'destinations'):
                saved[key] = []
            usable = False
    items, sources, formats = [], [], []
    native_source = 'macos_coregraphics' if kind == 'devices' else 'macos_avfoundation'
    native_rows = native.get('devices', []) if native.get('status') == 'ready' else []
    for device in native_rows:
        identity = device.get('screen_id') if kind == 'devices' else device.get('id')
        if identity is None:
            continue
        row = dict(device, ref=_device_ref(native_source, identity), source=native_source,
                   observed_in_qlab=False, route_ids=[], route_reference_source='saved_archive')
        if kind == 'devices':
            # A saved screen ID alone can be recycled; also require the hardware tuple.
            for route in saved.get('routes', []) if usable else []:
                info = route.get('destination_info') or {}
                if (info.get('screenID') == identity and all(device.get(a) is not None
                        and device.get(a) == info.get(b) for a, b in
                        [('vendor', 'screenVendorNumber'), ('model', 'screenModelNumber'), ('serial', 'screenSerialNumber')])):
                    row['route_ids'].append(route['id'])
            items.append(row)
        else:
            sources.append(row)
    source_refs = {s['id']: s['ref'] for s in sources if s.get('id')}
    if kind == 'devices':
        for route in overview.get('routes') or []:
            uid = route.get('uniqueID')
            if uid:
                items.append(dict(ref='qlab-route:' + uid, source='live_osc', type=route.get('destination_type'),
                    name=(route.get('device') or {}).get('name'), connected=route.get('connected'),
                    route_ids=[uid], route_reference_source='live_osc',
                    identity_scope='destination_observed_through_route_not_hardware_identity',
                    parameters=route.get('device')))
        for device in saved.get('destinations', []) if usable else []:
            identity = device.get('id')
            if not identity:
                continue
            parameters = deepcopy(device.get('fields') or {})
            parameters['pixel_format_name'] = _pixel_format(parameters.get('pixelFormat'))
            items.append(dict(ref='saved-virtual:' + identity, id=identity, source='saved_archive',
                name=device.get('name'), type=device.get('destination_type'), parameters=parameters,
                route_ids=[], identity_scope='workspace_configured_virtual_destination',
                candidate_route_ids=[r['id'] for r in saved.get('routes', []) if identity in r.get('destination_candidates', [])],
                candidate_match='type_name_only_not_identity_verified'))
    else:
        live_rows = {str(x['uniqueID']).upper(): x for x in overview.get('input_patches') or [] if x.get('uniqueID')}
        saved_rows = {str(x['id']).upper(): x for x in saved.get('inputs', []) if x.get('id')} if usable else {}
        saved_positions = {uid: i + 1 for i, uid in enumerate(saved_rows)}
        ordered_ids = list(live_rows) + [uid for uid in saved_rows if uid not in live_rows]
        for uid in ordered_ids:
            current, stored = live_rows.get(uid), saved_rows.get(uid)
            descriptor = (stored or {}).get('descriptor')
            config = descriptor.get('config') if isinstance(descriptor, dict) else None
            available = source_refs.get(descriptor.get('uniqueID')) if descriptor and descriptor.get('type') == 'AVCaptureDevice' else None
            items.append(dict(ref=uid, id=uid, name=(current or stored or {}).get('name'),
                source='live_osc_and_saved_archive' if current and stored else 'live_osc' if current else 'saved_archive',
                live=current, saved=stored, available_source_ref=available,
                position=dict(live_osc=(current or {}).get('number'), saved_archive=saved_positions.get(uid)),
                source_match_basis='saved_descriptor_uniqueID' if available else None,
                configured_mode=dict(source='saved_archive', status='unavailable' if stored is None else
                    'unassigned' if descriptor is None else 'automatic' if config == {} and descriptor.get('type') == 'AVCaptureDevice'
                    else 'not_applicable' if descriptor.get('type') in {'NDI', 'Syphon'} else 'explicit' if config else 'unknown',
                    configuration=config), effective_capture_format=None))
        for fmt in native.get('formats', []) if native.get('status') == 'ready' else []:
            formats.append(dict(fmt, source='macos_avfoundation', source_ref=source_refs.get(fmt.get('source_id')),
                                pixel_format_name=_pixel_format(fmt.get('pixel_format'))))
    if ref is not None:
        items = [item for item in items if item['ref'].casefold() == str(ref).casefold()]
        if kind == 'inputs':
            matched = {x['available_source_ref'] for x in items if x.get('available_source_ref')}
            sources = [s for s in sources if s['ref'] in matched]
            formats = [f for f in formats if f.get('source_ref') in matched]
    saved_meta = {k: v for k, v in saved.items() if k not in {'stages', 'routes', 'inputs', 'destinations'}}
    osc_observed = any(overview.get(key) is not None for key in ('routes', 'input_patches', 'stages'))
    data = dict(items=[], available_sources=[], available_formats=[], saved_video=saved_meta,
        local_metadata={k: v for k, v in native.items() if k not in {'devices', 'formats'}},
        coverage=dict(complete_qlab_device_registry=False, atomic_snapshot=False, passive=True,
            source_status=dict(live_osc=('partial' if result.get('errors') else 'available') if osc_observed else 'unavailable', saved_archive=saved.get('status'),
                               local_metadata=native.get('status')),
            unavailable=['unobserved_qlab_process_registry', 'network_source_discovery',
                         'Blackmagic_backend_enumeration', 'effective_capture_format', 'rendered_or_physical_output']))
    result.update(data=data, view='output_devices' if kind == 'devices' else 'input_patches', ref=ref)
    # Local hardware alone cannot prove that the requested workspace exists.
    result['ok'] = bool(osc_observed or usable)
    if result['ok']:
        result['error_code'] = None
    if ref is not None and not items:
        result.update(ok=False, error_code='reference_not_observed',
                      message='Reference not observed in the available sources; absence is not proved by partial coverage.')
    if saved.get('document_modified'):
        result.setdefault('warnings', []).append('Unsaved changes: saved configuration and references may be stale; no save was performed.')
    all_sections = dict(items=items, available_sources=sources, available_formats=formats)
    import json
    data['snapshot_id'] = hashlib.sha256(json.dumps(dict(sections=all_sections,
        saved_sha256=saved.get('sha256'), document_modified=saved.get('document_modified'),
        source_status=data['coverage']['source_status']),
        sort_keys=True, allow_nan=False).encode()).hexdigest()
    counts = {k: len(v) for k, v in all_sections.items()}
    effective = limit
    while True:
        for key, rows in all_sections.items():
            data[key] = rows[offset:offset + effective]
        more = any(offset + effective < n for n in counts.values())
        data['pagination'] = dict(section=result['view'], offset=offset, limit=limit, effective_limit=effective,
            counts=counts, truncated=more or bool(native.get('truncated')), byte_limit=MAX_RESPONSE_BYTES,
            byte_truncated=effective < limit, next_requests=[dict(
                tool='qlab_get_video_output_devices' if kind == 'devices' else 'qlab_get_video_input_patches',
                arguments=dict(workspace_id=workspace_id, profile=result.get('profile', 'safe'),
                    offset=offset + effective, limit=effective, **({'device_ref' if kind == 'devices' else 'patch_id': ref} if ref else {})))] if more else [])
        result.update(partial=True, status='partial' if result['ok'] else 'error')
        payload = VideoInventoryResult.model_validate(result)
        if len(payload.model_dump_json().encode()) <= MAX_RESPONSE_BYTES:
            return result
        if effective > 1:
            effective = max(1, effective // 2)
        else:
            result.update(ok=False, status='error', error_code='response_too_large',
                          message='One inventory record exceeds the response byte budget.', data=None)
            return result
