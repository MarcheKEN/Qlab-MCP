"""Read-only orchestration and bounded public Light Patch pages."""
from copy import deepcopy
import hashlib
from types import SimpleNamespace

import pytest

from qlab_mcp.light_patch import reader as module
from qlab_mcp.models import WorkspaceLightSettingsResult
from test_light_patch_archive import workspace

WS = '11111111-1111-4111-8111-111111111111'


def live(ok=True):
    return dict(ok=ok, status='ok' if ok else 'error', partial=not ok, workspace_id=WS,
                domain='light', profile='safe', view='light_patch', data={'detail': {
                'summary': {'patch_present': True}, 'instruments': [{'name': 'Door', 'comment': 'Keep', 'definition': {'name': 'Dimmer'}}]}} if ok else None)


@pytest.fixture
def local(tmp_path, monkeypatch):
    path = tmp_path / 'sample.qlab5'
    path.write_bytes(workspace())
    row = dict(workspace_id=WS, path=str(path), modified=False)
    calls = []
    def inventory(reader):
        calls.append('inventory')
        return {'documents': [deepcopy(row)]}
    monkeypatch.setattr(module.docs, '_inventory', inventory)
    return SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host='127.0.0.1'))), path, row, calls


def test_clean_read_uses_only_inventory_and_preserves_bytes(local):
    reader, path, row, calls = local
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = module.enrich_light_settings(reader, WS, live())
    saved = result['data']['saved_patch']
    assert saved['status'] == 'ready' and saved['sha256'] == before
    assert saved['freshness'] == 'last_saved'
    assert saved['instruments'][0]['name'] == 'Door'
    assert result['data']['source_status']['comparison'] == 'matches_observable_fields'
    assert calls == ['inventory', 'inventory']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert WorkspaceLightSettingsResult.model_validate(result).data.saved_patch.definitions[0].name == 'Dimmer'


def test_dirty_returns_current_osc_and_separate_last_saved(local):
    reader, path, row, calls = local
    row['modified'] = True
    current = live()
    current['data']['detail']['instruments'][0]['name'] = 'New Name'
    result = module.enrich_light_settings(reader, WS, current)
    assert result['data']['saved_patch']['freshness'] == 'possibly_stale'
    assert result['data']['saved_patch']['instruments'][0]['name'] == 'Door'
    assert result['data']['detail']['instruments'][0]['name'] == 'New Name'
    assert result['data']['source_status']['comparison'] == 'differs'


def test_remote_keeps_live_without_accessing_local_document(monkeypatch):
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host='10.0.0.2')))
    monkeypatch.setattr(module.docs, '_inventory', lambda reader: pytest.fail('remote native read'))
    result = module.enrich_light_settings(reader, WS, live())
    assert result['ok'] and result['partial']
    assert result['data']['detail']['instruments'][0]['name'] == 'Door'
    assert result['data']['saved_patch']['status'] == 'unavailable'


def test_osc_failure_can_return_saved_patch(local):
    reader, *_ = local
    result = module.enrich_light_settings(reader, WS, live(False))
    assert result['ok'] and result['status'] == 'partial'
    assert result['data']['saved_patch']['status'] == 'ready'
    assert result['data']['source_status']['comparison'] == 'not_comparable'


@pytest.mark.parametrize('kind', ['dirty', 'file'])
def test_concurrent_change_discards_saved_records(local, monkeypatch, kind):
    reader, path, row, calls = local
    original = module._read_file
    reads = []
    def read(path):
        value = original(path)
        reads.append(True)
        if len(reads) == 1 and kind == 'dirty':
            row['modified'] = True
        if len(reads) == 2 and kind == 'file':
            return value[0] + b'changed', value[1]
        return value
    monkeypatch.setattr(module, '_read_file', read)
    result = module.enrich_light_settings(reader, WS, live())
    assert result['data']['saved_patch']['status'] == 'changed_during_read'
    assert result['data']['saved_patch']['instruments'] == []
    assert result['data']['detail']['instruments']


def test_uuid_mismatch_is_not_merged(local):
    reader, path, row, calls = local
    other = '22222222-2222-4222-8222-222222222222'
    row['workspace_id'] = other
    result = module.enrich_light_settings(reader, other, live())
    assert result['data']['saved_patch']['status'] == 'unavailable'
    assert not result['data']['saved_patch']['instruments']


def saved_many(count, note=''):
    return dict(status='ready', source='saved_archive', freshness='last_saved', coverage='complete',
                workspace_id=WS, version='5.5.10', build=5510, diagnostics=[], groups=[], definitions=[],
                instruments=[dict(name=f'Lamp {i}', note=note, definition='Dimmer', order=i, output={'backend': 'none'}) for i in range(count)])


def test_thousand_instruments_and_exact_followup(monkeypatch):
    monkeypatch.setattr(module, '_saved', lambda *_: saved_many(1001))
    result = module.enrich_light_settings(None, WS, live())
    page = result['data']['pagination']
    assert len(result['data']['saved_patch']['instruments']) == 1000
    assert page['sections']['instruments']['saved_total'] == 1001
    request = page['next_requests'][0]
    assert request == dict(workspace_id=WS, profile='safe', section='instruments', offset=1000, limit=1000)
    next_page = module.enrich_light_settings(None, WS, live(), **{key: value for key, value in request.items() if key != 'workspace_id'})
    assert next_page['data']['saved_patch']['instruments'][0]['name'] == 'Lamp 1000'
    assert not next_page['data']['pagination']['truncated']


def test_byte_budget_applies_after_typed_serialization(monkeypatch):
    monkeypatch.setattr(module, '_saved', lambda *_: saved_many(100, 'x' * 65536))
    result = module.enrich_light_settings(None, WS, live())
    assert result['data']['pagination']['byte_truncated']
    assert result['data']['pagination']['next_requests']
    assert len(WorkspaceLightSettingsResult.model_validate(result).model_dump_json().encode()) <= module.MAX_RESPONSE_BYTES


def test_technical_payload_stays_osc_and_is_paged(monkeypatch):
    monkeypatch.setattr(module, '_saved', lambda *_: saved_many(3))
    result = live()
    result['data']['technical_payload'] = {'settingKeywords': ['home'], 'instruments': [{'name': f'OSC {i}'} for i in range(3)], 'groups': []}
    page = module.enrich_light_settings(None, WS, result, profile='technical', limit=1)
    assert page['data']['technical_payload']['instruments'] == [{'name': 'OSC 0'}]
    assert page['data']['saved_patch']['instruments'][0]['name'] == 'Lamp 0'
    assert page['data']['pagination']['sections']['instruments']['live_total'] == 3


def test_unsupported_file_preserves_osc(local):
    reader, path, *_ = local
    path.write_bytes(b'bad archive')
    result = module.enrich_light_settings(reader, WS, live())
    assert result['ok'] and result['partial']
    assert result['data']['saved_patch']['status'] == 'unsupported_format'


def test_unsaved_document_and_missing_automation_keep_osc(local, monkeypatch):
    reader, path, row, calls = local
    row['path'] = ''
    result = module.enrich_light_settings(reader, WS, live())
    assert result['data']['saved_patch']['status'] == 'unavailable'
    assert 'no saved' in result['data']['saved_patch']['message']
    def unavailable(reader):
        raise ValueError('Automation permission unavailable')
    monkeypatch.setattr(module.docs, '_inventory', unavailable)
    result = module.enrich_light_settings(reader, WS, live())
    assert result['ok'] and result['data']['detail']['instruments']
    assert result['data']['saved_patch']['message'] == 'Automation permission unavailable'


def test_non_dictionary_technical_payload_is_not_interpreted_as_patch(monkeypatch):
    monkeypatch.setattr(module, '_saved', lambda *_: saved_many(0))
    result = live()
    result['data']['technical_payload'] = ['unrecognized']
    assert module.enrich_light_settings(None, WS, result)['data']['technical_payload'] == ['unrecognized']


def test_single_oversized_record_is_explicitly_omitted(monkeypatch):
    monkeypatch.setattr(module, '_saved', lambda *_: saved_many(1, 'x' * module.MAX_RESPONSE_BYTES))
    result = module.enrich_light_settings(None, WS, live())
    assert result['partial'] and result['data']['pagination']['truncated']
    assert result['data']['pagination']['omitted_fields']
    assert result['data']['saved_patch']['instruments'] == []
    assert len(WorkspaceLightSettingsResult.model_validate(result).model_dump_json().encode()) <= module.MAX_RESPONSE_BYTES


def test_oversized_first_record_does_not_block_following_records(monkeypatch):
    saved = saved_many(2)
    saved['instruments'][0]['note'] = 'x' * module.MAX_RESPONSE_BYTES
    monkeypatch.setattr(module, '_saved', lambda *_: deepcopy(saved))
    result = module.enrich_light_settings(None, WS, live(), section='instruments')
    pagination = result['data']['pagination']
    assert any('saved_patch.instruments[0]' in field and 'not recoverable' in field for field in pagination['omitted_fields'])
    assert pagination['sections']['instruments']['saved_total'] == 2
    assert pagination['next_requests'] == [dict(workspace_id=WS, profile='safe', section='instruments', offset=1, limit=1)]
    request = pagination['next_requests'][0]
    following = module.enrich_light_settings(None, WS, live(), **{key: value for key, value in request.items() if key != 'workspace_id'})
    assert following['data']['saved_patch']['instruments'][0]['name'] == 'Lamp 1'
    assert not following['data']['pagination']['truncated']
    assert not following['data']['pagination']['omitted_fields']
