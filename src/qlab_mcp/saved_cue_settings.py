"""Bounded saved Light/Video cue settings and isolated same-path archive edits."""
from __future__ import annotations

from functools import partial
import base64
import hashlib
import json
from pathlib import Path
import plistlib
from typing import Annotated, Literal, get_args
from uuid import UUID

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


class RemoveAudioEffect(Operation):
    action: Literal["remove_audio_effect"]
    effect_index: Annotated[StrictInt, Field(ge=0, le=49)]


class MoveAudioEffect(Operation):
    action: Literal["move_audio_effect"]
    effect_index: Annotated[StrictInt, Field(ge=0, le=49)]
    new_index: Annotated[StrictInt, Field(ge=0, le=49)]


class SetAudioEffectBypassed(Operation):
    action: Literal["set_audio_effect_bypassed"]
    effect_index: Annotated[StrictInt, Field(ge=0, le=49)]
    bypassed: StrictBool


SavedCueOperation = Annotated[SetHotkey | SetHotkeyEnabled | SetDays | SetEnvelope | InsertEffect | SelectTrack |
                              RemoveAudioEffect | MoveAudioEffect | SetAudioEffectBypassed,
                              Field(discriminator="action")]


def _point_budget(operations):
    if sum(len(op.points) for op in operations if isinstance(op, SetEnvelope)) > 8192:
        raise ValueError("A batch may contain at most 8192 replacement envelope points.")
    return operations


SavedCueOperations = Annotated[list[SavedCueOperation], Field(min_length=1, max_length=50), AfterValidator(_point_budget)]

PublicSavedCueOperation = Annotated[SetHotkey | SetHotkeyEnabled | SetDays | SetEnvelope | InsertEffect | SelectTrack,
                                    Field(discriminator="action")]
PublicSavedCueOperations = Annotated[list[PublicSavedCueOperation], Field(min_length=1, max_length=50), AfterValidator(_point_budget)]


def _archive(source):
    outer = Archive(source)
    meta = outer.mapping(outer.root)
    if outer.ref(meta.get("QLabShortVersionString")) != "5.5.10" or outer.ref(meta.get("QLabBuildNumber")) != 5510:
        raise ValueError("Saved cue settings require QLab 5.5.10/build 5510.")
    carrier = outer.ref(meta["cueLists"])
    inner = Archive(carrier["NS.data"])
    cues, incoming = _reachable_cues(inner, ("LightCue", "VideoCue", "AudioCue", "MicCue"))
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


def _settings(a, cue, *, include_audio_effects=True):
    result, issues = {}, []
    cue_kind = a.kind(cue)
    if cue_kind in {"LightCue", "VideoCue"}:
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
    if cue_kind == "VideoCue":
        try:
            result["video_effects"] = _effect_summary(a, cue)
        except (ValueError, KeyError, TypeError) as exc:
            issues.append("Video FX: " + str(exc))
        try:
            audio = a.ref(cue["audioCue"])
            if a.kind(audio) != "AudioCue":
                raise ValueError("Embedded AudioCue is unavailable.")
            if include_audio_effects:
                try:
                    result["audio_effects"] = _audio_effect_summary(a, audio)
                except (ValueError, KeyError, TypeError) as exc:
                    issues.append("Audio FX: " + str(exc))
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
    elif include_audio_effects and cue_kind in {"AudioCue", "MicCue"}:
        try:
            result["audio_effects"] = _audio_effect_summary(a, cue)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            issues.append("Audio FX: " + str(exc))
    return result, issues


def _audio_effect_summary(a, audio_cue):
    if a.kind(audio_cue) not in {"AudioCue", "MicCue"}:
        raise ValueError("Audio/Mic cue effect owner is unavailable.")
    effects_ref = audio_cue.get("effects")
    if not isinstance(effects_ref, plistlib.UID) or a.kind(effects_ref) not in {"NSArray", "NSMutableArray"}:
        raise ValueError("Saved Audio FX chain is unavailable or has an unknown array encoding.")
    from .audio_archive import _effect_chain
    return _effect_chain(a, effects_ref)


def _audio_cue_for_fx(a, cue):
    cue_kind = a.kind(cue)
    if cue_kind in {"AudioCue", "MicCue"}:
        return cue
    if cue_kind == "VideoCue":
        audio = a.ref(cue.get("audioCue"))
        if not isinstance(audio, dict) or a.kind(audio) != "AudioCue":
            raise ValueError("Embedded AudioCue is unavailable.")
        return audio
    raise ValueError("Audio FX edits require an Audio, Mic, or Video cue with an AudioCue.")


def _audio_fx_chain(a, cue):
    audio_cue = _audio_cue_for_fx(a, cue)
    if a.kind(cue) == "VideoCue":
        child_ref = cue.get("audioCue")
        owners = sum(1 for obj in a.objects if isinstance(obj, dict) and "$class" in obj
                     and a.kind(obj) == "VideoCue" and obj.get("audioCue") == child_ref)
        if owners != 1:
            raise ValueError("Shared Video audio track settings cannot be edited safely.")
    effects_ref = audio_cue.get("effects")
    if not isinstance(effects_ref, plistlib.UID) or a.kind(effects_ref) not in {"NSArray", "NSMutableArray"}:
        raise ValueError("Saved Audio FX chain is unavailable or has an unknown array encoding.")
    refs = list(a.array(effects_ref))
    effects = _audio_effect_summary(a, audio_cue)
    if len(refs) != len(effects):
        raise ValueError("Saved Audio FX chain changed while reading.")
    identifiers = [item.get("identifier") for item in effects]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Audio FX identities are missing or ambiguous.")
    return audio_cue, effects_ref, refs, effects


def _audio_effect_reference_count(a, target):
    count = 0
    stack = [a.data["$top"]["root"]]
    visited = set()
    while stack:
        value = stack.pop()
        if isinstance(value, plistlib.UID):
            if value == target:
                count += 1
            elif value.data and value.data not in visited:
                visited.add(value.data)
                stack.append(a.ref(value))
        elif isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return count


def _audio_effect_array_owner_count(a, target):
    cues, _ = _reachable_cues(a, ("AudioCue", "MicCue", "VideoCue"))
    count = 0
    for cue, _ in cues.values():
        kind = a.kind(cue)
        if kind == "VideoCue":
            owner = a.ref(cue.get("audioCue"))
            if not isinstance(owner, dict) or a.kind(owner) != "AudioCue":
                continue
        elif kind in {"AudioCue", "MicCue"}:
            owner = cue
        else:
            continue
        if owner.get("effects") == target:
            count += 1
    return count


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


def _inspect_cue(outer, meta, a, cues, cue_id, *, include_audio_effects=True):
    found = cues.get(str(cue_id).upper())
    if found is None:
        raise ValueError("No active supported cue has this exact UUID.")
    settings, issues = _settings(a, found[0], include_audio_effects=include_audio_effects)
    return dict(status="partial" if issues else "ready", workspace_id=str(outer.ref(meta["uniqueID"])).upper(),
                cue_type=a.kind(found[0]).removesuffix("Cue"), version="5.5.10", build=5510, settings=settings, issues=issues)


def inspect_saved_cue(source, cue_id, *, include_audio_effects=True):
    outer, meta, _, a, cues, _ = _archive(source)
    return _inspect_cue(outer, meta, a, cues, cue_id, include_audio_effects=include_audio_effects)


def inspect_saved_cue_object_ownership(source, cue_id, object_ids):
    outer, meta, _, a, cues, _ = _archive(source)
    uid = str(UUID(str(cue_id))).upper()
    requested = {str(UUID(str(value))).upper() for value in object_ids}
    if not requested:
        raise ValueError("At least one exact Audio Object UUID is required.")
    found = cues.get(uid)
    if found is None:
        raise ValueError("No active supported cue has this exact UUID.")
    cue = found[0]
    cue_kind = a.kind(cue)
    if cue_kind not in {"AudioCue", "MicCue"}:
        raise ValueError("Audio Object writes require an Audio or Mic cue owner.")
    map_id = a.ref(cue.get("audioMapID")) if "audioMapID" in cue else None
    if "audioMapID" not in cue or map_id not in (None, ""):
        raise ValueError("The saved cue has an Audio Map or unknown map ownership.")

    def object_collection(archive, owner):
        collection_ref = owner.get("audioObjects")
        collection = archive.ref(collection_ref)
        if not isinstance(collection, dict) or archive.kind(collection) != "AudioObjectCollection":
            raise ValueError("Saved cue Audio Object collection is unavailable or unknown.")
        return archive.array(collection["audioObjects"])

    def object_info(archive, reference):
        if not isinstance(reference, plistlib.UID):
            raise ValueError("Saved Audio Object reference is not a unique archive object.")
        value = archive.ref(reference)
        if not isinstance(value, dict) or archive.kind(value) != "F53AudioObject":
            raise ValueError("Saved Audio Object class is unknown.")
        identity = archive.ref(value.get("uniqueID"))
        if not isinstance(identity, str):
            raise ValueError("Saved Audio Object UUID is unavailable.")
        return str(UUID(identity)).upper(), reference.data

    def kind(archive, value):
        try:
            return archive.kind(value)
        except (KeyError, TypeError, ValueError, AttributeError):
            return None

    target_refs = {}
    owner_ids = []
    for reference in object_collection(a, cue):
        identity, index = object_info(a, reference)
        if identity in owner_ids:
            raise ValueError("Saved cue Audio Object UUIDs are duplicated.")
        owner_ids.append(identity)
        target_refs[identity] = index
    if not requested <= set(owner_ids):
        raise ValueError("Requested object UUID is absent from the cue-owned saved archive collection.")

    cue_ref = plistlib.UID(found[1])
    if any(isinstance(value, dict) and any(value.get(key) == cue_ref for key in ("audioCue", "micCue"))
           for value in a.objects):
        raise ValueError("Saved Audio Object cue is also referenced as another cue's embedded audio track.")

    for other_id, (other, _) in cues.items():
        if other_id == uid or a.kind(other) not in {"AudioCue", "MicCue"}:
            continue
        collection_ref = other.get("audioObjects")
        if a.ref(collection_ref) is None:
            continue
        if requested & {object_info(a, reference)[0] for reference in object_collection(a, other)}:
            raise ValueError("Saved Audio Object is also referenced by another cue.")

    for archive in (outer, a):
        for value in archive.objects:
            if not isinstance(value, dict) or "$class" not in value or kind(archive, value) != "AudioMap":
                continue
            collection_ref = value.get("audioObjects")
            collection = archive.ref(collection_ref)
            if collection is None:
                continue
            map_refs = object_collection(archive, value)
            if requested & {object_info(archive, reference)[0] for reference in map_refs}:
                raise ValueError("Requested Audio Object is owned by an Audio Map.")

    for archive in (outer, a):
        for index, value in enumerate(archive.objects):
            if not isinstance(value, dict) or "$class" not in value or kind(archive, value) != "F53AudioObject":
                continue
            identity = archive.ref(value.get("uniqueID"))
            if isinstance(identity, str) and str(UUID(identity)).upper() in requested:
                expected = target_refs.get(str(UUID(identity)).upper())
                if archive is not a or expected != index:
                    raise ValueError("Saved Audio Object identity is duplicated outside its owning cue.")

    return dict(source="saved_archive", workspace_id=str(outer.ref(meta["uniqueID"])).upper(),
                cue_id=uid, cue_type=cue_kind.removesuffix("Cue"), audio_map_id="",
                object_ids=sorted(requested), ownership="direct_cue_collection")


def read_saved_cue_object_ownership(reader, workspace_id, cue_id, object_ids):
    from . import workspace_documents as docs
    from .light_patch.reader import _read_file

    ws = docs._uuid(workspace_id)
    docs._local(reader)
    with docs._LOCK:
        before = docs._document(docs._inventory(reader), ws)
        if before["modified"]:
            raise ValueError("Save or discard workspace changes before verifying Audio Object ownership.")
        if not before["path"]:
            raise ValueError("Workspace has no saved document path.")
        data, identity = _read_file(Path(before["path"]))
        result = inspect_saved_cue_object_ownership(data, cue_id, object_ids)
        if result["workspace_id"] != ws:
            raise ValueError("Saved workspace UUID does not match the request.")
        after = docs._document(docs._inventory(reader), ws)
        current, current_identity = _read_file(Path(before["path"]))
        if before != after or current_identity != identity or current != data:
            raise ValueError("Workspace or saved archive changed during Audio Object ownership check.")
        result.update(sha256=hashlib.sha256(data).hexdigest(), freshness="last_saved")
        return result


def read_saved_cue_settings(reader, workspace_id, cue_id):
    from . import workspace_documents as docs
    from .light_patch.reader import _read_file
    result = dict(status="unavailable", source="saved_archive", settings={}, issues=[])
    try:
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader), workspace_id)
            data, identity = _read_file(Path(before["path"]))
            result.update(inspect_saved_cue(data, cue_id, include_audio_effects=False))
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


def plan_saved_cue_settings(source, operations, *, media=None, targets=(), include_audio_effects=True):
    ops = TypeAdapter(SavedCueOperations).validate_python(operations) if operations else []
    if {str(op.cue_id) for op in ops if isinstance(op, SetHotkey)} & {str(op.cue_id) for op in ops if isinstance(op, SetHotkeyEnabled)}:
        raise ValueError("Configure and activate Hotkey in separate confirmed calls.")
    patch = Patch(source)
    outer, meta, carrier, a, cues, incoming = _archive(source)
    from .audio_effect_integrity import capture_effects, effects_match
    effect_snapshot = capture_effects(outer, a) if ops and not include_audio_effects else None
    target_ids = set(targets) | {str(op.cue_id).upper() for op in ops}
    if not target_ids <= cues.keys():
        raise ValueError("An active unique Light, Audio, Mic, or Video cue is required.")
    original_settings = {uid: _settings(a, cues[uid][0], include_audio_effects=include_audio_effects)[0] for uid in target_ids}
    changes = []
    for op in ops:
        uid = str(op.cue_id).upper()
        if uid not in cues or incoming[cues[uid][1]] != 1:
            raise ValueError("An active unique Light, Audio, Mic, or Video cue is required.")
        cue = cues[uid][0]
        cue_kind = a.kind(cue)
        if isinstance(op, (SetHotkey, SetHotkeyEnabled, SetDays)) and cue_kind not in {"LightCue", "VideoCue"}:
            raise ValueError("Hotkey and Wall Clock edits require a Light or Video cue.")
        if isinstance(op, (SetEnvelope, SelectTrack, InsertEffect)) and cue_kind != "VideoCue":
            raise ValueError("Audio track, integrated fade and Video FX operations require a Video cue.")
        if isinstance(op, (RemoveAudioEffect, MoveAudioEffect, SetAudioEffectBypassed)) and cue_kind not in {"AudioCue", "MicCue", "VideoCue"}:
            raise ValueError("Audio FX edits require an Audio, Mic, or Video cue.")
        before = _settings(a, cue, include_audio_effects=include_audio_effects)[0]
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
        elif isinstance(op, (RemoveAudioEffect, MoveAudioEffect, SetAudioEffectBypassed)):
            audio_cue, effects_ref, effects, summaries = _audio_fx_chain(a, cue)
            if op.effect_index >= len(effects):
                raise ValueError("Audio effect index is outside the saved chain.")
            if summaries[op.effect_index].get("saved_state_write_supported") is not True:
                raise ValueError("Unknown or unvalidated AudioUnit identity for QLab 5.5.10.")
            if isinstance(op, RemoveAudioEffect):
                del effects[op.effect_index]
                audio_cue["effects"] = a.add({**a.ref(effects_ref), "NS.objects": effects})
            elif isinstance(op, MoveAudioEffect):
                if op.new_index >= len(effects):
                    raise ValueError("New audio effect index is outside the saved chain.")
                if op.new_index != op.effect_index:
                    effects.insert(op.new_index, effects.pop(op.effect_index))
                    audio_cue["effects"] = a.add({**a.ref(effects_ref), "NS.objects": effects})
            else:
                effect_ref = effects[op.effect_index]
                if (_audio_effect_array_owner_count(a, effects_ref) != 1
                        or _audio_effect_reference_count(a, effects_ref) != 1):
                    raise ValueError("Shared Audio FX chains cannot be bypassed safely.")
                if not isinstance(effect_ref, plistlib.UID):
                    raise ValueError("Audio effect reference has an unknown encoding.")
                if _audio_effect_reference_count(a, effect_ref) != 1:
                    raise ValueError("Shared AudioUnit effect references cannot be bypassed safely.")
                effect = a.ref(effect_ref)
                state_ref = effect.get("state")
                if not isinstance(state_ref, plistlib.UID) or a.kind(state_ref) not in {"NSDictionary", "NSMutableDictionary"}:
                    raise ValueError("Audio effect state has an unknown dictionary encoding.")
                state = a.mapping(state_ref)
                enabled_ref = state.get("enabled")
                enabled = a.ref(enabled_ref)
                if type(enabled) is not bool:
                    raise ValueError("Audio effect enabled state is unavailable.")
                requested_enabled = not op.bypassed
                if enabled != requested_enabled:
                    state["enabled"] = a.add(requested_enabled) if isinstance(enabled_ref, plistlib.UID) else requested_enabled
                    effect["state"] = a.make_dict(state)
        after = _settings(a, cue, include_audio_effects=include_audio_effects)[0]
        if after != before:
            field = ("hotkey" if isinstance(op, (SetHotkey,SetHotkeyEnabled)) else "wall_clock" if isinstance(op, SetDays)
                     else "video_effects" if isinstance(op, InsertEffect) else "audio_effects" if isinstance(op, (RemoveAudioEffect, MoveAudioEffect, SetAudioEffectBypassed))
                     else "video_audio")
            old_value, new_value = before[field], after[field]
            if isinstance(op, (SetEnvelope, SelectTrack)):
                subfield = "integrated_fade" if isinstance(op, SetEnvelope) else "track"
                old_value, new_value = old_value[subfield], new_value[subfield]
                field += "." + subfield
            changes.append(dict(cue_id=uid, action=op.action, field=field, before=old_value, after=new_value))
    if all(value == _settings(a, cues[uid][0], include_audio_effects=include_audio_effects)[0] for uid, value in original_settings.items()):
        changes = []
    output = source
    if changes:
        replacement = outer.add({**carrier, "NS.data": a.dump()})
        outer.data["$top"]["root"] = outer.replacing_mapping(outer.data["$top"]["root"], "cueLists", replacement)
        output = outer.dump()
        if len(output) > MAX_BYTES:
            raise ValueError("Edited workspace exceeds 64 MiB.")
    if effect_snapshot is not None and not effects_match(output, effect_snapshot):
        raise ValueError("Existing audio effect data could not be preserved.")
    snapshots = {}
    if target_ids:
        snapshot_outer, snapshot_meta, _, snapshot_archive, snapshot_cues, _ = _archive(output)
        snapshots = {uid:_inspect_cue(snapshot_outer, snapshot_meta, snapshot_archive, snapshot_cues, uid,
                                      include_audio_effects=include_audio_effects) for uid in target_ids}
    return dict(output_bytes=output, workspace_id=patch.workspace_id, summary=dict(cues=snapshots, media=media or {}),
        changes=changes, warnings=["Saved cue properties are checked after reopen; no playback is verified."],
        affected_cues=[change["cue_id"] for change in changes],
        cue_settings_summary=snapshots, include_audio_effects=include_audio_effects, effect_snapshot=effect_snapshot)


def _postcondition(source, plan):
    from .audio_effect_integrity import effects_match
    effect_snapshot = plan.get("effect_snapshot")
    if effect_snapshot is not None and not effects_match(source, effect_snapshot):
        return False
    snapshots = plan["cue_settings_summary"]
    if not snapshots:
        return True
    outer, meta, _, a, cues, _ = _archive(source)
    return all(_inspect_cue(outer, meta, a, cues, uid, include_audio_effects=plan.get("include_audio_effects", True)) == expected
               for uid, expected in snapshots.items())


def edit_saved_cue_settings(reader, workspace_id, operations, dry_run=True, confirm_token=None):
    from .workspace_archive import edit_archive
    from .workspace_documents import _uuid
    try:
        workspace_id = _uuid(workspace_id)
        ops = TypeAdapter(PublicSavedCueOperations).validate_python(operations)
        targets = {str(op.cue_id).upper() for op in ops}
        media_targets = {str(op.cue_id).upper() for op in ops if isinstance(op, SelectTrack)}
        media = _media_dependencies(reader, workspace_id, media_targets)
        def check():
            if _media_dependencies(reader, workspace_id, media_targets) != media:
                raise ValueError("Media changed since preview.")
        result = edit_archive(reader, workspace_id, operations, dry_run, confirm_token,
            planner=partial(plan_saved_cue_settings, media=media, targets=targets, include_audio_effects=False), token_family="savedCueSettings",
            dependencies=media, dependency_check=check, postcondition=_postcondition, live_verifier=_verify_live)
    except Exception as exc:
        result = dict(ok=False, status="blocked", planned_operations=[], executed_operations=[], error=sanitize_exception_message(exc))
    result["tool"] = "qlab_edit_saved_cue_settings"
    summary = result.get("summary")
    if isinstance(summary, dict):
        result["summary"] = dict(cue_ids=sorted(summary.get("cues", {})))
    result["native_cue_verified"] = result.pop("native_patch_verified", False)
    result.pop("native_patch_verification_scope", None)
    result["verification_scope"] = "Saved cue settings after reopen; native cue UUID/type, audio track, fade flags and Video FX count. No cue execution or physical output is verified."
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
        requires_clean_document=True,
        **({"insert_video_effect_types": list(get_args(InsertEffect.model_fields["effect_type"].annotation))} if result.identity.type == "Video" else {}),
        verification_scope="Saved archive after reopen; no trigger execution is tested.")
    cue_type = result.identity.type
    operations = []
    if cue_type in {"Light", "Video"}:
        operations.extend(["set_hotkey", "set_hotkey_enabled", "set_wall_clock_days"])
    if cue_type == "Video":
        operations.extend(["select_audio_track", "set_integrated_audio_fade", "insert_video_effect"])
    result.edit_capabilities["saved_settings"]["operations"] = operations
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
