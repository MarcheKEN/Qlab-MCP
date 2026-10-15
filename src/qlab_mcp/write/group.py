"""Typed edits for Group, Cue List, Cue Cart and Cart containers."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from ..models import CanonicalWorkspaceUUID
from .control import Nonnegative, CueEditCommonProperties, _FAMILIES, edit_control_cues
from .groups import GROUP_PROPERTIES
from ..control_applescript import trigger_capabilities


class GroupCueEditProperties(CueEditCommonProperties):
    model_config = ConfigDict(extra="forbid")

    duration: Nonnegative | None = None
    secondTriggerAction: Annotated[StrictInt, Field(ge=0, le=7)] | None = None
    mode: Literal[1, 2, 3, 4, 6] | None = None
    playlist_do_loop: StrictBool | None = Field(default=None, alias="playlist/doLoop")
    playlist_do_shuffle: StrictBool | None = Field(default=None, alias="playlist/doShuffle")
    playlist_do_crossfade: StrictBool | None = Field(default=None, alias="playlist/doCrossfade")
    playlist_crossfade_duration: Nonnegative | None = Field(default=None, alias="playlist/crossfade/duration")

    @field_validator("mode", mode="before")
    @classmethod
    def strict_group_mode(cls, value):
        if value is not None and (type(value) is not int or value not in {1, 2, 3, 4, 6}):
            raise ValueError("mode must be one of the supported Group modes: 1, 2, 3, 4, or 6.")
        return value

    @model_validator(mode="after")
    def require_changes(self):
        changes = self.model_dump(by_alias=True, exclude_unset=True)
        if not changes or any(value is None for value in changes.values()):
            raise ValueError("Provide one or more non-null Group properties.")
        return self


class GroupCueEditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cue_id: CanonicalWorkspaceUUID
    properties: GroupCueEditProperties
    confirm_gates: list[StrictStr] = Field(default_factory=list)


def group_edit_capabilities(mode: int | None = None, triggers=None) -> dict:
    common = [field.alias or name for name, field in CueEditCommonProperties.model_fields.items()] + ["duration"]
    playlist = sorted(GROUP_PROPERTIES - {"mode"})
    blocked = {}
    allowed = [*common, "mode"]
    if triggers is None or type(triggers.fadeAndStopOthers) is not int:
        blocked["fadeAndStopOthers"] = "Requires fresh integer scope; boolean cannot identify scope."
        allowed.remove("fadeAndStopOthers")
    if mode == 6:
        allowed.extend(playlist)
    else:
        blocked.update({key: "Requires a fresh mode=6 Playlist baseline." for key in playlist})
    return trigger_capabilities({
        "tool": "qlab_edit_group_cues",
        "allowed_properties": sorted(allowed),
        "blocked_properties": blocked,
        "requires_fresh_preflight": True,
        "allowed_second_trigger_actions": list(range(8 if mode == 6 else 6)),
        "mode_playlist_writes_require_one_property": True,
        "pending_validation": [
            "Playhead and playback-position controls",
            "Playlist navigation, current-cue, shuffle and crossfade-curve controls",
            "Cue Cart cell movement",
        ],
    }, triggers)


def edit_group_cues(reader, workspace_id, updates, dry_run=None):
    items = [
        GroupCueEditInput.model_validate(
            item.model_dump(by_alias=True, exclude_unset=True) if isinstance(item, BaseModel) else item
        )
        for item in updates
    ]
    ids = [str(item.cue_id).upper() for item in items]
    if not 1 <= len(items) <= 50 or len(set(ids)) != len(ids):
        raise ValueError("updates requires 1–50 distinct cue UUIDs.")
    changes = [item.properties.model_dump(by_alias=True, exclude_unset=True) for item in items]
    if any(GROUP_PROPERTIES & item.keys() for item in changes) and (
        len(items) != 1 or len(changes[0]) != 1
    ):
        raise ValueError("Group mode and Playlist setters require one cue and one property per call.")
    _FAMILIES["group"] = (GroupCueEditInput, GroupCueEditProperties, ("Group",), "group_basic", "qlab_edit_group_cues")
    return edit_control_cues(reader, workspace_id, items, dry_run, _family="group")


def preflight(reader, ws, item):
    from .control import _preflight, _read
    from .groups import GROUP_SOURCE_READ_KEYS, group_preflight
    changes = item.properties.model_dump(by_alias=True, exclude_unset=True)
    before, changes, operations, dependencies = _preflight(reader, ws, item, "group", _core=True)
    mode = before.get("mode")
    if type(mode) is not int or mode not in {1, 2, 3, 4, 6}:
        raise ValueError("Fresh Group mode is unavailable.")
    dependencies["group_mode"] = mode
    if changes.get("secondTriggerAction", 0) > 5 and mode != 6:
        raise ValueError("Second Trigger 6–7 requires fresh Playlist mode=6.")
    if GROUP_PROPERTIES & changes.keys():
        if "mode" in changes and (type(before.get("secondTriggerAction")) is not int or changes["mode"] != 6 and before["secondTriggerAction"] > 5):
            raise ValueError("Resolve Playlist Second Trigger before leaving mode=6.")
        before.update(_read(reader, ws, str(item.cue_id).upper(), list(GROUP_SOURCE_READ_KEYS)))
        legacy = {"cue_ref": before["uniqueID"], "profile": "group_basic", "operations": operations}
        errors, _ = group_preflight(reader, ws, legacy, before)
        if errors:
            raise ValueError(str(errors))
        dependencies["group_children"] = operations[0]["group_before_snapshot"]
        dependencies["group_source"] = {key: before.get(key) for key in (*GROUP_SOURCE_READ_KEYS, "secondTriggerAction")}
    return before, changes, operations, dependencies


def check_dependencies(reader, ws, uid, dependencies):
    from .groups import read_group_snapshot
    from .control import _scalar, _read
    if _scalar(reader, ws, uid, "mode") != dependencies["group_mode"]:
        raise ValueError("Group mode changed before setter.")
    if "group_source" in dependencies:
        source = _read(reader, ws, uid, list(dependencies["group_source"]))
        if source != dependencies["group_source"]:
            raise ValueError("Group source health or Playlist state changed before setter.")
    if "group_children" in dependencies:
        current, error = read_group_snapshot(reader, ws, uid)
        if error or current != dependencies["group_children"]:
            raise ValueError(error or "Group ordered children changed before setter.")


def verify_children(reader, ws, uid, operation, dependencies):
    from .groups import read_group_snapshot, group_side_effects
    if "group_children" not in dependencies:
        return
    after, error = read_group_snapshot(reader, ws, uid)
    if error or after is None:
        raise ValueError(error or "Group child readback unavailable.")
    effects = group_side_effects({"group_before_snapshot": dependencies["group_children"]}, after)
    operation["child_side_effects"] = effects
    operation["group_child_readback"] = after
    from .control import _read
    source = _read(reader, ws, uid, list(dependencies["group_source"]))
    operation["group_source_readback"] = source
    if any(source.get(key) != value for key, value in dependencies["group_source"].items()
           if key != operation["property"]):
        raise ValueError("Unexpected Group source side effects; inspect fresh readback.")
    allowed = operation["property"] == "mode" and operation["args"][0] in {3, 6}
    if any(not allowed or effect.get("field") != "continueMode" or effect.get("after") != 0 for effect in effects):
        raise ValueError("Unexpected Group child side effects; inspect fresh readback.")
