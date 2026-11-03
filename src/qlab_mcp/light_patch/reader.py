"""Public Light Patch enrichment; internal OSC dependency reads stay unchanged."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import subprocess

from .. import workspace_documents as docs
from ..sanitizer import sanitize_exception_message
from .inspection import inspect_saved_patch

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_FILE_BYTES = 64 * 1024 * 1024
_SECTIONS = ('instruments', 'groups', 'definitions')


def _read_file(path: Path) -> tuple[bytes, tuple]:
    if not path.is_absolute() or path.suffix.casefold() != '.qlab5' or path.resolve(strict=True) != path:
        raise ValueError('A canonical saved .qlab5 file is required.')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_FILE_BYTES:
            raise ValueError('Saved workspace must be a regular file bounded to 64 MiB.')
        source = stream.read(_MAX_FILE_BYTES + 1)
        after = os.fstat(stream.fileno())
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if len(source) > _MAX_FILE_BYTES or identity(before) != identity(after) or identity(after) != identity(path.stat()):
        raise ValueError('Saved workspace changed during reading.')
    return source, identity(after)


def _saved(reader, workspace_id: str) -> dict:
    result = dict(status='unavailable', source='saved_archive', freshness='unavailable',
                  document_modified=None, coverage='partial', instruments=[], groups=[],
                  definitions=[], diagnostics=[])
    try:
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader), workspace_id)
            result['document_modified'] = before['modified']
            if not before['path']:
                raise ValueError('Workspace has no saved document path.')
            path = Path(before['path'])
            source, identity = _read_file(path)
            try:
                decoded = inspect_saved_patch(source)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                result.update(status='unsupported_format', message=sanitize_exception_message(exc))
                return result
            if decoded['workspace_id'] != workspace_id:
                raise ValueError('Saved workspace UUID does not match the requested workspace.')
            after = docs._document(docs._inventory(reader), workspace_id)
            current, current_identity = _read_file(path)
            if any(before[key] != after[key] for key in ('workspace_id', 'path', 'modified')) or identity != current_identity or source != current:
                result.update(status='changed_during_read', message='Document or saved file changed during the read; saved data was discarded.')
                return result
            result.update(decoded, status='ready' if decoded['coverage'] == 'complete' else 'partial',
                          sha256=hashlib.sha256(source).hexdigest(), document_modified=before['modified'],
                          freshness='possibly_stale' if before['modified'] else 'last_saved')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        result['message'] = sanitize_exception_message(exc)
        if 'changed during' in str(exc):
            result['status'] = 'changed_during_read'
    return result


def _comparison(data: dict, saved: dict) -> dict:
    technical = data.get('technical_payload')
    live = technical.get('instruments') if isinstance(technical, dict) else None
    if live is None:
        live = (data.get('detail') or {}).get('instruments')
    result = dict(comparison='not_comparable', comparison_scope=['instrument names', 'definition names', 'instrument notes'], differences=[], atomic_snapshot=False)
    if not isinstance(live, list) or saved['status'] not in {'ready', 'partial'}:
        return result
    current = {item.get('name'): item for item in live if isinstance(item, dict)}
    stored = {item.get('name'): item for item in saved['instruments']}
    differences = []
    if set(current) != set(stored):
        differences.append('Instrument names differ between OSC and the saved archive.')
    for name in current.keys() & stored.keys():
        value = current[name]
        definition = value.get('definition')
        if isinstance(definition, dict) and definition.get('name') != stored[name]['definition']:
            differences.append(f'Instrument {name!r} has a different definition.')
        if 'comment' in value and value['comment'] != stored[name]['note']:
            differences.append(f'Instrument {name!r} has a different note.')
    result.update(comparison='differs' if differences else 'matches_observable_fields', differences=differences)
    return result


def _slice_collections(data: dict, section: str, offset: int, limit: int) -> dict:
    counts = {}
    detail = data.get('detail') or {}
    raw = data.get('technical_payload') or {}
    saved = data['saved_patch']
    for key in _SECTIONS:
        live = raw.get(key) if isinstance(raw, dict) else None
        if not isinstance(live, list):
            live = detail.get(key, [])
        if not isinstance(live, list):
            live = []
        stored = saved.get(key, [])
        selected = section in {'all', key}
        live_page = live[offset:offset + limit] if selected else []
        saved_page = stored[offset:offset + limit] if selected else []
        counts[key] = dict(live_total=len(live), saved_total=len(stored), live_returned=len(live_page), saved_returned=len(saved_page),
                           truncated=selected and offset + limit < max(len(live), len(stored)))
        if key in detail:
            detail[key] = detail[key][offset:offset + limit] if selected else []
        if isinstance(raw, dict) and key in raw:
            raw[key] = live_page
        saved[key] = saved_page
    names = {item.get('name') for key in ('instruments', 'groups') for item in detail.get(key, [])}
    if 'parameters' in detail:
        detail['parameters'] = [item for item in detail['parameters'] if item.get('owner_name') in names]
    if isinstance(detail.get('instrument_index'), dict):
        index = detail['instrument_index']
        index['rows'] = [row for row in index.get('rows', []) if row and row[0] in names]
    # Raw OSC groups embed instrument copies; keep only the current page's instrument data.
    if isinstance(raw, dict):
        allowed = {item.get('name') for item in raw.get('instruments', []) if isinstance(item, dict)}
        for group in raw.get('groups', []):
            if isinstance(group, dict) and isinstance(group.get('instruments'), list):
                group['instruments'] = [item for item in group['instruments'] if isinstance(item, dict) and item.get('name') in allowed]
    return counts


def _size(result: dict) -> int:
    from ..models import WorkspaceLightSettingsResult
    return len(WorkspaceLightSettingsResult.model_validate(result).model_dump_json().encode())


def enrich_light_settings(reader, workspace_id: str, result: dict, profile: str = 'safe',
                          section: str = 'all', offset: int = 0, limit: int = 1000) -> dict:
    """Add bounded last-saved configuration without changing or saving QLab state."""
    if section not in {'all', *_SECTIONS} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('section must be all/instruments/groups/definitions, offset >= 0 and limit 1–1000.')
    result = deepcopy(result)
    live_ok = result.get('ok') is True
    try:
        workspace_id = docs._uuid(result.get('workspace_id', workspace_id))
    except (ValueError, TypeError, AttributeError):
        pass
    data = result.get('data') or {}
    result['data'] = data
    saved = _saved(reader, workspace_id)
    data['saved_patch'] = saved
    comparison = _comparison(data, saved)
    if not live_ok:
        comparison.update(comparison='not_comparable', differences=[])
    data['source_status'] = dict(live_osc=result.get('status', 'error'), saved_archive=saved['status'], **comparison)
    if saved['status'] in {'ready', 'partial'}:
        result['ok'] = True
    if saved['status'] != 'ready' or not live_ok or result.get('partial'):
        result.update(partial=True, status='partial' if result.get('ok') else 'error')
    if saved.get('message'):
        result.setdefault('warnings', []).append(saved['message'])
    original = deepcopy(result)
    effective = limit
    omitted = []
    while True:
        page = deepcopy(original)
        counts = _slice_collections(page['data'], section, offset, effective)
        truncated = any(value['truncated'] for value in counts.values())
        requests = [dict(workspace_id=workspace_id, profile=profile, section=key, offset=offset + effective, limit=effective)
                    for key, value in counts.items() if value['truncated'] and effective]
        page_omissions = list(omitted)
        if not effective:
            # A record that cannot fit must not prevent paging through later records.
            requests = [dict(workspace_id=workspace_id, profile=profile, section=key, offset=offset + 1, limit=1)
                        for key, value in counts.items()
                        if section in {'all', key} and offset + 1 < max(value['live_total'], value['saved_total'])]
            for source_key in ('saved_patch', 'detail', 'technical_payload'):
                source = original['data'].get(source_key)
                if not isinstance(source, dict):
                    continue
                for key in _SECTIONS:
                    records = source.get(key)
                    if section in {'all', key} and isinstance(records, list) and offset < len(records):
                        page_omissions.append(f'{source_key}.{key}[{offset}]: omitted because the complete record page exceeds the byte budget; not recoverable through pagination')
        page['data']['pagination'] = dict(section=section, offset=offset, limit=limit, effective_limit=effective,
                                          byte_limit=MAX_RESPONSE_BYTES, truncated=truncated, byte_truncated=effective < limit,
                                          sections=counts, next_requests=requests, omitted_fields=page_omissions)
        if truncated or effective < limit or omitted:
            page.update(partial=True, status='partial' if page.get('ok') else 'error')
        if _size(page) <= MAX_RESPONSE_BYTES:
            return page
        if effective > 1:
            effective = max(1, effective // 2)
        elif 'technical_payload' in original['data']:
            del original['data']['technical_payload']
            omitted.append('technical_payload: response byte budget; use safe profile for normalized data')
        elif effective:
            effective = 0
        else:
            # Unknown or enormous metadata cannot bypass the public response limit.
            return dict(ok=False, status='error', partial=True, workspace_id=workspace_id, domain='light',
                        coverage='partial', profile=profile, view='light_patch', warnings=['Light Patch metadata exceeds the response byte budget.'],
                        errors={'response': 'response_too_large'}, data={'saved_patch': {'status': saved['status'], 'source': 'saved_archive',
                        'coverage': 'partial', 'freshness': 'unavailable', 'message': 'Response too large; no complete inventory returned.'}, 'pagination': page['data']['pagination']})
