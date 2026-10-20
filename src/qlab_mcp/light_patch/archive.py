"""QLab 5.5.10 keyed-archive inspection; preserve object tables and shared UIDs."""
from __future__ import annotations

import hashlib
import plistlib
import re

from pydantic import TypeAdapter
from .models import LightPatchOperations
from typing import Any
from uuid import UUID

MAX_BYTES = 64 * 1024 * 1024
MAX_OBJECTS = 200_000


class Archive:
    def __init__(self, source: bytes):
        if not source.startswith(b'bplist00') or len(source) > MAX_BYTES:
            raise ValueError('Expected a bounded binary .qlab5 archive.')
        self.data = plistlib.loads(source)
        if self.data.get('$archiver') != 'NSKeyedArchiver' or self.data.get('$version') != 100000:
            raise ValueError('Unsupported keyed archive.')
        self.objects = self.data.get('$objects')
        if not isinstance(self.objects, list) or not 1 <= len(self.objects) <= MAX_OBJECTS or self.objects[0] != '$null':
            raise ValueError('Invalid archive object table.')
        stack = [(self.data, 0)]
        while stack:
            value, depth = stack.pop()
            if depth > 100:
                raise ValueError('Archive nesting exceeds limit.')
            if isinstance(value, plistlib.UID):
                self.ref(value)
            elif isinstance(value, dict):
                stack.extend((v, depth + 1) for v in value.values())
            elif isinstance(value, list):
                stack.extend((v, depth + 1) for v in value)
        self.root = self.ref(self.data['$top']['root'])

    def ref(self, value):
        if isinstance(value, plistlib.UID):
            if not 0 <= value.data < len(self.objects):
                raise ValueError('Invalid archive UID.')
            return self.objects[value.data] if value.data else None
        return value

    def mapping(self, value):
        value = self.ref(value)
        keys, values = value.get('NS.keys'), value.get('NS.objects')
        if not isinstance(keys, list) or not isinstance(values, list) or len(keys) != len(values):
            raise ValueError('Invalid archived dictionary.')
        result = {self.ref(k): v for k, v in zip(keys, values)}
        if len(result) != len(keys):
            raise ValueError('Invalid or duplicate archived keys.')
        return result

    def array(self, value):
        value = self.ref(value)
        if not isinstance(value, dict) or not isinstance(value.get('NS.objects'), list) or 'NS.keys' in value:
            raise ValueError('Invalid archived array.')
        return value['NS.objects']

    def kind(self, value):
        value = self.ref(value)
        return self.ref(value['$class'])['$classname']

    def add(self, value):
        if len(self.objects) >= MAX_OBJECTS:
            raise ValueError('Archive object limit exceeded.')
        self.objects.append(value)
        return plistlib.UID(len(self.objects) - 1)

    def cls(self, name, parents=()):
        for i, value in enumerate(self.objects):
            if isinstance(value, dict) and value.get('$classname') == name:
                return plistlib.UID(i)
        return self.add({'$classname': name, '$classes': [name, *parents, 'NSObject']})

    def make_array(self, values):
        return self.add({'$class': self.cls('NSMutableArray', ('NSArray',)), 'NS.objects': list(values)})

    def make_dict(self, values):
        return self.add({'$class': self.cls('NSMutableDictionary', ('NSDictionary',)),
                         'NS.keys': [self.add(k) for k in values], 'NS.objects': list(values.values())})

    def replacing_mapping(self, reference, key, replacement):
        value = self.ref(reference)
        keys = [self.ref(v) for v in value['NS.keys']]
        self.mapping(reference)
        values = list(value['NS.objects'])
        values[keys.index(key)] = replacement
        return self.add({**value,'NS.objects':values})

    def dump(self):
        return plistlib.dumps(self.data, fmt=plistlib.FMT_BINARY, sort_keys=False)


class Patch:
    def __init__(self, source: bytes):
        self.outer = Archive(source)
        meta = self.outer.mapping(self.outer.root)
        r = self.outer.ref
        if r(meta.get('QLabBuildNumber')) != 5510 or r(meta.get('QLabShortVersionString')) != '5.5.10':
            raise ValueError('Light Patch editing requires QLab 5.5.10/build 5510.')
        self.workspace_id = str(UUID(r(meta['uniqueID']))).upper()
        settings = self.outer.mapping(meta['settings'])
        general = self.outer.mapping(settings['General'])
        if any(r(general.get(key)) is not False for key in ('doStartOnOpen','doStartOnClose')):
            raise ValueError('Workspace automatic open/close cues must be known disabled.')
        light = self.outer.mapping(settings['Light'])
        self.data_object = r(light['patch'])
        if not isinstance(self.data_object, dict) or not isinstance(self.data_object.get('NS.data'), bytes):
            raise ValueError('Unsupported Light Patch data carrier.')
        self.archive = Archive(self.data_object['NS.data'])
        a = self.archive
        if a.kind(a.root) != 'LightPatch':
            raise ValueError('Unsupported Light Patch root.')
        self.root = a.root
        self.items = list(a.array(self.root['itemList']))
        library = a.ref(a.ref(self.root['library'])['library'])
        self.library = library
        self.definitions = a.mapping(library['dictionary'])
        self.definition_order = [a.ref(v) for v in a.array(library['array'])]
        if set(self.definition_order) != set(self.definitions) or len(self.definition_order) != len(self.definitions):
            raise ValueError('Definition dictionary/order mismatch.')

    def snapshot(self):
        a = self.archive
        instruments, groups, definitions = [], [], []
        for name in self.definition_order:
            value = a.ref(self.definitions[name])
            parameters = value.get('parameters')
            p = a.ref(parameters)
            entries = a.mapping(parameters) if 'NS.keys' in p else dict(enumerate(a.array(parameters)))
            if any(type(key) is not int for key in entries):
                raise ValueError('Unsupported definition channel keys.')
            ordered = sorted(entries,key=lambda key:(key < 0,key if key >= 0 else -key))
            refs = [entries[key] for key in ordered]
            params = []
            for key, ref in zip(ordered,refs):
                v = a.ref(ref)
                entry = {k: a.ref(v.get(k)) for k in ('name','type','twoBytes','valueIsPercentage','homeValue','homeValueDouble')}
                entry['channel'] = key
                if 'outputs' in v:
                    raw_outputs = a.ref(v['outputs'])
                    entry['outputs'] = ({k:a.ref(x) for k,x in a.mapping(v['outputs']).items()} if 'NS.keys' in raw_outputs else [a.ref(x) for x in a.array(v['outputs'])])
                params.append(entry)
            definitions.append({'name':name,'manufacturer':a.ref(value['manufacturer']),
                                'parameters':params,'default_parameter':value.get('defaultParameter',-1)})
        for ref in self.items:
            item = a.ref(ref)
            common = {'name':a.ref(item['name']), 'note':a.ref(item.get('comment')) or ''}
            if a.kind(ref) == 'LightCueInstrument':
                output = {'backend':'none'}
                universe = a.ref(item.get('dmxUniverse'))
                if universe:
                    info = a.ref(universe['backendInfo'])
                    if universe['backendType'] == 0 and a.kind(universe['backendInfo']) == 'LightDMXArtNetInfo':
                        output = {'backend':'artnet','net':info['net'],'subnet':info['sub_net'],'universe':info['universe'],'address':item['address']+1}
                    elif universe['backendType'] == 1 and a.kind(universe['backendInfo']) == 'LightDMXUSBInfo':
                        output = {'backend':'usb','device_serial':a.ref(info['deviceSerial']),'device_name':a.ref(info['deviceString']), 'device_universes':info['deviceNumUniverses'],'universe':info['universe'],'address':item['address']+1}
                    else:
                        output = {'backend':'unsupported'}
                instruments.append({**common,'definition':a.ref(item['definitionName']),'output':output})
            elif a.kind(ref) == 'LightCueInstrumentGroup':
                groups.append({**common,'members':[a.ref(a.ref(v)['name']) for v in a.array(item['members'])]})
            else:
                raise ValueError('Unsupported active Light Patch item.')
        return {'instruments': instruments, 'groups': groups, 'definitions':definitions}


    def find(self, name, kind):
        a = self.archive
        refs = list(self.definitions.values()) if kind == 'definition' else self.items
        classname = {'instrument':'LightCueInstrument','group':'LightCueInstrumentGroup','definition':'LightCueInstrumentDefinition'}[kind]
        matches = [v for v in refs if a.kind(v) == classname and a.ref(a.ref(v)['name']) == name]
        if len(matches) != 1:
            raise ValueError(f'{kind} {name!r} must resolve exactly once.')
        return matches[0]

    def identical_create(self, op, kind):
        snapshot = self.snapshot()
        section = {'instrument':'instruments','group':'groups','definition':'definitions'}[kind]
        matches = [v for v in snapshot[section] if v['name'] == op['name']]
        if not matches:
            return False
        actual = matches[0]
        if kind == 'instrument':
            expected = dict(name=op['name'],note=op.get('note',''),definition=op['definition'],output=op.get('output',{'backend':'none'}))
        elif kind == 'group':
            expected = dict(name=op['name'],note=op.get('note',''),members=op.get('members',[]))
        else:
            parameters = []
            channel,virtual = 0,-2
            for value in op['parameters']:
                scalar = value['type'] == 'scalar'
                home = value.get('home_value',0)
                parameters.append(dict(name=value['name'],type=value['type'],
                    twoBytes=value.get('two_bytes',False) if scalar else None,
                    valueIsPercentage=value.get('value_is_percentage',True) if scalar else None,
                    homeValue=int(home) if scalar else None,homeValueDouble=float(home) if scalar else None,
                    channel=channel if scalar else virtual,
                    **({} if scalar else {'outputs':dict(zip(('red','green','blue'),value['outputs']))})))
                if scalar: channel += 2 if value.get('two_bytes') else 1
                else: virtual -= 1
            parameters.sort(key=lambda p:(p['channel'] < 0,p['channel'] if p['channel'] >= 0 else -p['channel']))
            default = next((v['channel'] for v in parameters if v['name'] == op.get('default_parameter')),-1)
            expected = dict(name=op['name'],manufacturer=op['manufacturer'],parameters=parameters,default_parameter=default)
        if actual != expected:
            raise ValueError('Create conflicts with existing object; use an explicit update.')
        return True

    def name_free(self, name, kind):
        a = self.archive
        names = self.definitions if kind == 'definition' else {a.ref(a.ref(v)['name']) for v in self.items} | {'all'}
        if name in names:
            raise ValueError(f'Duplicate or reserved {kind} name {name!r}.')

    def members(self, names):
        a = self.archive
        return a.make_array([a.add({'$class':a.cls('LightCueInstrumentGroupMember'),
            'name':a.add(name), 'nameRange': self.name_range()}) for name in names])

    def name_range(self):
        a = self.archive
        return a.add({'$class':a.cls('NSValue'), 'NS.special':4,
                      'NS.rangeval.location':a.add(9223372036854775807), 'NS.rangeval.length':a.add(0)})

    def set_output(self, item, output):
        a = self.archive
        if output['backend'] == 'none':
            item.update(address=-1, dmxUniverse=plistlib.UID(0))
            return
        if output['backend'] == 'artnet':
            info = {'$class':a.cls('LightDMXArtNetInfo'), 'net':output['net'],
                    'sub_net':output['subnet'], 'universe':output['universe']}
            backend = 0
        else:
            info = {'$class':a.cls('LightDMXUSBInfo'), 'deviceSerial':a.add(output['device_serial']),
                    'deviceString':a.add(output['device_name']), 'deviceNumUniverses':output['device_universes'],
                    'universe':output['universe']}
            backend = 1
        item['dmxUniverse'] = a.add({'$class':a.cls('LightDMXUniverse'),
                                    'backendType':backend, 'backendInfo':a.add(info)})
        item['address'] = output['address'] - 1

    def set_parameters(self, item, parameters):
        a = self.archive
        names = [p['name'] for p in parameters]
        if len(names) != len(set(names)):
            raise ValueError('Definition parameter names must be unique.')
        scalar_names = {p['name'] for p in parameters if p['type'] == 'scalar'}
        values = {}
        channel, virtual = 0, -2
        for p in parameters:
            kind = p['type']
            value = {'name':a.add(p['name']), 'type':a.add(kind)}
            if kind == 'scalar':
                two = p.get('two_bytes',False)
                home = p.get('home_value',0)
                value.update({'$class':a.cls('LightCueInstrumentDefinitionParameterScalar', ('LightCueInstrumentDefinitionParameter',)),
                    'twoBytes':two,'valueIsPercentage':p.get('value_is_percentage',True),
                    'homeValue':int(home),'homeValueDouble':float(home)})
                key = channel
                channel += 2 if two else 1
            else:
                if not set(p['outputs']) <= scalar_names:
                    raise ValueError('RGB outputs must resolve to physical scalar parameters.')
                value.update({'$class':a.cls('LightCueInstrumentDefinitionParameterRGBColor', ('LightCueInstrumentDefinitionParameter',)),
                    'outputs':a.make_dict({color:a.add(name) for color,name in zip(('red','green','blue'),p['outputs'])})})
                key = virtual
                virtual -= 1
            values[key] = a.add(value)
        if not 1 <= channel <= 512:
            raise ValueError('Definition footprint must be within 1..512.')
        item['parameters'] = a.make_dict(values)
        item['definitionVersion'] = 2

    def apply(self, op):
        a = self.archive
        verb, kind = op['action'].split('_',1)
        name = op['name']
        if name == 'all' and kind != 'definition':
            raise ValueError('The implicit all group cannot be edited.')
        if verb == 'create':
            if self.identical_create(op,kind):
                return
            self.name_free(name,kind)
            item = {'name':a.add(name)}
            if kind == 'definition':
                item.update({'$class':a.cls('LightCueInstrumentDefinition'), 'manufacturer':a.add(op['manufacturer']), 'defaultParameter':-1})
                self.set_parameters(item,op['parameters'])
                self.definitions[name] = a.add(item)
                self.definition_order.append(name)
            elif kind == 'instrument':
                # Normal QLab decode allocates runtime IDs; archived IDs are not public identity.
                item.update({'$class':a.cls('LightCueInstrument'),'comment':a.add(op.get('note','')),
                    'definitionName':a.add(op['definition']), 'lightOutputID':0, 'address':-1,'dmxUniverse':plistlib.UID(0)})
                self.items.append(a.add(item))
            else:
                item.update({'$class':a.cls('LightCueInstrumentGroup'),'comment':a.add(op.get('note','')),
                    'members':self.members(op.get('members',[])), 'flavor':0, 'nameRange':self.name_range()})
                self.items.append(a.add(item))
        else:
            ref = self.find(name,kind)
            item = a.ref(ref)
        if verb in {'create','update'}:
            if 'note' in op:
                item['comment'] = a.add(op['note'])
            if kind == 'instrument':
                if 'definition' in op:
                    item['definitionName'] = a.add(op['definition'])
                if 'output' in op:
                    self.set_output(item,op['output'])
            elif kind == 'group' and 'members' in op:
                item['members'] = self.members(op['members'])
            elif kind == 'definition':
                if 'manufacturer' in op:
                    item['manufacturer'] = a.add(op['manufacturer'])
                if verb == 'update' and 'parameters' in op:
                    old_parameters = a.mapping(item['parameters'])
                    old_default = old_parameters.get(item.get('defaultParameter',-1))
                    old_name = a.ref(a.ref(old_default)['name']) if old_default is not None else None
                    self.set_parameters(item,op['parameters'])
                    if 'default_parameter' not in op and old_name is not None:
                        found = [key for key,value in a.mapping(item['parameters']).items() if a.ref(a.ref(value)['name']) == old_name]
                        if len(found) != 1:
                            raise ValueError('Replacing parameters removed the default; supply default_parameter explicitly.')
                        item['defaultParameter'] = found[0]
                if 'default_parameter' in op:
                    params = a.mapping(item['parameters'])
                    found = [key for key,value in params.items() if a.ref(a.ref(value)['name']) == op['default_parameter']]
                    if op['default_parameter'] is not None and len(found) != 1:
                        raise ValueError('Default parameter must resolve exactly once.')
                    item['defaultParameter'] = found[0] if found else -1
        elif verb == 'rename':
            new = op['new_name']
            if new == name:
                return
            self.name_free(new,kind)
            item['name'] = a.add(new)
            if kind == 'definition':
                self.definitions[new] = self.definitions.pop(name)
                self.definition_order = [new if n == name else n for n in self.definition_order]
                for v in self.items:
                    x = a.ref(v)
                    if a.kind(v) == 'LightCueInstrument' and a.ref(x['definitionName']) == name:
                        x['definitionName'] = a.add(new)
            else:
                self.rewrite_members(name,new)
        elif verb == 'delete':
            if kind == 'definition':
                del self.definitions[name]
                self.definition_order.remove(name)
            else:
                self.items.remove(ref)
                self.rewrite_members(name,None)

    def rewrite_members(self, old, new):
        a = self.archive
        for ref in self.items:
            if a.kind(ref) != 'LightCueInstrumentGroup':
                continue
            group = a.ref(ref)
            names = [a.ref(a.ref(v)['name']) for v in a.array(group['members'])]
            if old in names:
                members = []
                for member_ref in a.array(group['members']):
                    member = a.ref(member_ref)
                    if a.ref(member['name']) == old:
                        if new is None:
                            continue
                        member_ref = a.add({**member,'name':a.add(new)})
                    members.append(member_ref)
                group['members'] = a.make_array(members)

    def finish(self):
        a = self.archive
        self.root['itemList'] = a.make_array(self.items)
        self.library['dictionary'] = a.make_dict(self.definitions)
        self.library['array'] = a.make_array([a.add(n) for n in self.definition_order])
        outer = self.outer
        meta = outer.mapping(outer.root)
        settings = outer.mapping(meta['settings'])
        light = outer.mapping(settings['Light'])
        carrier = outer.add({**self.data_object,'NS.data':a.dump()})
        light_ref = outer.replacing_mapping(settings['Light'],'patch',carrier)
        settings_ref = outer.replacing_mapping(meta['settings'],'Light',light_ref)
        root_ref = outer.replacing_mapping(outer.data['$top']['root'],'settings',settings_ref)
        outer.data['$top'] = {**outer.data['$top'],'root':root_ref}
        return outer.dump()


def _validate(summary):
    instruments, groups, definitions = summary['instruments'], summary['groups'], summary['definitions']
    names = [v['name'] for v in instruments + groups]
    if len(names) != len(set(names)) or 'all' in names:
        raise ValueError('Duplicate or reserved patch names.')
    defs = {v['name']:v for v in definitions}
    group_map = {v['name']:v['members'] for v in groups}
    done, visiting = set(), set()
    def visit(name):
        if name in visiting:
            raise ValueError('Light group cycle.')
        if name in done:
            return
        visiting.add(name)
        members = group_map.get(name,[])
        if len(members) != len(set(members)):
            raise ValueError('Duplicate group member.')
        for member in members:
            if member not in names:
                raise ValueError('Unresolved Light group member.')
            visit(member)
        visiting.remove(name)
        done.add(name)
    for name in group_map:
        visit(name)
    occupied = {}
    for item in instruments:
        if item['definition'] not in defs:
            raise ValueError('Instrument definition is still in use or does not exist.')
        definition = defs[item['definition']]
        params = definition['parameters']
        footprint = 0
        for parameter in params:
            if parameter['type'] in {'scalar',0}:
                channel = parameter.get('channel',footprint)
                if channel < 0:
                    raise ValueError('Physical parameter has a negative channel.')
                footprint = max(footprint, channel + (2 if parameter.get('twoBytes') else 1))
            elif parameter['type'] not in {'rgbcolor','cmycolor','hsicolor','pantilt','muxer'}:
                raise ValueError('Unsupported definition parameter type.')
        output = item['output']
        if output['backend'] == 'none':
            continue
        if output['backend'] == 'unsupported':
            raise ValueError('Unsupported output backend.')
        start = output['address']
        if footprint < 1 or not 1 <= start <= 512 or start + footprint - 1 > 512:
            raise ValueError('Instrument footprint is outside 1..512.')
        space = tuple(output.get(k) for k in ('backend','device_serial','net','subnet','universe'))
        for address in range(start,start+footprint):
            key = (space,address)
            if key in occupied:
                raise ValueError(f'DMX overlap between {occupied[key]!r} and {item["name"]!r}.')
            occupied[key] = item['name']


def _affected_cues(patch, operations):
    names = {op['name'] for op in operations if op['action'].startswith(('rename_','delete_'))}
    result = []
    if not names:
        return result
    a = patch.outer
    for index, value in enumerate(a.objects):
        if not isinstance(value,dict):
            continue
        if 'NS.keys' in value:
            try:
                value = a.mapping(value)
            except ValueError:
                continue
        command = a.ref(value.get('lightCommandText'))
        if not isinstance(command,str):
            continue
        matches = [name for name in names if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',command,re.IGNORECASE)]
        if matches:
            result.append({'archive_object':index,'cue_ref':a.ref(value.get('uniqueID')),
                           'matched_names':sorted(matches), 'match':'possible_reference'})
    return result


def plan_patch(source: bytes, operations: list[dict[str, Any]]) -> dict:
    patch = Patch(source)
    before = patch.snapshot()
    normalized = [op.model_dump(exclude_unset=True) for op in TypeAdapter(LightPatchOperations).validate_python(operations)] if operations else []
    for op in normalized:
        patch.apply(op)
    after = patch.snapshot()
    if normalized:
        _validate(after)
    changed = before != after
    warnings = []
    if any(item['output']['backend'] == 'usb' for item in after['instruments']):
        warnings.append('USB-DMX serials are configured identities, not detected devices. Disconnected/unavailable devices can remain unpatched; no physical output is verified.')
    if normalized:
        warnings.append('Light cues are not changed. Reference analysis is partial; repair cues separately after renaming, deleting or changing definitions.')
        warnings.append('Native OSC readback cannot verify DMX addresses/output identities or unused definitions; these are verified in the saved archive.')
    output = patch.finish() if changed else source
    if changed and Patch(output).snapshot() != after:
        raise ValueError('Serialized Light Patch does not match the plan.')
    return {'output_bytes':output,'workspace_id':patch.workspace_id,'summary':after,
            'changes':normalized if changed else [],'warnings':warnings,'affected_cues':_affected_cues(patch,normalized),
            'input_hash':hashlib.sha256(source).hexdigest()}


def verify_live_patch(summary: dict, payload: dict) -> bool:
    """Check OSC-visible identity/properties; archive verification covers saved routing."""
    if not isinstance(payload,dict) or not isinstance(payload.get('instruments'),list) or not isinstance(payload.get('groups'),list):
        return False
    actual = {v.get('name'):v for v in payload['instruments']}
    if set(actual) != {v['name'] for v in summary['instruments']}:
        return False
    definitions = {v['name']:v for v in summary['definitions']}
    for expected in summary['instruments']:
        value = actual[expected['name']]
        if value.get('comment','') != expected['note'] or value.get('definition',{}).get('name') != expected['definition']:
            return False
        definition = value.get('definition',{})
        planned = definitions.get(expected['definition'])
        if planned is None or definition.get('manufacturer') != planned['manufacturer'] or definition.get('defaultParameter') != planned['default_parameter']:
            return False
        parameters = definition.get('parameters')
        if not isinstance(parameters,dict) or set(parameters) != {str(p['channel']) for p in planned['parameters']}:
            return False
        for parameter in planned['parameters']:
            native = parameters[str(parameter['channel'])]
            if any(native.get(key) != parameter[key] for key in ('name','type')):
                return False
            if parameter['type'] == 'scalar':
                if any(native.get(key) != parameter[key] for key in ('twoBytes','valueIsPercentage')):
                    return False
                home = parameter['homeValueDouble'] if parameter['homeValueDouble'] is not None else parameter['homeValue']
                if native.get('homeValue') != home:
                    return False
            elif 'outputs' in parameter and native.get('outputs') != parameter['outputs']:
                return False
        if expected['output']['backend'] != 'usb' and bool(value.get('patched')) != (expected['output']['backend'] != 'none'):
            return False
    groups = {v.get('name'):v for v in payload['groups'] if v.get('name') != 'all'}
    if set(groups) != {v['name'] for v in summary['groups']}:
        return False
    for expected in summary['groups']:
        value = groups[expected['name']]
        if not isinstance(value.get('members'),list) or sorted(v.get('name','') for v in value['members']) != sorted(expected['members']):
            return False
    return True
