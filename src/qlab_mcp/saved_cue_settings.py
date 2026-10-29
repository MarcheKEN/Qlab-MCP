"""Bounded saved Light/Video cue settings and isolated same-path archive edits."""
from __future__ import annotations

from functools import partial
import base64
import hashlib
import json
from pathlib import Path
import plistlib
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictInt, StrictStr, TypeAdapter, model_validator

from .light_patch.archive import Archive, Patch, MAX_BYTES
from .light_patch.curves import _reachable_cues, _readable_curve_side, _write_points
from .cues.list_models import FiniteNumber
from .models import CanonicalWorkspaceUUID
from .sanitizer import sanitize_exception_message

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MODIFIERS = ("shift", "control", "option", "command")
Day = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
Modifier = Literal["shift", "control", "option", "command"]


class HotkeySettings(BaseModel):
    key_code: StrictInt
    character: StrictInt
    modifiers: list[StrictStr]
    enabled: StrictBool | None = None


class WallClockSettings(BaseModel):
    days: list[Day]
    mode: StrictInt | None = None
    enabled: StrictBool | None = None


class InputChannelName(BaseModel):
    native_key: StrictInt | StrictStr
    channel: StrictInt | None
    name: StrictStr


class GangMember(BaseModel):
    row: StrictInt
    column: StrictInt


class ChannelGang(BaseModel):
    name: StrictStr
    members: list[GangMember]


class SavedVideoAudio(BaseModel):
    track: StrictInt | None = None
    input_channel_names: list[InputChannelName] = Field(default_factory=list)
    input_names_scope: Literal["saved_overrides"] = "saved_overrides"
    gangs: list[ChannelGang] = Field(default_factory=list)
    channel_metadata_truncated: StrictBool = False
    integrated_fade: dict[str, JsonValue] = Field(default_factory=dict)


class CueFileSettings(BaseModel):
    hotkey: HotkeySettings | None = None
    wall_clock: WallClockSettings | None = None
    video_audio: SavedVideoAudio | None = None
    video_effects: list[dict[str, JsonValue]] = Field(default_factory=list)


class SavedCueSettings(BaseModel):
    status: Literal["ready", "partial", "unavailable", "changed_during_read", "unsupported_version", "cue_not_found"]
    source: Literal["saved_archive"] = "saved_archive"
    sha256: StrictStr | None = None
    version: StrictStr | None = None
    build: StrictInt | None = None
    document_modified: StrictBool | None = None
    freshness: Literal["last_saved", "possibly_stale", "unavailable"] = "unavailable"
    settings: CueFileSettings = Field(default_factory=CueFileSettings)
    issues: list[StrictStr] = Field(default_factory=list)
    coverage: StrictStr = "Saved configuration only; no playback or physical output is verified."


class SavedCueEditResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    ok: StrictBool
    status: StrictStr
    planned_operations: list[dict[str, JsonValue]] = Field(default_factory=list)
    executed_operations: list[dict[str, JsonValue]] = Field(default_factory=list)
    confirm_token: StrictStr | None = None
    error: StrictStr | None = None


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cue_id: CanonicalWorkspaceUUID


class SetHotkey(Operation):
    action: Literal["set_hotkey"]
    key_code: Annotated[StrictInt, Field(ge=0, le=127)]
    character: Annotated[StrictStr, Field(max_length=1)]
    modifiers: list[Modifier]

    @model_validator(mode="after")
    def valid_descriptor(self):
        if len(set(self.modifiers)) != len(self.modifiers):
            raise ValueError("Hotkey modifiers must be unique.")
        if not self.character and (self.key_code or self.modifiers):
            raise ValueError("Clearing Hotkey uses key_code=0, character='', modifiers=[].")
        if self.character and (ord(self.character) > 65535 or 0xD800 <= ord(self.character) <= 0xDFFF):
            raise ValueError("Hotkey character must be one native UTF-16 code unit.")
        return self


class SetDays(Operation):
    action: Literal["set_wall_clock_days"]
    days: list[Day]

    @model_validator(mode="after")
    def unique_days(self):
        if len(set(self.days)) != len(self.days):
            raise ValueError("Weekdays must be unique.")
        return self


class SetHotkeyEnabled(Operation):
    action: Literal["set_hotkey_enabled"]
    enabled: StrictBool


class EnvelopePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: Annotated[FiniteNumber, Field(ge=0, le=1)]
    v: Annotated[FiniteNumber, Field(ge=0, le=1)]


class SetEnvelope(Operation):
    action: Literal["set_integrated_audio_fade"]
    type: Literal["custom", "linear"]
    points: Annotated[list[EnvelopePoint], Field(min_length=2, max_length=4096)]

    @model_validator(mode="after")
    def full_envelope(self):
        if self.points[0].t != 0 or self.points[-1].t != 1 or any(b.t <= a.t for a,b in zip(self.points,self.points[1:])):
            raise ValueError("Envelope points must increase strictly from normalized time 0 to 1.")
        return self


class InsertEffect(Operation):
    action: Literal["insert_video_effect"]
    effect_type: Literal["LinearKey", "DropShadow"]
    index: Annotated[StrictInt, Field(ge=0, le=49)]


class SelectTrack(Operation):
    action: Literal["select_audio_track"]
    track_id: StrictInt | StrictStr

    @model_validator(mode="after")
    def exact_track_id(self):
        if str(self.track_id) != str(int(self.track_id)) or not -1 <= int(self.track_id) <= 2147483647:
            raise ValueError("Audio track ID must be a canonical integer identifier or -1 (automatic).")
        return self


SavedCueOperation = Annotated[SetHotkey | SetHotkeyEnabled | SetDays | SetEnvelope | InsertEffect | SelectTrack, Field(discriminator="action")]


def _point_budget(operations):
    if sum(len(op.points) for op in operations if isinstance(op, SetEnvelope)) > 8192:
        raise ValueError("A batch may contain at most 8192 replacement envelope points.")
    return operations


SavedCueOperations = Annotated[list[SavedCueOperation], Field(min_length=1, max_length=50), AfterValidator(_point_budget)]


def _archive(source):
    outer = Archive(source)
    meta = outer.mapping(outer.root)
    if outer.ref(meta.get("QLabShortVersionString")) != "5.5.10" or outer.ref(meta.get("QLabBuildNumber")) != 5510:
        raise ValueError("Saved cue settings require QLab 5.5.10/build 5510.")
    carrier = outer.ref(meta["cueLists"])
    inner = Archive(carrier["NS.data"])
    cues, incoming = _reachable_cues(inner, ("LightCue", "VideoCue"))
    return outer, meta, carrier, inner, cues, incoming


def _hotkey(a, cue):
    obj = a.ref(cue.get("hotKey"))
    if not isinstance(obj, dict) or a.kind(obj) != "F53HotKey":
        raise ValueError("Hotkey descriptor is unavailable.")
    code, character = (a.ref(obj.get("QLActionKey" + k)) for k in ("KeyCode", "KeyCharacter"))
    if type(code) is not int or not 0 <= code <= 127 or type(character) is not int or not 0 <= character <= 65535:
        raise ValueError("Hotkey code/character is unknown.")
    flags = {k: a.ref(obj.get("QLActionKey" + k.title())) for k in (*MODIFIERS, "capsLock", "numericPad", "function")}
    # Mixed-case native names are not title-cased by Python.
    for key, native in (("capsLock", "CapsLock"), ("numericPad", "NumericPad")):
        flags[key] = a.ref(obj.get("QLActionKey" + native))
    if any(type(value) is not bool for value in flags.values()):
        raise ValueError("Hotkey modifier state is unavailable.")
    return dict(key_code=code, character=character, modifiers=[k for k,v in flags.items() if v],
                enabled=a.ref(cue.get("useHotKey")))


def _settings(a, cue):
    result, issues = {}, []
    try:
        result["hotkey"] = _hotkey(a, cue)
    except (ValueError, KeyError, TypeError) as exc:
        issues.append(str(exc))
    days = {day: a.ref(cue.get("wall" + day.title())) for day in DAYS}
    if all(type(value) is bool for value in days.values()):
        result["wall_clock"] = dict(days=[day for day,value in days.items() if value],
            mode=a.ref(cue.get("wallClockMode")), enabled=a.ref(cue.get("useWallClock")))
    else:
        issues.append("Wall Clock days are unavailable.")
    if a.kind(cue) == "VideoCue":
        try:
            result["video_effects"] = _effect_summary(a, cue)
        except (ValueError, KeyError, TypeError) as exc:
            issues.append("Video FX: " + str(exc))
        try:
            audio = a.ref(cue["audioCue"])
            if a.kind(audio) != "AudioCue":
                raise ValueError("Embedded AudioCue is unavailable.")
            track = a.ref(audio.get("track"))
            result["video_audio"] = dict(track=track if type(track) is int else None,
                input_channel_names=[], gangs=[], integrated_fade={})
            if type(track) is not int:
                issues.append("Unknown embedded audio track encoding.")
            fade = a.ref(audio["fade"]); shapes = a.ref(fade["shapes"])
            envelope = _readable_curve_side(a, shapes, "down")
            envelope.update(status="available" if not envelope["issues"] else "partial",
                            resolution=a.ref(shapes.get("resolution")), mirror_shape=a.ref(shapes.get("mirrorShape")))
            envelope.update(enabled=a.ref(audio.get("doFade")), lock_to_cue=a.ref(audio.get("lockFadeToCue")),
                domain={k:a.ref(v) for k,v in a.ref(shapes["domain"]).items() if k != "$class"},
                coordinate_scope="Normalized 0–1 over selected start/end when locked; otherwise over the media duration.")
            result["video_audio"]["integrated_fade"] = envelope
            issues.extend("Integrated fade: " + issue for issue in envelope["issues"])
            names = a.mapping(audio["inputNames"]) if a.ref(audio.get("inputNames")) is not None else {}
            matrix = a.ref(audio["levels"])
            gangs = a.mapping(matrix["gangs"])
            channel_names, group_records = [], []
            truncated = len(names) > 128 or len(gangs) > 1000
            for key, value in list(names.items())[:128]:
                name = a.ref(value)
                if type(key) not in {int,str} or type(name) is not str:
                    issues.append("Unknown input name key/value encoding.")
                    continue
                channel_names.append(dict(native_key=key, channel=key if type(key) is int and key >= 1 else None, name=name))
            remaining = 4096
            for name, value in list(gangs.items())[:1000]:
                members = a.array(value)
                parsed = []
                truncated |= len(members) > remaining
                for ref in members[:remaining]:
                    cell = a.ref(ref)
                    row, column = a.ref(cell.get("row")), a.ref(cell.get("column"))
                    if a.kind(cell) != "AudioLevelKnobs" or type(row) is not int or type(column) is not int or min(row,column) < 0:
                        raise ValueError("Unknown audio gang member encoding.")
                    parsed.append(dict(row=row,column=column))
                remaining -= len(parsed)
                if type(name) is not str:
                    raise ValueError("Unknown audio gang name encoding.")
                group_records.append(dict(name=name,members=parsed))
            if truncated:
                issues.append("Channel metadata truncated at 128 names, 1000 gangs or 4096 total members.")
            result["video_audio"].update(input_channel_names=channel_names, gangs=group_records,
                channel_metadata_truncated=truncated)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            issues.append("Embedded audio: " + str(exc))
    return result, issues


def _effect_summary(a, cue):
    entries = a.array(a.mapping(cue["videoEffects"])["effectEntries"])
    if len(entries) > 50:
        raise ValueError("Video FX chain exceeds 50 instances.")
    result = []
    for index, ref in enumerate(entries):
        entry = a.mapping(ref); effect = a.ref(entry["effect"])
        result.append(dict(index=index, type=a.kind(effect).removeprefix("VideoEffect"),
            instance_id=a.ref(entry["instanceID"]), enabled=a.ref(a.mapping(entry["parameters"]).get("_F53VideoEffectEnabled"))))
    return result


def _effect_template(target, name):
    templates = json.loads((Path(__file__).parent / "write/saved_video_fx_templates.json").read_text())
    record = templates["templates"][name]
    data = base64.b64decode(record["archive_base64"], validate=True)
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("Native Video FX template changed.")
    source = Archive(data); copied = {0: plistlib.UID(0)}
    def clone(value):
        if isinstance(value, plistlib.UID):
            if value.data not in copied:
                copied[value.data] = target.add(None)
                target.objects[copied[value.data].data] = clone(source.ref(value))
            return copied[value.data]
        if isinstance(value, dict):
            return {k:clone(v) for k,v in value.items()}
        if isinstance(value, list):
            return [clone(v) for v in value]
        return value
    return clone(source.data["$top"]["root"])


def inspect_saved_cue(source, cue_id):
    outer, meta, _, a, cues, _ = _archive(source)
    found = cues.get(str(cue_id).upper())
    if found is None:
        raise ValueError("No active Light/Video cue has this exact UUID.")
    settings, issues = _settings(a, found[0])
    return dict(status="partial" if issues else "ready", workspace_id=str(outer.ref(meta["uniqueID"])).upper(),
                cue_type=a.kind(found[0]).removesuffix("Cue"), version="5.5.10", build=5510, settings=settings, issues=issues)


def read_saved_cue_settings(reader, workspace_id, cue_id):
    from . import workspace_documents as docs
    from .light_patch.reader import _read_file
    result = dict(status="unavailable", source="saved_archive", settings={}, issues=[])
    try:
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader), workspace_id)
            data, identity = _read_file(Path(before["path"]))
            result.update(inspect_saved_cue(data, cue_id))
            if result.pop("workspace_id") != workspace_id:
                raise ValueError("Saved workspace UUID does not match the request.")
            after = docs._document(docs._inventory(reader), workspace_id)
            if before != after or _read_file(Path(before["path"])) != (data, identity):
                return dict(status="changed_during_read", settings={}, issues=["Document or file changed; enrichment discarded."])
            result.update(sha256=hashlib.sha256(data).hexdigest(), document_modified=before["modified"],
                          freshness="possibly_stale" if before["modified"] else "last_saved")
            if len(json.dumps(result, allow_nan=False).encode()) > 2*1024*1024:
                raise ValueError("Saved cue settings exceed the 2 MiB limit.")
        return SavedCueSettings.model_validate(result).model_dump(mode="json")
    except Exception as exc:
        return dict(status="unavailable", settings={}, issues=[sanitize_exception_message(exc)])


def plan_saved_cue_settings(source, operations, *, media=None, targets=()):
    ops = TypeAdapter(SavedCueOperations).validate_python(operations) if operations else []
    if {str(op.cue_id) for op in ops if isinstance(op, SetHotkey)} & {str(op.cue_id) for op in ops if isinstance(op, SetHotkeyEnabled)}:
        raise ValueError("Configure and activate Hotkey in separate confirmed calls.")
    patch = Patch(source)
    outer, meta, carrier, a, cues, incoming = _archive(source)
    target_ids = set(targets) | {str(op.cue_id).upper() for op in ops}
    if not target_ids <= cues.keys():
        raise ValueError("An active unique Light/Video cue is required.")
    original_settings = {uid: _settings(a, cues[uid][0])[0] for uid in target_ids}
    changes = []
    for op in ops:
        uid = str(op.cue_id).upper()
        if uid not in cues or incoming[cues[uid][1]] != 1:
            raise ValueError("An active unique Light/Video cue is required.")
        cue = cues[uid][0]
        before = _settings(a, cue)[0]
        if isinstance(op, SetHotkey):
            if a.ref(cue.get("useHotKey")) is not False:
                raise ValueError("Hotkey must be disabled before assignment.")
            if any(key not in MODIFIERS for key in _hotkey(a, cue)["modifiers"]):
                raise ValueError("Unvalidated Hotkey modifiers must be cleared natively first.")
            descriptor = dict(a.ref(cue["hotKey"]))
            descriptor.update(QLActionKeyKeyCode=op.key_code, QLActionKeyKeyCharacter=ord(op.character) if op.character else 0)
            for key in MODIFIERS:
                descriptor["QLActionKey"+key.title()] = key in op.modifiers
            if descriptor != a.ref(cue["hotKey"]):
                cue["hotKey"] = a.add(descriptor)
        elif isinstance(op, SetHotkeyEnabled):
            hotkey = _hotkey(a, cue)
            if type(hotkey["enabled"]) is not bool:
                raise ValueError("Hotkey enabled state is unknown.")
            if op.enabled:
                if not hotkey["character"] or any(k not in MODIFIERS for k in hotkey["modifiers"]):
                    raise ValueError("Hotkey activation requires a known assigned key and modifiers.")
                if a.ref(cue.get("armed")) is not False or a.ref(cue.get("continueMode")) != 0 or a.ref(cue.get("skipIfDisarmed")) is not False:
                    raise ValueError("Activation requires disarmed, Do not continue and Skip if disarmed off.")
            cue["useHotKey"] = a.add(op.enabled) if isinstance(cue.get("useHotKey"), plistlib.UID) else op.enabled
        elif isinstance(op, SetDays):
            if a.ref(cue.get("useWallClock")) is not False:
                raise ValueError("Wall Clock must be disabled before changing its days.")
            if "wall_clock" not in before or before["wall_clock"]["mode"] != 0:
                raise ValueError("Unknown Wall Clock mode or weekday encoding.")
            for day in DAYS:
                key = "wall"+day.title()
                cue[key] = a.add(day in op.days) if isinstance(cue[key], plistlib.UID) else day in op.days
        elif isinstance(op, SetEnvelope):
            if a.kind(cue) != "VideoCue":
                raise ValueError("Integrated audio fade requires a Video cue.")
            audio = dict(a.ref(cue["audioCue"]))
            fade = dict(a.ref(audio["fade"])); shapes = dict(a.ref(fade["shapes"]))
            domain = a.ref(shapes["domain"])
            if a.ref(shapes.get("mirrorShape")) is not False or a.kind(domain) != "FadeDomain" or {
                    k:a.ref(v) for k,v in domain.items() if k != "$class"} != {"mode":1,"absolute":False}:
                raise ValueError("Unknown or mirrored integrated fade domain.")
            points = [p.model_dump() for p in op.points]
            for side in ("up", "down"):
                current = _readable_curve_side(a, shapes, side)
                if (current["type"] not in {"custom", "linear"} or current["truncated"]
                        or set(current["issues"]) - {"unknown_shape_fields", "unknown_point_fields"}):
                    raise ValueError("Unsupported integrated fade shape.")
                shape = dict(a.ref(shapes[side+"Shape"]))
                old_refs = a.array(shape["shapeEntries"])
                old_points = current["points"]
                if (len(old_points) < 2 or old_points[0]["t"] != 0 or old_points[-1]["t"] != 1
                        or any(not 0 <= p["v"] <= 1 or not 0 <= p["t"] <= 1 for p in old_points)
                        or any(y["t"] <= x["t"] for x,y in zip(old_points,old_points[1:]))):
                    raise ValueError("Existing integrated fade points are outside the validated domain.")
                for index, ref in enumerate(old_refs):
                    point = a.ref(ref)
                    for key, expected in (("previous", old_refs[index-1] if index else None),
                                          ("next", old_refs[index+1] if index+1 < len(old_refs) else None)):
                        observed = point.get(key)
                        if (observed if a.ref(observed) is not None else None) != expected:
                            raise ValueError("Integrated fade point links are inconsistent.")
                shape["type"] = 0 if op.type == "custom" else 3
                if side == "down" and current["points"] != points:
                    shape["shapeEntries"] = _write_points(a, shape, old_refs, points)
                shapes[side+"Shape"] = a.add(shape)
            fade["shapes"] = a.add(shapes); audio["fade"] = a.add(fade)
            cue["audioCue"] = a.add(audio)
        elif isinstance(op, SelectTrack):
            if a.kind(cue) != "VideoCue" or not media or uid not in media or (
                    int(op.track_id) != -1 and int(op.track_id) not in media[uid]["track_ids"]):
                raise ValueError("Select an exact available audio track from the current media dependency.")
            audio = dict(a.ref(cue["audioCue"]))
            if a.kind(audio) != "AudioCue" or type(a.ref(audio.get("track"))) is not int:
                raise ValueError("Embedded audio track encoding is unknown.")
            audio["track"] = a.add(int(op.track_id)) if isinstance(audio["track"], plistlib.UID) else int(op.track_id)
            cue["audioCue"] = a.add(audio)
        elif isinstance(op, InsertEffect):
            if a.kind(cue) != "VideoCue":
                raise ValueError("Video FX insertion requires a Video cue.")
            entries_ref = a.mapping(cue["videoEffects"])["effectEntries"]
            entries = list(a.array(entries_ref))
            if len(entries) >= 50 or op.index > len(entries):
                raise ValueError("Effect insertion index or chain size is out of bounds.")
            ids = [item["instance_id"] for item in _effect_summary(a, cue)]
            if any(type(n) is not int or n < 1 for n in ids) or len(set(ids)) != len(ids):
                raise ValueError("Existing effect instance IDs are ambiguous.")
            ref = _effect_template(a, op.effect_type); entry = a.mapping(ref)
            instance_id = max(ids, default=0) + 1
            a.ref(entry["effect"])["instanceID"] = instance_id
            ref = a.replacing_mapping(ref, "instanceID", a.add(instance_id))
            entries.insert(op.index, ref)
            array = a.add({**a.ref(entries_ref), "NS.objects": entries})
            cue["videoEffects"] = a.replacing_mapping(cue["videoEffects"], "effectEntries", array)
        after = _settings(a, cue)[0]
        if after != before:
            field = ("hotkey" if isinstance(op, (SetHotkey,SetHotkeyEnabled)) else "wall_clock" if isinstance(op, SetDays)
                     else "video_effects" if isinstance(op, InsertEffect) else "video_audio")
            old_value, new_value = before[field], after[field]
            if isinstance(op, (SetEnvelope, SelectTrack)):
                subfield = "integrated_fade" if isinstance(op, SetEnvelope) else "track"
                old_value, new_value = old_value[subfield], new_value[subfield]
                field += "." + subfield
            changes.append(dict(cue_id=uid, action=op.action, field=field, before=old_value, after=new_value))
    if all(value == _settings(a, cues[uid][0])[0] for uid, value in original_settings.items()):
        changes = []
    output = source
    if changes:
        replacement = outer.add({**carrier, "NS.data": a.dump()})
        outer.data["$top"]["root"] = outer.replacing_mapping(outer.data["$top"]["root"], "cueLists", replacement)
        output = outer.dump()
        if len(output) > MAX_BYTES:
            raise ValueError("Edited workspace exceeds 64 MiB.")
    snapshots = {uid:inspect_saved_cue(output, uid) for uid in target_ids}
    return dict(output_bytes=output, workspace_id=patch.workspace_id, summary=dict(cues=snapshots, media=media or {}),
        changes=changes, warnings=["Saved cue properties are checked after reopen; no playback is verified."],
        affected_cues=[change["cue_id"] for change in changes],
        cue_settings_summary=snapshots)


def _postcondition(source, plan):
    return all(inspect_saved_cue(source, uid) == expected for uid,expected in plan["cue_settings_summary"].items())


def edit_saved_cue_settings(reader, workspace_id, operations, dry_run=True, confirm_token=None):
    from .workspace_archive import edit_archive
    from .workspace_documents import _uuid
    try:
        workspace_id = _uuid(workspace_id)
        ops = TypeAdapter(SavedCueOperations).validate_python(operations)
        targets = {str(op.cue_id).upper() for op in ops}
        media_targets = {str(op.cue_id).upper() for op in ops if isinstance(op, SelectTrack)}
        media = _media_dependencies(reader, workspace_id, media_targets)
        def check():
            if _media_dependencies(reader, workspace_id, media_targets) != media:
                raise ValueError("Media changed since preview.")
        result = edit_archive(reader, workspace_id, operations, dry_run, confirm_token,
            planner=partial(plan_saved_cue_settings, media=media, targets=targets), token_family="savedCueSettings",
            dependencies=media, dependency_check=check, postcondition=_postcondition, live_verifier=_verify_live)
    except Exception as exc:
        result = dict(ok=False, status="blocked", planned_operations=[], executed_operations=[], error=sanitize_exception_message(exc))
    result["tool"] = "qlab_edit_saved_cue_settings"
    summary = result.get("summary")
    if isinstance(summary, dict):
        result["summary"] = dict(cue_ids=sorted(summary.get("cues", {})))
    result["native_cue_verified"] = result.pop("native_patch_verified", False)
    result.pop("native_patch_verification_scope", None)
    result["verification_scope"] = "Saved cue settings after reopen; current cue UUID/type, audio track, fade flags and Video FX count; FX types are archive-verified and compared natively only when explicitly exposed. No cue execution or physical output is verified."
    return result


def _media_dependencies(reader, ws, targets):
    from .write.control import _scalar
    result = {}
    for uid in sorted(targets):
        path = _scalar(reader, ws, uid, "fileTarget")
        formats = _scalar(reader, ws, uid, "audioTrackFormats")
        if not isinstance(path, str) or not Path(path).is_absolute() or not isinstance(formats, dict) or not formats:
            raise ValueError("Current file target and audio tracks are unavailable.")
        stat = Path(path).stat()
        if not Path(path).is_file():
            raise ValueError("Media must be a readable regular file.")
        ids = [int(key) for key in formats if str(key).isdecimal()]
        if len(ids) != len(formats):
            raise ValueError("Unrecognized audio track identifiers.")
        result[uid] = dict(path=path, track_ids=sorted(ids), formats=formats,
            identity=[stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns])
    return result


def _verify_live(reader, ws, summary):
    from .write.control import _scalar
    if _media_dependencies(reader, ws, set(summary["media"])) != summary["media"]:
        raise ValueError("Media dependencies changed during the transaction.")
    effect_types_observed = True
    for uid, expected in summary["cues"].items():
        if str(_scalar(reader, ws, uid, "uniqueID")).upper() != uid or _scalar(reader, ws, uid, "type") != expected["cue_type"]:
            raise ValueError("Native cue identity changed.")
        settings = expected["settings"]
        if "video_audio" in settings:
            audio = settings["video_audio"]
            if type(audio["track"]) is int and audio["track"] != -1 and str(_scalar(reader, ws, uid, "audioTrackID")) != str(audio["track"]):
                raise ValueError("Native selected audio track does not match the archive.")
            for native,key in (("doFade", "enabled"), ("lockFadeToCue", "lock_to_cue")):
                expected_flag = audio["integrated_fade"].get(key)
                if type(expected_flag) is bool and _scalar(reader, ws, uid, native) != expected_flag:
                    raise ValueError("Native integrated fade flags differ from the archive.")
        if "video_effects" in settings:
            actual = _scalar(reader, ws, uid, "videoEffects")
            if not isinstance(actual, list) or len(actual) != len(settings["video_effects"]):
                raise ValueError("Native Video FX instance count differs from the archive.")
            effect_types_observed &= all(isinstance(item, dict) and "type" in item for item in actual)
            if any(isinstance(item, dict) and "type" in item and item["type"] != expected["type"]
                   for item, expected in zip(actual, settings["video_effects"], strict=True)):
                raise ValueError("Native Video FX types differ from the archive.")
    return dict(cue_ids=sorted(summary["cues"]), effect_types_observed=effect_types_observed,
        scope="Native cue identities, track, fade flags and FX count; other properties checked in the saved archive.")


def enrich_cue_details(reader, result, max_bytes=None):
    if not result.identity:
        return result
    result.saved_settings = SavedCueSettings.model_validate(read_saved_cue_settings(reader, result.workspace_id, result.cue_id))
    result.edit_capabilities["saved_settings"] = dict(tool="qlab_edit_saved_cue_settings",
        operations=["set_hotkey", "set_hotkey_enabled", "set_wall_clock_days", *(["select_audio_track", "set_integrated_audio_fade", "insert_video_effect"] if result.identity.type == "Video" else [])], requires_clean_document=True,
        verification_scope="Saved archive after reopen; no trigger execution is tested.")
    from .cues.limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES
    from .cues.limits import serialized_payload_bytes
    maximum = max_bytes if max_bytes is not None else MAX_SENSITIVE_CUE_RESPONSE_BYTES
    if serialized_payload_bytes(result.model_dump(mode="json")) > maximum:
        result.saved_settings = None
        result.edit_capabilities.pop("saved_settings", None)
        note = "Saved settings omitted because the response byte limit was reached."
        result.coverage.notes.append(note)
        if serialized_payload_bytes(result.model_dump(mode="json")) > maximum:
            result.coverage.notes.pop()
        result.partial = True
        result.status = "partial"
    return result
