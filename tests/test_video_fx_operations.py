import json
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from qlab_mcp.write import video_fx as fx


def operation(prop='videoEffectIndex/parameter', **args):
    return {'property': prop, 'args': {'effect_type': 'BloomGloom', 'index': 0, **args}}


class Reader:
    def __init__(self):
        self.stack = [{'type': 'BloomGloom', 'enabled': False, 'custom': 'preserve'},
                      {'type': 'Gamma', 'enabled': True}]
        self.params = [{'Choose_Effect': 0, 'inputRadius': 10., 'inputIntensity': .5}, {'inputPower': 1.}]
        self.reads = []

    def read_cue_values(self, ws, uid, keys, **kwargs):
        assert kwargs.get('cacheable') is False
        return {'values': {'uniqueID': uid, 'videoEffects': self.stack}}

    def _request(self, address, **kwargs):
        if address == '/version':
            return SimpleNamespace(data='5.5.10')
        path = address.split('/cue_id/')[1].split('/', 1)[1]
        self.reads.append(path)
        if path == 'uniqueID':
            assert kwargs.get('ensure_always_reply') is True
            return SimpleNamespace(data=address.split('/cue_id/')[1].split('/')[0])
        if path.startswith('videoEffect/'):
            from qlab_mcp.errors import QLabReplyError
            raise QLabReplyError('error', address=path)
        if path == 'videoEffects':
            value = self.stack
        else:
            _, index, route = path.split('/', 2)
            index = int(index)
            value = self.stack[index]['enabled'] if route == 'enabled' else self.params[index] if route == 'parameters' else self.params[index][route.split('/')[1]]
        return SimpleNamespace(data=value)


def test_complete_catalogue():
    assert len(fx.CATALOGUE) == 60
    assert sum(len(p) for p in fx.CATALOGUE.values()) == 262
    counts = {kind: sum(s['kind'] == kind for p in fx.CATALOGUE.values() for s in p.values()) for kind in ('number', 'enum', 'vector', 'boolean')}
    assert counts == {'number': 229, 'enum': 21, 'vector': 11, 'boolean': 1}


@pytest.mark.parametrize('args', [dict(key='inputRadius', value=True), dict(key='inputRadius', value=101),
                                 dict(key='inputRadius', value=float('nan')), dict(key='fake', value=1),
                                 dict(key='Choose_Effect', value=.0)])
def test_invalid_values(args):
    with pytest.raises(ValidationError):
        TypeAdapter(fx.FxOperation).validate_python(operation(**args))


def test_identity_mandatory_and_compound_conflict():
    with pytest.raises(ValidationError):
        TypeAdapter(fx.FxOperation).validate_python({'property': 'videoEffectIndex/enabled', 'args': {'index': 0, 'value': True}})
    with pytest.raises(ValueError):
        fx.normalize_operations([{'property': 'videoEffectIndex/parameters', 'args': {'effect_type': 'Window', 'index': 0, 'parameters': {'inputRectangle': [0, 0, 1, 1], 'Origin_X': 0}}}])


def test_snapshot_guard_and_verification():
    reader = Reader()
    before, changes, ops, deps = fx.preflight(reader, 'ws', 'uid', [operation(key='inputRadius', value=20)])
    key = ops[0]['property']
    assert before[key] == 10
    assert ops[0]['address_suffix'] == 'videoEffectIndex/0/parameter/inputRadius'
    reader.params[0]['inputRadius'] = 20
    assert fx.matches(key, 20, changes[key], deps, reader, 'ws', 'uid')
    fx.check_dependencies(reader, 'ws', 'uid', deps)
    reader.stack[1]['custom'] = 'changed'
    with pytest.raises(ValueError):
        fx.check_dependencies(reader, 'ws', 'uid', deps)


def test_neighbour_change_not_accepted():
    reader = Reader()
    _, changes, ops, deps = fx.preflight(reader, 'ws', 'uid', [operation(key='inputRadius', value=20)])
    reader.params[0]['inputRadius'] = 20
    reader.params[1]['inputPower'] = 2
    key = ops[0]['property']
    assert not fx.matches(key, 20, changes[key], deps, reader, 'ws', 'uid')


def test_observed_outside_band_preserved():
    reader = Reader()
    reader.params[0]['inputRadius'] = 500
    before, _, _, deps = fx.preflight(reader, 'ws', 'uid', [operation(key='inputIntensity', value=.7)])
    assert deps['video_fx']['stack'][0]['parameters']['inputRadius'] == 500


def test_structure_gate_and_single_operation(monkeypatch):
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', set())
    reader = Reader()
    move = operation('videoEffectIndex/move', new_index=1)
    with pytest.raises(ValueError):
        fx.preflight(reader, 'ws', 'uid', [move])
    with pytest.raises(ValueError):
        fx.preflight(reader, 'ws', 'uid', [move, operation(key='inputRadius', value=20)])


def test_parameters_wire_and_bounded_read():
    raw = operation('videoEffectIndex/parameters', parameters={'inputRadius': 20, 'inputIntensity': .7})
    ops = fx.normalize_operations([raw])
    assert json.loads(ops[0]['args'][0]) == raw['args']['parameters']
    reader = Reader()
    selected = fx.read_selected(reader, 'ws', 'uid', [{'effect_type': 'BloomGloom', 'index': 0, 'key': 'inputRadius'}])
    assert selected[0]['parameters'] == {'inputRadius': 10.}
    assert 'videoEffectIndex/0/parameter/inputRadius' in reader.reads


def test_selected_metadata_enabled_unknown_and_outside_band():
    reader = Reader()
    reader.params[0].update(inputRadius=500, nativeExtra={'keep': [1]})
    item = fx.read_selected(reader, 'ws', 'uid', [{'effect_type': 'BloomGloom', 'index': 0}])[0]
    assert item['enabled'] is False
    assert 'videoEffectIndex/0/enabled' in reader.reads
    assert item['parameters']['inputRadius'] == 500
    assert item['parameters']['nativeExtra'] == {'keep': [1]}
    spec = item['parameter_metadata']['inputRadius']
    assert spec['kind'] == 'number' and spec['maximum'] == 100
    assert spec['documented_key'] == 'inputRadius' and spec['native_key'] == 'inputRadius'
    assert spec['source'] == fx.CATALOGUE_METADATA['source']
    assert 'conservative' in spec['range_policy'].lower()
    unknown = item['parameter_metadata']['nativeExtra']
    assert unknown['documented'] is False and unknown['writable'] is False and unknown['reason']
    item['parameter_metadata']['Choose_Effect']['values']['0'] = 'changed'
    assert fx.CATALOGUE['BloomGloom']['Choose_Effect']['values']['0'] != 'changed'


@pytest.mark.parametrize('enabled', [None, 0, 1, 'true'])
def test_selected_enabled_invalid_is_not_hidden(enabled):
    reader = Reader()
    reader.stack[0]['enabled'] = enabled
    with pytest.raises(ValueError, match='enabled readback is not boolean'):
        fx.read_selected(reader, 'ws', 'uid', [{'effect_type': 'BloomGloom', 'index': 0}])


def test_documentary_catalogue_pages_exact_names_and_creation_gates():
    page = fx.catalogue()
    assert page['effect_count'] == 60 and page['parameter_count'] == 262
    assert len(page['effects']) == 10 and page['next_offset'] == 10
    assert fx.catalogue(offset=60)['effects'] == []
    selected = fx.catalogue(['DropShadow', 'LinearKey'])
    assert [item['type'] for item in selected['effects']] == ['DropShadow', 'LinearKey']
    shadow = selected['effects'][0]
    assert shadow['native_parameter_aliases'] == {'Color': 'inputColor'}
    assert shadow['parameters']['inputColor']['aliases'] == ['Color']
    assert shadow['creation_blocked_reason'] == fx.BLOCKED_CREATION['DropShadow']
    assert shadow['write_readiness']['ready'] is False
    assert shadow['write_readiness']['requires_full_stack_preflight'] is True
    shadow['parameters']['inputColor']['maximum'] = 99
    assert fx.CATALOGUE['DropShadow']['inputColor']['maximum'] == 1
    color = fx.catalogue(['ColorControls'])['effects'][0]
    assert color['creation_defaults_available'] is True and color['creation_blocked_reason'] is None
    assert color['write_readiness']['ready'] is False


@pytest.mark.parametrize('kwargs', [{'effect_types': ['dropShadow']}, {'effect_types': ['Gamma'] * 11},
                                 {'effect_types': 'Gamma'}, {'offset': True}, {'offset': -1},
                                 {'limit': True}, {'limit': 0}, {'limit': 11}])
def test_documentary_catalogue_rejects_invalid_request(kwargs):
    with pytest.raises(ValueError):
        fx.catalogue(**kwargs)


def test_vector_uses_documented_json_route():
    ops = fx.normalize_operations([{'property': 'videoEffectIndex/parameter', 'args': {
        'index': 0, 'effect_type': 'WhitePoint', 'key': 'inputColor', 'value': [0, 0, 1, 1]}}])
    assert ops[0]['property'] == 'videoEffectIndex/0/parameter/inputColor'
    assert ops[0]['path'] == 'videoEffectIndex/0/parameters'
    assert json.loads(ops[0]['args'][0]) == {'inputColor': [0, 0, 1, 1]}


def test_validated_structure_still_requires_fade_proof(monkeypatch):
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffectIndex/move'})
    reader = Reader()
    move = operation('videoEffectIndex/move', new_index=1)
    monkeypatch.setattr(fx, 'fade_dependency_proof', lambda *a: {'safe': False, 'fade_dependents': ['fade']})
    with pytest.raises(ValueError, match='Fade dependency'):
        fx.preflight(reader, 'ws', 'uid', [move])
    monkeypatch.setattr(fx, 'fade_dependency_proof', lambda *a: {'safe': True, 'fade_dependents': []})
    _, changes, ops, deps = fx.preflight(reader, 'ws', 'uid', [move])
    reader.stack.reverse()
    reader.params.reverse()
    assert fx.matches(ops[0]['property'], [], changes[ops[0]['property']], deps, reader, 'ws', 'uid')


def test_submode_normalization_is_not_silently_accepted():
    reader = Reader()
    _, changes, ops, deps = fx.preflight(reader, 'ws', 'uid', [operation(key='Choose_Effect', value=1)])
    reader.params[0].update(Choose_Effect=1, inputRadius=50)
    assert not fx.matches(ops[0]['property'], 1, changes[ops[0]['property']], deps, reader, 'ws', 'uid')


def test_delete_restoration_preserves_unknown_attributes(monkeypatch):
    reader = Reader()
    stack = fx.snapshot(reader, 'ws', 'uid')
    monkeypatch.setattr(fx, 'VERIFIED_DEFAULTS', {'BloomGloom': stack[0]})
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffects/insert', 'videoEffectIndex/delete'})
    assert len(fx.restoration_plan(stack, 0)) == 3
    reader.stack[0]['custom'] = 'cannot restore'
    with pytest.raises(ValueError, match='Unknown FX attributes'):
        fx.restoration_plan(fx.snapshot(reader, 'ws', 'uid'), 0)


@pytest.mark.parametrize('effect_type', ['FalseColor', 'GlassLozenge', 'ReflectedTiles'])
def test_delete_restoration_accepts_unknown_native_attributes_at_recorded_defaults(monkeypatch, effect_type):
    default = deepcopy(fx.VERIFIED_DEFAULTS[effect_type])
    monkeypatch.setattr(fx, 'VERIFIED_DEFAULTS', {effect_type: default})
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffects/insert', 'videoEffectIndex/delete'})

    plan = fx.restoration_plan([deepcopy(default)], 0)

    assert plan[0] == {'property': 'videoEffects/insert', 'args': {'effect_type': effect_type, 'index': 0}}
    for operation in plan[1:]:
        if operation['property'] == 'videoEffectIndex/parameters':
            assert set(operation['args']['parameters']) <= set(fx.CATALOGUE[effect_type])


@pytest.mark.parametrize(('effect_type', 'unknown_key'), [
    ('FalseColor', 'inputColor0'),
    ('GlassLozenge', 'Point_2_X'),
    ('ReflectedTiles', '_inputX'),
])
def test_delete_restoration_still_blocks_changed_unknown_native_attributes(monkeypatch, effect_type, unknown_key):
    default = deepcopy(fx.VERIFIED_DEFAULTS[effect_type])
    monkeypatch.setattr(fx, 'VERIFIED_DEFAULTS', {effect_type: default})
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffects/insert', 'videoEffectIndex/delete'})
    changed = deepcopy(default)
    changed['parameters'][unknown_key] = 0 if unknown_key == 'Choose_Effect' else 0.25
    changed['raw'][unknown_key] = changed['parameters'][unknown_key]

    with pytest.raises(ValueError, match='Unknown FX attributes'):
        fx.restoration_plan([changed], 0)


def test_delete_restoration_sets_documented_values_and_uses_default_for_unknowns(monkeypatch):
    default = deepcopy(fx.VERIFIED_DEFAULTS['GlassLozenge'])
    monkeypatch.setattr(fx, 'VERIFIED_DEFAULTS', {'GlassLozenge': default})
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffects/insert', 'videoEffectIndex/delete'})
    changed = deepcopy(default)
    changed['parameters']['inputRadius'] = 125
    changed['raw']['inputRadius'] = 125

    plan = fx.restoration_plan([changed], 0)

    parameters = next(op['args']['parameters'] for op in plan if op['property'] == 'videoEffectIndex/parameters')
    assert parameters == {key: value for key, value in changed['parameters'].items() if key in fx.CATALOGUE['GlassLozenge']}
    assert 'Point_2_X' not in parameters


def test_flat_native_inventory_does_not_prove_type():
    reader = Reader()
    reader.stack = [{'inputRadius': 10, 'inputIntensity': .5, 'Choose_Effect': 0}]
    assert not fx.capabilities(reader.stack)['allowed_operations']
    with pytest.raises(ValueError, match='type identity'):
        fx.preflight(reader, 'ws', 'uid', [operation(key='inputRadius', value=20)])


@pytest.mark.parametrize('kind', ['Video', 'Camera', 'Text'])
@pytest.mark.parametrize('legacy', [False, True])
def test_integrated_signed_writer_repeated_fx_operations(monkeypatch, kind, legacy):
    from qlab_mcp.write import control, visual
    from test_control_cue_writes import Reader as ControlReader, WS, START
    monkeypatch.setattr(control, 'check_write_readiness', lambda *a: {'ok': True})
    monkeypatch.setattr(control, 'ensure_write_ready', lambda *a: None)
    reader = ControlReader()
    reader.values[START]['type'] = kind
    state = Reader()
    reader.values[START]['videoEffects'] = state.stack
    base_request = reader._request

    def request(address, *args, **kwargs):
        field = address.split('/cue_id/')[1].split('/', 1)[1]
        if not field.startswith(('videoEffects', 'videoEffectIndex')):
            return base_request(address, *args, **kwargs)
        if args:
            reader.setters.append((START, field, args))
            _, index, route = field.split('/', 2)
            index = int(index)
            if route == 'parameters':
                state.params[index].update(json.loads(args[0]))
            elif route == 'enabled':
                state.stack[index]['enabled'] = args[0]
            else:
                state.params[index][route.split('/')[1]] = args[0]
        return state._request(address)

    reader._request = request
    fn = getattr(visual, f'edit_{kind.lower()}_cues')
    items = [{'cue_id': START, 'operations': [operation(key='inputRadius', value=20),
                                            operation(key='inputIntensity', value=.7)]}]
    if legacy:
        items[0]['properties'] = {'videoEffectIndex/enabled': {'index': 0, 'value': True}}
    plan = fn(reader, WS, items, True)
    assert plan['ok'], plan
    assert not reader.setters
    items[0]['confirm_gates'] = [op['confirm_token'] for op in plan['results'][0]['planned_operations']]
    result = fn(reader, WS, items, False)
    assert result['ok'], result
    assert len(reader.setters) == (3 if legacy else 2)
    assert state.params[0]['inputRadius'] == 20
    assert state.params[0]['inputIntensity'] == .7
    if legacy:
        assert state.stack[0]['enabled'] is True


def test_selected_read_error_is_partial_preserving_inventory():
    from qlab_mcp.cues.visual import VisualCuesMixin, VideoCueDetailsResult, VideoCueSummary
    class SelectedReader(Reader, VisualCuesMixin):
        pass
    reader = SelectedReader()
    reader.stack = [{'inputRadius': 10}]
    result = VideoCueDetailsResult(workspace_id='ws', cue_id='uid', identity=VideoCueSummary(uniqueID='uid', type='Video'))
    result = reader._selected_video_effects(result, [{'effect_type': 'BloomGloom', 'index': 0, 'key': 'inputRadius'}])
    assert result.status == 'partial' and result.identity is not None
    assert 'videoEffectSelectors' in result.errors


def test_named_native_getter_proves_flat_index_identity(monkeypatch):
    reader = Reader()
    reader.stack = [dict(reader.params[0]), dict(reader.params[1])]
    original = reader._request
    def request(address, **kwargs):
        path = address.split('/cue_id/')[1].split('/', 1)[1]
        if path.endswith('/enabled'):
            return SimpleNamespace(data=True)
        if path.startswith('videoEffect/'):
            name = path.split('/')[1]
            if name not in ['BloomGloom', 'Gamma']:
                from qlab_mcp.errors import QLabReplyError
                raise QLabReplyError('error', address=path)
            return SimpleNamespace(data=reader.params[['BloomGloom', 'Gamma'].index(name)])
        return original(address, **kwargs)
    reader._request = request
    before, _, _, deps = fx.preflight(reader, 'ws', 'uid', [operation(key='inputRadius', value=20)])
    assert before['videoEffectIndex/0/parameter/inputRadius'] == 10
    assert [item['type'] for item in deps['video_fx']['stack']] == ['BloomGloom', 'Gamma']


def test_selected_get_discovers_native_type_without_selector_type():
    reader = Reader()
    reader.stack = [dict(reader.params[0])]
    original = reader._request

    def request(address, **kwargs):
        path = address.split('/cue_id/')[1].split('/', 1)[1]
        if path == 'uniqueID':
            return SimpleNamespace(data='uid')
        if path == 'videoEffectIndex/0/enabled':
            return SimpleNamespace(data=True)
        if path == 'videoEffectIndex/0/parameters':
            return SimpleNamespace(data=reader.params[0])
        if path == 'videoEffectIndex/0/parameter/inputRadius':
            return SimpleNamespace(data=10.)
        if path.startswith('videoEffect/'):
            from qlab_mcp.errors import QLabReplyError
            if path == 'videoEffect/BloomGloom/parameters':
                return SimpleNamespace(data=reader.params[0])
            raise QLabReplyError('error', address=path)
        return original(address, **kwargs)

    reader._request = request
    selected = fx.read_selected(reader, 'ws', 'uid', [{'index': 0, 'key': 'inputRadius'}])[0]
    assert selected['type'] == 'BloomGloom'
    assert selected['parameters'] == {'inputRadius': 10.}
    with pytest.raises(ValueError, match='index/type identity'):
        fx.read_selected(reader, 'ws', 'uid', [{'effect_type': 'Gamma', 'index': 0}])


def test_duplicate_flat_native_payload_cannot_prove_index_identity():
    reader = Reader()
    reader.stack = [dict(reader.params[0]), dict(reader.params[0])]
    with pytest.raises(ValueError, match='identity'):
        fx.snapshot(reader, 'ws', 'uid')


def test_changed_fade_dependency_invalidates_structural_plan(monkeypatch):
    reader = Reader()
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffectIndex/move'})
    monkeypatch.setattr(fx, 'fade_dependency_proof', lambda *a: {'safe': True, 'fade_dependents': [], 'targets': {'fade': ''}})
    _, _, _, deps = fx.preflight(reader, 'ws', 'uid', [operation('videoEffectIndex/move', new_index=1)])
    monkeypatch.setattr(fx, 'fade_dependency_proof', lambda *a: {'safe': False, 'fade_dependents': ['fade'], 'targets': {'fade': 'uid'}})
    with pytest.raises(ValueError, match='Fade dependencies changed'):
        fx.check_dependencies(reader, 'ws', 'uid', deps)


def test_structural_add_repeated_type_rejected_before_setter(monkeypatch):
    reader = Reader()
    monkeypatch.setattr(fx, 'VERIFIED_STRUCTURAL_OPS', {'videoEffects/add'})
    monkeypatch.setattr(fx, 'VERIFIED_DEFAULTS', {'Gamma': fx.snapshot(reader, 'ws', 'uid')[1]})
    with pytest.raises(ValueError, match='repeated FX types'):
        fx.preflight(reader, 'ws', 'uid', [{'property':'videoEffects/add','args':{'effect_type':'Gamma'}}])


def test_native_named_identity_denial_is_not_hidden():
    from qlab_mcp.errors import QLabReplyError
    reader = Reader()
    reader.stack = [dict(reader.params[0])]
    original = reader._request
    def request(address, **kwargs):
        if '/videoEffect/' in address:
            raise QLabReplyError('denied', address=address)
        return original(address, **kwargs)
    reader._request = request
    with pytest.raises(QLabReplyError, match='denied'):
        fx.snapshot(reader, 'ws', 'uid')


def test_structure_blocks_unvalidated_qlab_version():
    reader = Reader()
    original = reader._request
    reader._request = lambda address, **kwargs: SimpleNamespace(data='5.6') if address == '/version' else original(address, **kwargs)
    with pytest.raises(ValueError, match='only for QLab 5.5.10'):
        fx.preflight(reader, 'ws', 'uid', [{'property':'videoEffects/add','args':{'effect_type':'Gamma'}}])


def test_empty_inventory_prepares_queries_and_verifies_identity():
    reader = Reader()
    reader.stack = []
    assert fx.snapshot(reader, 'ws', 'uid') == []
    assert reader.reads == ['uniqueID', 'uniqueID']
    reader.read_cue_values = lambda *a, **k: {'values':{'uniqueID':'wrong','videoEffects':[]}}
    with pytest.raises(ValueError, match='inventory/identity'):
        fx.snapshot(reader, 'ws', 'uid')


def test_recorded_creation_requires_exact_complete_result(monkeypatch):
    reader = Reader()
    reader.stack, reader.params = [], []
    request = {'property': 'videoEffects/add', 'args': {'effect_type': 'ColorControls'}}
    before, changes, ops, deps = fx.preflight(reader, 'ws', 'uid', [request])
    assert before['videoEffects/add'] == []
    assert ops[0]['args'] == ['ColorControls']
    observed = [json.loads(json.dumps(fx.VERIFIED_DEFAULTS['ColorControls']))]
    monkeypatch.setattr(fx, 'snapshot', lambda *a: observed)
    assert fx.matches('videoEffects/add', observed, changes['videoEffects/add'], deps, reader, 'ws', 'uid')
    assert deps['video_fx']['stack'] == observed


@pytest.mark.parametrize('failure', ['wrong_type', 'disabled', 'extra_effect', 'missing_parameter', 'changed_readback'])
def test_recorded_creation_rejects_unexpected_result(failure, monkeypatch):
    reader = Reader()
    reader.stack, reader.params = [], []
    request = {'property': 'videoEffects/add', 'args': {'effect_type': 'ColorControls'}}
    _, changes, _, deps = fx.preflight(reader, 'ws', 'uid', [request])
    observed = [json.loads(json.dumps(fx.VERIFIED_DEFAULTS['ColorControls']))]
    if failure == 'wrong_type':
        observed[0]['type'] = 'Gamma'
    elif failure == 'disabled':
        observed[0]['enabled'] = False
    elif failure == 'extra_effect':
        observed.append(fx.VERIFIED_DEFAULTS['Gamma'])
    elif failure == 'missing_parameter':
        del observed[0]['parameters']['inputContrast']
    else:
        observed[0]['parameters']['inputContrast'] = 2
    monkeypatch.setattr(fx, 'snapshot', lambda *a: observed)
    assert not fx.matches('videoEffects/add', observed, changes['videoEffects/add'], deps, reader, 'ws', 'uid')


@pytest.mark.parametrize('empty', [True, False])
def test_unknown_defaults_blocked_on_any_stack(empty, monkeypatch):
    monkeypatch.setattr(fx, 'VERIFIED_DEFAULTS', {name: value for name, value in fx.VERIFIED_DEFAULTS.items() if name != 'ColorControls'})
    reader = Reader()
    if empty:
        reader.stack, reader.params = [], []
    with pytest.raises(ValueError, match='requires recorded native defaults'):
        fx.preflight(reader, 'ws', 'uid', [{'property': 'videoEffects/add', 'args': {'effect_type': 'ColorControls'}}])


@pytest.mark.parametrize('name,parameters', [
    ('FalseColor', {'inputColor0': [1, 1, 1, 1], 'inputColor1': [1, 1, 1, 1]}),
    ('GlassLozenge', {'Point_1_X': .5, 'Point_1_Y': .5, 'Point_2_X': .5, 'Point_2_Y': .5, 'inputRadius': 100, 'inputRefraction': 1.7}),
    ('ReflectedTiles', {'_inputX': .5, '_inputY': .5, 'inputAngle': 0, 'inputWidth': 100, 'Choose_Effect': 0}),
    ('Window', {'Origin_X': 0, 'Origin_Y': 0, 'Size_W': 1, 'Size_H': 1}),
])
def test_native_shape_differences_require_named_identity_and_complete_aggregate(name, parameters):
    reader = Reader()
    reader.stack, reader.params = [dict(parameters)], [dict(parameters)]
    original = reader._request
    def request(address, **kwargs):
        if f'/videoEffect/{name}/parameters' in address:
            return SimpleNamespace(data=dict(parameters))
        if address.endswith('/enabled'):
            return SimpleNamespace(data=True)
        return original(address, **kwargs)
    reader._request = request
    stack = fx.snapshot(reader, 'ws', 'uid')
    assert stack[0]['type'] == name
    assert stack[0]['parameters'] == parameters
    assert stack[0]['raw'] == parameters


def test_unreadable_documented_parameter_remains_blocked():
    reader = Reader()
    reader.stack = [{'Origin_X': 0, 'Origin_Y': 0, 'Size_W': 1, 'Size_H': 1}]
    reader.params = [dict(reader.stack[0])]
    original = reader._request
    def request(address, **kwargs):
        if '/videoEffect/Window/parameters' in address:
            return SimpleNamespace(data=dict(reader.params[0]))
        if address.endswith('/enabled'):
            return SimpleNamespace(data=True)
        return original(address, **kwargs)
    reader._request = request
    with pytest.raises(ValueError, match='readable native baseline'):
        fx.preflight(reader, 'ws', 'uid', [{'property':'videoEffectIndex/parameter', 'args':{'effect_type':'Window','index':0,'key':'inputRectangle','value':[0,0,1,1]}}])


def test_creation_defaults_come_from_all_verified_native_fixtures():
    assert set(fx.VERIFIED_DEFAULTS) == set(fx.CATALOGUE) - {'LinearKey', 'DropShadow'}
    for name, item in fx.VERIFIED_DEFAULTS.items():
        assert item['type'] == name and item['enabled'] is True
        assert item['parameters'] == item['raw']
        for key, value in item['parameters'].items():
            if key in fx.CATALOGUE[name]:
                fx.validate_value(name, key, value, write=False)


@pytest.mark.parametrize('name', ['LinearKey', 'DropShadow'])
def test_observed_noop_creation_blocked_before_setter(name):
    reader = Reader()
    reader.stack, reader.params = [], []
    with pytest.raises(ValueError, match='returned OSC status=error') as error:
        fx.preflight(reader, 'ws', 'uid', [{'property':'videoEffects/add','args':{'effect_type':name}}])
    assert f'unrecognized video effect name: {name}' in str(error.value)


@pytest.mark.parametrize('name,key,baseline,wanted', [
    ('WhitePoint','inputColor',[1,1,1,1],[.1,.2,.3,1]),
    ('NinePartTiled','inputFlipYTiles',False,True),
])
def test_non_numeric_parameter_uses_json_and_aggregate_reads(name,key,baseline,wanted):
    from qlab_mcp.errors import QLabReplyError
    reader = Reader()
    reader.stack = [{'type': name, 'enabled': True}]
    reader.params = [dict(fx.VERIFIED_DEFAULTS[name]['parameters'])]
    reader.params[0][key] = baseline
    original = reader._request
    def request(address, **kwargs):
        if address.endswith(f'/parameter/{key}'):
            raise QLabReplyError('error', address=address)
        return original(address, **kwargs)
    reader._request = request
    request_op = {'property':'videoEffectIndex/parameter','args':{'effect_type':name,'index':0,'key':key,'value':wanted}}
    before, changes, ops, deps = fx.preflight(reader,'ws','uid',[request_op])
    assert ops[0]['path'] == 'videoEffectIndex/0/parameters'
    assert json.loads(ops[0]['args'][0]) == {key:wanted}
    prop = ops[0]['property']
    assert before[prop] == baseline
    assert fx.read_values(reader,'ws','uid',[prop],changes)[prop] == baseline
    reader.params[0][key] = wanted
    observed = fx.read_values(reader,'ws','uid',[prop],changes)[prop]
    assert fx.matches(prop,observed,changes[prop],deps,reader,'ws','uid')
    selected = fx.read_selected(reader,'ws','uid',[{'effect_type':name,'index':0,'key':key}])
    assert selected[0]['parameters'] == {key:wanted}


def test_drop_shadow_native_color_is_typed_and_aliases_cannot_conflict():
    op = {'property': 'videoEffectIndex/parameter', 'args': {
        'effect_type': 'DropShadow', 'index': 0, 'key': 'Color', 'value': [.2, .3, .4, 1]}}
    TypeAdapter(fx.FxOperation).validate_python(op)
    for value in (True, [0, 0, 0], [0, 0, 2, 1], [0, 0, float('nan'), 1]):
        with pytest.raises(ValidationError):
            TypeAdapter(fx.FxOperation).validate_python({**op, 'args': {**op['args'], 'value': value}})
    with pytest.raises(ValidationError):
        TypeAdapter(fx.FxOperation).validate_python({**op, 'args': {**op['args'], 'effect_type': 'WhitePoint'}})
    with pytest.raises(ValueError, match='Duplicate FX destination'):
        fx.normalize_operations([op, {**op, 'args': {**op['args'], 'key': 'inputColor'}}])
    with pytest.raises(ValueError, match='Duplicate FX destination'):
        fx.normalize_operations([{'property': 'videoEffectIndex/parameters', 'args': {
            'effect_type': 'DropShadow', 'index': 0, 'parameters': {
                'Color': [0, 0, 0, 1], 'inputColor': [1, 1, 1, 1]}}}])


def test_drop_shadow_native_color_preflight_readback_and_capability():
    reader = Reader()
    params = {'Color': [0, 0, 0, 1], 'Distance': 0, 'Angle': 0, 'BlurRadius': 10, 'Alpha': 1}
    reader.stack, reader.params = [dict(params)], [dict(params)]
    original = reader._request
    def request(address, **kwargs):
        if address.endswith('/videoEffect/DropShadow/parameters'):
            return SimpleNamespace(data=reader.params[0])
        if address.endswith('/videoEffectIndex/0/enabled'):
            return SimpleNamespace(data=True)
        return original(address, **kwargs)
    reader._request = request
    wanted = [.2, .3, .4, 1]
    request_op = {'property': 'videoEffectIndex/parameter', 'args': {
        'effect_type': 'DropShadow', 'index': 0, 'key': 'Color', 'value': wanted}}
    before, changes, ops, deps = fx.preflight(reader, 'ws', 'uid', [request_op])
    prop = ops[0]['property']
    assert before[prop] == params['Color']
    assert ops[0]['path'] == 'videoEffectIndex/0/parameters'
    assert json.loads(ops[0]['args'][0]) == {'Color': wanted}
    reader.params[0]['Color'] = reader.stack[0]['Color'] = wanted
    observed = fx.read_values(reader, 'ws', 'uid', [prop], changes)[prop]
    assert fx.matches(prop, observed, changes[prop], deps, reader, 'ws', 'uid')
    selected = fx.read_selected(reader, 'ws', 'uid', [{'effect_type': 'DropShadow', 'index': 0, 'key': 'Color'}])
    assert selected[0]['parameters'] == {'Color': wanted}
    assert selected[0]['enabled'] is True
    metadata = selected[0]['parameter_metadata']['Color']
    assert metadata['native_key'] == 'Color' and metadata['documented_key'] == 'inputColor'
    assert metadata['aliases'] == ['Color'] and metadata['kind'] == 'vector'
    assert metadata['semantic'] == 'rgba' and metadata['maximum'] == 1
    assert 'inputColor' not in selected[0]['raw_attributes']
    caps = fx.capabilities([{'type': 'DropShadow'}])
    assert caps['native_parameter_aliases'] == {'DropShadow': {'Color': 'inputColor'}}
    assert 'DropShadow' in caps['blocked_creation_effects']


def test_existing_linear_key_edit_is_independent_of_creation_block():
    reader = Reader()
    reader.stack = [{'type': 'LinearKey', 'enabled': True}]
    reader.params = [{'inputKeyColor': 0, 'inputCutoff': 3, 'inputContrast': 4.7}]
    before, _, _, _ = fx.preflight(reader, 'ws', 'uid', [{
        'property': 'videoEffectIndex/parameter', 'args': {
            'effect_type': 'LinearKey', 'index': 0, 'key': 'inputCutoff', 'value': 2.5}}])
    assert before['videoEffectIndex/0/parameter/inputCutoff'] == 3
