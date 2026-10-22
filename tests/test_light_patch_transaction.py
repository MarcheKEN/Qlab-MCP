"""Same-path Light Patch transactions preserve recovery and native identity."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from qlab_mcp.light_patch import transaction as tx

_NATIVE_REOPEN = tx._reopen

WS = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


@pytest.fixture
def state(tmp_path, monkeypatch):
    path = tmp_path / 'Show.qlab5'
    source = json.dumps({'workspace_id': WS, 'patch': {'name': 'before'}}).encode()
    path.write_bytes(source)
    row = dict(workspace_id=WS, name='Show', path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    s = SimpleNamespace(path=path, source=source, rows=[row], calls=[], fail=None,
                        mismatch=False, live={'name': 'before'})
    monkeypatch.setattr(tx, '_app_build', lambda: ('5.5.10', '5510'))
    config = SimpleNamespace(host='127.0.0.1', enable_write=True, timeout=2)
    s.reader = SimpleNamespace(client=SimpleNamespace(config=config))
    s.reader.get_workspace_setting_details = lambda *a, **k: dict(
        ok=True, partial=False, details={'patch': deepcopy(s.live)})

    def plan(source, operations):
        value = json.loads(source)
        changes = []
        if operations and value['patch']['name'] != operations[0]['name']:
            value['patch']['name'] = operations[0]['name']
            changes = deepcopy(operations)
        return dict(output_bytes=json.dumps(value).encode() if changes else source,
                    workspace_id=value['workspace_id'], summary=value['patch'],
                    changes=changes, warnings=[], affected_cues=[])

    monkeypatch.setitem(sys.modules, 'qlab_mcp.light_patch.archive', SimpleNamespace(
        plan_patch=plan, verify_live_patch=lambda summary, payload: summary == payload))
    monkeypatch.setattr(tx.docs, '_inventory', lambda reader: {'documents': deepcopy(s.rows)})
    monkeypatch.setattr(tx.docs, 'check_write_readiness', lambda *a: {'ok': True})

    def close(reader, action, **payload):
        s.calls.append(action)
        if s.fail == 'close_unsent':
            return {'sent': False, 'error': 'not sent'}
        s.rows = [r for r in s.rows if r['workspace_id'] != WS]
        if s.fail == 'close':
            raise TimeoutError('native close timeout')
        return {'sent': True}

    def reopen(reader, path, workspace_id, expected_inventory):
        s.calls.append('open')
        assert s.rows == expected_inventory
        if s.fail == 'open':
            raise TimeoutError('native open timeout')
        s.rows.append({**row, 'workspace_id': OTHER if s.mismatch else WS})
        s.live = json.loads(Path(path).read_bytes())['patch']
        return {'sent': True}

    monkeypatch.setattr(tx.docs, '_native_request', close)
    monkeypatch.setattr(tx, '_reopen', reopen)
    return s


def edit(s, dry_run=True, token=None):
    return tx.edit_light_patch(s.reader, WS, [{'name': 'after'}], dry_run, token)


def test_preview_has_no_disk_or_native_side_effects(state):
    result = edit(state)
    assert result['ok'] and result['status'] == 'planned'
    assert result['confirm_token'].startswith('confirm:lightPatch:v1:')
    assert state.path.read_bytes() == state.source
    assert not tx._recovery_path(state.path).exists()
    assert state.calls == []


def test_dirty_workspace_needs_save_without_mutation(state):
    state.rows[0]['modified'] = True
    result = edit(state)
    assert not result['ok'] and result['status'] == 'needs_save'
    assert state.calls == []


def test_noop_does_not_close_or_rewrite(state):
    result = tx.edit_light_patch(state.reader, WS, [{'name': 'before'}])
    assert result['ok'] and result['status'] == 'no_op'
    assert 'confirm_token' not in result
    assert state.path.read_bytes() == state.source
    assert state.calls == []


def test_execute_same_path_and_keep_other_documents(state):
    state.rows.append(dict(workspace_id=OTHER, name='Other', path='', modified=True,
                           edit_mode=True, show_mode=False, active_cue_ids=[]))
    other = deepcopy(state.rows[1])
    token = edit(state)['confirm_token']
    result = edit(state, False, token)
    assert result['ok'] and result['status'] == 'verified', result
    assert result['native_patch_verified'] is True
    assert state.calls == ['close', 'open']
    assert state.rows[0] == other
    assert json.loads(state.path.read_bytes())['patch'] == {'name': 'after'}
    recovery = tx._recovery_path(state.path)
    assert (recovery / 'original.qlab5').read_bytes() == state.source
    assert json.loads((recovery / 'journal.json').read_text())['phase'] == 'verified'


@pytest.mark.parametrize('change', ['file', 'dirty', 'inventory', 'operations'])
def test_stale_plan_blocks_before_events(state, change):
    token = edit(state)['confirm_token']
    if change == 'file':
        state.path.write_bytes(state.source + b' ')
    elif change == 'dirty':
        state.rows[0]['modified'] = True
    elif change == 'inventory':
        state.rows[0]['name'] = 'Changed'
    result = tx.edit_light_patch(state.reader, WS,
        [{'name': 'different' if change == 'operations' else 'after'}], False, token)
    assert not result['ok']
    assert state.calls == []


def test_invalid_expired_and_used_tokens(state, monkeypatch):
    token = edit(state)['confirm_token']
    assert not edit(state, False, token + '0')['ok']
    old_time = tx.time.time()
    monkeypatch.setattr(tx.time, 'time', lambda: old_time + 301)
    assert not edit(state, False, token)['ok']
    monkeypatch.setattr(tx.time, 'time', lambda: old_time)
    assert edit(state, False, token)['ok']
    assert not edit(state, False, token)['ok']
    assert state.calls == ['close', 'open']


@pytest.mark.parametrize('failure', ['close', 'open'])
def test_native_timeout_retains_recovery_no_retry(state, failure):
    token = edit(state)['confirm_token']
    state.fail = failure
    result = edit(state, False, token)
    assert not result['ok'] and result['status'] == 'uncertain'
    assert tx._recovery_path(state.path).exists()
    assert state.calls.count(failure) <= 1
    assert (tx._recovery_path(state.path) / 'original.qlab5').read_bytes() == state.source
    if failure == 'close':
        assert state.path.read_bytes() == state.source
        assert 'open' not in state.calls


def test_wrong_reopen_identity_is_not_success(state):
    token = edit(state)['confirm_token']
    state.mismatch = True
    result = edit(state, False, token)
    assert not result['ok'] and result['status'] == 'uncertain'
    assert result['file_replaced'] and not result['native_patch_verified']


def test_unresolved_recovery_blocks_new_plan(state):
    recovery = tx._recovery_path(state.path)
    recovery.mkdir()
    (recovery / 'journal.json').write_text('{"phase":"closed"}')
    result = edit(state)
    assert not result['ok'] and result['status'] == 'blocked'
    assert state.calls == []


def test_symlink_and_hardlink_rejected(state, tmp_path):
    linked = tmp_path / 'Linked.qlab5'
    linked.symlink_to(state.path)
    state.rows[0]['path'] = str(linked)
    assert not edit(state)['ok']
    linked.unlink()
    linked.hardlink_to(state.path)
    state.rows[0]['path'] = str(state.path)
    assert not edit(state)['ok']


def test_live_source_mismatch_blocks_plan(state):
    state.live = {'name': 'other'}
    assert not edit(state)['ok']
    assert state.calls == []


def test_disk_race_after_close_does_not_replace_newer_file(state, monkeypatch):
    token = edit(state)['confirm_token']
    close = tx.docs._native_request
    def changed(reader, action, **payload):
        result = close(reader, action, **payload)
        state.path.write_bytes(state.source + b' ')
        return result
    monkeypatch.setattr(tx.docs, '_native_request', changed)
    result = edit(state, False, token)
    assert not result['ok']
    assert state.path.read_bytes() == state.source + b' '
    assert 'open' not in state.calls


def test_pending_save_before_replacement_preserves_newer_bytes_and_recovery(state, monkeypatch):
    token = edit(state)['confirm_token']
    newer = json.dumps({'workspace_id': WS, 'patch': {'name': 'autosaved'}}).encode()
    journal = tx._journal

    def save_pending_bytes(directory, record):
        journal(directory, record)
        if record['phase'] == 'replacement_pending':
            state.path.write_bytes(newer)

    monkeypatch.setattr(tx, '_journal', save_pending_bytes)
    result = edit(state, False, token)

    assert not result['ok'] and not result['file_replaced']
    assert state.path.read_bytes() == newer
    assert state.calls == ['close']
    recovery = tx._recovery_path(state.path)
    assert (recovery / 'original.qlab5').read_bytes() == state.source


def test_live_readback_mismatch_retains_replaced_file_and_recovery(state):
    token = edit(state)['confirm_token']
    reopen = tx._reopen
    def wrong_live(*args, **kwargs):
        response = reopen(*args, **kwargs)
        state.live = {'name': 'unexpected'}
        return response
    from unittest.mock import patch
    with patch.object(tx, '_reopen', wrong_live):
        result = edit(state, False, token)
    assert not result['ok'] and result['status'] == 'uncertain'
    assert result['file_replaced'] and result['document_reopened']
    assert not result['native_patch_verified']
    assert (tx._recovery_path(state.path) / 'original.qlab5').read_bytes() == state.source


def test_second_success_reuses_one_recovery_and_preserves_permissions(state):
    state.path.chmod(0o640)
    first = edit(state, False, edit(state)['confirm_token'])
    assert first['ok']
    after = state.path.read_bytes()
    operations = [{'name': 'third'}]
    plan = tx.edit_light_patch(state.reader, WS, operations)
    result = tx.edit_light_patch(state.reader, WS, operations, False, plan['confirm_token'])
    assert result['ok']
    recovery = tx._recovery_path(state.path)
    assert (recovery / 'original.qlab5').read_bytes() == after
    assert state.path.stat().st_mode & 0o777 == 0o640
    assert len(list(state.path.parent.glob('.*.light-patch-recovery'))) == 1


def test_close_declined_keeps_original_and_does_not_open(state):
    token = edit(state)['confirm_token']
    state.fail = 'close_unsent'
    result = edit(state, False, token)
    assert not result['ok']
    assert not result['file_replaced']
    assert state.path.read_bytes() == state.source
    assert state.calls == ['close']


def test_new_document_appearing_after_close_blocks_file_replacement(state, monkeypatch):
    token = edit(state)['confirm_token']
    close = tx.docs._native_request
    def unexpected(reader, action, **payload):
        result = close(reader, action, **payload)
        state.rows.append(dict(workspace_id=OTHER, name='Other', path='', modified=False,
                               edit_mode=True, show_mode=False, active_cue_ids=[]))
        return result
    monkeypatch.setattr(tx.docs, '_native_request', unexpected)
    result = edit(state, False, token)
    assert not result['ok'] and not result['file_replaced']
    assert state.path.read_bytes() == state.source
    assert state.calls == ['close']


def test_reopen_script_does_not_weaken_public_open_contract():
    assert 'Opening requires all existing workspaces to be closed.' in tx.docs.SCRIPT
    assert 'Opening requires all existing workspaces to be closed.' not in tx.REOPEN_SCRIPT
    assert 'Workspace UUID is already open.' in tx.REOPEN_SCRIPT
    assert 'Open workspace inventory changed.' in tx.REOPEN_SCRIPT


def test_unsupported_native_build_blocks_before_events(state, monkeypatch):
    monkeypatch.setattr(tx, '_app_build', lambda: ('5.6.0', '5600'))
    result = edit(state)
    assert not result['ok'] and result['status'] == 'blocked'
    assert state.calls == []


def test_failure_to_acquire_recovery_lock_does_not_change_existing_journal(state, monkeypatch):
    assert edit(state, False, edit(state)['confirm_token'])['ok']
    directory = tx._recovery_path(state.path)
    journal = (directory / 'journal.json').read_bytes()
    operations = [{'name': 'third'}]
    plan = tx.edit_light_patch(state.reader, WS, operations)
    def locked(*args):
        raise BlockingIOError('another process owns this recovery')
    monkeypatch.setattr(tx.fcntl, 'flock', locked)
    result = tx.edit_light_patch(state.reader, WS, operations, False, plan['confirm_token'])
    assert not result['ok']
    assert (directory / 'journal.json').read_bytes() == journal


def test_reopen_canonicalizes_other_document_paths_before_native_comparison():
    assert '''set expectedRows to current application's NSMutableArray's array()''' in tx.REOPEN_SCRIPT
    assert '''expectedRow's setObject:(my canonicalPath(rawExpectedPath)) forKey:"path"''' in tx.REOPEN_SCRIPT
    assert '''set expectedRows to payload's objectForKey:"expected_inventory"''' in tx.docs.SCRIPT


@pytest.mark.skipif(sys.platform != 'darwin', reason='Foundation path normalization is macOS-specific')
def test_foundation_reopen_inventory_normalizes_private_tmp_alias_without_qlab():
    canonical_handler = tx.docs.SCRIPT.split('on inventory()')[0]
    script = canonical_handler + '''
on run argv
 set raw to current application's NSString's stringWithString:(item 1 of argv)
 set payload to current application's NSJSONSerialization's JSONObjectWithData:(raw's dataUsingEncoding:(current application's NSUTF8StringEncoding)) options:0 |error|:(missing value)
 ''' + tx._CANONICAL_EXPECTED_ROWS + '''
 set actualPath to my canonicalPath((payload's objectForKey:"actual_path") as text)
 set actualRow to current application's NSMutableDictionary's dictionary()
 actualRow's setObject:actualPath forKey:"path"
 actualRow's setObject:"unchanged" forKey:"name"
 set actualRows to current application's NSMutableArray's arrayWithObject:actualRow
 return (expectedRows's isEqualToArray:actualRows) as boolean
end run
'''
    import tempfile
    with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
        path = Path(directory) / 'Show.qlab5'
        path.write_bytes(b'synthetic workspace path only')
        alias = str(path).replace('/private/tmp/', '/tmp/', 1)
        payload = {'expected_inventory': [{'path': str(path), 'name': 'unchanged'}],
                   'actual_path': alias}
        result = tx.subprocess.run(['/usr/bin/osascript', '-', json.dumps(payload)], input=script,
            text=True, capture_output=True, timeout=10, check=False)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == 'true'


@pytest.mark.parametrize('failure, expected', [
    (tx.subprocess.TimeoutExpired('osascript', 30), 'verified_with_confirmed_timeout'),
    (ValueError('lost native acknowledgement'), 'verified_with_confirmed_error'),
])
def test_reopen_error_with_exact_fresh_readback_is_confirmed_without_resend(state, monkeypatch, failure, expected):
    token = edit(state)['confirm_token']
    reopen = tx._reopen
    def acknowledged_then_error(*args, **kwargs):
        reopen(*args, **kwargs)
        raise failure
    monkeypatch.setattr(tx, '_reopen', acknowledged_then_error)
    result = edit(state, False, token)
    assert result['ok'] and result['status'] == expected, result
    assert result['file_replaced'] and result['document_reopened'] and result['native_patch_verified']
    assert 'OSC-visible' in result['native_patch_verification_scope']
    assert result['warnings'] and result['event_error'] == str(failure)
    assert state.calls == ['close', 'open']
    record = json.loads((tx._recovery_path(state.path) / 'journal.json').read_text())
    assert record['phase'] == 'verified'


def test_reopen_timeout_with_bad_live_readback_remains_uncertain(state, monkeypatch):
    token = edit(state)['confirm_token']
    reopen = tx._reopen
    def wrong_then_timeout(*args, **kwargs):
        reopen(*args, **kwargs)
        state.live = {'name': 'wrong'}
        raise tx.subprocess.TimeoutExpired('osascript', 30)
    monkeypatch.setattr(tx, '_reopen', wrong_then_timeout)
    result = edit(state, False, token)
    assert not result['ok'] and result['status'] == 'uncertain'
    assert not result['native_patch_verified']
    assert state.calls == ['close', 'open']


@pytest.mark.parametrize("configured, expected", [(2, 30), (45, 45)])
def test_native_reopen_has_its_own_bounded_timeout_budget(state, monkeypatch, configured, expected):
    state.reader.client.config.timeout = configured
    calls = []
    def run(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(returncode=0, stdout='{"sent":true}', stderr='')
    monkeypatch.setattr(tx.subprocess, "run", run)
    assert _NATIVE_REOPEN(state.reader, str(state.path), WS, []) == {"sent": True}
    assert len(calls) == 1 and calls[0]["timeout"] == expected


def test_failed_final_durable_journal_is_uncertain_even_after_patch_readback(state, monkeypatch):
    token = edit(state)["confirm_token"]
    journal = tx._journal
    def fail_final(directory, record):
        if record["phase"] == "verified":
            raise OSError("final fsync failed")
        return journal(directory, record)
    monkeypatch.setattr(tx, "_journal", fail_final)
    result = edit(state, False, token)
    assert not result["ok"] and result["status"] == "uncertain"
    assert result["file_replaced"] and result["document_reopened"]
    assert state.calls == ["close", "open"]


def test_reopen_dirty_flag_is_reported_without_saving_unrelated_changes(state, monkeypatch):
    original=tx._reopen
    def reopen(*args, **kwargs):
        response=original(*args, **kwargs)
        state.rows[0]['modified']=True
        return response
    monkeypatch.setattr(tx,'_reopen',reopen)
    preview=edit(state)
    result=edit(state,False,preview['confirm_token'])
    assert result['ok'] and result['document_modified_after_reopen'] is True
    assert state.calls==['close','open']
    assert any('unsaved' in w for w in result['warnings'])


def test_missing_fcntl_does_not_break_remote_read_server_import(monkeypatch):
    import builtins
    import importlib.util
    original=builtins.__import__
    def restricted(name,*args,**kwargs):
        if name=='fcntl':
            raise ImportError('fcntl is unavailable on Windows')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',restricted)
    spec=importlib.util.spec_from_file_location('qlab_mcp.light_patch.portability_probe',tx.__file__)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.fcntl is None


def test_reopen_discards_authenticated_osc_session_before_readback(state, monkeypatch):
    events = []
    state.reader.client.close = lambda: events.append(tuple(state.calls))
    preview = edit(state)
    result = edit(state, False, preview['confirm_token'])
    assert result['ok']
    assert events == [('close', 'open')]
