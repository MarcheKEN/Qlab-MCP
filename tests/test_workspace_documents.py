"""Document lifecycle uses fixed native events, signed plans and fresh evidence."""
from copy import deepcopy
import json
from types import SimpleNamespace
import subprocess

import pytest

from qlab_mcp import workspace_documents as docs

WS = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def native(tmp_path, monkeypatch):
    path = tmp_path / "Show.qlab5"
    path.write_text("workspace")
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(
        host="127.0.0.1", enable_write=True, timeout=2)))
    state = SimpleNamespace(reader=reader, path=str(path), calls=[], timeout=False,
        failed_read=False, documents=[dict(workspace_id=WS, name="Show", path=str(path),
            modified=True, edit_mode=True, show_mode=False, active_cue_ids=[])])

    def request(reader, action="inventory", **payload):
        state.calls.append((action, payload))
        if action == "inventory":
            if state.failed_read:
                raise ValueError("native inventory unavailable")
            return {"documents": deepcopy(state.documents)}
        if action == "save":
            state.documents[0]["modified"] = False
        elif action == "close":
            state.documents = []
        elif action == "open":
            state.documents.append(dict(workspace_id=OTHER, name="Other", path=payload["path"],
                modified=False, edit_mode=True, show_mode=False, active_cue_ids=[]))
        if state.timeout:
            raise subprocess.TimeoutExpired("osascript", 2)
        return {"sent": True}

    monkeypatch.setattr(docs, "_native_request", request)
    monkeypatch.setattr(docs, "check_write_readiness", lambda *a: {"ok": True})
    return state


def test_get_document_exact_identity_and_native_state(native):
    result = docs.get_workspace_document(native.reader, WS)
    assert result["ok"] and result["document"]["modified"] is True
    assert result["document"]["path"] == native.path
    native.documents.append(deepcopy(native.documents[0]))
    assert not docs.get_workspace_document(native.reader, WS)["ok"]


@pytest.mark.parametrize("workspace", ["ws", "", "../workspace", None])
def test_invalid_workspace_never_calls_native(native, workspace):
    assert not docs.save_workspace(native.reader, workspace)["ok"]
    assert native.calls == []


def test_save_plan_execute_fresh_readback_single_use(native):
    plan = docs.save_workspace(native.reader, WS)
    assert plan["ok"] and plan["executed_operations"] == []
    result = docs.save_workspace(native.reader, WS, False, plan["confirm_token"])
    assert result["ok"] and result["document"]["modified"] is False
    assert len([c for c in native.calls if c[0] == "save"]) == 1
    assert not docs.save_workspace(native.reader, WS, False, plan["confirm_token"])["ok"]


@pytest.mark.parametrize("change", [dict(modified=False), dict(edit_mode=False),
    dict(active_cue_ids=[OTHER]), dict(path="")])
def test_save_baseline_change_blocks_event(native, change):
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    native.documents[0].update(change)
    assert not docs.save_workspace(native.reader, WS, False, token)["ok"]
    assert not any(c[0] == "save" for c in native.calls)


def test_expired_and_falsified_tokens(native, monkeypatch):
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    assert not docs.save_workspace(native.reader, WS, False, token + "0")["ok"]
    now = docs.time.time()
    monkeypatch.setattr(docs.time, "time", lambda: now + 301)
    assert not docs.save_workspace(native.reader, WS, False, token)["ok"]
    assert not any(c[0] == "save" for c in native.calls)


def test_close_never_discards_dirty_changes(native):
    assert not docs.close_workspace(native.reader, WS)["ok"]
    native.documents[0]["modified"] = False
    token = docs.close_workspace(native.reader, WS)["confirm_token"]
    native.documents[0]["modified"] = True
    assert not docs.close_workspace(native.reader, WS, False, token)["ok"]
    assert not any(c[0] == "close" for c in native.calls)


def test_close_success_verified_absent(native):
    native.documents[0]["modified"] = False
    token = docs.close_workspace(native.reader, WS)["confirm_token"]
    result = docs.close_workspace(native.reader, WS, False, token)
    assert result["ok"] and result["readback"]["documents"] == []


def test_timeout_reads_fresh_state_once_no_retry(native):
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    native.timeout = True
    result = docs.save_workspace(native.reader, WS, False, token)
    assert result["ok"] and result["status"] == "saved_with_confirmed_timeout"
    assert [c[0] for c in native.calls].count("save") == 1


def test_unavailable_readback_uncertain_and_token_consumed(native, monkeypatch):
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    request = docs._native_request
    def failing(reader, action="inventory", **payload):
        result = request(reader, action, **payload)
        if action == "save":
            native.failed_read = True
        return result
    monkeypatch.setattr(docs, "_native_request", failing)
    result = docs.save_workspace(native.reader, WS, False, token)
    assert result["status"] == "uncertain" and not result["ok"]
    native.failed_read = False
    assert not docs.save_workspace(native.reader, WS, False, token)["ok"]
    assert [c[0] for c in native.calls].count("save") == 1


def test_open_path_bound_fingerprint_and_inventory(native, tmp_path):
    path = tmp_path / "Other.qlab5"
    path.write_text("other")
    native.documents = []
    plan = docs.open_workspace(native.reader, str(path))
    assert plan["ok"]
    path.write_text("changed")
    assert not docs.open_workspace(native.reader, str(path), False, plan["confirm_token"])["ok"]
    assert not any(c[0] == "open" for c in native.calls)
    plan = docs.open_workspace(native.reader, str(path))
    result = docs.open_workspace(native.reader, str(path), False, plan["confirm_token"])
    assert result["ok"] and result["workspace_id"] == OTHER
    assert not docs.open_workspace(native.reader, str(path))["ok"]


def test_open_requires_empty_inventory_without_any_event(native, tmp_path):
    path = tmp_path / "Other.qlab5"
    path.write_text("other")
    result = docs.open_workspace(native.reader, str(path))
    assert not result["ok"] and result["executed_operations"] == []
    assert "all existing workspaces" in result["error"]
    assert not any(c[0] == "open" for c in native.calls)


def test_fingerprint_failure_after_token_reservation_has_no_event(native, monkeypatch):
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    original = docs._fingerprint
    calls = []
    def fingerprint(path):
        calls.append(path)
        if len(calls) > 1:
            raise OSError("file unavailable before event")
        return original(path)
    monkeypatch.setattr(docs, "_fingerprint", fingerprint)
    result = docs.save_workspace(native.reader, WS, False, token)
    assert not result["ok"] and result["executed_operations"] == []
    assert not any(c[0] == "save" for c in native.calls)


@pytest.mark.parametrize("path", ["relative.qlab5", "/missing.qlab5", "/tmp/a.txt", "", None])
def test_open_rejects_invalid_path_without_native(native, path):
    assert not docs.open_workspace(native.reader, path)["ok"]
    assert native.calls == []


def test_inventory_fail_closed_on_malformed_flags(native):
    native.documents[0]["modified"] = "false"
    assert not docs.get_workspace_document(native.reader, WS)["ok"]


def test_fixed_script_guards_immediately_before_events():
    assert 'tell application "/Applications/QLab.app"' in docs.SCRIPT
    assert "set workspaceRecord to" in docs.SCRIPT
    assert "row's setObject" not in docs.SCRIPT
    assert "close w saving no" in docs.SCRIPT
    assert "save w" in docs.SCRIPT
    assert "modified of w" in docs.SCRIPT
    assert "active cues of w" in docs.SCRIPT
    assert "edit mode of w" in docs.SCRIPT
    assert "No QLab instance is running." in docs.SCRIPT
    assert "Multiple QLab instances are running." in docs.SCRIPT
    assert "open (POSIX file targetPath)" in docs.SCRIPT


def test_reply_acknowledgment_without_state_change_is_uncertain(native, monkeypatch):
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    original = docs._native_request
    def acknowledgment(reader, action="inventory", **payload):
        if action == "save":
            native.calls.append((action, payload))
            return {"sent": True}
        return original(reader, action, **payload)
    monkeypatch.setattr(docs, "_native_request", acknowledgment)
    result = docs.save_workspace(native.reader, WS, False, token)
    assert result["status"] == "uncertain" and not result["ok"]
    assert result["document"]["modified"] is True
    assert [c[0] for c in native.calls].count("save") == 1


def test_save_does_not_confirm_without_send_ack_even_when_already_clean(native, monkeypatch):
    native.documents[0]["modified"] = False
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    original = docs._native_request

    def unacknowledged(reader, action="inventory", **payload):
        if action == "save":
            native.calls.append((action, payload))
            return {"sent": False}
        return original(reader, action, **payload)

    monkeypatch.setattr(docs, "_native_request", unacknowledged)
    result = docs.save_workspace(native.reader, WS, False, token)

    assert result["status"] == "blocked" and not result["ok"]
    assert result["executed_operations"] == []
    assert [c[0] for c in native.calls].count("save") == 1


def test_save_with_missing_send_ack_remains_uncertain_when_already_clean(native, monkeypatch):
    native.documents[0]["modified"] = False
    token = docs.save_workspace(native.reader, WS)["confirm_token"]
    original = docs._native_request

    def unacknowledged(reader, action="inventory", **payload):
        if action == "save":
            native.calls.append((action, payload))
            return {}
        return original(reader, action, **payload)

    monkeypatch.setattr(docs, "_native_request", unacknowledged)
    result = docs.save_workspace(native.reader, WS, False, token)

    assert result["status"] == "uncertain" and not result["ok"]
    assert result["readback"]["documents"][0]["modified"] is False
    assert [c[0] for c in native.calls].count("save") == 1


def test_script_preflight_refusal_consumes_token_without_event(native, monkeypatch):
    native.documents[0]["modified"] = False
    token = docs.close_workspace(native.reader, WS)["confirm_token"]
    original = docs._native_request
    def changed_inside_script(reader, action="inventory", **payload):
        if action == "close":
            native.calls.append((action, payload))
            return {"sent": False, "error": "Closing unsaved changes is forbidden."}
        return original(reader, action, **payload)
    monkeypatch.setattr(docs, "_native_request", changed_inside_script)
    result = docs.close_workspace(native.reader, WS, False, token)
    assert result["status"] == "blocked" and result["executed_operations"] == []
    assert not docs.close_workspace(native.reader, WS, False, token)["ok"]
    assert [c[0] for c in native.calls].count("close") == 1


def test_open_inventory_change_invalidates_token(native, tmp_path):
    path = tmp_path / "Other.qlab5"
    path.write_text("other")
    native.documents = []
    token = docs.open_workspace(native.reader, str(path))["confirm_token"]
    native.documents.append(dict(workspace_id=WS, name="New", path="", modified=False,
        edit_mode=True, show_mode=False, active_cue_ids=[]))
    assert not docs.open_workspace(native.reader, str(path), False, token)["ok"]
    assert not any(c[0] == "open" for c in native.calls)


def test_open_ambiguous_readback_is_uncertain(native, tmp_path, monkeypatch):
    path = tmp_path / "Other.qlab5"
    path.write_text("other")
    native.documents = []
    token = docs.open_workspace(native.reader, str(path))["confirm_token"]
    original = docs._native_request
    def duplicate(reader, action="inventory", **payload):
        result = original(reader, action, **payload)
        if action == "open":
            native.documents.append(deepcopy(native.documents[0]))
        return result
    monkeypatch.setattr(docs, "_native_request", duplicate)
    result = docs.open_workspace(native.reader, str(path), False, token)
    assert not result["ok"] and result["status"] == "uncertain"
    assert [c[0] for c in native.calls].count("open") == 1


def test_open_package_manifest_changes_invalidate_confirmation(native, tmp_path):
    package = tmp_path / "Package.qlab5"
    package.mkdir()
    (package / "workspace.xml").write_text("one")
    native.documents = []
    token = docs.open_workspace(native.reader, str(package))["confirm_token"]
    (package / "workspace.xml").write_text("two")
    assert not docs.open_workspace(native.reader, str(package), False, token)["ok"]
    assert not any(c[0] == "open" for c in native.calls)


def test_bounded_package_fingerprint_and_symlink_rejection(tmp_path, monkeypatch):
    package = tmp_path / "Package.qlab5"
    package.mkdir()
    (package / "one").write_text("data")
    monkeypatch.setattr(docs, "_MAX_BYTES", 3)
    with pytest.raises(ValueError, match="byte limit"):
        docs._fingerprint(package)
    monkeypatch.setattr(docs, "_MAX_BYTES", 64)
    monkeypatch.setattr(docs, "_MAX_ENTRIES", 1)
    with pytest.raises(ValueError, match="entry limit"):
        docs._fingerprint(package)
    monkeypatch.setattr(docs, "_MAX_ENTRIES", 10)
    (package / "alias").symlink_to(package / "one")
    with pytest.raises(ValueError, match="unsupported entry"):
        docs._fingerprint(package)


def test_remote_native_document_read_is_rejected(native):
    native.reader.client.config.host = "192.0.2.1"
    assert not docs.get_workspace_document(native.reader, WS)["ok"]
    assert native.calls == []


def test_fixed_bridge_passes_untrusted_path_only_as_json_argv(tmp_path, monkeypatch):
    path = str(tmp_path / 'quoted"; do shell script "bad.qlab5')
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1", timeout=2)))
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"sent":true}', stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    docs._native_request(reader, "open", path=path, expected_inventory=[])
    argv, options = calls[0]
    assert argv[:2] == ["/usr/bin/osascript", "-"]
    assert json.loads(argv[2])["path"] == path
    assert options["input"] == docs.SCRIPT and "shell" not in options
