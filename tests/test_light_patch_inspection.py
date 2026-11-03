"""Saved patch reads inspect configuration without authoring or QLab events."""
import pytest

from qlab_mcp.light_patch.archive import Patch, plan_patch
from qlab_mcp.light_patch.inspection import inspect_saved_patch
from test_light_patch_archive import workspace


def test_reads_outputs_nested_groups_and_unused_definitions():
    source = plan_patch(workspace(), [
        {'action': 'update_instrument', 'name': 'Door', 'output': {'backend': 'artnet', 'net': 1, 'subnet': 2, 'universe': 3, 'address': 512}},
        {'action': 'create_instrument', 'name': 'USB', 'definition': 'Dimmer', 'output': {'backend': 'usb', 'device_serial': 'SYNTHETIC', 'device_name': 'Example', 'device_universes': 2, 'universe': 1, 'address': 10}},
        {'action': 'create_definition', 'name': 'Unused', 'manufacturer': 'Example', 'parameters': [{'type': 'scalar', 'name': 'fine', 'two_bytes': True}]},
        {'action': 'create_group', 'name': 'Child', 'members': ['Door']},
        {'action': 'create_group', 'name': 'Parent', 'members': ['Child', 'USB']},
    ])['output_bytes']
    result = inspect_saved_patch(source)
    assert result['coverage'] == 'complete'
    assert result['instruments'][0]['dmx_address_end'] == 512
    assert result['instruments'][0]['output']['net'] == 1
    assert result['instruments'][1]['output']['device_serial'] == 'SYNTHETIC'
    assert result['groups'][1]['members'] == ['Child', 'USB']
    assert result['definitions'][1]['used_by'] == []
    assert result['definitions'][1]['dmx_footprint'] == 2
    assert result['definitions'][0]['version'] == 2


def test_read_does_not_require_disabled_automatic_cues():
    patch = Patch(workspace())
    a = patch.outer
    general = a.ref(a.mapping(a.mapping(a.root)['settings'])['General'])
    index = [a.ref(key) for key in general['NS.keys']].index('doStartOnOpen')
    general['NS.objects'][index] = True
    source = a.dump()
    assert inspect_saved_patch(source)['instruments'][0]['name'] == 'Door'
    with pytest.raises(ValueError, match='automatic'):
        Patch(source)


def test_only_active_items_and_partial_unknowns_are_reported():
    patch = Patch(workspace())
    a = patch.archive
    a.add(dict(a.ref(patch.items[0]), name=a.add('Residual')))
    unknown = a.add({'$class': a.cls('UnknownLightItem'), 'name': a.add('Future')})
    patch.items.append(unknown)
    result = inspect_saved_patch(patch.finish())
    assert [entry['name'] for entry in result['instruments']] == ['Door']
    assert result['coverage'] == 'partial'
    assert result['diagnostics'][0]['code'] == 'unsupported_item'


def test_broken_group_references_and_cycles_remain_inspectable():
    patch = Patch(plan_patch(workspace(), [
        {'action': 'create_group', 'name': 'A', 'members': []},
        {'action': 'create_group', 'name': 'B', 'members': ['A']},
    ])['output_bytes'])
    a = patch.archive
    a.ref(patch.find('A', 'group'))['members'] = patch.members(['B', 'Missing'])
    result = inspect_saved_patch(patch.finish())
    assert len(result['groups']) == 2
    assert {'group_cycle', 'unresolved_member'} <= {d['code'] for d in result['diagnostics']}


def test_unsupported_backend_does_not_become_unpatched():
    patch = Patch(workspace())
    a = patch.archive
    a.ref(patch.items[0])['dmxUniverse'] = a.add({'backendType': 9, 'backendInfo': a.add({'$class': a.cls('FutureBackend')})})
    result = inspect_saved_patch(patch.finish())
    assert result['instruments'][0]['output']['backend'] == 'unsupported'
    assert result['coverage'] == 'partial'


def test_version_and_invalid_archive_rejected():
    with pytest.raises(ValueError):
        inspect_saved_patch(b'not a workspace')
    patch = Patch(workspace())
    a = patch.outer
    index = [a.ref(key) for key in a.root['NS.keys']].index('QLabBuildNumber')
    a.root['NS.objects'][index] = 5600
    with pytest.raises(ValueError, match='5.5.10'):
        inspect_saved_patch(a.dump())


def test_shared_definition_is_returned_once_for_thousand_instruments():
    patch = Patch(workspace())
    a = patch.archive
    original = a.ref(patch.items[0])
    patch.items = [a.add({**original, 'name': a.add(f'Fixture {index}')}) for index in range(1000)]
    result = inspect_saved_patch(patch.finish())
    assert len(result['instruments']) == 1000
    assert len(result['definitions']) == 1
    assert len(result['definitions'][0]['used_by']) == 1000
    assert result['coverage'] == 'complete'


def test_rgb_links_and_scalar_width_home_and_units_are_known():
    source = plan_patch(workspace(), [
        {'action': 'update_definition', 'name': 'Dimmer', 'default_parameter': 'fine', 'parameters': [
            {'type': 'scalar', 'name': 'red'}, {'type': 'scalar', 'name': 'green'}, {'type': 'scalar', 'name': 'blue'},
            {'type': 'scalar', 'name': 'fine', 'two_bytes': True, 'value_is_percentage': False, 'home_value': 1024},
            {'type': 'rgbcolor', 'name': 'color', 'outputs': ['red', 'green', 'blue']},
        ]},
    ])['output_bytes']
    definition = inspect_saved_patch(source)['definitions'][0]
    assert definition['dmx_footprint'] == 5
    assert definition['default_parameter'] == 3
    assert definition['parameters'][3]['two_bytes'] is True
    assert definition['parameters'][3]['home_value'] == 1024
    assert definition['parameters'][3]['value_is_percentage'] is False
    assert definition['parameters'][4]['outputs'] == {'red': 'red', 'green': 'green', 'blue': 'blue'}


def test_unknown_parameter_preserves_other_known_information():
    patch = Patch(workspace())
    a = patch.archive
    definition = a.ref(patch.definitions['Dimmer'])
    parameter = a.ref(next(iter(a.mapping(definition['parameters']).values())))
    parameter['type'] = a.add('future')
    result = inspect_saved_patch(patch.finish())
    assert result['definitions'][0]['parameters'][0]['type'] == 'future'
    assert result['definitions'][0]['dmx_footprint'] is None
    assert result['instruments'][0]['name'] == 'Door'
    assert result['coverage'] == 'partial'


@pytest.mark.parametrize('invalid', ['bad', True, 1.5, None, 128])
def test_malformed_output_coordinate_is_partial_and_preserves_instrument(invalid):
    from qlab_mcp.models import SavedLightOutput
    patch = Patch(plan_patch(workspace(), [
        {'action': 'update_instrument', 'name': 'Door', 'output': {'backend': 'artnet', 'net': 0, 'subnet': 2, 'universe': 3, 'address': 1}},
    ])['output_bytes'])
    a = patch.archive
    universe = a.ref(a.ref(patch.items[0])['dmxUniverse'])
    a.ref(universe['backendInfo'])['net'] = a.add(invalid) if isinstance(invalid, str) else invalid
    result = inspect_saved_patch(patch.finish())
    instrument = result['instruments'][0]
    assert instrument['name'] == 'Door'
    assert instrument['output']['net'] is None
    assert instrument['output']['subnet'] == 2
    assert SavedLightOutput.model_validate(instrument['output']).backend == 'artnet'
    assert result['coverage'] == 'partial'
    assert 'invalid_output_field' in {d['code'] for d in result['diagnostics']}


def test_malformed_usb_count_and_address_do_not_break_public_model():
    from qlab_mcp.models import SavedLightOutput
    patch = Patch(plan_patch(workspace(), [
        {'action': 'update_instrument', 'name': 'Door', 'output': {'backend': 'usb', 'device_serial': 'SYNTHETIC', 'device_name': 'Example', 'device_universes': 2, 'universe': 1, 'address': 10}},
    ])['output_bytes'])
    a = patch.archive
    instrument = a.ref(patch.items[0])
    instrument['address'] = a.add('not an address')
    info = a.ref(a.ref(instrument['dmxUniverse'])['backendInfo'])
    info['deviceNumUniverses'] = True
    info['universe'] = a.add('wrong')
    result = inspect_saved_patch(patch.finish())
    output = SavedLightOutput.model_validate(result['instruments'][0]['output'])
    assert output.backend == 'usb' and output.device_serial == 'SYNTHETIC'
    assert output.device_universes is None and output.universe is None and output.address is None
    assert result['instruments'][0]['dmx_address_end'] is None
    assert result['coverage'] == 'partial'


def test_scalar_with_virtual_channel_has_unknown_footprint():
    patch = Patch(workspace())
    a = patch.archive
    definition = a.ref(patch.definitions['Dimmer'])
    parameter = next(iter(a.mapping(definition['parameters']).values()))
    definition['parameters'] = a.make_dict({-2: parameter})
    result = inspect_saved_patch(patch.finish())
    assert result['definitions'][0]['dmx_footprint'] is None
    assert result['coverage'] == 'partial'
    assert result['diagnostics'][0]['code'] == 'invalid_parameter_channel'


@pytest.mark.parametrize('target', ['instrument', 'group', 'definition', 'parameter', 'universe', 'backend'])
def test_unknown_fields_keep_known_records_but_mark_coverage_partial(target):
    patch = Patch(plan_patch(workspace(), [
        {'action': 'update_instrument', 'name': 'Door', 'output': {'backend': 'artnet', 'net': 0, 'subnet': 0, 'universe': 0, 'address': 1}},
        {'action': 'create_group', 'name': 'Front', 'members': ['Door']},
    ])['output_bytes'])
    a = patch.archive
    instrument = a.ref(patch.find('Door', 'instrument'))
    definition = a.ref(patch.definitions['Dimmer'])
    universe = a.ref(instrument['dmxUniverse'])
    targets = {'instrument': instrument, 'group': a.ref(patch.find('Front', 'group')),
               'definition': definition, 'parameter': a.ref(next(iter(a.mapping(definition['parameters']).values()))),
               'universe': universe, 'backend': a.ref(universe['backendInfo'])}
    targets[target]['futureProperty'] = a.add('PRIVATE VALUE NOT TO RETURN')
    result = inspect_saved_patch(patch.finish())
    assert result['instruments'][0]['name'] == 'Door'
    assert result['groups'][0]['members'] == ['Door']
    assert result['definitions'][0]['name'] == 'Dimmer'
    assert result['coverage'] == 'partial'
    assert 'futureProperty' in next(d['message'] for d in result['diagnostics'] if d['code'] == 'unknown_fields')
    assert 'PRIVATE VALUE' not in str(result)


def test_unknown_field_diagnostic_names_are_bounded():
    patch = Patch(workspace())
    a = patch.archive
    instrument = a.ref(patch.items[0])
    for index in range(25):
        instrument[f'{index:02d}' + 'x' * 200] = a.add('private')
    result = inspect_saved_patch(patch.finish())
    message = next(d['message'] for d in result['diagnostics'] if d['code'] == 'unknown_fields')
    assert len(message) < 1200
    assert '(+9 more)' in message


def test_missing_output_field_is_unknown_instead_of_unpatched():
    patch = Patch(workspace())
    del patch.archive.ref(patch.items[0])['dmxUniverse']
    result = inspect_saved_patch(patch.finish())
    assert result['instruments'][0]['output']['backend'] == 'unsupported'
    assert result['coverage'] == 'partial'
    assert result['diagnostics'][0]['code'] == 'unsupported_output'
