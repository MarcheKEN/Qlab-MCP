"""Guarded saved-archive Playlist crossfade edits."""
from __future__ import annotations

from functools import partial
import math
import plistlib
from uuid import UUID

from ..audio_effect_integrity import capture_effects, effects_match
from ..light_patch.archive import MAX_BYTES
from ..saved_cue_settings import _archive, _settings


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _snapshot(archive, cue):
    if archive.kind(cue) != "GroupCue" or archive.ref(cue.get("groupMode")) != 6:
        raise ValueError("A Playlist Group cue is required.")
    duration = archive.ref(cue.get("playlistCrossfadeDuration"))
    offset = archive.ref(cue.get("playlistOffsetTime"))
    if not _finite(duration) or duration <= 0 or not _finite(offset) or offset > 0:
        raise ValueError("Playlist crossfade baseline is unknown or unsupported.")
    fades = {}
    for side, key in (("in", "playlistInFade"), ("out", "playlistOutFade")):
        if not isinstance(cue.get(key), plistlib.UID):
            raise ValueError("Playlist fade reference is unsupported.")
        fade = archive.ref(cue.get(key))
        fade_type = archive.ref(fade.get("fadeType")) if isinstance(fade, dict) else None
        if not isinstance(fade, dict) or archive.kind(fade) != "Fade" or type(fade_type) is not int or fade_type != 1:
            raise ValueError("Playlist fade structure is unsupported.")
        value = archive.ref(fade.get("duration"))
        if not _finite(value) or value <= 0:
            raise ValueError("Playlist fade duration is unknown or unsupported.")
        fades[side] = value
    settings, issues = _settings(archive, cue, include_audio_effects=False)
    if issues:
        raise ValueError("Playlist curves are not fully understood: " + ", ".join(issues))
    return {"duration": duration, "offset": offset, "fades": fades,
            "curves": settings["playlist_curves"]}


def plan_playlist_crossfade(source, operations, *, cue_id):
    """Build a copy-on-write plan; callers must independently gate and verify it."""
    cue_id = str(UUID(str(cue_id))).upper()
    outer, meta, carrier, archive, cues, incoming = _archive(source, include_fade=True)
    workspace_id = str(UUID(str(outer.ref(meta["uniqueID"])))).upper()
    settings = outer.mapping(meta["settings"])
    general = outer.mapping(settings["General"])
    if any(outer.ref(general.get(key)) is not False for key in ("doStartOnOpen", "doStartOnClose")):
        raise ValueError("Workspace automatic open/close cues must be known disabled.")
    if cue_id not in cues or incoming[cues[cue_id][1]] != 1:
        raise ValueError("An active uniquely owned Group cue is required.")
    cue = cues[cue_id][0]
    before = _snapshot(archive, cue)
    effects = capture_effects(outer, archive)
    if len(operations) > 1:
        raise ValueError("One Playlist crossfade edit is required.")
    changes = []
    if operations:
        op = operations[0]
        if set(op) != {"cue_id", "duration"} or str(UUID(str(op["cue_id"]))).upper() != cue_id:
            raise ValueError("An exact target and duration are required.")
        requested = op["duration"]
        if not _finite(requested) or requested < 0.05:
            raise ValueError("Playlist duration must be finite and at least 0.05 seconds.")
        if requested != before["duration"]:
            ratio = requested / before["duration"]
            values = [before["offset"] * ratio, *(v * ratio for v in before["fades"].values())]
            if not all(_finite(value) for value in values) or any(value <= 0 for value in values[1:]):
                raise ValueError("Scaled Playlist timing is outside supported limits.")
            copies = {}
            for key in ("playlistInFade", "playlistOutFade"):
                original_ref = cue[key]
                if original_ref.data in copies:
                    cue[key] = copies[original_ref.data]
                    continue
                fade = dict(archive.ref(original_ref))
                old_duration = fade["duration"]
                value = archive.ref(old_duration) * ratio
                fade["duration"] = archive.add(value) if isinstance(old_duration, plistlib.UID) else value
                cue[key] = archive.add(fade)
                copies[original_ref.data] = cue[key]
            for key, value in (("playlistCrossfadeDuration", requested), ("playlistOffsetTime", values[0])):
                cue[key] = archive.add(value) if isinstance(cue[key], plistlib.UID) else value
            changes.append({"cue_id": cue_id, "property": "playlist/crossfade/duration",
                            "before": before["duration"], "after": requested})
    summary = {"cue_id": cue_id, **_snapshot(archive, cue)}
    output = source
    if changes:
        replacement = outer.add({**carrier, "NS.data": archive.dump()})
        root = outer.data["$top"]["root"]
        outer.data["$top"]["root"] = outer.replacing_mapping(root, "cueLists", replacement)
        output = outer.dump()
        if len(output) > MAX_BYTES or not effects_match(output, effects):
            raise ValueError("Existing audio effects could not be preserved.")
    return {"output_bytes": output, "workspace_id": workspace_id, "summary": summary,
            "changes": changes, "affected_cues": [cue_id] if changes else [],
            "warnings": ["Saved Playlist timing only; no cue execution or audio output verified."],
            "effect_snapshot": effects}


def _postcondition(source, plan):
    try:
        _, _, _, archive, cues, incoming = _archive(source, include_fade=True)
        uid = plan["summary"]["cue_id"]
        return (uid in cues and incoming[cues[uid][1]] == 1
                and {"cue_id": uid, **_snapshot(archive, cues[uid][0])} == plan["summary"]
                and effects_match(source, plan["effect_snapshot"]))
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def _context(reader, ws, uid, requested):
    from .control import _read
    from .groups import GROUP_SOURCE_READ_KEYS, _source_error, _value_error, read_group_snapshot

    source = _read(reader, ws, uid, list(GROUP_SOURCE_READ_KEYS))
    error = _source_error(source, {"cue_ref": uid})
    if error:
        raise ValueError(error)
    children, error = read_group_snapshot(reader, ws, uid)
    if error or children is None:
        raise ValueError(error or "Group children are unavailable.")
    key = "playlist/crossfade/duration"
    error = _value_error(key, requested, source.get(key), source, children)
    if error:
        raise ValueError(error)
    return {"source": source, "children": children}


def edit_playlist_crossfade(reader, workspace_id, item, dry_run):
    """Use the existing archive transaction and return the Group editor contract."""
    from .control import _read, resolve_dry_run
    from .groups import GROUP_SOURCE_READ_KEYS, read_group_snapshot
    from .safety import check_write_readiness
    from ..workspace_archive import edit_archive

    ws = str(UUID(str(workspace_id))).upper()
    uid = str(item.cue_id).upper()
    key = "playlist/crossfade/duration"
    requested = item.properties.playlist_crossfade_duration
    dry = resolve_dry_run(reader, dry_run)
    base = None
    try:
        readiness = check_write_readiness(reader, ws)
        if not readiness.get("ok"):
            raise ValueError(readiness.get("message", "Workspace write readiness is blocked."))
        base = _context(reader, ws, uid, requested)
        if not dry and len(item.confirm_gates) != 1:
            raise ValueError("Provide exactly one fresh archive confirmation token.")
        def check_dependencies():
            if _context(reader, ws, uid, requested) != base:
                raise ValueError("Group or ordered children changed since planning.")

        def verify_live(reader, ws, summary):
            current = _read(reader, ws, uid, list(GROUP_SOURCE_READ_KEYS))
            source = base["source"]
            if any(current.get(k) != v for k, v in source.items() if k != key):
                raise ValueError("Native Group identity or state changed unexpectedly.")
            value = current.get(key)
            if not _finite(value) or not math.isclose(value, summary["duration"], rel_tol=0, abs_tol=1e-6):
                raise ValueError("Native Playlist duration does not match the saved archive.")
            children, error = read_group_snapshot(reader, ws, uid)
            if error or children != base["children"]:
                raise ValueError(error or "Group children changed unexpectedly.")
            return {"cue_id": uid, "scope": "Native Group duration and ordered children; curves checked in archive."}

        result = edit_archive(reader, ws, [{"cue_id": uid, "duration": requested}], dry,
            item.confirm_gates[0] if item.confirm_gates else None,
            planner=partial(plan_playlist_crossfade, cue_id=uid), token_family="playlistCrossfade",
            dependencies=base, dependency_check=check_dependencies,
            postcondition=_postcondition, live_verifier=verify_live)
    except Exception as exc:
        result = {"ok": False, "status": "blocked", "error": str(exc), "executed_operations": []}

    success = result.get("ok") is True
    archive_status = result.get("status", "blocked")
    status = ("dry_run" if dry else "updated") if success else (
        "verification_inconclusive" if result.get("file_replaced") or result.get("executed_operations") else "preflight_failed")
    planned = []
    if result.get("changes"):
        planned = [{"property": key, "transport": "saved_archive", "args": [requested],
                    "confirm_token": result.get("confirm_token")}]
    error = None if success else {"archive": str(result.get("error") or archive_status)}
    details = {k: result[k] for k in ("status", "path", "recovery_path", "file_replaced",
               "document_reopened", "native_patch_verified", "postcondition_verified",
               "source_sha256", "output_sha256") if k in result}
    result_item = {"cue_ref": uid, "cue_id": uid, "profile": "group_basic", "status": status,
        "properties": {key: requested}, "before": base["source"] if base else None,
        "planned_operations": planned, "executed_operations": result.get("executed_operations", []),
        "errors": error, "debug": {"archive_transaction": details},
        "notices": ["Archive transaction closes and reopens the saved workspace; no cue is executed."]}
    return {"ok": success, "status": status, "workspace_id": ws, "dry_run": dry,
        "requested_count": 1, "planned_count": int(bool(planned)),
        "updated_count": int(success and not dry and bool(result.get("changes"))),
        "failed_count": int(not success), "timeout_confirmed_count": 0, "results": [result_item],
        "errors": None if success else {"batch": "Inspect the archive transaction and its recovery status."},
        "warnings": result.get("warnings", []), "message": archive_status}
