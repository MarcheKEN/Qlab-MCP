"""Saved video archive reads use synthetic keyed archives, not a user workspace."""
from copy import deepcopy
import hashlib
import plistlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from qlab_mcp.light_patch.archive import Archive
from qlab_mcp.models import WorkspaceVideoSettingsResult
from qlab_mcp import video_settings as module
from test_light_patch_archive import workspace

WS = "11111111-1111-4111-8111-111111111111"


def video_workspace(*, version="5.5.10", broken=False, unknown=False, cycle=False):
    outer = Archive(workspace())

    def obj(class_name, **fields):
        return outer.add({"$class": outer.cls(class_name), **fields})

    def uuid(value):
        return obj("NSUUID", **{"NS.uuidbytes": UUID(value).bytes})

    route_id = "22222222-2222-4222-8222-222222222222"
    stage_id = "33333333-3333-4333-8333-333333333333"
    viewport_id = "44444444-4444-4444-8444-444444444444"
    region_id = "55555555-5555-4555-8555-555555555555"
    missing_route_id = "66666666-6666-4666-8666-666666666666"
    route_info = outer.make_dict({
        "destinationType": "NDI", "name": "NDI", "videoOutputKeyPath": "ndi.NDI",
        "videoOutputRasterSize": "{1920, 1080}",
    })
    route = obj("F53VideoOutputRoute", uniqueID=route_id, name="Output 1",
                destinationInfo=route_info, naturalSize="{1920, 1080}",
                rotationDegrees=0, scalingMode=2, rear=False,
                layoutWide=1, layoutHigh=1, layoutIndex=0, guidelineMode=15)
    stage = obj("VideoStage", uniqueID=stage_id, name="Main", width=640, height=360,
                keepRendering=True, gridIsDark=False, gridBypassesEdgeBlends=False,
                viewport=plistlib.UID(0), regions=plistlib.UID(0))
    viewport = obj("VideoStageViewport", uniqueID=viewport_id, name="main", stage=stage,
                   boundsOnStage="{{0, 0}, {640, 360}}", layer=1000, audition=False,
                   maskAlias=plistlib.UID(0))
    bookmark = obj("NSData", **{"NS.data": b"private-bookmark-bytes"})
    alias = obj("F53Alias", bookmark=bookmark, lastKnownPath="/private/tmp/mask.png",
                lastKnownRelativePath="mask.png")
    outer.ref(viewport)["maskAlias"] = alias
    point = obj("VideoStageRegionControlPoint", region=plistlib.UID(0),
                linkID=uuid("77777777-7777-4777-8777-777777777777"),
                outputPoint="{1.5, 2.5}", pristine=False)
    region_route = plistlib.UID(0) if broken else route
    if broken:
        region_route = obj("F53VideoOutputRoute", uniqueID=missing_route_id, name="Missing")
    region = obj("VideoStageRegion", uniqueID=uuid(region_id), stage=stage,
                 route=region_route, boundsOnStage="{{0, 0}, {640, 360}}",
                 initialBoundsOnRoute="{{0, 0}, {1920, 1080}}", warpType=3,
                 meshWidth=1, meshHeight=1, autoEdgeBlends=True,
                 edgeBlendTopPixels=0.0, edgeBlendRightPixels=0.0,
                 edgeBlendBottomPixels=0.0, edgeBlendLeftPixels=0.0,
                 edgeBlendCenterLuminance=0.5, edgeBlendPower=2.0, edgeBlendGamma=0.8,
                 controlPoints=outer.make_array([point]), shadowControlPoints=plistlib.UID(0),
                 meshSubregions=outer.make_array([]))
    outer.ref(point)["region"] = region
    if cycle:
        outer.ref(region)["meshSubregions"] = outer.make_array([region])
    outer.ref(stage)["viewport"] = viewport
    outer.ref(stage)["regions"] = outer.make_array([region])
    destination = obj("F53VideoOutputDestinationNDI", virtualID="88888888-8888-4888-8888-888888888888",
                      name="NDI", size="{1920, 1080}", refreshRate=30.0,
                      pixelFormat=1111970369, audioChannels=2, audioSampleRate=48000.0,
                      audioBufferSize=512)
    description = outer.make_dict({"type": "AVCaptureDevice", "name": "Camera",
                                   "uniqueID": "camera-1", "config": outer.make_dict({})})
    camera_patch = obj("CameraPatch", uniqueID="99999999-9999-4999-8999-999999999999",
                       name="Camera Input", serializedDescription=description)
    video = outer.make_dict({"stages": outer.make_array([stage]), "routes": outer.make_array([route]),
                             "virtualDestinations": outer.make_array([destination]),
                             "virtualOutputID": "88888888-8888-4888-8888-888888888888"})
    camera = outer.make_dict({"cameraPatches": outer.make_array([camera_patch])})
    root = outer.data["$top"]["root"]
    meta = outer.mapping(root)
    settings = outer.ref(meta["settings"])
    for key, value in (("Video", video), ("Camera", camera)):
        settings["NS.keys"].append(outer.add(key))
        settings["NS.objects"].append(value)
    if version != "5.5.10":
        replacement = outer.replacing_mapping(root, "QLabShortVersionString", outer.add(version))
        outer.data["$top"]["root"] = replacement
        outer.root = outer.ref(replacement)
    if unknown:
        outer.ref(stage)["unexpected"] = "keep-readable"
    return outer.dump()


def live(*, ok=True):
    return dict(ok=ok, status="ok" if ok else "error", partial=not ok,
                workspace_id=WS, domain="video", profile="safe", view="overview",
                data={"overview": {
                    "stages": [{"uniqueID": "33333333-3333-4333-8333-333333333333",
                                "name": "Main", "size": {"width": 640, "height": 360}}] if ok else None,
                    "routes": [{"uniqueID": "22222222-2222-4222-8222-222222222222",
                                "name": "Output 1", "destination_type": "NDI"}] if ok else None,
                    "input_patches": [{"uniqueID": "99999999-9999-4999-8999-999999999999",
                                        "name": "Camera Input - USB Camera"}] if ok else None,
                    "problems": [],
                }} if ok else None)


@pytest.fixture
def local(tmp_path, monkeypatch):
    path = tmp_path / "sample.qlab5"
    path.write_bytes(video_workspace())
    row = dict(workspace_id=WS, path=str(path), modified=False, edit_mode=True,
               show_mode=False, active_cue_ids=[])
    calls = []

    def inventory(reader, *, running_bundle=False):
        assert running_bundle is True
        calls.append("inventory")
        return {"documents": [deepcopy(row)]}

    monkeypatch.setattr(module.docs, "_inventory", inventory)
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    return reader, path, row, calls


def test_inspect_saved_video_decodes_shared_ids_mesh_masks_and_descriptors():
    saved = module.inspect_saved_video(video_workspace())
    stage = saved["stages"][0]
    region = stage["regions"][0]
    assert saved["coverage"] == "complete"
    assert (stage["width"], stage["height"]) == (640, 360)
    assert region["stage_id"] == stage["id"]
    assert region["route_id"] == saved["routes"][0]["id"]
    assert region["control_points"][0]["link_id"] == "77777777-7777-4777-8777-777777777777"
    assert stage["viewport"]["mask_alias"] == {
        "class_name": "F53Alias", "last_known_path": "/private/tmp/mask.png",
        "relative_path": "mask.png", "bookmark_present": True,
    }
    assert saved["routes"][0]["destination_ids"] == []
    assert saved["routes"][0]["destination_candidates"] == [saved["destinations"][0]["id"]]
    assert saved["routes"][0]["destination_match"] == "type_name_candidate_not_identity_verified"
    assert saved["inputs"][0]["descriptor"]["type"] == "AVCaptureDevice"


def test_unknown_and_broken_references_are_diagnostics_not_read_failures():
    saved = module.inspect_saved_video(video_workspace(broken=True, unknown=True, cycle=True))
    codes = {row["code"] for row in saved["diagnostics"]}
    assert saved["coverage"] == "partial"
    assert {"unknown_fields", "broken_route_reference", "mesh_cycle"} <= codes
    assert saved["stages"] and saved["routes"] and saved["diagnostics"]


def test_unsupported_version_fails_closed():
    with pytest.raises(ValueError, match="5.5.10/build 5510"):
        module.inspect_saved_video(video_workspace(version="5.6.0"))


def test_clean_read_is_read_only_and_compares_only_shared_input_uuid(local):
    reader, path, _, calls = local
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = module.enrich_video_settings(reader, WS, live())
    saved = result["data"]["saved_video"]
    assert saved["status"] == "ready" and saved["sha256"] == before
    assert result["data"]["source_status"]["comparison"] == "matches_observable_fields"
    assert calls == ["inventory", "inventory"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    validated = WorkspaceVideoSettingsResult.model_validate(result)
    assert validated.data.saved_video.stages[0].regions[0]["warp_type"] == 3
    assert validated.data.saved_video.process_inventory == "not_in_saved_workspace_archive"


def test_dirty_read_keeps_osc_and_saved_sources_separate(local):
    reader, _, row, _ = local
    row["modified"] = True
    current = live()
    current["data"]["overview"]["stages"][0]["name"] = "Unsaved name"
    result = module.enrich_video_settings(reader, WS, current)
    assert result["data"]["saved_video"]["freshness"] == "possibly_stale"
    assert result["data"]["saved_video"]["stages"][0]["name"] == "Main"
    assert result["data"]["overview"]["stages"][0]["name"] == "Unsaved name"
    assert result["data"]["source_status"]["comparison"] == "differs"


def test_remote_or_missing_automation_keeps_osc_only(local, monkeypatch):
    _, _, _, _ = local
    remote = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="10.0.0.2")))
    result = module.enrich_video_settings(remote, WS, live())
    assert result["ok"] and result["partial"]
    assert result["data"]["saved_video"]["status"] == "unavailable"
    monkeypatch.setattr(module.docs, "_inventory", lambda reader, **kwargs: (_ for _ in ()).throw(ValueError("Automation permission unavailable")))
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    result = module.enrich_video_settings(reader, WS, live())
    assert result["data"]["saved_video"]["status"] == "unavailable"
    assert result["data"]["overview"]["stages"]


def test_archive_only_read_survives_osc_failure(local):
    reader, _, _, _ = local
    result = module.enrich_video_settings(reader, WS, live(ok=False))
    assert result["ok"] and result["partial"] and result["status"] == "partial"
    assert result["data"]["saved_video"]["status"] == "ready"
    assert result["data"]["source_status"]["comparison"] == "not_comparable"


@pytest.mark.parametrize("change", ["document", "file"])
def test_concurrent_change_discards_enrichment(local, monkeypatch, change):
    reader, _, row, _ = local
    original = module._read_file
    reads = []

    def read(path):
        value = original(path)
        reads.append(True)
        if len(reads) == 1 and change == "document":
            row["modified"] = True
        if len(reads) == 2 and change == "file":
            return value[0] + b"changed", value[1]
        return value

    monkeypatch.setattr(module, "_read_file", read)
    result = module.enrich_video_settings(reader, WS, live())
    assert result["data"]["saved_video"]["status"] == "changed_during_read"
    assert not result["data"]["saved_video"]["stages"]
    assert result["data"]["overview"]["stages"]


def test_thousand_records_have_exact_followup(monkeypatch):
    records = [dict(id=f"{i:08X}-1111-4111-8111-111111111111", name=f"Stage {i}",
                    class_name="VideoStage", width=100, height=100, regions=[], viewport=None)
               for i in range(1001)]
    saved = dict(status="ready", source="saved_archive", freshness="last_saved", coverage="complete",
                 workspace_id=WS, version="5.5.10", build=5510, diagnostics=[], stages=records,
                 routes=[], inputs=[], destinations=[])
    monkeypatch.setattr(module, "_saved", lambda *_: deepcopy(saved))
    result = module.enrich_video_settings(None, WS, live())
    assert len(result["data"]["saved_video"]["stages"]) == 1000
    request = result["data"]["pagination"]["next_requests"][0]
    assert request == dict(workspace_id=WS, section="stages", offset=1000, limit=1000)
    second = module.enrich_video_settings(None, WS, live(), **{k: v for k, v in request.items() if k != "workspace_id"})
    assert second["data"]["saved_video"]["stages"][0]["name"] == "Stage 1000"


def test_byte_budget_reduces_page_and_keeps_model_under_limit(monkeypatch):
    records = [dict(id=f"{i:08X}-1111-4111-8111-111111111111", name=f"Route {i}",
                    class_name="F53VideoOutputRoute", fields={"opaque_known_text": "x" * 65536})
               for i in range(40)]
    saved = dict(status="ready", source="saved_archive", freshness="last_saved", coverage="complete",
                 workspace_id=WS, version="5.5.10", build=5510, diagnostics=[], stages=[],
                 routes=records, inputs=[], destinations=[])
    monkeypatch.setattr(module, "_saved", lambda *_: deepcopy(saved))
    result = module.enrich_video_settings(None, WS, live(), section="routes")
    validated = WorkspaceVideoSettingsResult.model_validate(result)
    assert len(validated.model_dump_json().encode()) <= module.MAX_RESPONSE_BYTES
    assert result["data"]["pagination"]["effective_limit"] < 1000
    assert result["data"]["pagination"]["next_requests"]


def test_unsupported_archive_keeps_osc(local):
    reader, path, _, _ = local
    path.write_bytes(b"not a keyed archive")
    result = module.enrich_video_settings(reader, WS, live())
    assert result["ok"] and result["partial"]
    assert result["data"]["saved_video"]["status"] == "unsupported_format"
    assert result["data"]["overview"]["stages"]


def test_saved_uuid_mismatch_discards_archive(local, monkeypatch):
    reader, _, _, _ = local
    original = module.inspect_saved_video
    def changed(source):
        result = original(source)
        result['workspace_id'] = 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA'
        return result
    monkeypatch.setattr(module, 'inspect_saved_video', changed)
    result = module.enrich_video_settings(reader, WS, live())
    assert result['data']['saved_video']['status'] == 'unavailable'
    assert result['data']['saved_video']['stages'] == []
    assert result['data']['overview']['stages']


def test_oversized_stage_reports_live_detail_recovery_limit(monkeypatch):
    saved = dict(status='ready', source='saved_archive', freshness='last_saved', coverage='complete',
                 stages=[dict(id='33333333-3333-4333-8333-333333333333', name='Main',
                              viewport={'layer':1000}, regions=[{'known_text':'x' * (3 * 1024 * 1024)}])],
                 routes=[], inputs=[], destinations=[], diagnostics=[])
    monkeypatch.setattr(module, '_saved', lambda *_: deepcopy(saved))
    result = module.enrich_video_settings(None, WS, live(), section='stages')
    assert len(WorkspaceVideoSettingsResult.model_validate(result).model_dump_json().encode()) <= module.MAX_RESPONSE_BYTES
    pagination = result['data']['pagination']
    assert pagination['truncated']
    omitted = pagination['omitted_records'][0]
    assert omitted['recover_with']['tool'] == 'qlab_get_video_stage'
    assert omitted['stage_header']['viewport']['layer'] == 1000
    assert 'sha256' in omitted['recovery_limit']


def detail_result(kind="stage", ok=True):
    return dict(ok=ok, status="ok" if ok else "error", partial=not ok,
                workspace_id=WS, domain="video", view=kind, profile="safe", data={})


def test_stage_detail_geometry_pages_reconstruct_saved_tree(local):
    reader, path, row, _ = local
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    stage = module.inspect_saved_video(path.read_bytes())["stages"][0]
    entries = []
    offset = 0
    while True:
        result = module.enrich_video_detail(reader, WS, detail_result(), stage["id"], "stage", offset, 3, original_hash)
        page = result["data"]
        entries.extend(page["saved_video"]["stages"][0]["geometry_entries"])
        requests = page["pagination"]["next_requests"]
        if not requests:
            break
        assert requests[0]["expected_sha256"] == original_hash
        offset = requests[0]["offset"]
    for entry in entries:
        value = stage
        for part in entry["path"]:
            value = value[part]
        assert value == entry["value"]
    assert any("mesh_subregions" in entry["path"] for entry in entries)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert not row["modified"]


def test_stage_detail_changed_snapshot_and_dirty_preparation(local):
    reader, _, row, _ = local
    row["modified"] = True
    stage_id = "33333333-3333-4333-8333-333333333333"
    result = module.enrich_video_detail(reader, WS, detail_result(), stage_id, "stage")
    assert result["data"]["saved_video"]["preparation"]["status"] == "needs_save"
    assert "Explicitly save" in result["warnings"][0]
    changed = module.enrich_video_detail(reader, WS, detail_result(), stage_id, "stage", expected_sha256="old")
    assert changed["partial"]
    assert changed["data"]["saved_video"]["status"] == "changed_between_pages"
    assert changed["data"]["saved_video"]["stages"] == []


def test_route_saved_only_and_exact_identity(local):
    reader, _, _, _ = local
    result = module.enrich_video_detail(reader, WS, detail_result("route", False),
                                        "22222222-2222-4222-8222-222222222222", "route")
    assert result["ok"] and result["partial"]
    assert result["data"]["saved_video"]["routes"][0]["name"] == "Output 1"
    missing = module.enrich_video_detail(reader, WS, detail_result("route"),
                                        "66666666-6666-4666-8666-666666666666", "route")
    assert missing["data"]["saved_video"]["routes"] == []
    assert missing["data"]["saved_video"]["status"] == "object_not_in_saved_archive"


def test_stage_detail_byte_budget_is_enforced(local, monkeypatch):
    reader, _, _, _ = local
    original = module._saved
    def huge(*args):
        saved = original(*args)
        saved["stages"][0]["regions"][0]["name"] = "x" * (3 * 1024 * 1024)
        return saved
    monkeypatch.setattr(module, "_saved", huge)
    offset = 0
    while True:
        result = module.enrich_video_detail(reader, WS, detail_result(),
                                            "33333333-3333-4333-8333-333333333333", "stage", offset)
        if not result["ok"]:
            break
        from qlab_mcp.models import VideoStageResult
        assert len(VideoStageResult.model_validate(result).model_dump_json().encode()) <= module.MAX_RESPONSE_BYTES
        request = result["data"]["pagination"]["next_requests"][0]
        assert request["offset"] > offset
        offset = request["offset"]
    assert result["error_code"] == "response_too_large"
    assert result["data"] is None


def test_stage_readable_geometry_preserves_codes_and_matches_ui():
    stage = module.inspect_saved_video(video_workspace())["stages"][0]
    region = stage["regions"][0]
    assert region["warp_type"] == 3
    assert region["warp_type_name"] == "Perspective"
    assert region["ui_coordinates"]["lower_left"] == [-320, -180]
    assert region["ui_coordinates"]["upper_right"] == [320, 180]
    assert region["ui_coordinates"]["source"] == "saved_archive"


def test_stage_inspection_bounds_reads_and_reports_missing_visibility():
    calls = []
    def read(ws, command, errors, key):
        calls.append(command)
        if command.endswith('/enableGuide'):
            errors[key] = 'timeout'
            return None
        return False
    reader = SimpleNamespace(_read_workspace_setting=read)
    regions = [dict(uniqueID=str(UUID(int=i + 1)), route=dict(uniqueID=str(UUID(int=100)))) for i in range(17)]
    saved = dict(status='ready', coverage='complete', document_modified=True, freshness='possibly_stale')
    inspection = module._stage_inspection(reader, WS, str(UUID(int=200)), dict(regions=regions), saved)
    assert len(calls) == 33  # two reads per region, one per shared route
    assert all("stageID/" + str(UUID(int=200)).upper() in c for c in calls if "/regionID/" in c)
    assert inspection['visibility']['status'] == 'partial'
    assert len(inspection['visibility']['next_requests']) == 17
    assert inspection['visibility']['regions'][0]['enableGrid'] is False
    assert inspection['visibility']['regions'][0]['enableGuide'] is None
    assert inspection['preparation']['status'] == 'needs_save'
    assert inspection['sources']['saved']['document_modified'] is True
    assert inspection['atomic_snapshot'] is False


@pytest.mark.parametrize(('code', 'label'), [(1, 'Linear'), (2, 'Bézier'), (3, 'Perspective'), (99, 'unknown')])
def test_warp_variants_preserve_nested_linked_points(code, label):
    archive = Archive(video_workspace())
    region = next(x for x in archive.objects if isinstance(x, dict) and x.get('warpType') == 3)
    region['warpType'] = code
    child = deepcopy(region)
    child['uniqueID'] = archive.add('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
    child['meshSubregions'] = archive.make_array([])
    child['shadowControlPoints'] = region['controlPoints']
    region['meshSubregions'] = archive.make_array([archive.add(child)])
    stage = module.inspect_saved_video(archive.dump())['stages'][0]
    decoded = stage['regions'][0]
    assert decoded['warp_type'] == code
    assert decoded['warp_type_name'] == label
    nested = decoded['mesh_subregions'][0]
    assert nested['control_points'][0]['link_id'] == decoded['control_points'][0]['link_id']
    assert nested['shadow_control_points'][0]['output_point']['components'] == [1.5, 2.5]


@pytest.mark.parametrize("field", ["enableGrid", "enableGuide"])
def test_region_visibility_payload_requires_a_real_boolean(field):
    from qlab_mcp.settings.workspace import _validate_workspace_setting_payload
    command = f"video/stageID/{WS}/regionID/{WS}/{field}"
    assert _validate_workspace_setting_payload(command, False)
    assert _validate_workspace_setting_payload(command, True)
    assert not _validate_workspace_setting_payload(command, 0)
    assert not _validate_workspace_setting_payload(command, {})



def test_stage_inspection_time_budget_never_retries(monkeypatch):
    clock = iter([0, 9, 10])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(clock))
    def forbidden(*args):
        raise AssertionError('No query should start after the scheduling deadline')
    region = dict(uniqueID=str(UUID(int=10)))
    result = module._stage_inspection(SimpleNamespace(_read_workspace_setting=forbidden),
        WS, WS, dict(regions=[region]), dict(status='unavailable'))
    assert result['visibility']['status'] == 'partial'
    assert len(result['visibility']['errors']) == 2
    assert len(result['visibility']['next_requests']) == 1
    assert result['preparation']['status'] == 'saved_source_unavailable'


def test_rectangular_warping_center_and_unsupported_geometry():
    from qlab_mcp.video_settings import _region_center
    region = dict(warp_type=3, mesh_width=1, mesh_height=1, shadow_control_points=[],
                  control_points=[dict(output_point=dict(components=list(p))) for p in
                                  [(350, 0), (700, 0), (350, 477), (700, 477)]])
    route = dict(natural_size=dict(components=[2940, 1912]))
    assert _region_center(region, route)["value"] == [-945, -717.5]
    assert _region_center(region, None)["status"] == "unavailable"
    region["control_points"][0]["output_point"]["components"] = [351, 0]
    assert _region_center(region, route)["status"] == "available"
    region["warp_type"] = 2
    assert _region_center(region, route)["status"] == "unavailable"


def test_native_guideline_tags_and_invalid_values():
    expected = [f"{x}×{y}" for y in range(1, 5) for x in range(1, 5)]
    assert [module._guideline_grid(tag)["label"] for tag in range(16)] == expected
    for value in (None, True, False, -1, 16, 15.0, "15"):
        assert module._guideline_grid(value) is None


def test_stage_keeps_only_shared_assigned_routes_and_labels(local, monkeypatch):
    reader, path, _, _ = local
    saved = module.inspect_saved_video(path.read_bytes())
    original_route = saved["routes"][0]
    unused = deepcopy(original_route)
    unused["id"] = "66666666-6666-4666-8666-666666666666"
    saved["routes"].append(unused)
    stage = saved["stages"][0]
    stage["regions"].append(deepcopy(stage["regions"][0]))
    saved.update(status="ready", freshness="last_saved", document_modified=False)
    monkeypatch.setattr(module, "_saved", lambda *args: saved)
    result = module.enrich_video_detail(reader, WS, detail_result(), stage["id"], "stage")
    from qlab_mcp.models import VideoStageResult
    data = VideoStageResult.model_validate(result).model_dump()["data"]
    assert [r["id"] for r in data["saved_video"]["routes"]] == [original_route["id"]]
    assert data["saved_video"]["routes"][0]["guideline_grid"] == dict(width=4, height=4, label="4×4")
    assert data["saved_video"]["stages"][0]["viewport"]["layer_label"] == "top"
    coverage = data["inspection"]["coverage"]
    assert coverage["reader_executes_actions"] is False
    assert "crop_pad" in coverage["actions"]["resize"]
    assert "layout_aspect_lock_state" in coverage["ui_only"]
    assert "layout_aspect_lock_state" not in coverage["unverified"]


def test_warp_point_interpolation_and_mesh_selection():
    def region(kind, points, **extra):
        return dict(warp_type=kind, control_points=[dict(output_point=dict(components=p)) for p in points], **extra)
    corners = [[0, 0], [8, 0], [0, 4], [4, 4]]
    assert module._warp_point(region(1, corners), .5, .5) == pytest.approx([3, 2])
    assert module._warp_point(region(3, corners), .5, .5) == pytest.approx([8/3, 8/3])
    bezier = [[x, y] for y in range(4) for x in range(4)]
    assert module._warp_point(region(2, bezier), .25, .75) == pytest.approx([.75, 2.25])
    assert module._warp_point(region(3, corners, shadow_control_points=[dict(output_point=dict(components=p)) for p in bezier]), .25, .75) == pytest.approx([.75, 2.25])
    parent = region(3, corners, mesh_width=2, mesh_height=2,
                    mesh_subregions=[region(1, [[i, i]]*4) for i in range(4)])
    assert module._warp_point(parent, .5, .5) == [3, 3]
    assert module._warp_point(parent, 1, 1) == [3, 3]
    with pytest.raises(ValueError):
        module._warp_point(region(99, corners), .5, .5)
    with pytest.raises(ValueError):
        module._warp_point(region(3, [[0, 0]]*4), .5, .5)
    parent['mesh_subregions'].pop()
    with pytest.raises(ValueError):
        module._warp_point(parent, .5, .5)


def test_native_deformed_stage_midpoint_samples():
    route = dict(natural_size=dict(components=[2940, 1912]))
    def controls(points):
        return [dict(output_point=dict(components=p)) for p in points]
    child = dict(warp_type=1, control_points=controls([[350, 0], [700, 0], [350, 394], [740, 440]]))
    parent = dict(warp_type=1, mesh_width=1, mesh_height=1, mesh_subregions=[child])
    assert module._region_center(parent, route)['value'] == pytest.approx([-935, -747.5])
    child['warp_type'] = 3
    assert module._region_center(parent, route)['value'] == pytest.approx([-945.1933953065072, -758.7822921406748])
    xs = [350, 466.66141666666675, 583.3385833333331, 700]
    ys = [0, 131.3274233333333, 262.6725766666667, 394]
    points = [[x, y] for y in ys for x in xs]
    points[5] = [500, 180]
    child.update(warp_type=2, control_points=controls(points))
    center = module._region_center(parent, route)
    assert center['value'] == pytest.approx([-940.3117617187501, -752.15541890625])
    assert center['native_validation'] == 'sampled_linear_perspective_bezier_and_divided_meshes'


def test_virtual_destination_references_are_per_object_and_snapshot_bound():
    source = video_workspace()
    a = Archive(source)
    meta = a.mapping(a.root)
    settings = a.mapping(meta['settings'])
    video = a.mapping(settings['Video'])
    refs = a.array(video['virtualDestinations'])
    second = a.add({**a.ref(refs[0]), 'name': 'Second NDI'})
    a.ref(video['virtualDestinations'])['NS.objects'].append(second)
    source = a.dump()
    saved = module.inspect_saved_video(source)
    first, second = saved['destinations']
    assert first['id'] != second['id']
    assert first['registry_scope_id'] == second['registry_scope_id']
    assert first['archive_sha256'] == hashlib.sha256(source).hexdigest()
    assert first['archive_object_uid'] != second['archive_object_uid']
    assert first['id'] != first['registry_scope_id']
