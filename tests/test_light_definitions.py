"""Definition catalogue and dedicated writer, using synthetic data only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import plistlib
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from qlab_mcp.light_patch import catalogue as cat, definitions as defs, transaction as tx
from qlab_mcp.light_patch.archive import Patch, plan_patch
from qlab_mcp.light_patch.inspection import inspect_saved_patch
from qlab_mcp.light_patch.models import DefinitionOperations, LightPatchOperations
from test_light_patch_archive import workspace

WS = '11111111-1111-4111-8111-111111111111'


def native(name='Example RGBW'):
    parameters = {str(i): dict(type='scalar', name=name, twoBytes=False,
                              valueIsPercentage=True, homeValue=0)
                  for i, name in enumerate(('red', 'green', 'blue', 'white', 'warm white', 'amber'))}
    parameters['-2'] = dict(name='color', type='rgbcolor', outputs=dict(
        red='red', green='green', blue='blue', white='white', warmwhite='warm white', amber='amber'))
    return dict(name=name, manufacturer='Example', definitionVersion=2,
                defaultParameter=-2, parameters=parameters)


def native_virtuals(name='Example Virtuals'):
    names = ('cyan', 'magenta', 'yellow', 'hue', 'saturation', 'intensity',
             'pan', 'tilt', 'red', 'green', 'blue', 'lime')
    parameters = {str(channel): dict(type='scalar', name=parameter, twoBytes=False,
                                     valueIsPercentage=True, homeValue=0)
                  for channel, parameter in enumerate(names)}
    parameters.update({
        '-2': dict(name='cmy', type='cmycolor', outputs={
            'cyan': 'cyan', 'magenta': 'magenta', 'yellow': 'yellow'}),
        '-3': dict(name='hsi', type='hsicolor', outputs={
            'hue': 'hue', 'saturation': 'saturation', 'intensity': 'intensity'}),
        '-4': dict(name='position', type='pantilt', outputs={
            'pan': 'pan', 'tilt': 'tilt'}),
        '-5': dict(name='rgb', type='rgbcolor', outputs={
            'red': 'red', 'green': 'green', 'blue': 'blue', 'lime': 'lime'}),
        '-6': dict(name='controls', type='muxer', outputs=['cmy', 'rgb', 'intensity']),
    })
    return dict(name=name, manufacturer='Example', definitionVersion=2,
                defaultParameter=-3, parameters=parameters)


def library(records):
    objects = ['$null']
    def add(value):
        objects.append(value)
        return plistlib.UID(len(objects) - 1)
    root = add({'NS.keys': [add(name) for name in records],
                'NS.objects': [add(json.dumps(value).encode()) for value in records.values()]})
    return plistlib.dumps({'$archiver': 'NSKeyedArchiver', '$version': 100000,
                          '$top': {'root': root}, '$objects': objects}, fmt=plistlib.FMT_BINARY)


@pytest.fixture
def catalogues(tmp_path, monkeypatch):
    bundled = tmp_path / 'LightDefinitions'
    bundled.write_bytes(library({'example.qlablight': native()}))
    personal = tmp_path / 'LightLibrary'
    personal.mkdir()
    path = personal / 'example.qlablight'
    path.write_text(json.dumps(native()))
    monkeypatch.setattr(cat, 'BUNDLED_PATH', bundled)
    monkeypatch.setattr(cat, 'PERSONAL_PATH', personal)
    return bundled, path


def test_source_identity_filters_pages_and_exact_detail(catalogues):
    result = cat.get_light_definitions(None, query='RGBW', manufacturer='Example', limit=1)
    assert result['ok'] and result['total'] == 2 and result['truncated']
    assert 'parameters' not in result['definitions'][0]
    next_page = cat.get_light_definitions(None, **result['next_request'])
    assert next_page['definitions'][0]['definition_id'] != result['definitions'][0]['definition_id']
    record = cat.get_light_definitions(None, definition_id=result['definitions'][0]['definition_id'])['definitions'][0]
    assert record['importable'] and record['dmx_footprint'] == 6
    assert next(p for p in record['parameters'] if p['channel'] == -2)['outputs']['warmwhite'] == 'warm white'
    assert record['mode'] is None


def test_invalid_record_degrades_without_discarding_good_source(catalogues):
    catalogues[1].write_text('{bad')
    result = cat.get_light_definitions(None)
    assert result['ok'] and result['status'] == 'partial' and result['total'] == 1
    assert next(s for s in result['sources'] if s['source'] == 'personal')['failed_records'] == 1


def test_duplicate_json_keys_and_nonfinite_rejected():
    for data in (b'{"name":"a","name":"b"}', b'{"n":NaN}'):
        with pytest.raises(ValueError):
            cat._json(data)


def test_symlinks_and_limits_are_rejected(tmp_path):
    source = tmp_path / 'source'; source.write_bytes(b'1234')
    link = tmp_path / 'link'; link.symlink_to(source)
    with pytest.raises(OSError):
        cat.read_stable(link)
    with pytest.raises(ValueError):
        cat.read_stable(source, 3)
    with pytest.raises(ValueError):
        cat.decode_library(b'invalid')


def test_unknown_variant_is_visible_but_not_importable(catalogues):
    value = native(); value['parameters']['-2']['type'] = 'pantilt'
    catalogues[1].write_text(json.dumps(value))
    record = cat.get_light_definitions(None, source='personal')['definitions'][0]
    detail = cat.get_light_definitions(None, source='personal', definition_id=record['definition_id'])['definitions'][0]
    assert not detail['importable']
    assert any(p['type'] == 'pantilt' for p in detail['parameters'])


def test_native_virtual_variants_validate_and_do_not_add_dmx_footprint():
    detail = defs.inspect_native(native_virtuals())
    assert detail['importable']
    assert detail['dmx_footprint'] == 12
    assert {p['type'] for p in detail['parameters']} == {
        'scalar', 'rgbcolor', 'cmycolor', 'hsicolor', 'pantilt', 'muxer'}


def test_native_muxer_cycles_and_unresolved_outputs_are_not_importable():
    value = native_virtuals()
    value['parameters']['-6']['outputs'] = ['other']
    value['parameters']['-7'] = dict(name='other', type='muxer', outputs=['controls'])
    detail = defs.inspect_native(value)
    assert not detail['importable']
    assert any('cycle' in note for note in detail['compatibility_notes'])

    value = native_virtuals()
    value['parameters']['-6']['outputs'] = ['missing']
    assert not defs.inspect_native(value)['importable']


def test_rgb_extra_emitter_stays_blocked_except_lime():
    value = native_virtuals()
    value['parameters']['-5']['outputs']['ultraviolet'] = 'ultraviolet'
    value['parameters']['12'] = dict(type='scalar', name='ultraviolet', twoBytes=False,
                                     valueIsPercentage=True, homeValue=0)
    assert not defs.inspect_native(value)['importable']


def test_native_16bit_channel_cannot_cross_universe_end():
    value = native_virtuals()
    channel = value['parameters'].pop('11')
    channel['twoBytes'] = True
    value['parameters']['511'] = channel
    assert not defs.inspect_native(value)['importable']


def test_typed_definition_inputs_accept_all_supported_virtual_bindings():
    operation = dict(action='create_definition', name='Typed Virtuals', manufacturer='Example',
        default_parameter='controls', parameters=[
            dict(type='scalar', name='cyan'), dict(type='scalar', name='magenta'),
            dict(type='scalar', name='yellow'), dict(type='scalar', name='hue'),
            dict(type='scalar', name='saturation'), dict(type='scalar', name='intensity'),
            dict(type='scalar', name='pan'), dict(type='scalar', name='tilt'),
            dict(type='scalar', name='red'), dict(type='scalar', name='green'),
            dict(type='scalar', name='blue'), dict(type='scalar', name='lime'),
            dict(type='cmycolor', name='cmy', outputs={'cyan': 'cyan', 'magenta': 'magenta', 'yellow': 'yellow'}),
            dict(type='hsicolor', name='hsi', outputs={'hue': 'hue', 'saturation': 'saturation', 'intensity': 'intensity'}),
            dict(type='pantilt', name='position', outputs={'pan': 'pan', 'tilt': 'tilt'}),
            dict(type='rgbcolor', name='rgb', outputs={'red': 'red', 'green': 'green', 'blue': 'blue', 'lime': 'lime'}),
            dict(type='muxer', name='controls', outputs=['cmy', 'rgb', 'intensity']),
        ])
    validated = TypeAdapter(DefinitionOperations).validate_python([operation])[0]
    assert [parameter.type for parameter in validated.parameters[-5:]] == [
        'cmycolor', 'hsicolor', 'pantilt', 'rgbcolor', 'muxer']


def test_typed_virtual_definition_uses_native_subclasses_and_bindings():
    operation = dict(action='create_definition', name='Typed Virtuals', manufacturer='Example',
        default_parameter='controls', parameters=[
            dict(type='scalar', name='cyan'), dict(type='scalar', name='magenta'),
            dict(type='scalar', name='yellow'), dict(type='scalar', name='hue'),
            dict(type='scalar', name='saturation'), dict(type='scalar', name='intensity'),
            dict(type='scalar', name='pan'), dict(type='scalar', name='tilt'),
            dict(type='scalar', name='red'), dict(type='scalar', name='green'),
            dict(type='scalar', name='blue'), dict(type='scalar', name='lime'),
            dict(type='cmycolor', name='cmy', outputs={'cyan': 'cyan', 'magenta': 'magenta', 'yellow': 'yellow'}),
            dict(type='hsicolor', name='hsi', outputs={'hue': 'hue', 'saturation': 'saturation', 'intensity': 'intensity'}),
            dict(type='pantilt', name='position', outputs={'pan': 'pan', 'tilt': 'tilt'}),
            dict(type='rgbcolor', name='rgb', outputs={'red': 'red', 'green': 'green', 'blue': 'blue', 'lime': 'lime'}),
            dict(type='muxer', name='controls', outputs=['cmy', 'rgb', 'intensity']),
        ])
    planned = plan_patch(workspace(), [operation])
    patch = Patch(planned['output_bytes'])
    definition = patch.archive.ref(patch.find('Typed Virtuals', 'definition'))
    parameters = patch.parameter_entries(definition['parameters'])
    class_names = {channel: patch.archive.kind(ref) for channel, ref in parameters.items()}
    assert class_names == {
        **{channel: 'LightCueInstrumentDefinitionParameterScalar' for channel in range(12)},
        -2: 'LightCueInstrumentDefinitionParameterCMYColor',
        -3: 'LightCueInstrumentDefinitionParameterHSIColor',
        -4: 'LightCueInstrumentDefinitionParameterPanTilt',
        -5: 'LightCueInstrumentDefinitionParameterRGBColor',
        -6: 'LightCueInstrumentDefinitionParameterMuxer',
    }
    summary = next(item for item in planned['summary']['definitions'] if item['name'] == 'Typed Virtuals')
    assert summary['default_parameter'] == -6
    assert summary['parameters'][-1]['outputs'] == ['cmy', 'rgb', 'intensity']


def test_update_definition_encodes_virtuals_and_inspection_reads_all_bindings():
    value = native_virtuals('Dimmer')
    parameters = []
    for channel in range(12):
        name = value['parameters'][str(channel)]['name']
        parameters.append(dict(type='scalar', name=name))
    for channel in ('-2', '-3', '-4', '-5', '-6'):
        parameter = value['parameters'][channel]
        parameters.append(dict(type=parameter['type'], name=parameter['name'], outputs=parameter['outputs']))
    planned = plan_patch(workspace(), [dict(action='update_definition', name='Dimmer',
        parameters=parameters, default_parameter='hsi')])
    saved = inspect_saved_patch(planned['output_bytes'])
    assert saved['coverage'] == 'complete'
    definition = saved['definitions'][0]
    assert definition['dmx_footprint'] == 12
    assert definition['default_parameter'] == -3
    assert {parameter['type'] for parameter in definition['parameters']} == {
        'scalar', 'rgbcolor', 'cmycolor', 'hsicolor', 'pantilt', 'muxer'}
    assert next(p for p in definition['parameters'] if p['type'] == 'muxer')['outputs'] == [
        'cmy', 'rgb', 'intensity']


@pytest.mark.parametrize("version", [1, 2])
def test_native_virtual_import_preserves_unknown_json_metadata_and_classes(version):
    value = native_virtuals()
    value["definitionVersion"] = version
    value['vendorPayload'] = {'revision': 3, 'labels': ['native', 'preserved']}
    value['parameters']['-2']['futureCalibration'] = {'range': [0, 127]}
    operation = dict(action='create_definition', name=value['name'], manufacturer=value['manufacturer'],
                     parameters=[dict(type='scalar', name='placeholder')])
    assert defs.inspect_native(value)['importable']
    planned = plan_patch(workspace(), [operation], native_imports={value['name']: value})
    patch = Patch(planned['output_bytes'])
    archive = patch.archive
    definition = archive.ref(patch.find(value['name'], 'definition'))
    assert archive.ref(definition['definitionVersion']) == version
    payload = archive.mapping(definition['vendorPayload'])
    assert archive.ref(payload['revision']) == 3
    assert [archive.ref(ref) for ref in archive.array(payload['labels'])] == ['native', 'preserved']
    cmy_ref = patch.parameter_entries(definition['parameters'])[-2]
    cmy = archive.ref(cmy_ref)
    assert archive.kind(cmy_ref) == 'LightCueInstrumentDefinitionParameterCMYColor'
    calibration = archive.mapping(cmy['futureCalibration'])
    assert [archive.ref(ref) for ref in archive.array(calibration['range'])] == [0, 127]
    imported = next(d for d in inspect_saved_patch(planned['output_bytes'])['definitions']
                    if d['name'] == value['name'])
    assert imported['dmx_footprint'] == 12


@pytest.mark.parametrize('change', ['missing_output', 'overlap', 'default', 'home', 'duplicate'])
def test_native_import_validation(change):
    value = native()
    if change == 'missing_output': value['parameters']['-2']['outputs']['red'] = 'missing'
    if change == 'overlap': value['parameters']['0']['twoBytes'] = True
    if change == 'default': value['defaultParameter'] = 50
    if change == 'home': value['parameters']['0']['homeValue'] = 101
    if change == 'duplicate': value['parameters']['1']['name'] = 'red'
    assert not defs.inspect_native(value)['importable']


def test_native_16bit_channel_gap_is_preserved():
    value = native(); value['parameters']['0']['twoBytes'] = True
    value['parameters']['10'] = value['parameters'].pop('1')
    assert defs.inspect_native(value)['importable']
    op = dict(action='create_definition', name=value['name'], manufacturer='Example',
              parameters=[dict(type='scalar', name='intensity')])
    plan = plan_patch(workspace(), [op], native_imports={value['name']: value})
    result = next(d for d in plan['summary']['definitions'] if d['name'] == value['name'])
    assert result['default_parameter'] == -2
    assert next(p for p in result['parameters'] if p['name'] == 'green')['channel'] == 10
    assert result['parameters'][-1]['outputs'] == value['parameters']['-2']['outputs']


def test_public_patch_rejects_definitions_and_dedicated_model_accepts():
    operation = dict(action='delete_definition', name='Unused')
    with pytest.raises(ValidationError):
        TypeAdapter(LightPatchOperations).validate_python([operation])
    assert TypeAdapter(DefinitionOperations).validate_python([operation])[0].name == 'Unused'


@pytest.fixture
def document(tmp_path, monkeypatch):
    path = tmp_path / 'show.qlab5'; path.write_bytes(workspace())
    row = dict(workspace_id=WS, name='show', path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    state = SimpleNamespace(path=path, rows=[row], calls=[])
    monkeypatch.setattr(tx, '_app_build', lambda: ('5.5.10', '5510'))
    monkeypatch.setattr(tx.docs, '_inventory', lambda _: {'documents': deepcopy(state.rows)})
    monkeypatch.setattr(tx.docs, 'check_write_readiness', lambda *_: {'ok': True})
    monkeypatch.setattr(tx, '_live', lambda *args: {})
    def close(reader, action, **kwargs):
        state.calls.append('close'); state.rows.clear(); return {'sent': True}
    def reopen(*args):
        state.calls.append('open'); state.rows.append(deepcopy(row)); return {'sent': True}
    monkeypatch.setattr(tx.docs, '_native_request', close)
    monkeypatch.setattr(tx, '_reopen', reopen)
    state.reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host='127.0.0.1', timeout=2)))
    return state


def test_dedicated_import_transaction_preserves_other_data_and_token_family(catalogues, document):
    record = cat.get_light_definitions(None, source='personal')['definitions'][0]
    ops = [dict(action='import_definition', definition_id=record['definition_id'])]
    before = document.path.read_bytes()
    preview = defs.edit_light_definitions(document.reader, WS, ops)
    assert preview['ok'] and preview['confirm_token'].startswith('confirm:lightDefinitions:v1:')
    assert preview['planned_operations'][0]['action'] == 'import_definition'
    assert len(preview['planned_operations'][0]['parameters']) == 7
    assert document.calls == [] and document.path.read_bytes() == before
    result = defs.edit_light_definitions(document.reader, WS, ops, False, preview['confirm_token'])
    assert result['ok'], result
    assert document.calls == ['close', 'open']
    patch = Patch(document.path.read_bytes())
    assert len(patch.snapshot()['definitions']) == 2
    assert patch.snapshot()['instruments'][0]['name'] == 'Door'
    assert patch.outer.ref(patch.outer.mapping(patch.outer.root)['unrelated']) == 'keep cues'
    assert not defs.edit_light_definitions(document.reader, WS, ops, False, preview['confirm_token'])['ok']


def test_changed_catalogue_blocks_before_close(catalogues, document):
    record = cat.get_light_definitions(None, source='personal')['definitions'][0]
    ops = [dict(action='import_definition', definition_id=record['definition_id'])]
    preview = defs.edit_light_definitions(document.reader, WS, ops)
    value = native(); value['manufacturer'] = 'Changed'
    catalogues[1].write_text(json.dumps(value))
    result = defs.edit_light_definitions(document.reader, WS, ops, False, preview['confirm_token'])
    assert not result['ok'] and not document.calls


def test_in_use_delete_blocked_rename_references_and_noop(document):
    deleted = defs.edit_light_definitions(document.reader, WS, [dict(action='delete_definition', name='Dimmer')])
    assert not deleted['ok'] and not document.calls
    ops = [dict(action='rename_definition', name='Dimmer', new_name='Renamed')]
    preview = defs.edit_light_definitions(document.reader, WS, ops)
    assert preview['summary']['instruments'][0]['definition'] == 'Renamed'
    result = defs.edit_light_definitions(document.reader, WS, ops, False, preview['confirm_token'])
    assert result['ok']
    no_op = defs.edit_light_definitions(document.reader, WS, [dict(action='update_definition', name='Renamed', manufacturer='Example')])
    assert no_op['status'] == 'no_op'
    assert document.calls == ['close', 'open']


def test_dirty_and_expired_definition_preview(document, monkeypatch):
    ops = [dict(action='rename_definition', name='Dimmer', new_name='Renamed')]
    document.rows[0]['modified'] = True
    assert defs.edit_light_definitions(document.reader, WS, ops)['status'] == 'needs_save'
    document.rows[0]['modified'] = False
    preview = defs.edit_light_definitions(document.reader, WS, ops)
    now = tx.time.time(); monkeypatch.setattr(tx.time, 'time', lambda: now + 301)
    assert not defs.edit_light_definitions(document.reader, WS, ops, False, preview['confirm_token'])['ok']
    assert not document.calls


def test_workspace_uses_last_saved_source_and_exposes_dirty(catalogues, monkeypatch):
    monkeypatch.setattr(cat, '_saved', lambda *args: dict(status='ready', sha256='hash', document_modified=True,
        freshness='possibly_stale', definitions=[dict(name='Local', manufacturer='Example', parameters=[], dmx_footprint=1)],
        instruments=[], groups=[], diagnostics=[]))
    result = cat.get_light_definitions(None, workspace_id=WS, source='workspace')
    assert result['definitions'][0]['document_modified'] is True
    assert result['definitions'][0]['freshness'] == 'possibly_stale'


def test_catalogue_read_does_not_modify_library_bytes(catalogues):
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in catalogues]
    cat.get_light_definitions(None)
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in catalogues] == before


def test_import_never_replaces_existing_placeholder_shape(catalogues, document):
    value = native(name='Dimmer'); value['manufacturer'] = 'Example'
    catalogues[1].write_text(json.dumps(value))
    record = cat.get_light_definitions(None, source='personal')['definitions'][0]
    result = defs.edit_light_definitions(document.reader, WS, [dict(action='import_definition', definition_id=record['definition_id'])])
    assert not result['ok'] and 'Duplicate' in result['error']
    assert not document.calls


def test_native_double_home_without_integer_is_encodable():
    value = native(); value['parameters']['0']['homeValueDouble'] = 12.5
    del value['parameters']['0']['homeValue']
    assert defs.inspect_native(value)['importable']
    operation = dict(action='create_definition', name=value['name'], manufacturer='Example', parameters=[dict(type='scalar', name='intensity')])
    result = plan_patch(workspace(), [operation], native_imports={value['name']:value})
    record = next(d for d in result['summary']['definitions'] if d['name'] == value['name'])
    assert record['parameters'][0]['homeValueDouble'] == 12.5


def test_unavailable_exact_id_is_not_missing(catalogues, monkeypatch):
    monkeypatch.setattr(cat, 'BUNDLED_PATH', Path('/nonexistent/bundled/library'))
    result = cat.get_light_definitions(None, definition_id='bundled:missing')
    assert not result['ok'] and result['status'] == 'unavailable'
    result = cat.get_light_definitions(None, source='workspace')
    assert not result['ok'] and result['status'] == 'unavailable'


def test_array_definition_parameters_can_be_updated():
    patch = Patch(workspace()); a = patch.archive
    definition = a.ref(patch.find('Dimmer', 'definition'))
    definition['parameters'] = a.make_array(list(a.mapping(definition['parameters']).values()))
    result = plan_patch(patch.finish(), [dict(action='update_definition', name='Dimmer', default_parameter=None)])
    assert result['summary']['definitions'][0]['default_parameter'] == -1


def test_import_dependency_rechecked_before_close(catalogues, document, monkeypatch):
    record = cat.get_light_definitions(None, source='personal')['definitions'][0]
    ops = [dict(action='import_definition', definition_id=record['definition_id'])]
    preview = defs.edit_light_definitions(document.reader, WS, ops)
    original = cat.load_catalogue
    calls = []
    def changing(source):
        calls.append(source)
        if len(calls) == 2:
            catalogues[1].write_text(json.dumps(native('Changed')))
        return original(source)
    monkeypatch.setattr(cat, 'load_catalogue', changing)
    result = defs.edit_light_definitions(document.reader, WS, ops, False, preview['confirm_token'])
    assert not result['ok'] and 'changed before Close' in result['error']
    assert not document.calls


def test_workspace_uuid_is_canonicalized_before_native_inventory(monkeypatch):
    seen = []
    def saved(reader, workspace_id):
        seen.append(workspace_id)
        return dict(status='ready', definitions=[], instruments=[], groups=[], diagnostics=[])
    monkeypatch.setattr(cat, '_saved', saved)
    cat.get_light_definitions(None, source='workspace', workspace_id='abcdefab-abcd-4abc-8abc-abcdefabcdef')
    assert seen == ['ABCDEFAB-ABCD-4ABC-8ABC-ABCDEFABCDEF']


def test_oversized_detail_reports_unrecoverable_record(catalogues, monkeypatch):
    monkeypatch.setattr(cat, 'MAX_RESPONSE_BYTES', 33000)
    record = cat.load_catalogue('personal')[0][0]
    result = cat.get_light_definitions(None, source='personal', definition_id=record['definition_id'])
    assert not result['ok'] and result['status'] == 'partial' and result['truncated']
    assert any('exceeds the response budget' in warning for warning in result['warnings'])
