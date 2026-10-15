"""Saved Video FX contracts. Published bands are conservative write policy.

Parameter bands are documentary evidence; saved creation defaults have separate
QLab 5.5.10 runtime evidence. Reads preserve unknown and out-of-band attributes.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, TypeAdapter, model_validator

from . import control
from ..errors import QLabReplyError

CATALOGUE_METADATA = json.loads(Path(__file__).with_name('video_fx_catalogue.json').read_text())
CATALOGUE = CATALOGUE_METADATA['effects']
# Native spellings share documentary bands; preserve the requested OSC key.
NATIVE_PARAMETER_ALIASES = CATALOGUE_METADATA.get('native_parameter_aliases', {})
RANGE_POLICY = 'Conservative published bands; QLab can allow values outside them.'
EffectType = Literal[tuple(CATALOGUE)]
Index = Annotated[StrictInt, Field(ge=0)]
Value = StrictBool | StrictInt | StrictFloat | list[StrictInt | StrictFloat]
STRUCTURAL = {'videoEffects/add', 'videoEffects/insert', 'videoEffectIndex/delete', 'videoEffectIndex/move'}
WINDOW_COMPONENTS = {'Origin_X', 'Origin_Y', 'Size_W', 'Size_H'}

VERIFIED_DEFAULTS: dict[str, dict] = CATALOGUE_METADATA['creation_defaults']
BLOCKED_CREATION: dict[str, str] = CATALOGUE_METADATA['blocked_creation']
VERIFIED_STRUCTURAL_OPS: set[str] = set(STRUCTURAL)
VERIFIED_STRUCTURAL_VERSION = CATALOGUE_METADATA['creation_defaults_qlab_version']


def _parameter_spec(effect_type, key):
    documented_key = NATIVE_PARAMETER_ALIASES.get(effect_type, {}).get(key, key)
    if effect_type not in CATALOGUE or documented_key not in CATALOGUE[effect_type]:
        raise ValueError(f'{effect_type}/{key}: unknown catalogue destination.')
    return CATALOGUE[effect_type][documented_key]


def _parameter_metadata(effect_type, key):
    aliases = NATIVE_PARAMETER_ALIASES.get(effect_type, {})
    documented_key = aliases.get(key, key)
    try:
        spec = deepcopy(_parameter_spec(effect_type, key))
    except ValueError:
        return {'native_key': key, 'documented': False, 'writable': False,
                'reason': 'No documentary parameter contract; preserved without inferring a writable destination.'}
    return {**spec, 'native_key': key, 'documented_key': documented_key,
            'aliases': [alias for alias, target in aliases.items() if target == documented_key],
            'documented': True, 'writable': True,
            'source': CATALOGUE_METADATA['source'], 'range_policy': RANGE_POLICY}


def catalogue(effect_types=None, *, offset=0, limit=10):
    """Documentary contracts and existing write gates, without QLab I/O."""
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('Catalogue offset must be nonnegative and limit must be 1..10.')
    if effect_types is not None and (not isinstance(effect_types, list) or len(effect_types) > 10
            or any(type(name) is not str or name not in CATALOGUE for name in effect_types)):
        raise ValueError('At most 10 exact catalogue effect names.')
    names = list(CATALOGUE) if effect_types is None else effect_types
    effects = []
    for name in names[offset:offset + limit]:
        creation_reason = BLOCKED_CREATION.get(name)
        if name not in VERIFIED_DEFAULTS and creation_reason is None:
            creation_reason = 'FX creation requires recorded native defaults.'
        effects.append({'type': name,
                        'parameters': {key: _parameter_metadata(name, key) for key in CATALOGUE[name]},
                        'native_parameter_aliases': deepcopy(NATIVE_PARAMETER_ALIASES.get(name, {})),
                        'creation_defaults_available': name in VERIFIED_DEFAULTS,
                        'creation_defaults_qlab_version': VERIFIED_STRUCTURAL_VERSION,
                        'creation_blocked_reason': creation_reason,
                        'write_readiness': {'ready': False,
                            'reason': 'Documentary metadata alone does not establish native identity, readable baselines or write readiness.',
                            'requires_explicit_effect_type': True, 'requires_full_stack_preflight': True,
                            'requires_readable_native_baseline': True,
                            'repeated_type_identity_blocked': True,
                            'submode_changes_require_full_stack_verification': True}})
    return {'source': CATALOGUE_METADATA['source'], 'range_policy': RANGE_POLICY,
            'effect_count': len(CATALOGUE), 'parameter_count': sum(map(len, CATALOGUE.values())),
            'matched_count': len(names), 'returned_count': len(effects), 'offset': offset, 'limit': limit,
            'next_offset': offset + len(effects) if offset + len(effects) < len(names) else None,
            'effects': effects}


def validate_value(effect_type, key, value, *, write=True):
    spec = _parameter_spec(effect_type, key)
    kind = spec['kind']
    if kind == 'boolean':
        valid = type(value) is bool
    elif kind == 'enum':
        valid = type(value) is int and str(value) in spec['values']
    elif kind == 'vector':
        valid = isinstance(value, list) and len(value) == 4 and all(type(x) in (int, float) and math.isfinite(x) for x in value)
        if valid and write:
            valid = all(spec['minimum'] <= x <= spec['maximum'] for x in value)
    else:
        valid = type(value) in (int, float) and math.isfinite(value)
        if valid and write:
            valid = spec['minimum'] <= value <= spec['maximum']
    if not valid:
        raise ValueError(f'{effect_type}/{key}: invalid {kind}; writes use the published conservative band.')
    return value


def validate_parameters(effect_type, parameters, *, write=True):
    if not isinstance(parameters, dict) or not all(type(key) is str for key in parameters):
        raise ValueError('Expected a parameter object with exact catalogue keys.')
    for key, value in parameters.items():
        validate_value(effect_type, key, value, write=write)
    if write and effect_type == 'Window' and 'inputRectangle' in parameters and WINDOW_COMPONENTS & parameters.keys():
        raise ValueError('Window: use inputRectangle or its components, not both.')
    return parameters


class FxArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    effect_type: EffectType


class FxIndex(FxArgs):
    index: Index


class FxEnabled(FxIndex):
    value: StrictBool


class FxParameter(FxIndex):
    key: StrictStr
    value: Value

    @model_validator(mode='after')
    def valid_value(self):
        validate_value(self.effect_type, self.key, self.value)
        return self


class FxParameters(FxIndex):
    parameters: dict[StrictStr, Value] = Field(min_length=1)

    @model_validator(mode='after')
    def valid_parameters(self):
        validate_parameters(self.effect_type, self.parameters)
        return self


class FxMove(FxIndex):
    new_index: Index


class FxOperationBase(BaseModel):
    model_config = ConfigDict(extra='forbid')


class FxEnabledOperation(FxOperationBase):
    property: Literal['videoEffectIndex/enabled']
    args: FxEnabled


class FxParameterOperation(FxOperationBase):
    property: Literal['videoEffectIndex/parameter']
    args: FxParameter


class FxParametersOperation(FxOperationBase):
    property: Literal['videoEffectIndex/parameters']
    args: FxParameters


class FxAddOperation(FxOperationBase):
    property: Literal['videoEffects/add']
    args: FxArgs


class FxInsertOperation(FxOperationBase):
    property: Literal['videoEffects/insert']
    args: FxIndex


class FxDeleteOperation(FxOperationBase):
    property: Literal['videoEffectIndex/delete']
    args: FxIndex


class FxMoveOperation(FxOperationBase):
    property: Literal['videoEffectIndex/move']
    args: FxMove


FxOperation = Annotated[FxEnabledOperation | FxParameterOperation | FxParametersOperation | FxAddOperation | FxInsertOperation | FxDeleteOperation | FxMoveOperation, Field(discriminator='property')]
OPERATION_ADAPTER = TypeAdapter(FxOperation)


class FxReadSelector(BaseModel):
    model_config = ConfigDict(extra='forbid')
    index: Index
    effect_type: EffectType | None = Field(
        default=None,
        description='Optional exact type assertion. Omit to discover type from native indexed identity.',
    )
    key: StrictStr | None = None

    @model_validator(mode='after')
    def known_key(self):
        if self.effect_type is not None and self.key is not None:
            _parameter_spec(self.effect_type, self.key)
        return self


def normalize_operations(raw_operations):
    if len(raw_operations) > 50:
        raise ValueError('At most 50 FX operations per cue.')
    operations, destinations = [], set()
    for raw in raw_operations:
        parsed = OPERATION_ADAPTER.validate_python(raw.model_dump() if isinstance(raw, BaseModel) else raw)
        prop, arg = parsed.property, parsed.args.model_dump()
        index = arg.get('index')
        path = prop if prop.startswith('videoEffects/') else f"videoEffectIndex/{index}/{prop.split('/')[1]}"
        if prop.endswith('/parameter'):
            path += '/' + arg['key']
        key_path = path
        if prop.endswith('/parameters'):
            wire = [json.dumps(arg['parameters'], separators=(',', ':'), allow_nan=False)]
            wanted = arg['parameters']
        elif prop.endswith('/parameter'):
            # Native vector/bool scalar routes are unreliable; JSON preserves types.
            if isinstance(arg['value'], (list, bool)):
                path = f'videoEffectIndex/{index}/parameters'
                wire = [json.dumps({arg['key']: arg['value']}, separators=(',', ':'))]
            else:
                wire = [arg['value']]
            wanted = arg['value']
        elif prop.endswith('/enabled'):
            wire, wanted = [arg['value']], arg['value']
        elif prop == 'videoEffects/add':
            wire, wanted = [arg['effect_type']], arg
        elif prop == 'videoEffects/insert':
            wire, wanted = [arg['effect_type'], index], arg
        elif prop.endswith('/move'):
            wire, wanted = [arg['new_index']], arg
        else:
            wire, wanted = [], arg
        keys = set(arg.get('parameters', {})) or ({arg['key']} if 'key' in arg else {'enabled'} if prop.endswith('/enabled') else set())
        for key in keys:
            dest = (index, NATIVE_PARAMETER_ALIASES.get(arg['effect_type'], {}).get(key, key))
            if dest in destinations:
                raise ValueError('Duplicate FX destination.')
            destinations.add(dest)
        if arg['effect_type'] == 'Window' and (index, 'inputRectangle') in destinations and any((index, key) in destinations for key in WINDOW_COMPONENTS):
            raise ValueError('Window: inputRectangle conflicts with component writes.')
        operations.append({'property': key_path, 'key': key_path, 'path': path, 'address_suffix': path,
                           'args': wire, 'arg_values': arg, 'requested': wanted, 'fx_property': prop})
    if any(op['fx_property'] in STRUCTURAL for op in operations) and len(operations) != 1:
        raise ValueError('Use exactly one structural FX operation per cue.')
    types = {}
    for op in operations:
        arg = op['arg_values']
        if 'index' in arg and arg['index'] in types and types[arg['index']] != arg['effect_type']:
            raise ValueError('Conflicting effect identities at one index.')
        types[arg.get('index')] = arg['effect_type']
    return operations


def _type(raw):
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, dict):
        candidates = [raw[key] for key in ('oscName', 'type', 'effectType', 'name', 'effectName') if raw.get(key) in CATALOGUE]
    else:
        candidates = []
    if not candidates or len(set(candidates)) != 1 or candidates[0] not in CATALOGUE:
        raise ValueError('Native FX type identity is unavailable or ambiguous.')
    return candidates[0]


def _parameters(reader, ws, uid, index):
    value = control._scalar(reader, ws, uid, f'videoEffectIndex/{index}/parameters')
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or not all(type(key) is str for key in value):
        raise ValueError('Native FX parameter object is unavailable.')
    return deepcopy(value)


def _enabled(reader, ws, uid, index):
    enabled = control._scalar(reader, ws, uid, f'videoEffectIndex/{index}/enabled')
    if type(enabled) is not bool:
        raise ValueError('FX enabled readback is not boolean.')
    return enabled


def inventory(reader, ws, uid):
    # 5.5.10 suppresses consecutive identical inventory replies without preparation.
    identity = reader._request(control._workspace_address(ws, f'cue_id/{uid}/uniqueID'),
                               workspace_id=ws, ensure_always_reply=True).data
    if not isinstance(identity, str) or identity.casefold() != uid.casefold():
        raise ValueError('Native FX cue identity unavailable.')
    values = reader.read_cue_values(ws, uid, ['uniqueID', 'videoEffects'], cacheable=False)['values']
    if not isinstance(values, dict) or str(values.get('uniqueID', '')).casefold() != uid.casefold() or not isinstance(values.get('videoEffects'), list):
        raise ValueError('Native FX inventory/identity unavailable.')
    return deepcopy(values['videoEffects'])


def native_type(reader, ws, uid, raw_stack, index):
    """A named native getter must identify exactly one indexed payload."""
    entry = raw_stack[index]
    try:
        return _type(entry)
    except ValueError:
        if not isinstance(entry, dict) or any(control._same(entry, other) for i, other in enumerate(raw_stack) if i != index):
            raise ValueError('Native FX type identity is unavailable or ambiguous.')
    matches = []
    # Runtime keys can differ from the reference; only a native getter proves type.
    candidates = [name for name, parameters in CATALOGUE.items()
                  if set(entry) == set(parameters) or set(entry) == set(VERIFIED_DEFAULTS.get(name, {}).get('parameters', {}))]
    for names in (candidates, [name for name in CATALOGUE if name not in candidates]):
        for effect_type in names:
            try:
                named = control._scalar(reader, ws, uid, f'videoEffect/{effect_type}/parameters')
            except QLabReplyError as exc:
                if exc.status != 'error':
                    raise
                continue
            if isinstance(named, str):
                named = json.loads(named)
            if control._same(named, entry):
                matches.append(effect_type)
        if matches:
            break
    if len(matches) != 1:
        raise ValueError('Native FX type identity is unavailable or ambiguous.')
    return matches[0]


def snapshot(reader, ws, uid):
    raw = inventory(reader, ws, uid)
    if not isinstance(raw, list) or len(raw) > 50:
        raise ValueError('FX stack is unavailable or exceeds 50 instances.')
    raw = deepcopy(raw)
    stack = []
    for index, entry in enumerate(raw):
        effect_type = native_type(reader, ws, uid, raw, index)
        enabled = _enabled(reader, ws, uid, index)
        params = _parameters(reader, ws, uid, index)
        for key, value in params.items():
            if key in CATALOGUE[effect_type] or key in NATIVE_PARAMETER_ALIASES.get(effect_type, {}):
                validate_value(effect_type, key, value, write=False)
        if not CATALOGUE[effect_type].keys() <= params.keys() and not control._same(entry, params):
            raise ValueError(f'{effect_type}: incomplete parameter readback.')
        stack.append({'type': effect_type, 'enabled': enabled, 'parameters': params, 'raw': entry})
    if not control._same(inventory(reader, ws, uid), raw):
        raise ValueError('FX stack changed during snapshot.')
    return stack


def _assert_identity(stack, arg):
    index = arg['index']
    if index >= len(stack) or stack[index]['type'] != arg['effect_type']:
        raise ValueError('FX index/type identity does not match native stack.')


def _project(stack, op):
    expected = deepcopy(stack)
    arg, prop = op['arg_values'], op['fx_property']
    index = arg.get('index', len(stack))
    if prop in {'videoEffects/add', 'videoEffects/insert'}:
        expected.insert(index, deepcopy(VERIFIED_DEFAULTS[arg['effect_type']]))
    elif prop == 'videoEffectIndex/delete':
        expected.pop(index)
    elif prop == 'videoEffectIndex/move':
        expected.insert(arg['new_index'], expected.pop(index))
    else:
        item = expected[index]
        changes = arg.get('parameters', {arg['key']: arg['value']} if 'key' in arg else {})
        if prop.endswith('/enabled'):
            item['enabled'] = arg['value']
            if isinstance(item['raw'], dict):
                for key in ('enabled', 'isEnabled'):
                    if key in item['raw']:
                        item['raw'][key] = arg['value']
        else:
            item['parameters'].update(changes)
            if isinstance(item['raw'], dict):
                if isinstance(item['raw'].get('parameters'), dict):
                    item['raw']['parameters'].update(changes)
                for key, value in changes.items():
                    if key in item['raw']:
                        item['raw'][key] = value
    return expected


def restoration_plan(stack, index):
    """Prove a deleted instance can be reconstructed, without sending setters."""
    item = stack[index]
    effect_type = item['type']
    if effect_type not in VERIFIED_DEFAULTS or 'videoEffects/insert' not in VERIFIED_STRUCTURAL_OPS:
        raise ValueError('Deletion requires validated insert/default restoration evidence.')
    parameters = item['parameters']
    default = VERIFIED_DEFAULTS[effect_type]
    default_parameters = default.get('parameters', {})
    editable = {key: value for key, value in parameters.items()
                if key in CATALOGUE[effect_type] or key in NATIVE_PARAMETER_ALIASES.get(effect_type, {})}
    unknown = set(parameters) - editable.keys()
    if any(key not in default_parameters or not control._same(parameters[key], default_parameters[key])
           for key in unknown):
        raise ValueError('Unknown FX attributes cannot be demonstrably restored.')
    validate_parameters(effect_type, editable)
    args = {'effect_type': effect_type, 'index': index}
    restore = [{'property': 'videoEffects/insert', 'args': args}]
    rebuilt = [deepcopy(default)]
    if editable:
        request = {'property': 'videoEffectIndex/parameters', 'args': {**args, 'parameters': editable}}
        restore.append(request)
        op = normalize_operations([{**request, 'args': {**request['args'], 'index': 0}}])[0]
        rebuilt = _project(rebuilt, op)
    request = {'property': 'videoEffectIndex/enabled', 'args': {**args, 'value': item['enabled']}}
    restore.append(request)
    op = normalize_operations([{**request, 'args': {**request['args'], 'index': 0}}])[0]
    rebuilt = _project(rebuilt, op)
    if not control._same(rebuilt[0], item):
        raise ValueError('Unknown FX attributes cannot be demonstrably restored.')
    return restore


def fade_dependency_proof(reader, ws, uid):
    from ..cues.refs import _bounded_cue_refs_from_shallow
    bounded = _bounded_cue_refs_from_shallow(reader, ws, limit=5000, max_depth=None,
                                            cacheable=False, fallback_child_ids=False)
    if bounded['truncated'] or bounded['errors']:
        raise ValueError('FX structure requires a complete fresh workspace traversal.')
    targets = {}
    for ref in bounded['refs']:
        cue = ref['cue']
        if not isinstance(cue.get('uniqueID'), str) or not isinstance(cue.get('type'), str):
            raise ValueError('FX structure requires complete cue identities/types.')
        if cue['type'] == 'Fade':
            target = control._scalar(reader, ws, cue['uniqueID'], 'cueTargetID')
            if not isinstance(target, str):
                raise ValueError('Fade target identity is not reliably readable.')
            targets[cue['uniqueID']] = target
    return {'safe': not any(target.casefold() == uid.casefold() for target in targets.values()),
            'fade_dependents': sorted(key for key, target in targets.items() if target.casefold() == uid.casefold()),
            'targets': targets}


def preflight(reader, ws, uid, raw_operations, *, other_properties=False):
    ops = normalize_operations(raw_operations)
    if not ops:
        return {}, {}, [], {}
    structural = ops[0]['fx_property'] in STRUCTURAL
    if structural and other_properties:
        raise ValueError('Structural FX operations require a separate cue update.')
    if structural and reader._request('/version', workspace_id=ws).data != VERIFIED_STRUCTURAL_VERSION:
        raise ValueError('Structural FX defaults/restoration are validated only for QLab 5.5.10.')
    stack = snapshot(reader, ws, uid)
    before, changes = {}, {}
    structure_proof = None
    for op in ops:
        prop, arg = op['fx_property'], op['arg_values']
        if prop not in {'videoEffects/add', 'videoEffects/insert'}:
            _assert_identity(stack, arg)
        elif arg.get('index', len(stack)) > len(stack):
            raise ValueError('Insert index must be within the current stack.')
        if structural:
            if prop not in VERIFIED_STRUCTURAL_OPS:
                raise ValueError('Structural FX route requires recorded runtime/restoration validation.')
            if prop in {'videoEffects/add', 'videoEffects/insert'}:
                if arg['effect_type'] in BLOCKED_CREATION:
                    raise ValueError(BLOCKED_CREATION[arg['effect_type']])
                if len(stack) >= 50:
                    raise ValueError('FX creation would exceed the 50-instance snapshot limit.')
                if arg['effect_type'] not in VERIFIED_DEFAULTS:
                    raise ValueError('FX creation requires recorded native defaults.')
            if prop in {'videoEffects/add', 'videoEffects/insert'} and any(item['type'] == arg['effect_type'] for item in stack):
                raise ValueError('Adding repeated FX types lacks reliable indexed identity proof.')
            if prop == 'videoEffectIndex/move' and arg['new_index'] >= len(stack):
                raise ValueError('Move destination must be within the current stack.')
            if prop == 'videoEffectIndex/delete':
                op['restoration_validation'] = restoration_plan(stack, arg['index'])
            if prop in {'videoEffectIndex/delete', 'videoEffectIndex/move', 'videoEffects/insert'}:
                structure_proof = fade_dependency_proof(reader, ws, uid)
                if not structure_proof['safe']:
                    raise ValueError('FX structure requires reliable Fade dependency identity/read proof.')
            before[op['property']] = deepcopy(stack)
        else:
            item = stack[arg['index']]
            parameter_keys = set(arg.get('parameters', {})) | ({arg['key']} if 'key' in arg else set())
            if not parameter_keys <= item['parameters'].keys():
                raise ValueError('Selected FX parameter has no readable native baseline.')
            if prop.endswith('/enabled'):
                baseline = item['enabled']
            elif prop.endswith('/parameters'):
                baseline = deepcopy(item['parameters'])
            else:
                baseline = deepcopy(item['parameters'][arg['key']])
                direct = baseline if isinstance(arg['value'], (list, bool)) else control._scalar(reader, ws, uid, op['property'])
                if not control._same(direct, baseline):
                    raise ValueError('Direct FX parameter differs from aggregate baseline.')
            before[op['property']] = baseline
        changes[op['property']] = op['requested']
    return before, changes, ops, {'video_fx': {'stack': stack, 'operations': ops, 'fade_proof': structure_proof,
                                              'structural_version': VERIFIED_STRUCTURAL_VERSION if structural else None}}


def check_dependencies(reader, ws, uid, dependencies):
    state = dependencies.get('video_fx')
    if state is not None and state.get('structural_version') is not None and reader._request('/version', workspace_id=ws).data != state['structural_version']:
        raise ValueError('QLab version changed before FX structure setter.')
    if state is not None and not control._same(snapshot(reader, ws, uid), state['stack']):
        raise ValueError('FX stack, parameters or attributes changed before setter.')
    if state is not None and state.get('fade_proof') is not None and fade_dependency_proof(reader, ws, uid) != state['fade_proof']:
        raise ValueError('Fade dependencies changed before FX structure setter.')


def read_values(reader, ws, uid, keys, changes=None):
    values = {}
    for key in keys:
        if key.startswith('videoEffects/') or key.endswith(('/delete', '/move')):
            values[key] = snapshot(reader, ws, uid)
        elif key.startswith('videoEffectIndex/'):
            if '/parameter/' in key and isinstance((changes or {}).get(key), (list, bool)):
                _, index, _, parameter = key.split('/', 3)
                values[key] = _parameters(reader, ws, uid, int(index))[parameter]
                continue
            value = control._scalar(reader, ws, uid, key)
            if key.endswith('/parameters') and isinstance(value, str):
                value = json.loads(value)
            values[key] = value
    return values


def matches(key, observed, requested, dependencies, reader=None, ws=None, uid=None):
    state = dependencies.get('video_fx')
    if state is None or reader is None:
        return False
    op = next((op for op in state['operations'] if op['property'] == key), None)
    if op is None:
        return False
    if op['fx_property'] not in STRUCTURAL:
        wanted = requested
        if op['fx_property'].endswith('/parameters'):
            wanted = {**state['stack'][op['arg_values']['index']]['parameters'], **requested}
        if not control._same(observed, wanted):
            return False
    fresh = snapshot(reader, ws, uid)
    if not control._same(fresh, _project(state['stack'], op)):
        return False
    if state.get('structural_version') is not None and reader._request('/version', workspace_id=ws).data != state['structural_version']:
        return False
    if state.get('fade_proof') is not None and fade_dependency_proof(reader, ws, uid) != state['fade_proof']:
        return False
    state['stack'] = fresh
    return True


def read_selected(reader, ws, uid, selectors):
    if len(selectors) > 50:
        raise ValueError('At most 50 FX selectors.')
    raw_stack = inventory(reader, ws, uid)
    if not isinstance(raw_stack, list):
        raise ValueError('Native FX inventory unavailable.')
    selected = []
    for raw in selectors:
        selector = FxReadSelector.model_validate(raw.model_dump() if isinstance(raw, BaseModel) else raw)
        arg = selector.model_dump()
        index = selector.index
        if index >= len(raw_stack):
            raise ValueError('FX selector index is outside the native stack.')
        effect_type = native_type(reader, ws, uid, raw_stack, index)
        if selector.effect_type is not None and effect_type != selector.effect_type:
            raise ValueError('FX selector index/type identity mismatch.')
        enabled = _enabled(reader, ws, uid, index)
        if selector.key is None:
            params = _parameters(reader, ws, uid, index)
        elif _parameter_spec(effect_type, selector.key)['kind'] in {'vector', 'boolean'}:
            params = {selector.key: _parameters(reader, ws, uid, index)[selector.key]}
        else:
            params = {selector.key: control._scalar(reader, ws, uid, f'videoEffectIndex/{index}/parameter/{selector.key}')}
        for key, value in params.items():
            if key in CATALOGUE[effect_type] or key in NATIVE_PARAMETER_ALIASES.get(effect_type, {}):
                validate_value(effect_type, key, value, write=False)
        selected.append({'index': index, 'type': effect_type, 'enabled': enabled,
                         'parameters': params,
                         'parameter_metadata': {key: _parameter_metadata(effect_type, key) for key in params},
                         'raw_attributes': deepcopy(raw_stack[index])})
    if not control._same(raw_stack, inventory(reader, ws, uid)):
        raise ValueError('FX inventory changed during selected reads.')
    return selected


def capabilities(native_effects=None):
    candidates = ['videoEffectIndex/enabled', 'videoEffectIndex/parameter', 'videoEffectIndex/parameters']
    identity_error = None
    try:
        if not isinstance(native_effects, list) or not native_effects:
            raise ValueError('No existing effect with verifiable native type identity.')
        for entry in native_effects:
            _type(entry.model_dump() if isinstance(entry, BaseModel) else entry)
    except ValueError as exc:
        identity_error = str(exc)
    return {'allowed_operations': candidates if identity_error is None else [],
            'schema_operations': candidates + sorted(STRUCTURAL),
            'blocked_operations': {key: identity_error for key in candidates} if identity_error else {},
            'catalogue_effect_count': len(CATALOGUE), 'catalogue_parameter_count': sum(map(len, CATALOGUE.values())),
            'range_policy': RANGE_POLICY,
            'pending_validation': sorted(STRUCTURAL - VERIFIED_STRUCTURAL_OPS),
            'conditional_structural_operations': sorted(VERIFIED_STRUCTURAL_OPS),
            'validated_new_effects': sorted(VERIFIED_DEFAULTS),
            'unvalidated_new_effect_defaults_blocked': True,
            'blocked_creation_effects': dict(BLOCKED_CREATION),
            'native_parameter_aliases': deepcopy(NATIVE_PARAMETER_ALIASES),
            'structural_qlab_version': VERIFIED_STRUCTURAL_VERSION,
            'conditional_operations': candidates if identity_error else [],
            'identity_proof': 'Native type metadata, or a named native getter matching one unique indexed payload',
            'requires_explicit_effect_type': True, 'requires_full_stack_preflight': True,
            'excluded': ['Fade FX flags', '/live', 'effect-name write addressing']}
