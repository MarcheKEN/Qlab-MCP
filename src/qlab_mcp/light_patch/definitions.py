"""Dedicated definition authoring using the existing guarded document transaction."""
from __future__ import annotations

from copy import deepcopy
import math

from pydantic import TypeAdapter

from .archive import plan_patch
from .models import DefinitionOperations, Name
from .transaction import edit_light_patch

_RGB_OUTPUTS = {'red', 'green', 'blue', 'white', 'warmwhite', 'amber'}
_NAME = TypeAdapter(Name)


def _entries(native):
    parameters = native.get('parameters')
    if isinstance(parameters, list):
        return dict(enumerate(parameters))
    if not isinstance(parameters, dict):
        raise ValueError('Definition parameters must be a dictionary or array.')
    entries = {}
    for key, value in parameters.items():
        channel = int(key)
        if str(channel) != str(key) or channel in entries:
            raise ValueError('Ambiguous definition channel.')
        entries[channel] = value
    return entries


def inspect_native(native: dict) -> dict:
    """Describe all known fields; only scalar and RGB variants are write-enabled."""
    parameters, notes, unknown = [], [], []
    footprint = 0
    try:
        _NAME.validate_python(native.get('name'))
        _NAME.validate_python(native.get('manufacturer'))
        if type(native.get('definitionVersion', 1)) is not int or native.get('definitionVersion', 1) not in {1, 2}:
            raise ValueError('Unsupported definition version.')
        entries = _entries(native)
        if not 1 <= len(entries) <= 512:
            raise ValueError('Definition parameter count is outside 1..512.')
        names, scalars, occupied = set(), set(), set()
        for channel, value in sorted(entries.items(), key=lambda pair: (pair[0] < 0, pair[0] if pair[0] >= 0 else -pair[0])):
            if not isinstance(value, dict):
                raise ValueError('Invalid definition parameter.')
            name = _NAME.validate_python(value.get('name'))
            if name in names:
                raise ValueError('Duplicate parameter name.')
            names.add(name)
            kind = value.get('type', 'scalar')
            parameters.append(dict(channel=channel, name=name, type=kind,
                two_bytes=value.get('twoBytes'), value_is_percentage=value.get('valueIsPercentage'),
                units=('percent' if value.get('valueIsPercentage') else 'dmx') if kind == 'scalar' else None,
                home_value=value.get('homeValue'), home_value_double=value.get('homeValueDouble'),
                outputs=deepcopy(value.get('outputs'))))
            unknown.extend(f'parameters[{channel}].{key}' for key in value if key not in {
                'name', 'type', 'twoBytes', 'valueIsPercentage', 'homeValue', 'homeValueDouble', 'outputs'})
            if kind == 'scalar':
                if type(value.get('twoBytes')) is not bool or type(value.get('valueIsPercentage')) is not bool:
                    raise ValueError('Scalar width and units must be explicit booleans.')
                width = 2 if value['twoBytes'] else 1
                if not 0 <= channel <= 512 - width or occupied.intersection(range(channel, channel + width)):
                    raise ValueError('Physical channels overlap or exceed 512.')
                occupied.update(range(channel, channel + width))
                scalars.add(name)
                home = value.get('homeValueDouble', value.get('homeValue'))
                maximum = 100 if value['valueIsPercentage'] else 65535 if width == 2 else 255
                if type(home) not in {int, float} or not math.isfinite(home) or not 0 <= home <= maximum:
                    raise ValueError('Scalar home value is outside its units/width range.')
                if not value['valueIsPercentage'] and home != int(home):
                    raise ValueError('DMX home value must be integral.')
                footprint = max(footprint, channel + width)
            elif kind == 'rgbcolor':
                if channel > -2:
                    raise ValueError('Virtual channel must be <= -2.')
                outputs = value.get('outputs')
                if not isinstance(outputs, dict) or not {'red', 'green', 'blue'} <= outputs.keys() or not outputs.keys() <= _RGB_OUTPUTS:
                    raise ValueError('Unsupported RGB outputs.')
            else:
                notes.append(f'Parameter variant {kind!r} is readable but not validated for import.')
        for value in entries.values():
            if value.get('type', 'scalar') == 'rgbcolor':
                outputs = list(value['outputs'].values())
                if any(not isinstance(name, str) for name in outputs) or len(outputs) != len(set(outputs)) or not set(outputs) <= scalars:
                    raise ValueError('Virtual outputs must reference distinct physical scalar parameters.')
        default = native.get('defaultParameter', -1)
        if type(default) is not int or default != -1 and default not in entries:
            raise ValueError('Default parameter does not exist.')
        if footprint < 1:
            raise ValueError('Definition has no physical channels.')
        unknown.extend(key for key in native if key not in {'name', 'manufacturer', 'definitionVersion', 'defaultParameter', 'parameters', 'mode'})
        if unknown:
            notes.append('Uninterpreted fields require native validation before import.')
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        notes.append(str(exc))
    return dict(parameters=parameters, dmx_footprint=footprint or None,
                importable=not notes, compatibility_notes=notes, uninterpreted_fields=unknown)


def install_native_definition(patch, name: str, native: dict) -> None:
    """Encode known native JSON without losing channel positions or output bindings."""
    info = inspect_native(native)
    if not info['importable']:
        raise ValueError('Native definition is not importable: ' + '; '.join(info['compatibility_notes']))
    a = patch.archive
    item = a.ref(patch.find(name, 'definition'))
    def encode(value):
        if isinstance(value, str):
            return a.add(value)
        if isinstance(value, dict):
            return a.make_dict({key: encode(val) for key, val in value.items()})
        if isinstance(value, list):
            return a.make_array([encode(val) for val in value])
        return value
    parameters = {}
    for channel, value in _entries(native).items():
        kind = value.get('type', 'scalar')
        cls = 'LightCueInstrumentDefinitionParameterScalar' if kind == 'scalar' else 'LightCueInstrumentDefinitionParameterRGBColor'
        record = {key: encode(val) for key, val in value.items()}
        record.update({'$class': a.cls(cls, ('LightCueInstrumentDefinitionParameter',)), 'type': a.add(kind)})
        if kind == 'scalar' and 'homeValueDouble' not in record:
            record['homeValueDouble'] = float(value['homeValue'])
        parameters[channel] = a.add(record)
    item.clear()
    item.update({key: encode(value) for key, value in native.items() if key != 'parameters'})
    item.update({'$class': a.cls('LightCueInstrumentDefinition'), 'name': a.add(name),
                 'defaultParameter': native.get('defaultParameter', -1),
                 'parameters': a.make_dict(parameters)})


def edit_light_definitions(reader, workspace_id, operations, dry_run=True, confirm_token=None):
    from .catalogue import load_catalogue
    try:
        validated = TypeAdapter(DefinitionOperations).validate_python(operations)
        normalized = [op.model_dump(exclude_unset=True) for op in validated]
        sources = {op['definition_id'].split(':', 1)[0] for op in normalized if op['action'] == 'import_definition'}
        catalogue, statuses = [], []
        for source in sources:
            if source not in {'bundled', 'personal'}:
                raise ValueError('Import requires an exact bundled or personal catalogue definition_id.')
            entries, state = load_catalogue(source)
            catalogue.extend(entries)
            statuses.extend(state)
        lookup = {record['definition_id']: record for record in catalogue}
        imports, expanded, dependencies = {}, [], {}
        for op in normalized:
            if op['action'] != 'import_definition':
                expanded.append(op)
                continue
            record = lookup.get(op['definition_id'])
            if record is None or not record['importable']:
                raise ValueError('Definition is missing, changed or not validated for import.')
            name = op.get('name', record['name'])
            if name in imports:
                raise ValueError('Duplicate import target name.')
            imports[name] = record['_native']
            dependencies[op['definition_id']] = record['source_sha256']
            # The native record replaces this typed placeholder before final validation.
            expanded.append(dict(action='create_definition', name=name, manufacturer=record['manufacturer'],
                                 parameters=[dict(type='scalar', name='intensity')]))
        def planner(source, operations):
            return plan_patch(source, operations, native_imports=imports)
        def dependency_check():
            fresh = {}
            for source in sources:
                entries, _ = load_catalogue(source)
                fresh.update({entry['definition_id']: entry['source_sha256'] for entry in entries})
            if any(fresh.get(key) != value for key, value in dependencies.items()):
                raise ValueError('Definition catalogue changed before Close; obtain a fresh preview.')
        result = edit_light_patch(reader, workspace_id, expanded, dry_run, confirm_token,
                                  planner=planner, dependencies=dict(catalogue=dependencies, requests=normalized),
                                  token_family='lightDefinitions', dependency_check=dependency_check)
        result['tool'] = 'qlab_edit_light_definitions'
        result['native_definition_verification_scope'] = 'Full known definition configuration in saved archive; OSC verifies definitions assigned to instruments only.'
        result['requested_operations'] = normalized
        for field in ('changes', 'planned_operations'):
            for index, op in enumerate(result.get(field, [])):
                if op.get('action') == 'create_definition' and op.get('name') in imports:
                    record = next(record for record in catalogue if record['_native'] is imports[op['name']])
                    result[field][index] = dict(action='import_definition', name=op['name'],
                        definition_id=record['definition_id'], source_sha256=record['source_sha256'],
                        manufacturer=record['manufacturer'], parameters=record['parameters'],
                        default_parameter=record['default_parameter'], dmx_footprint=record['dmx_footprint'])
        return result
    except (ValueError, TypeError, KeyError, OSError) as exc:
        from ..sanitizer import sanitize_exception_message
        return dict(ok=False, status='blocked', error=sanitize_exception_message(exc),
                    planned_operations=[], executed_operations=[])
