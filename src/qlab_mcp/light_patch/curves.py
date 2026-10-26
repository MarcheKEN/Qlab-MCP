"""Guarded saved-archive edits for QLab Light cue curves."""
from __future__ import annotations

import hashlib
import json
import math
import plistlib
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StrictFloat, StrictInt, StrictStr

from .archive import Archive, MAX_BYTES, Patch
from .models import Input
from .transaction import edit_light_patch

_TYPE_TO_NATIVE = {"custom": 0, "s_curve": 1, "parametric": 2, "linear": 3}
_NATIVE_TO_TYPE = {value: key for key, value in _TYPE_TO_NATIVE.items()}
_SIDES = {"up": "upShape", "down": "downShape"}
_ENTRY_FIELDS = {"$class", "t", "v", "previous", "next"}
_MAX_OPERATIONS = 50
_MAX_POINTS = 4096
_MAX_TOTAL_POINTS = 8192
_MAX_READ_POINTS = _MAX_POINTS


def _finite_number(value: Any) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _readable_curve_side(archive: Archive, shapes: dict, side: str) -> dict:
    """Decode known curve fields without applying the writer's safety restrictions."""
    native_side = _SIDES[side]
    result = dict(status="partial", native_type=None, type=None, parameter=None,
                  points=[], total_points=None, truncated=False, resolution=None,
                  mirror_shape=None, domain=None, unknown_fields=[], issues=[])
    shape_ref = shapes.get(native_side)
    if not isinstance(shape_ref, plistlib.UID):
        result["issues"].append("shape_reference_unavailable")
        return result
    try:
        if archive.kind(shape_ref) != "FadeShape":
            result["issues"].append("unknown_shape_class")
            return result
        shape = archive.ref(shape_ref)
    except (KeyError, TypeError, ValueError, AttributeError):
        result["issues"].append("shape_unreadable")
        return result
    shape_unknown = set(shape) - {"$class", "type", "curveParameter", "shapeEntries"}
    result["unknown_fields"] = sorted(f"shape.{name}" for name in shape_unknown)
    if shape_unknown:
        result["issues"].append("unknown_shape_fields")
    raw_type = archive.ref(shape.get("type"))
    if type(raw_type) in (int, str):
        result["native_type"] = raw_type
    result["type"] = _NATIVE_TO_TYPE.get(raw_type) if type(raw_type) is int else None
    if result["type"] is None:
        result["issues"].append("unknown_curve_type")
    try:
        parameter = archive.ref(shape.get("curveParameter"))
        if _finite_number(parameter):
            result["parameter"] = float(parameter)
        else:
            result["issues"].append("curve_parameter_unavailable")
    except (TypeError, ValueError, OverflowError):
        result["issues"].append("curve_parameter_unavailable")

    entries_ref = shape.get("shapeEntries")
    try:
        if not isinstance(entries_ref, plistlib.UID):
            raise ValueError("shape_entries_unavailable")
        try:
            array_class = archive.kind(entries_ref)
        except (KeyError, TypeError, ValueError, AttributeError):
            array_class = None
        if array_class not in {"NSArray", "NSMutableArray"}:
            result["issues"].append("unknown_shape_entries_array_class")
            if array_class:
                result["unknown_fields"].append(f"shapeEntries.array_class:{array_class}")
        entries_object = archive.ref(entries_ref)
        if not isinstance(entries_object, dict) or "NS.keys" in entries_object or not isinstance(entries_object.get("NS.objects"), list):
            raise ValueError("shape_entries_unreadable")
        entries = entries_object["NS.objects"]
        result["total_points"] = len(entries)
        result["truncated"] = len(entries) > _MAX_READ_POINTS
        for ref in entries[:_MAX_READ_POINTS]:
            if not isinstance(ref, plistlib.UID):
                result["issues"].append("unknown_point_reference")
                continue
            try:
                if archive.kind(ref) != "FadeShapeEntry":
                    result["issues"].append("unknown_point_class")
                    continue
                entry = archive.ref(ref)
                t, v = archive.ref(entry.get("t")), archive.ref(entry.get("v"))
                if not _finite_number(t) or not _finite_number(v):
                    result["issues"].append("invalid_point_values")
                    continue
                point = {"t": float(t), "v": float(v)}
                result["points"].append(point)
                point_unknown = set(entry) - _ENTRY_FIELDS
                if point_unknown:
                    result["issues"].append("unknown_point_fields")
                    result["unknown_fields"].extend(f"shapeEntries[].{name}" for name in point_unknown)
            except (KeyError, TypeError, ValueError, AttributeError):
                result["issues"].append("point_unreadable")
        if result["truncated"]:
            result["issues"].append("point_limit_reached")
    except (KeyError, TypeError, ValueError, AttributeError):
        result["issues"].append("shape_entries_unreadable")

    # These settings belong to the shared FadeShapesFunction and are included on each side
    # so clients can consume either curve independently.
    return result


def _decode_saved_curves(source: bytes, cue_id: str) -> dict:
    outer = Archive(source)
    meta = outer.mapping(outer.root)
    version, build = outer.ref(meta.get("QLabShortVersionString")), outer.ref(meta.get("QLabBuildNumber"))
    workspace_id = str(UUID(outer.ref(meta["uniqueID"]))).upper()
    if (version, build) != ("5.5.10", 5510):
        return dict(status="unsupported_version", workspace_id=workspace_id,
                    version=version if isinstance(version, str) else None,
                    build=build if type(build) is int else None,
                    curves={}, coverage="Only QLab 5.5.10/build 5510 archive curves are decoded.")
    carrier_ref = outer.mapping(outer.root).get("cueLists")
    carrier = outer.ref(carrier_ref)
    if not isinstance(carrier, dict) or not isinstance(carrier.get("NS.data"), bytes):
        raise ValueError("Saved cue-list archive is unavailable.")
    inner = Archive(carrier["NS.data"])
    cues, _ = _reachable_cues(inner)
    found = cues.get(cue_id.upper())
    if found is None:
        return dict(status="cue_not_found", workspace_id=workspace_id, version=version,
                    build=build, curves={}, coverage="No active Light cue with this UUID was found in the saved archive.")
    cue, _ = found
    fade_ref = cue.get("fade")
    if not isinstance(fade_ref, plistlib.UID) or inner.kind(fade_ref) != "Fade":
        raise ValueError("Saved Light cue Fade structure is unavailable.")
    fade = inner.ref(fade_ref)
    shapes_ref = fade.get("shapes")
    if not isinstance(shapes_ref, plistlib.UID) or inner.kind(shapes_ref) != "FadeShapesFunction":
        raise ValueError("Saved Light cue FadeShapesFunction is unavailable.")
    shapes = inner.ref(shapes_ref)
    domain = inner.ref(shapes.get("domain"))
    try:
        domain_class = inner.kind(shapes.get("domain"))
    except (KeyError, TypeError, ValueError, AttributeError):
        domain_class = None
    raw_resolution = inner.ref(shapes.get("resolution"))
    raw_mirror = inner.ref(shapes.get("mirrorShape"))
    shared_domain = {}
    if isinstance(domain, dict):
        for key in ("mode", "absolute"):
            value = inner.ref(domain[key]) if key in domain else None
            if type(value) in (str, bool, int) or (type(value) is float and _finite_number(value)):
                if key in domain:
                    shared_domain[key] = value
    else:
        shared_domain = None
    shared_issues = []
    domain_unknown = (set(domain) - {"$class", "mode", "absolute"}) if isinstance(domain, dict) else set()
    if domain_unknown:
        shared_issues.append("unknown_fade_domain_fields")
    if not _finite_number(raw_resolution):
        shared_issues.append("resolution_unavailable")
    if type(raw_mirror) is not bool:
        shared_issues.append("mirror_state_unavailable")
    elif raw_mirror:
        shared_issues.append("curves_are_mirrored")
    if shared_domain is None or set(shared_domain) != {"mode", "absolute"}:
        shared_issues.append("fade_domain_unavailable")
    elif shared_domain != {"mode": 0, "absolute": False}:
        shared_issues.append("nonstandard_fade_domain")
    if domain_class != "FadeDomain":
        shared_issues.append("unknown_fade_domain_class")
    function_fields = {"$class", "upShape", "downShape", "mirrorShape", "domain", "resolution"}
    function_unknown_fields = sorted(set(shapes) - function_fields)
    if function_unknown_fields:
        shared_issues.append("unknown_fade_shape_function_fields")
    shared_unknown_fields = [*(f"fade_shape_function.{name}" for name in function_unknown_fields),
                             *(f"fade_domain.{name}" for name in domain_unknown)]
    if domain_class and domain_class != "FadeDomain":
        shared_unknown_fields.append(f"fade_domain.class:{domain_class}")
    shared = dict(
        resolution=float(raw_resolution) if _finite_number(raw_resolution) else None,
        mirror_shape=raw_mirror if type(raw_mirror) is bool else None,
        domain=shared_domain,
    )
    curves = {side: _readable_curve_side(inner, shapes, side) for side in _SIDES}
    for curve in curves.values():
        curve.update(shared)
        curve["unknown_fields"] = sorted(set(curve["unknown_fields"]) | set(shared_unknown_fields))
        curve["issues"].extend(shared_issues)
        curve["status"] = "available" if not curve["issues"] else "partial"
    complete = all(curve["status"] == "available" for curve in curves.values())
    return dict(status="ready" if complete else "partial", workspace_id=workspace_id,
                version=version, build=build, curves=curves,
                coverage="Both saved curve shapes are decoded." if complete else
                "Known saved curve fields are returned; inspect per-curve issues for unknown or unreadable fields.")


def read_saved_light_cue_curves(reader: Any, workspace_id: str, cue_id: str) -> dict:
    """Read stable last-saved Light cue curves without saving or changing QLab."""
    from .. import workspace_documents as docs
    from ..sanitizer import sanitize_exception_message
    from .reader import _read_file

    unavailable = dict(status="unavailable", source="saved_archive", freshness="unavailable",
                       document_modified=None, sha256=None, version=None, build=None,
                       curves={}, coverage="Saved Light cue curves could not be read.")
    try:
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader), workspace_id)
            unavailable["document_modified"] = before["modified"]
            if not before["path"]:
                raise ValueError("Workspace has no saved document path.")
            path = Path(before["path"])
            source, identity = _read_file(path)
            decoded = _decode_saved_curves(source, cue_id)
            if decoded["workspace_id"] != workspace_id:
                raise ValueError("Saved workspace UUID does not match the requested workspace.")
            after = docs._document(docs._inventory(reader), workspace_id)
            current, current_identity = _read_file(path)
            stable_keys = ("workspace_id", "path", "modified", "edit_mode", "show_mode", "active_cue_ids")
            if any(before.get(key) != after.get(key) for key in stable_keys) or identity != current_identity or source != current:
                return {**unavailable, "status": "changed_during_read",
                        "coverage": "Document or saved file changed during the read; saved curves were discarded."}
            digest = hashlib.sha256(source).hexdigest()
            return {**decoded, "source": "saved_archive", "sha256": digest,
                    "document_modified": before["modified"],
                    "freshness": "possibly_stale" if before["modified"] else "last_saved"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, plistlib.InvalidFileException) as exc:
        message = sanitize_exception_message(exc)
        status = "changed_during_read" if "changed during" in str(exc) else "unavailable"
        return {**unavailable, "status": status, "message": message,
                "coverage": message}


def _optional_without_null(schema: dict) -> None:
    # Omission preserves saved values; explicit null is rejected by Input.
    for value in schema.get("properties", {}).values():
        choices = value.get("anyOf", [])
        if any(choice == {"type": "null"} for choice in choices):
            choices = [choice for choice in choices if choice != {"type": "null"}]
            value.pop("default", None)
            value["anyOf"] = choices
            if len(choices) == 1:
                value.pop("anyOf")
                value.update(choices[0])


class CurvePoint(Input):
    model_config = ConfigDict(extra="forbid")
    t: Annotated[StrictFloat | StrictInt, Field(ge=0, le=1)]
    v: Annotated[StrictFloat | StrictInt, Field(ge=0, le=1)]


class CurveChanges(Input):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_optional_without_null)
    type: Literal["custom", "s_curve", "parametric", "linear"] | None = None
    parameter: Annotated[StrictFloat | StrictInt, Field(gt=0)] | None = None
    points: Annotated[list[CurvePoint], Field(min_length=2, max_length=4096)] | None = None


class LightCueCurveOperation(Input):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_optional_without_null)
    cue_id: StrictStr
    up: CurveChanges | None = None
    down: CurveChanges | None = None


LightCueCurveOperations = Annotated[list[LightCueCurveOperation], Field(min_length=1, max_length=50)]


def _number(value: Any, field: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number.")
    return float(value)


def _point_list(value: Any, side: str) -> list[dict[str, float]]:
    if not isinstance(value, list) or not 2 <= len(value) <= _MAX_POINTS:
        raise ValueError(f"{side}.points must contain 2..{_MAX_POINTS} points.")
    points = []
    for index, point in enumerate(value):
        if not isinstance(point, dict) or set(point) != {"t", "v"}:
            raise ValueError("Each curve point must contain only t and v.")
        t, v = _number(point["t"], "point.t"), _number(point["v"], "point.v")
        if not 0 <= t <= 1 or not 0 <= v <= 1:
            raise ValueError("Curve point t and v must be between 0 and 1.")
        if points and t <= points[-1]["t"]:
            raise ValueError("Curve point t values must be strictly increasing.")
        points.append({"t": t, "v": v})
    endpoint_values = ((0.0, 0.0), (1.0, 1.0)) if side == "up" else ((0.0, 1.0), (1.0, 0.0))
    if (points[0]["t"], points[0]["v"]) != endpoint_values[0] or \
       (points[-1]["t"], points[-1]["v"]) != endpoint_values[1]:
        raise ValueError(f"{side} curve endpoints must be {endpoint_values[0]} and {endpoint_values[1]}.")
    return points


def _operations(value: Any, *, allow_empty: bool = False) -> list[dict]:
    if not isinstance(value, list) or len(value) > _MAX_OPERATIONS or (not allow_empty and not value):
        raise ValueError(f"operations must contain 1..{_MAX_OPERATIONS} cue edits.")
    try:
        value = json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("operations must contain JSON values without NaN or infinity.") from exc
    result, seen, total_points = [], set(), 0
    for operation in value:
        if not isinstance(operation, dict) or set(operation) - {"cue_id", "up", "down"}:
            raise ValueError("Each operation requires cue_id and optional up/down changes only.")
        try:
            cue_id = str(UUID(operation.get("cue_id"))).upper()
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Each cue_id must be an exact Light cue UUID.") from exc
        if cue_id in seen:
            raise ValueError("Each Light cue UUID may appear only once per batch.")
        seen.add(cue_id)
        normalized = {"cue_id": cue_id}
        for side in _SIDES:
            if side not in operation:
                continue
            edit = operation[side]
            if not isinstance(edit, dict) or not edit or set(edit) - {"type", "parameter", "points"}:
                raise ValueError(f"{side} must specify type, parameter, and/or points.")
            normalized_edit = {}
            if "type" in edit:
                if not isinstance(edit["type"], str) or edit["type"] not in _TYPE_TO_NATIVE:
                    raise ValueError(f"{side}.type must be custom, s_curve, parametric, or linear.")
                normalized_edit["type"] = edit["type"]
            if "parameter" in edit:
                parameter = _number(edit["parameter"], f"{side}.parameter")
                if parameter <= 0:
                    raise ValueError(f"{side}.parameter must be greater than zero.")
                normalized_edit["parameter"] = parameter
            if "points" in edit:
                points = _point_list(edit["points"], side)
                total_points += len(points)
                if total_points > _MAX_TOTAL_POINTS:
                    raise ValueError(f"A batch may contain at most {_MAX_TOTAL_POINTS} replacement points.")
                normalized_edit["points"] = points
            normalized[side] = normalized_edit
        if len(normalized) == 1:
            raise ValueError("Each operation must change the up curve, down curve, or both.")
        result.append(normalized)
    return result


def _reachable_cues(archive: Archive) -> tuple[dict[str, tuple[dict, int]], dict[int, int]]:
    root = archive.data.get("$top", {}).get("root")
    if root is None:
        raise ValueError("Cue-list archive has no root object.")
    pending, visited, incoming, matches = [root], set(), {}, {}
    while pending:
        ref = pending.pop()
        if isinstance(ref, plistlib.UID):
            incoming[ref.data] = incoming.get(ref.data, 0) + 1
            if ref.data in visited:
                continue
            visited.add(ref.data)
            value = archive.ref(ref)
            uid = ref.data
        else:
            value, uid = ref, None
        if not isinstance(value, dict) or "$class" not in value:
            raise ValueError("Unsupported active cue-list containment structure.")
        kind = archive.kind(value)
        if kind in {"NSArray", "NSMutableArray"}:
            pending.extend(archive.array(value))
        elif kind == "GroupCue":
            if "cues" not in value:
                raise ValueError("Active Group cue has no supported child inventory.")
            pending.extend(archive.array(value["cues"]))
        elif kind == "LightCue":
            cue_id = archive.ref(value.get("uniqueID"))
            if isinstance(cue_id, str):
                matches.setdefault(cue_id.upper(), []).append((value, uid))
    if any(count > 1 and archive.kind(archive.objects[uid]) == "GroupCue"
           for uid, count in incoming.items()):
        raise ValueError("Shared or cyclic active Group cue containment is unsupported.")
    cues = {}
    for cue_id, found in matches.items():
        if len(found) != 1 or found[0][1] is None:
            raise ValueError("Reachable Light cue UUIDs must identify one archived object.")
        cues[cue_id] = found[0]
    return cues, incoming


def _read_shape(archive: Archive, shapes: dict, side: str) -> tuple[dict, dict, list[plistlib.UID], list[dict]]:
    shape_ref = shapes.get(side)
    if not isinstance(shape_ref, plistlib.UID) or archive.kind(shape_ref) != "FadeShape":
        raise ValueError(f"{side} is not a supported FadeShape.")
    shape = archive.ref(shape_ref)
    raw_type = archive.ref(shape.get("type"))
    if type(raw_type) is not int or raw_type not in _NATIVE_TO_TYPE:
        raise ValueError("Unknown native Light cue curve type.")
    parameter = _number(archive.ref(shape.get("curveParameter")), "curveParameter")
    if parameter <= 0:
        raise ValueError("Existing curveParameter must be greater than zero.")
    entries_ref = shape.get("shapeEntries")
    if not isinstance(entries_ref, plistlib.UID):
        raise ValueError("Curve shapeEntries must be a keyed archive array.")
    if archive.kind(entries_ref) not in {"NSArray", "NSMutableArray"}:
        raise ValueError("Unsupported curve shapeEntries array class.")
    entries_object = archive.ref(entries_ref)
    if not isinstance(entries_object, dict) or "NS.keys" in entries_object or not isinstance(entries_object.get("NS.objects"), list):
        raise ValueError("Malformed curve shapeEntries array.")
    entries = list(entries_object["NS.objects"])
    if not 2 <= len(entries) <= _MAX_POINTS:
        raise ValueError(f"Existing curve must contain 2..{_MAX_POINTS} points.")
    points = []
    for index, ref in enumerate(entries):
        if not isinstance(ref, plistlib.UID) or archive.kind(ref) != "FadeShapeEntry":
            raise ValueError("Curve contains an unsupported point object.")
        entry = archive.ref(ref)
        t, v = _number(archive.ref(entry.get("t")), "point.t"), _number(archive.ref(entry.get("v")), "point.v")
        expected_previous = entries[index - 1] if index else None
        expected_next = entries[index + 1] if index + 1 < len(entries) else None
        previous, following = entry.get("previous"), entry.get("next")
        if (previous if archive.ref(previous) is not None else None) != expected_previous or \
           (following if archive.ref(following) is not None else None) != expected_next:
            raise ValueError("Curve point links do not match the ordered shapeEntries list.")
        if not 0 <= t <= 1 or not 0 <= v <= 1 or (points and t <= points[-1]["t"]):
            raise ValueError("Existing curve points are outside the supported normalized domain or order.")
        points.append({"t": t, "v": v})
    side_name = "up" if side == "upShape" else "down"
    endpoints = ((0., 0.), (1., 1.)) if side_name == "up" else ((0., 1.), (1., 0.))
    if (points[0]["t"], points[0]["v"]) != endpoints[0] or \
       (points[-1]["t"], points[-1]["v"]) != endpoints[1]:
        raise ValueError("Existing curve endpoints are malformed.")
    return shape_ref, shape, entries, points


def _curve_state(archive: Archive, cue: dict) -> tuple[dict, dict, dict]:
    fade_ref = cue.get("fade")
    if not isinstance(fade_ref, plistlib.UID) or archive.kind(fade_ref) != "Fade":
        raise ValueError("Light cue Fade structure is unsupported.")
    fade = archive.ref(fade_ref)
    shapes_ref = fade.get("shapes")
    if not isinstance(shapes_ref, plistlib.UID) or archive.kind(shapes_ref) != "FadeShapesFunction":
        raise ValueError("Light cue FadeShapesFunction is unsupported.")
    shapes = archive.ref(shapes_ref)
    if archive.ref(shapes.get("mirrorShape")) is not False:
        raise ValueError("Mirrored curves are not supported by this writer.")
    domain_ref = shapes.get("domain")
    if not isinstance(domain_ref, plistlib.UID) or archive.kind(domain_ref) != "FadeDomain":
        raise ValueError("Unknown Light cue curve domain.")
    domain = archive.ref(domain_ref)
    if type(archive.ref(domain.get("mode"))) is not int or archive.ref(domain.get("mode")) != 0 or \
       archive.ref(domain.get("absolute")) is not False:
        raise ValueError("Only the validated relative FadeDomain is supported.")
    resolution = _number(archive.ref(shapes.get("resolution")), "curve resolution")
    if not 0 < resolution <= 1:
        raise ValueError("Curve resolution is outside the supported normalized range.")
    shape_data = {side: _read_shape(archive, shapes, name) for side, name in _SIDES.items()}
    return fade, shapes, shape_data


def _write_points(archive: Archive, shape: dict, old_refs: list[plistlib.UID],
                  points: list[dict[str, float]]) -> plistlib.UID:
    old_entries = [archive.ref(ref) for ref in old_refs]
    if len(points) != len(old_entries) and any(set(entry) - _ENTRY_FIELDS for entry in old_entries):
        raise ValueError("Changing the point count would discard unrecognized point metadata.")
    new_refs = []
    for index, point in enumerate(points):
        if index < len(old_entries):
            entry = dict(old_entries[index])
        else:
            entry = {"$class": old_entries[-1]["$class"]}
        entry.update(t=point["t"], v=point["v"], previous=None, next=None)
        new_refs.append(archive.add(entry))
    for index, ref in enumerate(new_refs):
        entry = archive.ref(ref)
        entry["previous"] = new_refs[index - 1] if index else plistlib.UID(0)
        entry["next"] = new_refs[index + 1] if index + 1 < len(new_refs) else plistlib.UID(0)
    old_array = archive.ref(shape["shapeEntries"])
    return archive.add({**old_array, "NS.objects": new_refs})


def _curve_snapshots(source: bytes, cue_ids: set[str]) -> dict[str, dict]:
    outer = Archive(source)
    carrier_ref = outer.mapping(outer.root).get("cueLists")
    carrier = outer.ref(carrier_ref)
    if not isinstance(carrier, dict) or not isinstance(carrier.get("NS.data"), bytes):
        raise ValueError("Saved cue-list archive is unavailable.")
    inner = Archive(carrier["NS.data"])
    cues, _ = _reachable_cues(inner)
    result = {}
    for cue_id in cue_ids:
        found = cues.get(cue_id)
        if found is None:
            raise ValueError(f"No reachable Light cue has exact UUID {cue_id}.")
        cue, _ = found
        _, _, shapes = _curve_state(inner, cue)
        result[cue_id] = {
            side: {
                "type": _NATIVE_TO_TYPE[inner.ref(state[1]["type"])],
                "parameter": inner.ref(state[1]["curveParameter"]),
                "points": state[3],
            }
            for side, state in shapes.items()
        }
    return result


def plan_light_cue_curves(source: bytes, operations: list[dict]) -> dict:
    """Return a graph-preserving plan; curve checks use saved archive data only."""
    normalized = _operations(operations, allow_empty=True)
    patch = Patch(source)
    if not normalized:
        return dict(output_bytes=source, workspace_id=patch.workspace_id,
                    summary=patch.snapshot(), changes=[], warnings=[], affected_cues=[],
                    curve_summary={}, curve_verification_scope=
                    "Saved cue-list archive; no documented OSC curve readback.")

    outer = Archive(source)
    meta = outer.mapping(outer.root)
    carrier_ref = meta.get("cueLists")
    carrier = outer.ref(carrier_ref)
    if not isinstance(carrier_ref, plistlib.UID) or not isinstance(carrier, dict) or \
       not isinstance(carrier.get("NS.data"), bytes):
        raise ValueError("Saved cue-list archive is unavailable.")
    inner = Archive(carrier["NS.data"])
    cues, incoming = _reachable_cues(inner)
    target_ids = {operation["cue_id"] for operation in normalized}
    changes, snapshots = [], {}
    total_points = 0
    for operation in normalized:
        cue_id = operation["cue_id"]
        found = cues.get(cue_id)
        if found is None:
            raise ValueError(f"No reachable Light cue has exact UUID {cue_id}.")
        cue, cue_uid = found
        if incoming.get(cue_uid) != 1:
            raise ValueError("The target Light cue is shared in the active archive and cannot be isolated safely.")
        fade, shapes, shape_data = _curve_state(inner, cue)
        updated_shapes = dict(shapes)
        side_changes = {}
        for side, native_side in _SIDES.items():
            edit = operation.get(side)
            if edit is None:
                continue
            shape_ref, shape, old_refs, before_points = shape_data[side]
            current_type = _NATIVE_TO_TYPE[inner.ref(shape["type"])]
            new_type = edit.get("type", current_type)
            if "points" in edit and new_type not in {"custom", "linear"}:
                raise ValueError("Control points can be supplied only for Custom or Linear curves.")
            effective_points = edit.get("points", before_points)
            total_points += len(effective_points) if "points" in edit else 0
            if total_points > _MAX_TOTAL_POINTS:
                raise ValueError(f"A batch may contain at most {_MAX_TOTAL_POINTS} replacement points.")
            if "points" in edit and effective_points == before_points:
                effective_points = before_points
            current_parameter = inner.ref(shape["curveParameter"])
            new_parameter = edit.get("parameter", current_parameter)
            side_change = {}
            if new_type != current_type:
                side_change["type"] = {"before": current_type, "after": new_type}
            if new_parameter != current_parameter:
                side_change["parameter"] = {"before": current_parameter, "after": new_parameter}
            if "points" in edit and effective_points != before_points:
                side_change["points"] = {"before_count": len(before_points), "after_count": len(effective_points)}
            if side_change:
                updated = dict(shape)
                updated["type"] = _TYPE_TO_NATIVE[new_type]
                updated["curveParameter"] = float(new_parameter)
                if "points" in edit and effective_points != before_points:
                    updated["shapeEntries"] = _write_points(inner, shape, old_refs, effective_points)
                updated_shapes[native_side] = inner.add(updated)
                side_changes[side] = side_change
        if side_changes:
            new_fade = dict(fade)
            new_fade["shapes"] = inner.add(updated_shapes)
            cue["fade"] = inner.add(new_fade)
            changes.append({"cue_id": cue_id, **side_changes})
    if not changes:
        return dict(output_bytes=source, workspace_id=patch.workspace_id,
                    summary=patch.snapshot(), changes=[], warnings=[], affected_cues=[],
                    curve_summary=_curve_snapshots(source, target_ids), curve_verification_scope=
                    "Saved cue-list archive; no documented OSC curve readback.")

    inner_bytes = inner.dump()
    if len(inner_bytes) > MAX_BYTES:
        raise ValueError("Edited cue-list archive exceeds the 64 MiB file limit.")
    replacement_carrier = outer.add({**carrier, "NS.data": inner_bytes})
    outer.data["$top"]["root"] = outer.replacing_mapping(
        outer.data["$top"]["root"], "cueLists", replacement_carrier)
    output = outer.dump()
    if len(output) > MAX_BYTES:
        raise ValueError("Edited workspace exceeds the 64 MiB file limit.")
    curve_summary = _curve_snapshots(output, target_ids)
    return dict(output_bytes=output, workspace_id=patch.workspace_id,
        summary=patch.snapshot(), changes=changes,
        warnings=["Light cue curves are verified from the saved archive after reopen; documented OSC does not expose curve readback."],
        affected_cues=[], curve_summary=curve_summary,
        curve_verification_scope="Saved cue-list archive; no documented OSC curve readback.")


def _verify_saved_curves(source: bytes, plan: dict) -> bool:
    expected = plan.get("curve_summary")
    if not isinstance(expected, dict) or not expected:
        return False
    return _curve_snapshots(source, set(expected)) == expected


def edit_light_cue_curves(reader: Any, workspace_id: str, operations: list[dict],
                          dry_run: bool = True, confirm_token: str | None = None) -> dict:
    """Plan or apply a guarded 1–50-cue Light curve batch."""
    try:
        normalized = _operations(operations)
        result = edit_light_patch(reader, workspace_id, normalized, dry_run, confirm_token,
            planner=plan_light_cue_curves, token_family="lightCueCurves",
            postcondition=_verify_saved_curves)
        result["tool"] = "qlab_edit_light_cue_curves"
        result["curve_verification_scope"] = "Saved cue-list archive after QLab reopen; OSC does not expose curve values."
        result["saved_curve_verified"] = result.get("postcondition_verified", False)
        return result
    except (ValueError, TypeError, KeyError, OSError) as exc:
        from ..sanitizer import sanitize_exception_message
        return dict(ok=False, status="blocked", error=sanitize_exception_message(exc),
                    planned_operations=[], executed_operations=[])
