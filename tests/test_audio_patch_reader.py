from qlab_mcp import audio_patch_reader


WS = "11111111-1111-4111-8111-111111111111"
PATCH = "22222222-2222-4222-8222-222222222222"


class FakeReader:
    def __init__(self, details=None, overview=None, error=None):
        self.details = details
        self.overview = overview
        self.error = error
        self.detail_calls = []
        self.overview_calls = []

    def get_workspace_setting_details(self, **kwargs):
        self.detail_calls.append(kwargs)
        if self.error:
            raise ValueError(self.error)
        return self.details

    def get_workspace_settings(self, **kwargs):
        self.overview_calls.append(kwargs)
        if self.error:
            raise ValueError(self.error)
        return self.overview


def _saved(status="ready", patch=None, **extra):
    return {
        "status": status,
        "source": "saved_archive",
        "freshness": "possibly_stale",
        "document_modified": True,
        "sha256": "abc",
        "saved": {
            "workspace_id": WS,
            "output_patches": [patch] if patch else [],
            "input_patches": [],
            "audio_effects": [],
            "audio_effects_issues": [],
        },
        "device_observations": {
            "status": "not_requested", "source": "macos_coreaudio", "capture_started": False,
        },
        "issues": [],
        **extra,
    }


def test_exact_patch_keeps_osc_routing_separate_from_saved_matrix(monkeypatch):
    patch = {
        "id": PATCH,
        "patch_type": "output",
        "name": "Previous Main",
        "routing_matrix": {
            "cells": [
                {"row": 1, "column": 1, "initial_level": -3.0, "trim_level": 0.0},
                {"row": 2, "column": 4, "initial_level": -6.0, "trim_level": 1.0},
            ],
            "total_cells": 2,
            "truncated": False,
            "status": "available",
        },
        "cue_output_buses": [{"index": 1, "name": "Mix", "channels": 2}],
    }
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(patch=patch))
    reader = FakeReader(details={
        "ok": True, "status": "ok", "partial": False, "workspace_id": WS,
        "details": {"uniqueID": PATCH, "name": "Main", "routing": [1, 4],
                    "level": {"input_channel": 2, "output_channel": 4, "decibels": -6.0}},
        "errors": None, "redactions": [],
    })

    result = audio_patch_reader.read_audio_patch(
        reader, WS, "output", PATCH, input_channel=2, output_channel=4,
        cell_offset=0, cell_limit=1,
    )

    assert reader.detail_calls == [{
        "workspace_id": WS, "section": "audio", "kind": "output_patch", "ref": PATCH,
        "profile": "safe", "input_channel": 2, "output_channel": 4,
    }]
    assert result["sources"]["live_osc"]["data"]["routing"] == [1, 4]
    assert result["sources"]["saved_archive"]["data"]["routing_matrix"]["cells"] == [
        {"row": 1, "column": 1, "initial_level": -3.0, "trim_level": 0.0}
    ]
    assert result["cell"]["live_osc"]["data"]["decibels"] == -6.0
    assert result["cell"]["saved_archive"]["data"] == {
        "row": 2, "column": 4, "initial_level": -6.0, "trim_level": 1.0,
    }
    assert result["sources"]["saved_archive"]["freshness"] == "possibly_stale"
    assert result["sources"]["saved_archive"]["data"]["cue_output_buses"] == [
        {"index": 1, "name": "Mix", "channels": 2}
    ]
    assert result["source_status"]["atomic_snapshot"] is False
    assert result["comparison"]["status"] == "not_comparable"
    assert result["comparison"]["differences"] == []


def test_patch_name_comparison_uses_persisted_osc_name_property():
    compare = audio_patch_reader._compare_patch_names

    assert compare(
        {"name": "Patch 1 - System Output - Speakers - (2 Out)", "name_property": "Patch 1"},
        {"name": "Patch 1"},
    )["status"] == "matches_observed_fields"
    difference = compare(
        {"name": "Renamed - System Output - Speakers - (2 Out)", "name_property": "Renamed"},
        {"name": "Patch 1"},
    )
    assert difference["status"] == "differs"
    assert difference["differences"] == [{
        "field": "name", "live_osc": "Renamed", "saved_archive": "Patch 1",
    }]


def test_patch_read_returns_saved_data_when_osc_read_fails(monkeypatch):
    saved_patch = {"id": PATCH, "patch_type": "input", "name": "Mic"}
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(
        patch=None, saved={"workspace_id": WS, "output_patches": [], "input_patches": [saved_patch]},
    ))
    reader = FakeReader(error="OSC unavailable")

    result = audio_patch_reader.read_audio_patch(reader, WS, "input", PATCH)

    assert result["ok"] is True
    assert result["partial"] is True
    assert result["sources"]["live_osc"]["status"] == "unavailable"
    assert result["sources"]["saved_archive"]["data"] == saved_patch
    assert result["errors"]["live_osc"] == ["OSC unavailable"]


def test_unavailable_live_result_does_not_expose_partial_details(monkeypatch):
    saved_patch = {
        "id": PATCH, "patch_type": "output", "name": "Saved Main",
        "routing_matrix": {
            "cells": [{"row": 1, "column": 1, "initial_level": -3.0, "trim_level": 0.0}],
            "total_cells": 1, "truncated": False, "status": "available",
        },
    }
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(patch=saved_patch))
    reader = FakeReader(details={
        "ok": False, "status": "error", "partial": True,
        "details": {"uniqueID": PATCH, "name": "Incomplete Live", "level": {
            "input_channel": 1, "output_channel": 1, "decibels": -9.0,
        }},
        "errors": {"audio.patch": "Patch detail read was incomplete."},
    })

    result = audio_patch_reader.read_audio_patch(
        reader, WS, "output", PATCH, input_channel=1, output_channel=1,
    )

    assert result["sources"]["live_osc"]["status"] == "unavailable"
    assert result["sources"]["live_osc"]["data"] is None
    assert result["comparison"]["status"] == "not_comparable"
    assert result["cell"]["live_osc"] == {"status": "unavailable", "data": None}
    assert result["cell"]["saved_archive"]["data"] == saved_patch["routing_matrix"]["cells"][0]


def test_audio_patch_returns_bounded_passive_devices_separately(monkeypatch):
    saved_patch = {"id": PATCH, "patch_type": "output", "name": "Main"}
    observations = {
        "source": "macos_coreaudio", "status": "ready", "output_status": "ready",
        "observed_at": "2026-11-12T12:00:00Z", "capture_started": False,
        "devices": [{"id": index, "uid": f"device-{index}", "name": f"Device {index}",
                     "output_channels": 2} for index in range(audio_patch_reader.MAX_DEVICE_OBSERVATIONS + 3)],
        "default_output_id": 0,
    }
    observations["devices"][0]["uid"] = "u" * 512
    observations["devices"][1]["uid"] = "u" * 513
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(
        patch=saved_patch, device_observations=observations,
    ))
    reader = FakeReader(details={
        "ok": True, "details": {"uniqueID": PATCH, "name": "Main"},
    })

    result = audio_patch_reader.read_audio_patch(reader, WS, "output", PATCH)

    devices = result["device_observations"]
    assert devices["source"] == "macos_coreaudio" and devices["status"] == "ready"
    assert devices["capture_started"] is False
    assert devices["device_count"] == audio_patch_reader.MAX_DEVICE_OBSERVATIONS + 3
    assert devices["returned_devices"] == audio_patch_reader.MAX_DEVICE_OBSERVATIONS
    assert devices["devices_truncated"] is True
    assert len(devices["devices"]) == audio_patch_reader.MAX_DEVICE_OBSERVATIONS
    assert devices["devices"][0]["uid"] == "u" * 512
    assert "uid" not in devices["devices"][1]
    assert devices["devices"][1]["uid_over_limit"] is True
    assert "device_observations" not in result["sources"]["saved_archive"]
    assert "signal" in devices["scope"] and "playback" in devices["scope"]


def test_device_observation_not_requested_survives_overview(monkeypatch):
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(
        patch={"id": PATCH, "patch_type": "output", "name": "Main"},
    ))
    reader = FakeReader(overview={
        "ok": True, "partial": False,
        "sections": {"audio": {"output_patches": [], "input_patches": []}},
    })

    result = audio_patch_reader.read_audio_overview(reader, WS)

    assert result["device_observations"]["source"] == "macos_coreaudio"
    assert result["device_observations"]["status"] == "not_requested"
    assert result["source_status"]["field_provenance"]["device_observations"] == "macos_coreaudio"


def test_overview_pages_both_sources_and_omits_matrix_cells(monkeypatch):
    saved_output = [
        {"id": PATCH, "patch_type": "output", "name": "Main",
         "routing_matrix": {"cells": [{"row": 1, "column": 1}], "total_cells": 1,
                            "truncated": False, "status": "available"},
         "cue_output_buses": [{"index": index, "name": f"Bus {index}", "channels": 2}
                              for index in range(256)],
         "device_output_buses": [{"index": index, "name": f"Device bus {index}", "channels": 2}
                                 for index in range(256)]},
        {"id": "33333333-3333-4333-8333-333333333333", "patch_type": "output", "name": "Alt",
         "routing_matrix": {"cells": [], "total_cells": 0, "truncated": False, "status": "available"}},
    ]
    archive = _saved(patch=None, saved={"workspace_id": WS, "output_patches": saved_output, "input_patches": []})
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: archive)
    reader = FakeReader(overview={
        "ok": True, "status": "ok", "partial": False, "workspace_id": WS,
        "sections": {"audio": {"output_patches": [
            {"uniqueID": PATCH, "name": "Main", "routing": [1]},
            {"uniqueID": "33333333-3333-4333-8333-333333333333", "name": "Alt", "routing": [2]},
        ], "input_patches": []}},
        "errors": None,
    })

    result = audio_patch_reader.read_audio_overview(reader, WS, offset=0, limit=1)

    assert reader.overview_calls == [{"workspace_id": WS, "mode": "summary", "sections": ["audio"], "profile": "safe"}]
    assert result["sources"]["live_osc"]["data"]["output_patches"][0]["name"] == "Main"
    saved_page = result["sources"]["saved_archive"]["data"]["output_patches"][0]
    assert saved_page["name"] == "Main"
    assert saved_page["routing_matrix"]["cells"] == []
    assert saved_page["cue_output_bus_count"] == 256
    assert saved_page["device_output_bus_count"] == 256
    assert "cue_output_buses" not in saved_page
    assert "device_output_buses" not in saved_page
    assert result["pagination"]["sources"]["saved_archive"]["output_patches"]["truncated"] is True


def test_patch_read_rejects_non_uuid_without_reading_sources(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("invalid target must be rejected before either source is read")

    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", unexpected)
    reader = FakeReader()

    try:
        audio_patch_reader.read_audio_patch(reader, WS, "output", "Main")
    except ValueError as exc:
        assert "UUID" in str(exc)
    else:
        raise AssertionError("non-UUID patch target was accepted")
    assert reader.detail_calls == []


def test_capped_saved_matrix_does_not_offer_unreachable_next_offset(monkeypatch):
    patch = {
        "id": PATCH, "patch_type": "output", "name": "Main",
        "routing_matrix": {
            "cells": [{"row": index // 128, "column": index % 128,
                       "initial_level": -1.0, "trim_level": 0.0} for index in range(4096)],
            "total_cells": 5000, "truncated": True, "status": "available",
        },
    }
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(patch=patch))
    reader = FakeReader(details={
        "ok": True, "status": "ok", "partial": False,
        "details": {"uniqueID": PATCH, "name": "Main"},
    })

    result = audio_patch_reader.read_audio_patch(
        reader, WS, "output", PATCH, input_channel=32, output_channel=0,
        cell_offset=4096, cell_limit=10,
    )

    assert result["pagination"]["matrix_cells"]["truncated"] is True
    assert result["pagination"]["matrix_cells"]["source_truncated"] is True
    assert result["pagination"]["matrix_cells"]["next_offset"] is None
    assert result["cell"]["saved_archive"]["status"] == "not_observed_in_incomplete_matrix"


def test_overview_does_not_turn_missing_patch_fields_into_empty_inventory(monkeypatch):
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: {
        "status": "unavailable", "source": "saved_archive", "freshness": "unavailable",
        "saved": {}, "issues": ["No saved document."],
    })
    reader = FakeReader(overview={
        "ok": True, "status": "ok", "partial": False,
        "sections": {"audio": {"max_volume": 12.0}},
    })

    result = audio_patch_reader.read_audio_overview(reader, WS)

    assert "output_patches" not in result["sources"]["live_osc"]["data"]
    assert result["pagination"]["sources"]["live_osc"]["output_patches"]["known"] is False
    assert result["sources"]["saved_archive"]["data"] is None
    assert result["device_observations"]["status"] == "unavailable"


def test_overview_does_not_compare_audio_from_unavailable_live_result(monkeypatch):
    saved_patch = {"id": PATCH, "patch_type": "output", "name": "Saved Main"}
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(patch=saved_patch))
    reader = FakeReader(overview={
        "ok": False, "partial": True, "errors": {"audio": "Audio overview was incomplete."},
        "sections": {"audio": {"output_patches": [
            {"uniqueID": PATCH, "name": "Unverified Live Name"},
        ], "input_patches": []}},
    })

    result = audio_patch_reader.read_audio_overview(reader, WS)

    assert result["sources"]["live_osc"]["status"] == "unavailable"
    assert result["sources"]["live_osc"]["data"] is None
    assert result["comparison"]["status"] == "not_comparable"
    assert result["pagination"]["sources"]["live_osc"]["output_patches"]["known"] is False


def test_overview_accepts_real_workspace_settings_payload_without_ok(monkeypatch):
    saved_patch = {"id": PATCH, "patch_type": "output", "name": "Main"}
    monkeypatch.setattr(audio_patch_reader, "read_saved_audio_patches", lambda *a, **k: _saved(patch=saved_patch))
    reader = FakeReader(overview={
        "status": "ok", "partial": False,
        "sections": {"audio": {"output_patches": [
            {"uniqueID": PATCH, "name": "Main"},
        ], "input_patches": []}},
        "errors": None,
    })

    result = audio_patch_reader.read_audio_overview(reader, WS)

    assert result["sources"]["live_osc"]["status"] == "available"
    assert result["sources"]["live_osc"]["data"]["output_patches"][0]["name"] == "Main"
    assert result["comparison"]["status"] == "matches_observed_fields"
