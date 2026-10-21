"""Bounded, read-only local QLab definition catalogues; never modify vendor/user files."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat

from .archive import Archive
from .reader import _saved
from ..workspace_documents import _uuid
from ..sanitizer import sanitize_exception_message

BUNDLED_PATH = Path('/Applications/QLab.app/Contents/Resources/LightDefinitions')
PERSONAL_PATH = Path.home() / 'Library/Application Support/QLab/LightLibrary'
MAX_BYTES = 64 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
MAX_RECORDS = 20_000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def read_stable(path: Path, maximum: int = MAX_BYTES) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise ValueError('Definition source exceeds the regular-file size limit.')
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if len(data) > maximum or identity(before) != identity(after) or identity(after) != identity(path.stat()):
        raise ValueError('Definition source changed during reading.')
    return data


def decode_library(data: bytes) -> dict[str, bytes]:
    if len(data) > MAX_BYTES:
        raise ValueError('Bundled library exceeds size limit.')
    if not data.startswith(b'bplist00'):
        if not data.startswith((b'bv4-', b'bv41')) or not data.endswith(b'bv4$'):
            raise ValueError('Unsupported bundled library container.')
        library = ctypes.CDLL('/usr/lib/libcompression.dylib')
        decode = library.compression_decode_buffer
        decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p,
                           ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int]
        decode.restype = ctypes.c_size_t
        target = ctypes.create_string_buffer(MAX_BYTES + 1)
        source = ctypes.create_string_buffer(data)
        size = decode(target, len(target), source, len(data), None, 0x100)
        if not 0 < size <= MAX_BYTES:
            raise ValueError('Bundled LZ4 library is invalid or exceeds decoded size limit.')
        data = target.raw[:size]
    archive = Archive(data)
    records = archive.mapping(archive.root)
    if len(records) > MAX_RECORDS:
        raise ValueError('Definition catalogue exceeds record limit.')
    result = {}
    for name, ref in records.items():
        payload = archive.ref(ref)
        if not isinstance(name, str) or not isinstance(payload, bytes) or len(payload) > MAX_RECORD_BYTES:
            raise ValueError('Unsupported bundled definition record.')
        result[name] = payload
    return result


def _json(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate definition JSON key.')
            result[key] = value
        return result
    value = json.loads(data, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON value.')))
    if not isinstance(value, dict):
        raise ValueError('Definition must be a JSON object.')
    # Serialization bounds also apply after parsing; reject pathological nesting.
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > 32:
            raise ValueError('Definition nesting exceeds limit.')
        if isinstance(item, dict):
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
    return value


def _record(source, origin, payload, fingerprint):
    native = _json(payload)
    name, manufacturer = native.get('name'), native.get('manufacturer')
    if not isinstance(name, str) or not isinstance(manufacturer, str):
        raise ValueError('Definition lacks a name or manufacturer.')
    digest = hashlib.sha256(source.encode() + b'\0' + origin.encode() + b'\0' + payload).hexdigest()
    from .definitions import inspect_native
    detail = inspect_native(native)
    return dict(definition_id=f'{source}:{digest}', source=source, name=name,
                manufacturer=manufacturer, mode=native.get('mode'),
                dmx_footprint=detail['dmx_footprint'], importable=detail['importable'],
                compatibility_notes=detail['compatibility_notes'],
                source_sha256=fingerprint, parameters=detail['parameters'],
                default_parameter=native.get('defaultParameter', -1),
                definition_version=native.get('definitionVersion'),
                uninterpreted_fields=detail['uninterpreted_fields'], _native=native)


def _personal_files():
    if not PERSONAL_PATH.exists():
        return []
    if PERSONAL_PATH.is_symlink() or not PERSONAL_PATH.is_dir():
        raise ValueError('Personal definition library must be a real directory.')
    paths = sorted(PERSONAL_PATH.glob('*.qlablight'))
    if len(paths) > MAX_RECORDS:
        raise ValueError('Personal library exceeds record limit.')
    return paths


def load_catalogue(source: str) -> tuple[list[dict], list[dict]]:
    records, statuses = [], []
    for selected in ('bundled', 'personal'):
        if source not in ('all', selected):
            continue
        errors = []
        try:
            if selected == 'bundled':
                data = read_stable(BUNDLED_PATH)
                fingerprint = hashlib.sha256(data).hexdigest()
                items = [(name, payload, fingerprint) for name, payload in decode_library(data).items()]
            else:
                paths = _personal_files()
                items = []
                total_bytes = 0
                for path in paths:
                    try:
                        payload = read_stable(path, MAX_RECORD_BYTES)
                        total_bytes += len(payload)
                        if total_bytes > MAX_BYTES:
                            errors.append('Personal catalogue exceeds the total 64 MiB read budget; remaining files omitted.')
                            break
                        items.append((path.name, payload, hashlib.sha256(payload).hexdigest()))
                    except (OSError, ValueError) as exc:
                        errors.append(sanitize_exception_message(exc))
                if _personal_files() != paths:
                    raise ValueError('Personal library changed during reading.')
            for name, payload, fingerprint in items:
                try:
                    records.append(_record(selected, name, payload, fingerprint))
                except (ValueError, TypeError, KeyError, RecursionError) as exc:
                    errors.append(sanitize_exception_message(exc))
            statuses.append(dict(source=selected, status='partial' if errors else 'ready',
                                 failed_records=len(errors), errors=errors[:20]))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
            statuses.append(dict(source=selected, status='unavailable', message=sanitize_exception_message(exc)))
    return records, statuses


def get_light_definitions(reader, workspace_id=None, source='all', query='', manufacturer='',
                          definition_id=None, offset=0, limit=100):
    if source not in {'all', 'bundled', 'personal', 'workspace'} or type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('Invalid source, offset or limit.')
    if workspace_id is not None:
        workspace_id = _uuid(workspace_id)
    records, statuses = load_catalogue(source)
    if source in {'all', 'workspace'}:
        if workspace_id is None:
            statuses.append(dict(source='workspace', status='not_requested', message='Supply workspace_id for saved workspace definitions.'))
        else:
            saved = _saved(reader, workspace_id)
            statuses.append({key: value for key, value in saved.items()
                             if key not in {'instruments', 'groups', 'definitions', 'diagnostics'}} | {'source': 'workspace'})
            for definition in saved['definitions']:
                payload = json.dumps(definition, ensure_ascii=False, sort_keys=True).encode()
                records.append(dict(definition_id='workspace:' + hashlib.sha256(workspace_id.encode() + payload).hexdigest(),
                                    source='workspace', **definition, mode=None, importable=False,
                                    compatibility_notes=['Already in this workspace; use update or rename.'],
                                    source_sha256=saved.get('sha256'), document_modified=saved.get('document_modified'),
                                    freshness=saved['freshness']))
    records = [record for record in records if query.casefold() in (record['name'] + ' ' + record['manufacturer']).casefold()
               and (not manufacturer or manufacturer.casefold() == record['manufacturer'].casefold())
               and (definition_id is None or record['definition_id'] == definition_id)]
    records.sort(key=lambda r: (r['manufacturer'].casefold(), r['name'].casefold(), r['source'], r['definition_id']))
    page = []
    page_bytes = 2
    oversized_record = False
    for record in records[offset:offset + limit]:
        value = {key: val for key, val in record.items() if not key.startswith('_') and (definition_id is not None or key not in {'parameters', 'used_by'})}
        record_bytes = len(json.dumps(value, ensure_ascii=False).encode()) + (2 if page else 0)
        if page_bytes + record_bytes > MAX_RESPONSE_BYTES - 32768:
            oversized_record = not page
            break
        page.append(value)
        page_bytes += record_bytes
    available = any(s['status'] in {'ready', 'partial'} for s in statuses)
    partial = any(s['status'] not in {'ready', 'not_requested'} for s in statuses)
    requested_source = definition_id.split(':', 1)[0] if definition_id else None
    source_unavailable = requested_source is not None and not any(
        s['source'] == requested_source and s['status'] in {'ready', 'partial'} for s in statuses)
    status = 'unavailable' if not available or source_unavailable else 'partial' if partial or oversized_record else 'ok'
    if definition_id is not None and not records and status == 'ok':
        status = 'not_found'
    next_offset = offset + len(page)
    return dict(ok=available and not source_unavailable and not oversized_record and (definition_id is None or bool(page)),
                status=status,
                definitions=page, sources=statuses, total=len(records), offset=offset, limit=limit,
                truncated=next_offset < len(records),
                next_request=dict(workspace_id=workspace_id, source=source, query=query,
                                  manufacturer=manufacturer, definition_id=definition_id,
                                  offset=next_offset, limit=limit) if page and next_offset < len(records) else None,
                warnings=['Saved definitions do not prove fixture identity, connection or physical DMX output.'] +
                (['The next complete definition exceeds the response budget; it was omitted and cannot be recovered through this page.'] if oversized_record else []))
