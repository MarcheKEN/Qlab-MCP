from __future__ import annotations

from pathlib import Path

from qlab_mcp.write.osc_inventory import (
    coverage_summary,
    extract_cue_osc_inventory,
    extract_workspace_video_osc_inventory,
    registry_coverage,
)
from qlab_mcp.write.registry import UPDATE_PROFILES, profile_catalog
from qlab_mcp.write import (
    text_basics,
    video_appearance,
    video_audio_time,
    video_opacity,
    video_scalars,
    video_translation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_PATH = PROJECT_ROOT / "docs" / "references" / "qlab_osc_dictionary.md"


EXTRACTED_FAMILY_REGISTRY_MEMBERSHIP = (
    ("text_basics", {"text_basic": text_basics.TEXT_PHASE3E_PROPERTIES}),
    (
        "video_opacity",
        {
            profile: frozenset({video_opacity.PROPERTY})
            for profile in video_opacity.PROFILE_TYPES
        },
    ),
    (
        "video_translation",
        {
            profile: video_translation.PROPERTIES
            for profile in video_translation.PROFILE_TYPES
        },
    ),
    (
        "video_scalars",
        {
            profile: video_scalars.PROPERTIES
            for profile in video_scalars.PROFILE_TYPES
        },
    ),
    (
        "video_appearance",
        {
            profile: video_appearance.PROPERTIES
            for profile in video_appearance.PROFILE_TYPES
        },
    ),
    (
        "video_audio_time",
        {
            profile: video_audio_time.PROPERTIES
            for profile in video_audio_time.PROFILE_TYPES
        },
    ),
)


def test_extracted_write_family_surfaces_remain_exact() -> None:
    assert video_opacity.PROPERTY == "opacity"
    assert video_opacity.PROFILE_TYPES == {
        "video_basic": "Video",
        "camera_basic": "Camera",
        "text_basic": "Text",
    }
    assert video_translation.PROPERTIES == frozenset({"translation/x", "translation/y"})
    assert video_translation.PROFILE_TYPES == video_opacity.PROFILE_TYPES
    assert video_scalars.PROPERTIES == frozenset(
        {
            "scale/x",
            "scale/y",
            "anchor/x",
            "anchor/y",
            "cropTop",
            "cropBottom",
            "cropLeft",
            "cropRight",
        }
    )
    assert video_scalars.PROFILE_TYPES == video_opacity.PROFILE_TYPES
    assert video_appearance.PROPERTIES == frozenset({"blendMode", "preserveAspectRatio"})
    assert video_appearance.PROFILE_TYPES == video_opacity.PROFILE_TYPES
    assert video_audio_time.PROPERTIES == frozenset(
        {
            "startTime",
            "endTime",
            "playCount",
            "infiniteLoop",
            "rate",
            "preservePitch",
            "holdLastFrame",
        }
    )
    assert video_audio_time.PROFILE_TYPES == {"video_basic": "Video"}
    assert video_audio_time.AUDIO_TRACK_PROPERTIES == video_audio_time.PROPERTIES - {
        "holdLastFrame"
    }
    assert video_audio_time.EVIDENCE_KEYS == (
        "audioTrackFormats",
        "numChannelsIn",
        "levels",
    )


def test_extracted_write_family_registry_tags_match_handlers_exactly() -> None:
    expected = {
        (family, profile, property_name)
        for family, profiles in EXTRACTED_FAMILY_REGISTRY_MEMBERSHIP
        for profile, properties in profiles.items()
        for property_name in properties
    }
    actual = {
        (property_spec.write_family, profile, property_spec.name)
        for profile, profile_spec in UPDATE_PROFILES.items()
        for property_spec in profile_spec.properties
        if property_spec.write_family is not None
    }

    assert actual == expected


def test_update_registry_has_specs_for_all_mutating_cue_osc_routes() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    coverage = registry_coverage(inventory, profile_catalog())
    missing = [entry for entry in coverage if entry["registry_status"] == "missing"]

    assert missing == []
    assert coverage_summary(coverage) == {
        "common/global cue properties": {"real_write": 15, "gated": 21},
        "Group/List/Cart": {"gated": 9, "real_write": 6, "planned_only": 12},
        "Audio": {"gated": 65, "real_write": 6},
        "Mic": {"gated": 5, "real_write": 2},
        "Video": {"gated": 79},
        "Camera": {"gated": 4, "real_write": 2},
        "Text": {"gated": 19},
        "Light": {"gated": 11},
        "Fade": {"gated": 25},
        "Network": {"gated": 20},
        "MIDI": {"gated": 29},
        "MIDI File": {"gated": 4, "real_write": 1},
        "Timecode": {"gated": 6, "real_write": 3, "planned_only": 2},
        "Reset": {"gated": 3},
        "Devamp": {"gated": 3},
        "Script": {"gated": 1},
    }


def test_group_inventory_includes_documented_playlist_routes_and_actions() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    group_entries = {
        entry["property"]: entry
        for entry in inventory
        if entry["section"] == "Group/List/Cart"
    }

    for property_name in (
        "playlist/currentCue",
        "playlist/currentCueID",
        "playlist/doCrossfade",
        "playlist/doLoop",
        "playlist/doShuffle",
        "playlist/crossfade/duration",
        "playlistCrossfade",
        "playlistCrossfadeDuration",
        "playlistLoop",
        "playlistShuffle",
        "playlist/next",
        "playlist/previous",
        "shuffle",
    ):
        assert property_name in group_entries

    coverage = registry_coverage(inventory, profile_catalog())
    group_status = {
        entry["property"]: entry["registry_status"]
        for entry in coverage
        if entry["section"] == "Group/List/Cart"
    }
    for property_name in (
        "mode",
        "playlist/doCrossfade",
        "playlist/doLoop",
        "playlist/doShuffle",
        "playlist/crossfade/duration",
    ):
        assert group_status[property_name] == "gated"
    for property_name in ("playlist/next", "playlist/previous", "shuffle"):
        assert group_status[property_name] == "planned_only"


def test_devamp_and_network_catalog_routes_remain_gated_until_specialized_evidence() -> None:
    catalog = profile_catalog()
    devamp = catalog["devamp_basic"]["properties"]
    network = catalog["network_basic"]["properties"]

    for property_name in ("cueTargetID", "devampType", "startNextCueWhenSliceEnds", "stopTargetWhenSliceEnds"):
        assert devamp[property_name]["real_write_enabled"] is False
    assert devamp["cueTargetID"]["planned_only_reason"] == "devamp_target_requires_confirm_token"
    assert devamp["devampType"]["planned_only_reason"] == "devamp_settings_require_confirm_token"
    assert network["customString"]["real_write_enabled"] is False
    assert network["customString"]["planned_only_reason"] == "network_osc_message_requires_patch_type_validation"
    assert network["networkPatchID"]["planned_only_reason"] == "network_osc_message_requires_patch_type_validation"
    assert network["fadeEntries"]["planned_only_reason"] == "network_fade_routes_require_deterministic_readback"


def test_audio_time_route_metadata_keeps_profile_specific_policies() -> None:
    catalog = profile_catalog()
    routes = (
        ("rate", "rate"),
        ("startTime", "non_negative_number"),
        ("endTime", "non_negative_number"),
        ("playCount", "positive_int"),
        ("infiniteLoop", "boolean"),
        ("preservePitch", "boolean"),
    )
    policies = (
        ("audio_basic", "safe", True, None, None),
        ("video_basic", "high", False, "video_audio_time_requires_confirm_token", "audio_output"),
    )

    for profile, risk_tier, real_write_enabled, planned_only_reason, capability_gate in policies:
        properties = catalog[profile]["properties"]
        for name, validator in routes:
            property_spec = properties[name]
            assert property_spec["path"] == name
            assert property_spec["args"] == [{"name": "value", "validator": validator}]
            assert property_spec["read_key"] == name
            assert property_spec["modes"] == ["saved"]
            assert property_spec["risk_tier"] == risk_tier
            assert property_spec["real_write_enabled"] is real_write_enabled
            assert property_spec["planned_only_reason"] == planned_only_reason
            assert property_spec["capability_gate"] == capability_gate
            assert property_spec["readback"] == "value"
            assert property_spec["contextual_requirements"] == []


def test_audio_mic_scope_keeps_time_loops_and_format_type_specific() -> None:
    catalog = profile_catalog()
    audio = catalog["audio_basic"]["properties"]
    mic = catalog["mic_basic"]["properties"]

    for property_name in ("rate", "startTime", "endTime", "playCount", "infiniteLoop", "preservePitch"):
        assert audio[property_name]["real_write_enabled"] is True
        assert property_name not in mic

    for property_name in ("audioOutputPatchID", "audioInputPatchID"):
        if property_name == "audioOutputPatchID":
            assert property_name in audio
        assert property_name in mic
        assert mic[property_name]["real_write_enabled"] is False

    assert mic["channelOffset"]["planned_only_reason"] == "audio_input_channel_offset_needs_patch_bounds_validation"
    assert mic["channels"]["planned_only_reason"] == "audio_input_channel_count_needs_patch_bounds_validation"


def test_updateq_coverage_snapshot_doc_matches_summary() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    summary = coverage_summary(registry_coverage(inventory, profile_catalog()))
    snapshot = (PROJECT_ROOT / "docs" / "current" / "coverage" / "osc_coverage_snapshot.md").read_text()

    for section, counts in summary.items():
        expected_row = (
            f"| {section} | {counts.get('real_write', 0)} | {counts.get('gated', 0)} | "
            f"{counts.get('planned_only', 0)} | {counts.get('missing', 0)} |"
        )
        assert expected_row in snapshot


def test_update_registry_coverage_prefers_exact_indexed_route_matches() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    coverage = registry_coverage(inventory, profile_catalog())
    by_section_property = {(entry["section"], entry["property"]): entry for entry in coverage}

    assert by_section_property[("Audio", "object/{name}/name")]["registry_property"] == "object/name"
    assert by_section_property[("Audio", "object/{name}/colorName")]["registry_property"] == "object/colorName"
    assert by_section_property[("Video", "stage/regionIndex/{index}/bounds/origin")]["registry_property"] == (
        "stage/regionIndex/bounds/origin"
    )
    assert by_section_property[("Video", "videoEffect/{name}/enabled")]["registry_property"] == "videoEffect/enabled"


def test_update_registry_marks_script_source_as_not_editable_by_osc() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    catalog = profile_catalog()

    assert not any(entry["property"] == "scriptSource" for entry in inventory)
    assert catalog["script_basic"]["properties"]["scriptSource"]["planned_only_reason"] == "not_editable_by_osc"
    assert catalog["script_basic"]["properties"]["compileSource"]["capability_gate"] == "script_compile"


def test_video_phase1_inventory_tracks_live_increment_and_deprecation() -> None:
    inventory = extract_cue_osc_inventory(DICTIONARY_PATH.read_text())
    by_property = {(entry["section"], entry["property"]): entry for entry in inventory}

    assert by_property[("Video", "opacity")]["live"] is True
    assert by_property[("Video", "opacity")]["read"] is True
    assert by_property[("Video", "opacity")]["write"] is True
    assert by_property[("Text", "text/format/fontSize")]["increment_decrement"] is True
    assert by_property[("Camera", "cameraPatch")]["deprecated"] is True


def test_workspace_video_inventory_is_explicitly_read_only_or_blocked() -> None:
    inventory = extract_workspace_video_osc_inventory(DICTIONARY_PATH.read_text())
    by_property = {entry["property"]: entry for entry in inventory}

    assert len(inventory) == 118
    assert by_property["inputPatchList"]["mcp_status"] == "read_only"
    assert by_property["routes"]["mcp_status"] == "read_only"
    assert by_property["stage/{current_name}/name"]["mcp_status"] == "blocked"
    assert by_property["undo"]["kind"] == "action"
    assert by_property["undo"]["mcp_status"] == "blocked"


def test_video_phase1_matrix_documents_required_columns_and_blocked_families() -> None:
    matrix = (PROJECT_ROOT / "docs" / "current" / "coverage" / "video_phase1_osc_matrix.md").read_text()

    assert "| Area | Property | OSC path | Read | Write | Live | +/- | Deprecated | MCP status | Risk |" in matrix
    assert "`/cue/{cue_number}/cameraPatch`" in matrix
    assert "`/settings/video/undo`, `/redo`" in matrix
    assert "scalar rotation" in matrix
    assert "blocked; removed from Video/Camera registry" in matrix
