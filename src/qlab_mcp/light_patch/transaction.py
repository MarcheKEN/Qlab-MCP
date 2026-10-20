"""Signed same-path Light Patch edits with bounded recovery and native readback."""
from __future__ import annotations

try:
    import fcntl
except ImportError:  # Native file locking is unavailable on Windows; OSC reads still work.
    fcntl = None
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import secrets
import stat
import subprocess
import time
from typing import Any

from .. import workspace_documents as docs
from ..runtime.read_cache import shared_read_cache
from ..write.tokens import decode_confirm_token, encode_confirm_token

_SECRET = secrets.token_bytes(32)
_USED: dict[str, float] = {}
_MAX_BYTES = 64 * 1024 * 1024

# The public Open contract remains empty-inventory-only. This fixed variant is
# private to a transaction whose file UUID/hash and other documents are bound.
_REOPEN_GUARD = '''set expectedUUID to (payload's objectForKey:"workspace_id") as text
     repeat with existingRow in currentRows
      if ((existingRow's objectForKey:"workspace_id") as text) is expectedUUID then error "Workspace UUID is already open."
      if ((existingRow's objectForKey:"path") as text) is targetPath then error "Workspace path is already open."
     end repeat'''
_CANONICAL_EXPECTED_ROWS = '''set expectedRows to current application's NSMutableArray's array()
     repeat with originalRow in (payload's objectForKey:"expected_inventory")
      set expectedRow to originalRow's mutableCopy()
      set rawExpectedPath to (expectedRow's objectForKey:"path") as text
      expectedRow's setObject:(my canonicalPath(rawExpectedPath)) forKey:"path"
      expectedRows's addObject:expectedRow
     end repeat'''
REOPEN_SCRIPT = docs.SCRIPT.replace(
    'if (currentRows\'s |count|() as integer) is not 0 then error "Opening requires all existing workspaces to be closed."',
    _REOPEN_GUARD,
).replace(
    'set expectedRows to payload\'s objectForKey:"expected_inventory"',
    _CANONICAL_EXPECTED_ROWS,
)


def _reopen(reader: Any, path: str, workspace_id: str, expected_inventory: list[dict]) -> dict:
    docs._local(reader)
    timeout = reader.client.config.timeout
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Native timeout must be positive and finite.')
    payload = dict(action='open', path=path, workspace_id=workspace_id,
                   expected_inventory=expected_inventory)
    process = subprocess.run(['/usr/bin/osascript', '-', json.dumps(payload, allow_nan=False)],
        input=REOPEN_SCRIPT, capture_output=True, text=True, timeout=max(30, timeout), check=False)
    if process.returncode:
        raise ValueError(f'Native reopen failed: {process.stderr.strip()}')
    response = json.loads(process.stdout)
    if not isinstance(response, dict):
        raise ValueError('Invalid native reopen response.')
    return response


def _app_build() -> tuple[str, str]:
    info = plistlib.loads(Path('/Applications/QLab.app/Contents/Info.plist').read_bytes())
    return str(info.get('CFBundleShortVersionString')), str(info.get('CFBundleVersion'))


def _recovery_path(path: Path) -> Path:
    return path.with_name(f'.{path.name}.light-patch-recovery')


def _read(path: Path) -> tuple[bytes, list[int]]:
    if not path.is_absolute() or path.suffix.casefold() != '.qlab5' or path.resolve() != path:
        raise ValueError('A canonical existing .qlab5 file is required.')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > _MAX_BYTES:
            raise ValueError('Workspace must be a single-link regular file bounded to 64 MiB.')
        if before.st_uid != os.getuid():
            raise ValueError('Workspace must be owned by the MCP user.')
        source = stream.read(_MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode, s.st_uid, s.st_gid]
    if len(source) > _MAX_BYTES or identity(before) != identity(after):
        raise ValueError('Workspace changed while being read.')
    return source, identity(after)


def _digest(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _journal(directory: Path, record: dict) -> None:
    temporary = directory / 'journal.tmp'
    _write_new(temporary, json.dumps(record, allow_nan=False, sort_keys=True).encode())
    os.replace(temporary, directory / 'journal.json')
    _sync_directory(directory)


def _recovery_state(path: Path) -> dict | None:
    directory = _recovery_path(path)
    if not directory.exists() and not directory.is_symlink():
        return None
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Recovery path must be an owned private directory.')
    entries = list(directory.iterdir())
    if any(entry.name not in {'original.qlab5', 'journal.json'} or entry.is_symlink()
           or not entry.is_file() for entry in entries):
        raise ValueError('Unresolved or unexpected recovery artifacts require inspection.')
    record = json.loads((directory / 'journal.json').read_bytes())
    if not isinstance(record, dict) or record.get('phase') != 'verified':
        raise ValueError('An unresolved Light Patch recovery blocks another transaction.')
    return record


def _live(reader: Any, ws: str, summary: dict) -> dict:
    from .archive import verify_live_patch
    shared_read_cache().clear()
    response = reader.get_workspace_setting_details(ws, 'light', kind='light_patch', profile='technical')
    if response.get('ok') is not True or response.get('partial') or response.get('errors'):
        raise ValueError('Fresh native Light Patch readback is unavailable or incomplete.')
    payload = (response.get('details') or {}).get('patch')
    if not isinstance(payload, dict) or not verify_live_patch(summary, payload):
        raise ValueError('Fresh QLab Light Patch does not match the saved/planned patch.')
    return payload


def _reserve(token: str | None, baseline: dict) -> None:
    if not isinstance(token, str):
        raise ValueError('A fresh Light Patch confirmation token is required.')
    payload, error = decode_confirm_token(token, 'lightPatch', 1, _SECRET)
    if error or payload is None:
        raise ValueError(f'Invalid Light Patch confirmation token: {error}.')
    expiry = payload.get('expires_at')
    now = time.time()
    if type(expiry) not in {int, float} or not math.isfinite(expiry) or now >= expiry:
        raise ValueError('Light Patch confirmation token expired.')
    if payload.get('baseline') != baseline:
        raise ValueError('Light Patch confirmation token does not match the fresh plan.')
    for used, deadline in list(_USED.items()):
        if now >= deadline:
            del _USED[used]
    if token in _USED:
        raise ValueError('Light Patch confirmation token was already used.')
    _USED[token] = expiry


def _result(ok: bool, status: str, **values: Any) -> dict:
    return dict(ok=ok, status=status, planned_operations=[], executed_operations=[],
                file_replaced=False, document_reopened=False, native_patch_verified=False,
                native_patch_verification_scope='OSC-visible properties only; output/address verified in saved archive.',
                **values)


def edit_light_patch(reader: Any, workspace_id: str, operations: list[dict],
                     dry_run: bool = True, confirm_token: str | None = None) -> dict:
    """Plan a complete patch batch or execute its one-use same-path transaction."""
    # Share the native document lock so Save/Close/Open cannot interleave locally.
    with docs._LOCK:
        try:
            return _edit(reader, workspace_id, operations, dry_run, confirm_token)
        except Exception as exc:
            return _result(False, 'blocked', error=str(exc))


def _edit(reader: Any, workspace_id: str, operations: list[dict],
          dry_run: bool, confirm_token: str | None) -> dict:
    from .archive import plan_patch
    ws = docs._uuid(workspace_id)
    if fcntl is None:
        raise ValueError('Native Light Patch editing requires filesystem locking on the QLab host.')
    if type(dry_run) is not bool:
        raise ValueError('dry_run must be boolean.')
    if not dry_run and isinstance(confirm_token, str) and confirm_token in _USED:
        raise ValueError('Light Patch confirmation token was already used.')
    # JSON round-trip fixes the immutable token baseline and rejects NaN values.
    normalized = json.loads(json.dumps(operations, allow_nan=False))
    docs._local(reader)
    if _app_build() != ('5.5.10', '5510'):
        raise ValueError('Light Patch writing requires QLab 5.5.10 build 5510.')
    readiness = docs.check_write_readiness(reader, ws)
    if not readiness.get('ok'):
        return _result(False, 'blocked', readiness=readiness, error='Workspace write readiness is blocked.')
    inventory = docs._inventory(reader)
    row = docs._document(inventory, ws)
    if not row['edit_mode'] or row['show_mode'] or row['active_cue_ids']:
        raise ValueError('Workspace must be inactive and in Edit Mode.')
    if row['modified']:
        return _result(False, 'needs_save', workspace_id=ws,
            error='Save all pending changes using the existing Save flow, then obtain a fresh patch plan.')
    path = Path(row['path'])
    _recovery_state(path)
    source, identity = _read(path)
    original = plan_patch(source, [])
    plan = plan_patch(source, normalized)
    if original['workspace_id'].upper() != ws or plan['workspace_id'].upper() != ws:
        raise ValueError('Saved workspace UUID does not match the native document.')
    _live(reader, ws, original['summary'])
    result = _result(True, 'planned', workspace_id=ws, path=str(path),
        source_sha256=_digest(source), output_sha256=_digest(plan['output_bytes']),
        changes=plan['changes'], warnings=plan['warnings'], affected_cues=plan['affected_cues'],
        summary=plan['summary'])
    result['planned_operations'] = plan['changes']
    if not plan['changes']:
        result['status'] = 'no_op'
        return result
    baseline = dict(workspace_id=ws, inventory=inventory, identity=identity,
                    source_sha256=_digest(source), output_sha256=_digest(plan['output_bytes']),
                    operations=normalized)
    if dry_run:
        result['confirm_token'] = encode_confirm_token('lightPatch', 1,
            dict(baseline=baseline, expires_at=time.time() + 300, nonce=secrets.token_hex(16)), _SECRET)
        return result
    _reserve(confirm_token, baseline)
    # Recheck after all planning/reads, before creating recovery or a native event.
    if _app_build() != ('5.5.10', '5510') or docs._inventory(reader) != inventory or _read(path) != (source, identity):
        raise ValueError('Workspace state changed before the transaction.')
    return _execute(reader, ws, path, source, identity, inventory, plan, result)


def _execute(reader: Any, ws: str, path: Path, source: bytes, identity: list[int],
             inventory: dict, plan: dict, result: dict) -> dict:
    from .archive import plan_patch
    directory = _recovery_path(path)
    descriptor = None
    journal_started = False
    record = dict(phase='prepared', workspace_id=ws, path=str(path),
                  source_sha256=_digest(source), output_sha256=_digest(plan['output_bytes']))
    result = {**result, 'ok': False, 'status': 'uncertain', 'recovery_path': str(directory)}
    others = [row for row in inventory['documents'] if row['workspace_id'] != ws]
    try:
        try:
            directory.mkdir(mode=0o700)
            _sync_directory(path.parent)
        except FileExistsError:
            _recovery_state(path)
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (directory / 'journal.json').exists():
            _recovery_state(path)
            for entry in directory.iterdir():
                entry.unlink()
        _write_new(directory / 'original.qlab5', source)
        _journal(directory, record)
        journal_started = True
        result['executed_operations'].append({'action': 'close', 'sent': 'attempted'})
        response = docs._native_request(reader, 'close', workspace_id=ws,
                                        path=str(path), expected_modified=False)
        if response.get('sent') is not True or response.get('error'):
            raise ValueError(response.get('error') or 'Native Close acknowledgement is uncertain.')
        if docs._inventory(reader)['documents'] != others:
            raise ValueError('Close did not preserve the expected other-document inventory.')
        record['phase'] = 'closed'
        _journal(directory, record)
        if _read(path) != (source, identity):
            raise ValueError('Workspace file changed after Close; newer bytes were not replaced.')
        output = plan['output_bytes']
        if plan_patch(output, [])['summary'] != plan['summary']:
            raise ValueError('Generated file readback does not match the plan.')
        temporary = directory / 'result.qlab5'
        _write_new(temporary, b'')
        # macOS cp preserves ACLs/xattrs that this Python runtime cannot expose.
        copied = subprocess.run(['/bin/cp', '-p', str(path), str(temporary)],
            capture_output=True, text=True, timeout=reader.client.config.timeout, check=False)
        if copied.returncode:
            raise ValueError(f'Workspace metadata copy failed: {copied.stderr.strip()}')
        descriptor_output = os.open(temporary, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(descriptor_output, 'wb') as stream:
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
        record['phase'] = 'replacement_pending'
        _journal(directory, record)
        if docs._inventory(reader)['documents'] != others or _read(path) != (source, identity):
            raise ValueError('Workspace file or native inventory changed before replacement.')
        os.replace(temporary, path)
        result['file_replaced'] = True
        result['executed_operations'].append({'action': 'replace_file', 'sha256': _digest(output)})
        _sync_directory(path.parent)
        record['phase'] = 'replaced'
        _journal(directory, record)
        if _read(path)[0] != output:
            raise ValueError('Workspace file changed before reopening.')
        result['executed_operations'].append({'action': 'open', 'sent': 'attempted'})
        reopen_error = None
        try:
            response = _reopen(reader, str(path), ws, others)
        except Exception as exc:
            reopen_error = exc
        else:
            if response.get('sent') is not True:
                raise ValueError(response.get('error') or 'Native Open event was not sent.')
            if response.get('error'):
                reopen_error = ValueError(response['error'])
        # A lost acknowledgement may follow a successful Open. Read once, never resend.
        if _read(path)[0] != output:
            raise ValueError('Workspace file changed during reopen.')
        current = docs._inventory(reader)
        row = docs._document(current, ws)
        if row['path'] != str(path) or not row['edit_mode'] or row['show_mode'] or row['active_cue_ids']:
            raise ValueError('Reopened document identity or native state did not match.')
        if [r for r in current['documents'] if r['workspace_id'] != ws] != others:
            raise ValueError('Other open documents changed during reopen.')
        result['document_reopened'] = True
        result['document_modified_after_reopen'] = row['modified']
        if row['modified']:
            result['warnings'] = [*result['warnings'], 'The reopened document has unsaved changes. QLab may normalize it on open; no automatic save was performed.']
        _live(reader, ws, plan['summary'])
        result['native_patch_verified'] = True
        result.update(ok=True, status='verified')
        if reopen_error is not None:
            timed_out = isinstance(reopen_error, subprocess.TimeoutExpired)
            result['status'] = 'verified_with_confirmed_timeout' if timed_out else 'verified_with_confirmed_error'
            result['event_error'] = str(reopen_error)
            result['warnings'] = [*result['warnings'],
                'Native Open acknowledgement failed; fresh file, document identity and OSC-visible patch confirmed the result. No event was retried.']
        record['phase'] = 'verified'
        _journal(directory, record)
        return result
    except Exception as exc:
        result.update(ok=False, status='uncertain')
        result['phase'] = record['phase']
        result['error'] = f'{exc} Do not retry automatically; inspect document, file and recovery state.'
        try:
            result['native_inventory'] = docs._inventory(reader)
        except Exception:
            result['native_inventory'] = None
        if journal_started:
            try:
                _journal(directory, {**record, 'error': str(exc)})
            except Exception:
                pass
        return result
    finally:
        if descriptor is not None:
            os.close(descriptor)
