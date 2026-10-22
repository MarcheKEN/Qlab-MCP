"""Read known saved Light Patch fields without applying authoring preconditions."""
from __future__ import annotations

import math
from uuid import UUID

from .archive import Archive


def inspect_saved_patch(source: bytes) -> dict:
    outer = Archive(source)
    meta = outer.mapping(outer.root)
    version = outer.ref(meta.get('QLabShortVersionString'))
    build = outer.ref(meta.get('QLabBuildNumber'))
    if version != '5.5.10' or build != 5510:
        raise ValueError('Saved Light Patch inspection supports QLab 5.5.10/build 5510.')
    workspace_id = str(UUID(outer.ref(meta['uniqueID']))).upper()
    settings = outer.mapping(meta['settings'])
    carrier = outer.ref(outer.mapping(settings['Light'])['patch'])
    if not isinstance(carrier, dict) or not isinstance(carrier.get('NS.data'), bytes):
        raise ValueError('Unsupported Light Patch data carrier.')
    a = Archive(carrier['NS.data'])
    if a.kind(a.root) != 'LightPatch':
        raise ValueError('Unsupported Light Patch root.')
    result = dict(workspace_id=workspace_id, version=version, build=build,
                  instruments=[], groups=[], definitions=[], coverage='complete', diagnostics=[])

    def diagnostic(section, code, message, **identity):
        result['coverage'] = 'partial'
        result['diagnostics'].append(dict(section=section, code=code, message=message, **identity))

    def unknown_fields(value, allowed, section, name):
        unknown = sorted(set(value) - (set(allowed) | {'$class'}))
        if unknown:
            names = ', '.join(key[:64] for key in unknown[:16])
            suffix = f' (+{len(unknown) - 16} more)' if len(unknown) > 16 else ''
            diagnostic(section, 'unknown_fields', f'Uninterpreted field names: {names}{suffix}.', name=name)

    def text(value):
        value = a.ref(value)
        if not isinstance(value, str):
            raise ValueError('Expected an archived string.')
        return value

    def scalar(value):
        value = a.ref(value)
        if value is not None and type(value) not in (str, bool, int, float):
            raise ValueError('Unsupported archived scalar.')
        if type(value) is float and not math.isfinite(value):
            raise ValueError('Non-finite archived scalar.')
        return value

    def parameter(channel, reference, definition_name):
        value = a.ref(reference)
        if type(channel) is not int or not isinstance(value, dict):
            raise ValueError('Unsupported definition parameter channel or object.')
        unknown_fields(value, {'name', 'type', 'twoBytes', 'valueIsPercentage', 'homeValue', 'homeValueDouble', 'outputs'},
                       'definitions', definition_name)
        entry = {'channel': channel}
        for saved, public in (('name', 'name'), ('type', 'type'), ('twoBytes', 'two_bytes'),
                              ('valueIsPercentage', 'value_is_percentage'), ('homeValue', 'home_value'),
                              ('homeValueDouble', 'home_value_double')):
            entry[public] = scalar(value.get(saved))
        if 'outputs' in value:
            outputs = a.ref(value['outputs'])
            if isinstance(outputs, dict):
                entry['outputs'] = ({str(key): scalar(ref) for key, ref in a.mapping(value['outputs']).items()}
                                    if 'NS.keys' in outputs else [scalar(ref) for ref in a.array(value['outputs'])])
            elif isinstance(outputs, list):
                entry['outputs'] = [scalar(ref) for ref in outputs]
            else:
                raise ValueError('Unsupported virtual parameter outputs.')
        return entry

    library = {}
    try:
        library = a.ref(a.ref(a.root['library'])['library'])
        definitions = a.mapping(library['dictionary'])
    except (KeyError, TypeError, AttributeError, ValueError):
        definitions = {}
        diagnostic('definitions', 'invalid_library', 'Workspace definition library could not be interpreted.')
    try:
        order = [text(ref) for ref in a.array(library['array'])]
    except (KeyError, TypeError, AttributeError, ValueError):
        order = []
        if definitions:
            diagnostic('definitions', 'invalid_definition_order', 'Definition order could not be interpreted.')
    if len(order) != len(set(order)) or set(order) != set(definitions):
        diagnostic('definitions', 'definition_order_mismatch', 'Definition order and dictionary differ.')
    names = list(dict.fromkeys(order + list(definitions)))
    for name in names:
        try:
            if not isinstance(name, str):
                raise ValueError('Unsupported definition name.')
            value = a.ref(definitions[name])
            if a.kind(value) != 'LightCueInstrumentDefinition':
                raise ValueError('Unsupported definition class.')
            unknown_fields(value, {'name', 'manufacturer', 'definitionVersion', 'defaultParameter', 'parameters'},
                           'definitions', name)
            raw = a.ref(value['parameters'])
            entries = a.mapping(value['parameters']) if 'NS.keys' in raw else dict(enumerate(a.array(value['parameters'])))
            parameters = []
            complete = True
            for channel, ref in entries.items():
                try:
                    entry = parameter(channel, ref, name)
                    parameters.append(entry)
                    if entry['type'] not in {'scalar', 'rgbcolor', 'cmycolor', 'hsicolor', 'pantilt', 'muxer'}:
                        complete = False
                        diagnostic('definitions', 'unsupported_parameter', 'Parameter subtype is only partially interpreted.', name=name)
                    elif ((entry['type'] == 'scalar' and not 0 <= entry['channel'] <= 511)
                          or (entry['type'] != 'scalar' and entry['channel'] > -2)):
                        complete = False
                        diagnostic('definitions', 'invalid_parameter_channel', 'Parameter channel does not match its known subtype.', name=name)
                except (KeyError, TypeError, AttributeError, ValueError):
                    complete = False
                    diagnostic('definitions', 'invalid_parameter', 'A definition parameter could not be interpreted.', name=name)
            parameters.sort(key=lambda p: (p['channel'] < 0, p['channel'] if p['channel'] >= 0 else -p['channel']))
            footprint = 0
            for entry in parameters:
                if entry['channel'] >= 0:
                    if entry['type'] != 'scalar' or type(entry['two_bytes']) is not bool:
                        complete = False
                        diagnostic('definitions', 'invalid_parameter_width', 'Physical parameter width could not be interpreted.', name=name)
                    else:
                        footprint = max(footprint, entry['channel'] + (2 if entry['two_bytes'] else 1))
            result['definitions'].append(dict(name=name, manufacturer=text(value['manufacturer']),
                version=scalar(value.get('definitionVersion')), default_parameter=scalar(value.get('defaultParameter')),
                parameters=parameters, dmx_footprint=footprint if complete else None, used_by=[]))
        except (KeyError, TypeError, AttributeError, ValueError):
            diagnostic('definitions', 'invalid_definition', 'A workspace definition could not be interpreted.', name=str(name))

    def output(item, name):
        def integer(value, field, minimum, maximum):
            value = a.ref(value)
            if type(value) is not int or not minimum <= value <= maximum:
                diagnostic('instruments', 'invalid_output_field', f'Configured output {field} is not a valid integer.', name=name)
                return None
            return value

        if 'dmxUniverse' not in item:
            raise ValueError('Configured output field is missing.')
        universe = a.ref(item['dmxUniverse'])
        if universe is None:
            return {'backend': 'none'}
        unknown_fields(universe, {'backendInfo', 'backendType'}, 'instruments', name)
        info = a.ref(universe['backendInfo'])
        backend_type = scalar(universe['backendType'])
        kind = text(a.kind(info))
        address = integer(item.get('address'), 'address', 0, 511)
        address = address + 1 if address is not None else None
        if type(backend_type) is int and backend_type == 0 and kind == 'LightDMXArtNetInfo':
            unknown_fields(info, {'net', 'sub_net', 'universe'}, 'instruments', name)
            return dict(backend='artnet', net=integer(info.get('net'), 'net', 0, 127),
                        subnet=integer(info.get('sub_net'), 'subnet', 0, 15),
                        universe=integer(info.get('universe'), 'universe', 0, 15), address=address)
        if type(backend_type) is int and backend_type == 1 and kind == 'LightDMXUSBInfo':
            unknown_fields(info, {'deviceSerial', 'deviceString', 'deviceNumUniverses', 'universe'}, 'instruments', name)
            count = integer(info.get('deviceNumUniverses'), 'device_universes', 1, 512)
            selected = integer(info.get('universe'), 'universe', 0, 511)
            if count is not None and selected is not None and selected >= count:
                diagnostic('instruments', 'invalid_output_field', 'USB universe is outside the configured device universe count.', name=name)
                selected = None
            return dict(backend='usb', device_serial=text(info['deviceSerial']), device_name=text(info['deviceString']),
                        device_universes=count, universe=selected, address=address)
        return dict(backend='unsupported', backend_type=backend_type, backend_class=kind, address=address)

    try:
        items = a.array(a.root['itemList'])
    except (KeyError, TypeError, AttributeError, ValueError):
        items = []
        diagnostic('instruments', 'invalid_item_list', 'Active Light Patch item list could not be interpreted.')
    for index, ref in enumerate(items):
        try:
            item = a.ref(ref)
            common = dict(name=text(item['name']), note=text(item['comment']) if a.ref(item.get('comment')) is not None else '', order=index)
            kind = a.kind(item)
            if kind == 'LightCueInstrument':
                unknown_fields(item, {'name', 'comment', 'definitionName', 'address', 'dmxUniverse', 'lightOutputID'},
                               'instruments', common['name'])
                try:
                    destination = output(item, common['name'])
                except (KeyError, TypeError, AttributeError, ValueError):
                    destination = {'backend': 'unsupported'}
                if destination['backend'] == 'unsupported':
                    diagnostic('instruments', 'unsupported_output', 'Configured output could not be fully interpreted.', name=common['name'])
                result['instruments'].append(dict(**common, definition=text(item['definitionName']), output=destination))
            elif kind == 'LightCueInstrumentGroup':
                unknown_fields(item, {'name', 'comment', 'members', 'nameRange', 'flavor', 'type'}, 'groups', common['name'])
                members = []
                try:
                    member_refs = a.array(item['members'])
                except (KeyError, TypeError, AttributeError, ValueError):
                    member_refs = []
                    diagnostic('groups', 'invalid_members', 'Group membership list could not be interpreted.', name=common['name'])
                for member in member_refs:
                    try:
                        value = a.ref(member)
                        unknown_fields(value, {'name', 'nameRange'}, 'groups', common['name'])
                        members.append(text(value['name']))
                    except (KeyError, TypeError, AttributeError, ValueError):
                        diagnostic('groups', 'invalid_member', 'A group member could not be interpreted.', name=common['name'])
                result['groups'].append(dict(**common, members=members))
            else:
                diagnostic('items', 'unsupported_item', 'Unknown active Light Patch item class.', index=index, name=common['name'])
        except (KeyError, TypeError, AttributeError, ValueError):
            diagnostic('items', 'invalid_item', 'An active Light Patch item could not be interpreted.', index=index)

    by_definition = {entry['name']: entry for entry in result['definitions']}
    for instrument in result['instruments']:
        definition = by_definition.get(instrument['definition'])
        footprint = definition['dmx_footprint'] if definition else None
        if definition:
            definition['used_by'].append(instrument['name'])
        else:
            diagnostic('instruments', 'unresolved_definition', 'Instrument definition is unavailable.', name=instrument['name'])
        start = instrument['output'].get('address')
        instrument.update(dmx_footprint=footprint, dmx_address_start=start,
                          dmx_address_end=start + footprint - 1 if start is not None and footprint else None)
    item_names = [entry['name'] for entry in result['instruments'] + result['groups']]
    if len(item_names) != len(set(item_names)):
        diagnostic('items', 'duplicate_name', 'Active patch item names are not unique.')
    group_map = {entry['name']: entry['members'] for entry in result['groups']}
    known_names = set(item_names) | {'all'}
    for group in result['groups']:
        for member in group['members']:
            if member not in known_names:
                diagnostic('groups', 'unresolved_member', 'Group references an unavailable patch item.', name=group['name'])
    colors = {}
    for name in group_map:
        stack = [(name, False)]
        while stack:
            current, leaving = stack.pop()
            if leaving:
                colors[current] = 2
            elif colors.get(current) == 1:
                diagnostic('groups', 'group_cycle', 'Group membership contains a cycle.', name=current)
            elif colors.get(current, 0) == 0:
                colors[current] = 1
                stack.append((current, True))
                stack.extend((member, False) for member in group_map[current] if member in group_map)
    return result
