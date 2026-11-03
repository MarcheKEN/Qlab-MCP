"""Fresh family dependencies for the shared, signed cue writer."""
from __future__ import annotations

import hashlib
import os
import re
import struct

from . import control
from .remaining import COMMON, _depend, _finite, _fingerprint, _raw, _reference, _time_seconds, _scalar, read

PATCH_ROUTES = {'audioOutputPatchID': 'settings/audio/patchList',
                'audioInputPatchID': 'settings/mic/patchList',
                'networkPatchID': 'settings/network/patchList', 'midiPatchID': 'settings/midi/patchList'}
LEVELS = {'level', 'sliderLevel', 'inputChannelName', 'gang', 'mute', 'solo',
          'mute/clear', 'solo/clear', 'mute/channel/clear', 'solo/channel/clear',
          'setSilentLevels', 'doLevel', 'objectIDLevel', 'doObjectIDLevel'}
SLICES = {'addSliceMarker', 'deleteSliceMarker', 'deleteSliceMarkers', 'sliceMarker/time', 'sliceMarker/playCount'}
VOICE = {'channel', 'status', 'note', 'velocity', 'programChange', 'pitchBend', 'byte1', 'byte2', 'byteCombo', 'endValue', 'doFade'}
MSC = {'command', 'commandFormat', 'controlNumber', 'controlValue', 'deviceID', 'hours', 'minutes', 'seconds', 'frames', 'subframes', 'macro', 'qList', 'qNumber', 'qPath', 'timecodeString', 'timecodeFormat'}
MSC_COMMANDS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, *range(16, 31)}
MAX_LIGHT_CUE_PULLS = 100
MAX_LIGHT_CUE_PULL_DEPTH = 32


def _light_pull_number_index(snapshot, cue_numbers):
    nodes = snapshot.get('nodes')
    if not isinstance(nodes, dict):
        raise ValueError('Light cue structure is unavailable.')
    return {
        number: sorted(
            (
                {
                    'uniqueID': str(node.get('uniqueID', '')).upper(),
                    'number': node.get('number'),
                    'type': node.get('type'),
                }
                for node in nodes.values()
                if str(node.get('number', '')) == number
            ),
            key=lambda item: item['uniqueID'],
        )
        for number in sorted(set(cue_numbers))
    }


def _light_cue_pull_context(reader, ws, cue_uid, command_text, deps):
    from uuid import UUID
    from .moves import _read_snapshot
    from ..settings.light_commands import light_cue_references

    references = light_cue_references(command_text)
    if not references:
        return {}

    snapshot = _read_snapshot(reader, ws)
    nodes = list(snapshot['nodes'].values())
    resolved_by_uuid = {}
    resolved_by_number = {}
    visiting = {cue_uid}

    def resolve(number, depth):
        if depth > MAX_LIGHT_CUE_PULL_DEPTH:
            raise ValueError('Light cue pull chain exceeds the supported depth limit.')
        matches = [node for node in nodes if str(node.get('number', '')) == number]
        if not matches:
            raise ValueError(f'Light cue pull target {number!r} does not exist.')
        if len(matches) != 1:
            raise ValueError(f'Light cue pull target {number!r} is ambiguous.')
        node = matches[0]
        if node.get('type') != 'Light':
            raise ValueError(f'Light cue pull target {number!r} is not a Light cue.')
        try:
            source_uid = str(UUID(str(node.get('uniqueID')))).upper()
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f'Light cue pull target {number!r} has no valid cue UUID.') from None
        if source_uid == cue_uid:
            raise ValueError('A Light cue cannot pull from itself.')
        if source_uid in visiting:
            raise ValueError('Light cue pull references form a cycle.')
        cached = resolved_by_uuid.get(source_uid)
        if cached is not None:
            resolved_by_number[number] = cached
            return cached
        if len(resolved_by_uuid) >= MAX_LIGHT_CUE_PULLS:
            raise ValueError(f'Light cue pull graph exceeds the {MAX_LIGHT_CUE_PULLS}-cue limit.')

        source = read(reader, ws, source_uid, ['number', 'lightCommandText'])
        if source['type'] != 'Light' or str(source['number']) != number:
            raise ValueError(f'Light cue pull target {number!r} changed during preflight.')
        text = source.get('lightCommandText')
        if not isinstance(text, str):
            raise ValueError(f'Light cue pull target {number!r} command text is unavailable.')
        value = {'uniqueID': str(source['uniqueID']).upper(), 'number': source['number'], 'type': source['type']}
        deps.setdefault('light_pull_sources', {})[source_uid] = {
            **value,
            'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        }
        visiting.add(source_uid)
        try:
            nested = light_cue_references(text)
            if len(nested) > MAX_LIGHT_CUE_PULLS:
                raise ValueError(f'Light cue pull graph exceeds the {MAX_LIGHT_CUE_PULLS}-cue limit.')
            for target_number in nested:
                resolve(target_number, depth + 1)
        finally:
            visiting.remove(source_uid)
        resolved_by_uuid[source_uid] = value
        resolved_by_number[number] = value
        return value

    if len(references) > MAX_LIGHT_CUE_PULLS:
        raise ValueError(f'Light cue pull graph exceeds the {MAX_LIGHT_CUE_PULLS}-cue limit.')
    for number in references:
        resolve(number, 1)
    cue_numbers = sorted(resolved_by_number)
    deps['light_pull_number_index'] = {
        'numbers': cue_numbers,
        'fingerprint': _fingerprint(_light_pull_number_index(snapshot, cue_numbers)),
    }
    return resolved_by_number


def validate(reader, ws, uid, family, operations, before):
    deps = {'routes': {}, 'cues': {}, 'files': {}}
    changes = {o['property']: o['requested'] for o in operations}
    names = set(changes)
    specific = names - COMMON
    # A selector can recreate dependent state. Plan it separately, then read again.
    selectors = {'fileTarget', 'audioOutputPatchID', 'audioInputPatchID', 'networkPatchID',
                 'midiPatchID', 'cueTargetID', 'patchTargetID', 'targetMode',
                 'messageType', 'status', 'outputType', 'timecodeFrameRate', 'fadeType'}
    if names & selectors and len(specific | ({'duration'} if 'duration' in names else set())) > 1:
        raise ValueError('Change selectors separately from dependent family properties; run another dry run.')
    for key in PATCH_ROUTES.keys() & names:
        if changes[key]:
            _reference(reader, ws, PATCH_ROUTES[key], changes[key], deps)
    if 'fileTarget' in names:
        path = changes['fileTarget']
        if path:
            if not os.path.isabs(path) or not os.path.isfile(path):
                raise ValueError('fileTarget requires an existing absolute regular file.')
            stat = os.stat(path)
            deps['files'][path] = {'realpath': os.path.realpath(path), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
            if family == 'midi_file':
                with open(path, 'rb') as stream:
                    header = stream.read(14)
                if len(header) != 14 or header[:4] != b'MThd' or struct.unpack('>I', header[4:8])[0] != 6:
                    raise ValueError('Invalid Standard MIDI File header.')
                fmt, tracks, division = struct.unpack('>HHH', header[8:14])
                if fmt not in (0, 1) or tracks == 0 or division == 0 or (fmt == 0 and tracks != 1):
                    raise ValueError('Only valid MIDI Type 0/1 files are supported; Type 2 is rejected.')
    if family in {'audio', 'midi_file'} and names & {'startTime', 'endTime', 'rate', 'playCount', 'infiniteLoop', 'preservePitch', 'lastSlicePlayCount', 'lastSliceInfiniteLoop', 'doFade', 'lockFadeToCue'}:
        media = _depend(reader, ws, uid, ['fileTarget'], deps)
        if not media['fileTarget'] or before.get('isBroken') is not False:
            raise ValueError('Media configuration requires a readable, healthy file target.')
        if names & {'startTime', 'endTime'}:
            times = _depend(reader, ws, uid, ['startTime', 'endTime'], deps)
            start, end = changes.get('startTime', times['startTime']), changes.get('endTime', times['endTime'])
            if not _finite(start) or not _finite(end) or start >= end:
                raise ValueError('startTime must precede endTime.')
            # No media-length endpoint proves an extension beyond the observed end.
            if end > times['endTime']:
                raise ValueError('Extending endTime needs independently verified media length.')
            operations.sort(key=lambda o: o['property'] == 'startTime' if start >= times['endTime'] else o['property'] == 'endTime')
    level_ops = [o for o in operations if o['property'] in LEVELS]
    if level_ops:
        owner = uid
        if family == 'fade':
            target = _depend(reader, ws, uid, ['targetMode', 'cueTargetID', 'patchTargetID'], deps)
            if target['targetMode'] == 0:
                owner = target['cueTargetID'].upper()
                if not owner:
                    raise ValueError('Fade Levels require a cue or patch target.')
            else:
                owner = None
        if owner:
            context = _depend(reader, ws, owner, ['audioOutputPatchID', 'numChannelsIn'], deps)
            patch_id = context['audioOutputPatchID']
            channels = context['numChannelsIn']
        else:
            patch_id = target['patchTargetID']
            channels = 0
        patch = _reference(reader, ws, 'settings/audio/patchList', patch_id, deps)
        detail_route = 'settings/audio/patchID/' + patch_id
        detail = _raw(reader, ws, detail_route)
        if not isinstance(detail, dict) or str(detail.get('uniqueID', '')).casefold() != patch_id.casefold():
            raise ValueError('Audio patch identity unavailable.')
        outputs = detail.get('cueOutputChannels')
        if type(channels) is not int or channels < 0 or type(outputs) is not int or outputs < 1:
            raise ValueError('Audio channel bounds are unavailable.')
        deps['routes'][detail_route] = {k: detail[k] for k in detail}  # exact patch snapshot
        for op in level_ops:
            args = op.get('arg_values', {})
            row = args.get('inChannel', args.get('row', args.get('number', 0)))
            col = args.get('outChannel', args.get('column', args.get('channel', args.get('output', 0))))
            if row > channels or col > outputs:
                raise ValueError('Requested channel is outside the cue/patch bounds.')
            if op['property'].endswith('/clear'):
                baseline = op['baseline']
                if isinstance(baseline, dict):
                    if any(not isinstance(v, list) for v in baseline.values()):
                        raise ValueError('Complete mute/solo snapshot unavailable.')
                    op['requested'] = {k: [] for k in baseline}
                elif isinstance(baseline, list):
                    op['requested'] = []
                else:
                    raise ValueError('Complete mute/solo snapshot unavailable.')
            if op['property'] == 'setSilentLevels':
                matrix = op['baseline']
                if not isinstance(matrix, list) or len(matrix) != channels + 1 or not matrix or not isinstance(matrix[0], list) or not outputs + 1 <= len(matrix[0]) <= 129 or any(not isinstance(row, list) or len(row) != len(matrix[0]) or not all(_finite(v) for v in row) for row in matrix):
                    raise ValueError('Complete Levels snapshot unavailable.')
                minimum = _raw(reader, ws, 'settings/audio/minVolume')
                if not _finite(minimum):
                    raise ValueError('Workspace audio minimum is unavailable.')
                deps['routes']['settings/audio/minVolume'] = minimum
                op['requested'] = [[minimum for _ in row] for row in matrix]
        if any(o['requested'] == '-inf' for o in level_ops):
            minimum = _raw(reader, ws, 'settings/audio/minVolume')
            if not _finite(minimum):
                raise ValueError('Workspace audio minimum is unavailable.')
            deps['routes']['settings/audio/minVolume'] = minimum
            deps['audio_minimum'] = minimum
        if names & {'mute/clear', 'solo/clear', 'mute/channel/clear', 'solo/channel/clear', 'setSilentLevels'} and len(level_ops) > 1:
            raise ValueError('Separate bulk cleanups from individual Levels operations.')
    objects = [o for o in operations if 'objectID' in o.get('arg_values', {})]
    object_ids = [op['arg_values']['objectID'] for op in objects]
    for op in level_ops:
        if op['property'] in {'mute/clear', 'solo/clear'}:
            object_ids.extend(op['baseline'].get('objects', []))
    if object_ids:
        inventory = _raw(reader, ws, f'cue_id/{uid}/objects')
        from ..settings.summarizers import _collection_items
        entries = _collection_items(inventory)
        map_id = _raw(reader, ws, f'cue_id/{uid}/audioMap/uniqueID')
        if map_id not in ('', None):
            raise ValueError('Cannot prove objects are cue-owned with an attached Audio Map; object editing blocked.')
        if map_id is None:
            raise ValueError('Audio Map ownership is unknown; object editing blocked.')
        deps['routes'][f'cue_id/{uid}/objects'] = inventory
        deps['routes'][f'cue_id/{uid}/audioMap/uniqueID'] = map_id
        for object_id in object_ids:
            if not isinstance(object_id, str) or not any(str(x.get('uniqueID', x.get('id', ''))).casefold() == object_id.casefold() for x in entries):
                raise ValueError('Object UUID is absent from the cue-owned inventory.')
        # The inventory can contain fields being edited. Store only identity/ownership.
        deps['routes'].pop(f'cue_id/{uid}/objects')
        deps['object_ids'] = sorted(str(x.get('uniqueID', x.get('id', ''))).upper() for x in entries)
    slices = [o for o in operations if o['property'] in SLICES]
    if slices:
        from .operations import _phase8c_expected_slice_markers, _canonical_slice_markers
        context = _depend(reader, ws, uid, ['startTime', 'endTime', 'sliceMarkers'], deps)
        if _canonical_slice_markers(context['sliceMarkers']) is None:
            raise ValueError('Slice inventory unavailable.')
        structural = names & {'addSliceMarker', 'deleteSliceMarker', 'deleteSliceMarkers', 'sliceMarker/time'}
        if structural and len(slices) > 1:
            raise ValueError('Slice reordering requires a separate dry run before subsequent indexed changes.')
        for op in slices:
            expected, error = _phase8c_expected_slice_markers(op, context)
            if error:
                raise ValueError(error)
            deps.setdefault('slice_expected', {})[op['key']] = expected
            context = {**context, 'sliceMarkers': expected}
            if op['property'] in {'addSliceMarker', 'deleteSliceMarker', 'deleteSliceMarkers'}:
                op['requested'] = expected
        deps['slice_inventory'] = deps['cues'][uid]['sliceMarkers']
        deps['cues'][uid].pop('sliceMarkers', None)
    if family == 'light' and 'lightCommandText' in names:
        from .operations import _try_read_safe_light_patch, _summarize_light_command_analysis
        from ..settings.light_commands import analyze_light_command_text
        patch, error = _try_read_safe_light_patch(reader, ws)
        if error or patch is None:
            raise ValueError(error or 'Light patch unavailable.')
        cue_references = _light_cue_pull_context(reader, ws, uid, changes['lightCommandText'], deps)
        analysis = analyze_light_command_text(
            changes['lightCommandText'], patch, cue_references=cue_references
        )
        if not changes['lightCommandText'].strip() or _summarize_light_command_analysis(analysis)['overall_status'] != 'valid':
            raise ValueError('Light commands must resolve entirely against the workspace patch.')
        deps['light_patch'] = patch
    if family == 'fade' and (specific or 'duration' in names):
        _fade(reader, ws, uid, changes, deps, operations)
    if family == 'network' and (specific - {'networkPatchID'} or 'duration' in names):
        context = _depend(reader, ws, uid, ['networkPatchID'], deps)
        if not context['networkPatchID']:
            raise ValueError('Network configuration requires a workspace patch.')
        _reference(reader, ws, PATCH_ROUTES['networkPatchID'], context['networkPatchID'], deps)
        if names & {'fadeEntries', 'fadeFrom', 'fadeTo', 'fadeNumberType', 'fps', 'pathHeight', 'pathWidth', 'duration'}:
            context = _depend(reader, ws, uid, ['fadeType', 'duration', 'fadeFrom', 'fadeTo'], deps)
            if context['fadeType'] not in (1, 2):
                raise ValueError('Network fades require a readable fade mode.')
            points = changes.get('fadeEntries')
            if points:
                duration = changes.get('duration', context['duration'])
                lower, upper = sorted((changes.get('fadeFrom', context['fadeFrom']), changes.get('fadeTo', context['fadeTo'])))
                if context['fadeType'] == 1 and any(not lower <= point['y'] <= upper for point in points):
                    raise ValueError('1D fade point exceeds fadeFrom/fadeTo bounds.')
                if context['fadeType'] == 1 and (points[0]['x'] != 0 or points[-1]['x'] != duration or any(a['x'] >= b['x'] for a, b in zip(points, points[1:]))):
                    raise ValueError('1D fade points must increase from zero to duration.')
    if family == 'midi' and (specific - {'midiPatchID'} or 'duration' in names):
        _midi(reader, ws, uid, changes, deps)
    if family == 'timecode' and specific:
        context = _depend(reader, ws, uid, ['outputType', 'timecodeFrameRate'], deps)
        fmt = context['timecodeFrameRate']
        deps['timecode_frame_rate'] = fmt
        if 'timecodeFrameRate' in names:
            times = _depend(reader, ws, uid, ['startTime', 'endTime', 'duration'], deps)
            proposed = changes['timecodeFrameRate']
            if _time_seconds(times['startTime'], proposed) < 0 or not _finite(times['duration']) or times['duration'] < 0:
                raise ValueError('Existing Timecode times are invalid for the requested frame rate.')
            deps['timecode_selector_times'] = times
            deps['cues'][uid].pop('endTime', None)
        if 'outputType' in names:
            deps['timecode_output_snapshot'] = control._try_read_update_values(reader, ws, uid, ['outputType', 'framerate', 'startTime', 'endTime', 'midiPatchID', 'audioOutputPatchID', 'ltcChannel'])[0]
        if names & {'startTime', 'endTime'}:
            times = _depend(reader, ws, uid, ['startTime', 'endTime'], deps)
            start, end = changes.get('startTime', times['startTime']), changes.get('endTime', times['endTime'])
            if _time_seconds(start, fmt) > _time_seconds(end, fmt):
                raise ValueError('Timecode start must not exceed end; equal endpoints mean continuous output.')
        if names & {'ltcChannel', 'audioOutputPatchID'} and context['outputType'] != 1:
            raise ValueError('LTC properties require LTC mode.')
        if 'midiPatchID' in names and context['outputType'] != 0:
            raise ValueError('MTC patch requires MTC mode.')
        if 'ltcChannel' in names:
            source = _depend(reader, ws, uid, ['audioOutputPatchID'], deps)
            patch = _reference(reader, ws, 'settings/audio/patchList', source['audioOutputPatchID'], deps)
            route = 'settings/audio/patchID/' + source['audioOutputPatchID']
            detail = _raw(reader, ws, route)
            capacity = detail.get('cueOutputChannels') if isinstance(detail, dict) else None
            if type(capacity) is not int or not 1 <= changes['ltcChannel'] <= capacity:
                raise ValueError('LTC channel requires a positive output within the known patch.')
            deps['routes'][route] = detail
    return deps


def _fade(reader, ws, uid, changes, deps, operations):
    target = _depend(reader, ws, uid, ['targetMode', 'cueTargetID', 'patchTargetID'], deps)
    names = set(changes)
    if 'cueTargetID' in names:
        cue = changes['cueTargetID']
        if cue:
            if cue.upper() == uid:
                raise ValueError('A Fade cannot target itself.')
            _fade_cue_target(reader, ws, uid, cue, deps)
        if target['targetMode'] != 0:
            raise ValueError('Set targetMode=0 separately before assigning a cue target.')
    if 'patchTargetID' in names:
        _reference(reader, ws, 'settings/audio/patchList', changes['patchTargetID'], deps)
        if target['targetMode'] != 1:
            raise ValueError('Set targetMode=1 separately before assigning a patch target.')
    if 'targetMode' in names:
        destination = target['cueTargetID'] if changes['targetMode'] == 0 else target['patchTargetID']
        if not destination:
            raise ValueError('Requested Fade mode has no existing valid destination.')
        if changes['targetMode'] == 1:
            _reference(reader, ws, 'settings/audio/patchList', destination, deps)
            flags = _depend(reader, ws, uid, ['doOpacity', 'doRate', 'doRotation', 'doScale', 'doTranslation'], deps)
            if any(value is not False for key, value in flags.items() if key.startswith('do')):
                raise ValueError('Patch-target Fade requires all geometry/rate flags to be disabled.')
        else:
            _fade_cue_target(reader, ws, uid, destination, deps)
        return
    fields = (names - COMMON - {'cueTargetID', 'patchTargetID'}) | ({'duration'} if 'duration' in names else set())
    if not fields:
        return
    if target['targetMode'] == 1:
        if fields - LEVELS - {'levelsMode', 'stopTargetWhenDone', 'duration'}:
            raise ValueError('Patch-target Fades support only audio Levels settings.')
        _reference(reader, ws, 'settings/audio/patchList', target['patchTargetID'], deps)
        if fields & LEVELS:
            source = _depend(reader, ws, uid, ['levelsMode', 'doLevel'], deps)
            matrix = source['doLevel']
            if not isinstance(matrix, list) or any(not isinstance(row, list) or any(type(value) is not bool for value in row) for row in matrix):
                raise ValueError('Fade activation matrix is unavailable.')
            from .operations import _fade_matrix_cell, _fade_operation_coordinates
            prospective = [list(row) for row in matrix]
            for op in operations:
                if op['property'] in {'level', 'sliderLevel', 'doLevel'}:
                    row, column = _fade_operation_coordinates(op)
                    if _fade_matrix_cell(matrix, row, column) is None:
                        raise ValueError('Fade crosspoint does not exist.')
                    if op['requested'] == '-inf' and source['levelsMode'] != 0:
                        raise ValueError('Fade silence requires absolute Levels mode.')
                    if op['property'] in {'level', 'sliderLevel'} and _fade_matrix_cell(matrix, row, column) is not True:
                        raise ValueError('Fade level requires its crosspoint to be enabled.')
                    if op['property'] == 'doLevel':
                        prospective[row][column] = op['requested']
            if not any(value is True for row in prospective for value in row):
                raise ValueError('Fade edit would remove the last active parameter.')
            deps['fade_activation'] = matrix
            deps['cues'][uid].pop('doLevel', None)
        return
    destination = target['cueTargetID'].upper()
    if not destination or destination == uid:
        raise ValueError('Fade configuration needs an existing target.')
    context = _depend(reader, ws, destination, ['type', 'isBroken', 'isWarning', 'isRunning', 'isPaused'], deps)
    if any(context[k] is not False for k in ('isBroken', 'isWarning', 'isRunning', 'isPaused')):
        raise ValueError('Fade target health/inactivity is unavailable.')
    geometry = {'geoMode', 'fadeType', 'pathHeight', 'pathWidth', 'rotation', 'rotationType', 'doOpacity', 'doRotation', 'doScale', 'doTranslation', 'opacity', 'translation/x', 'translation/y', 'scale/x', 'scale/y', 'quaternion'}
    if fields & geometry and context['type'] not in {'Video', 'Camera', 'Text'}:
        raise ValueError('Fade geometry requires a visual target.')
    if fields & {'rate', 'doRate'} and context['type'] not in {'Audio', 'Video'}:
        raise ValueError('Fade rate requires an Audio or Video target.')
    if fields & LEVELS and context['type'] not in {'Audio', 'Mic', 'Video', 'Camera'}:
        raise ValueError('Fade Levels require an audio-capable target.')
    flags = ('doOpacity', 'doRate', 'doRotation', 'doScale', 'doTranslation')
    source = _depend(reader, ws, uid, [*flags, 'geoMode', 'rotationType', 'levelsMode'], deps)
    required = {'opacity': 'doOpacity', 'rate': 'doRate', 'rotation': 'doRotation', 'rotationType': 'doRotation',
                'quaternion': 'doRotation', 'scale/x': 'doScale', 'scale/y': 'doScale',
                'translation/x': 'doTranslation', 'translation/y': 'doTranslation'}
    for key, flag in required.items():
        if key in names and source[flag] is not True:
            raise ValueError(f'Fade {key} requires an already enabled {flag}; configure it separately.')
    if 'rotation' in names and source['rotationType'] not in (1, 2, 3):
        raise ValueError('Fade rotation requires single-axis rotationType.')
    if 'quaternion' in names and (source['rotationType'] != 0 or source['geoMode'] != 0):
        raise ValueError('Fade quaternion requires 3D rotation and absolute geometry mode.')
    if changes.get('rotationType') == 0:
        raise ValueError('Changing to 3D rotation needs a separate verified quaternion snapshot.')
    if 'rate' in names and source['geoMode'] != 0:
        raise ValueError('Relative Fade rate has no documented operator.')
    if 'geoMode' in names and not any(source[flag] is True for flag in flags):
        raise ValueError('Geometry mode requires an active geometry parameter.')
    if fields & LEVELS or any(changes.get(flag) is False for flag in flags):
        from .operations import _fade_matrix_cell, _fade_operation_coordinates, _fade_missing_parameter_state
        matrix = _depend(reader, ws, uid, ['doLevel'], deps)['doLevel']
        if not isinstance(matrix, list) or any(not isinstance(row, list) or any(type(value) is not bool for value in row) for row in matrix):
            raise ValueError('Fade activation matrix is unavailable.')
        prospective = {**source, **{flag: changes.get(flag, source[flag]) for flag in flags}, 'doLevel': [list(row) for row in matrix]}
        for op in operations:
            prop = op['property']
            if prop in {'level', 'sliderLevel', 'gang', 'inputChannelName', 'doLevel'}:
                row, column = _fade_operation_coordinates(op)
                if prop == 'inputChannelName':
                    column = 0
                target_cell = _scalar(reader, ws, destination, f'level/{row}/{column}')
                if target_cell is None or _fade_matrix_cell(matrix, row, column) is None:
                    raise ValueError('Fade crosspoint must exist in source and target.')
                if prop in {'level', 'sliderLevel'} and _fade_matrix_cell(matrix, row, column) is not True:
                    raise ValueError('Fade level requires its crosspoint to be enabled.')
                if prop == 'doLevel':
                    prospective['doLevel'][row][column] = op['requested']
                if op['requested'] == '-inf' and source['levelsMode'] != 0:
                    raise ValueError('Fade silence requires absolute Levels mode.')
        if _fade_missing_parameter_state(prospective):
            raise ValueError('Fade edit would remove the last active parameter.')
        # Indexed activation changes are verified against their complete expected matrix.
        deps['fade_activation'] = matrix
        deps['cues'][uid].pop('doLevel', None)



def _fade_cue_target(reader, ws, uid, destination, deps):
    if destination.upper() == uid:
        raise ValueError('A Fade cannot target itself.')
    context = _depend(reader, ws, destination.upper(), ['type', 'isRunning', 'isPaused', 'isBroken', 'isWarning'], deps)
    if any(context[k] is not False for k in ('isRunning', 'isPaused', 'isBroken', 'isWarning')):
        raise ValueError('New Fade target must be healthy and inactive.')
    active = _depend(reader, ws, uid, ['doOpacity', 'doRate', 'doRotation', 'doScale', 'doTranslation', 'doLevel'], deps)
    if any(type(active[k]) is not bool for k in ('doOpacity', 'doRate', 'doRotation', 'doScale', 'doTranslation')):
        raise ValueError('Fade activation flags are unavailable.')
    if any(active[k] is True for k in ('doOpacity', 'doRotation', 'doScale', 'doTranslation')) and context['type'] not in {'Video', 'Camera', 'Text'}:
        raise ValueError('Active Fade geometry requires a visual target.')
    if active['doRate'] is True and context['type'] not in {'Audio', 'Video'}:
        raise ValueError('Active Fade rate requires an Audio or Video target.')
    matrix = active['doLevel']
    if not isinstance(matrix, list) or any(not isinstance(row, list) or any(type(v) is not bool for v in row) for row in matrix):
        raise ValueError('Fade activation matrix is unavailable.')
    if any(value is True for row in matrix for value in row) and context['type'] not in {'Audio', 'Mic', 'Video', 'Camera'}:
        raise ValueError('Active Fade Levels require an audio-capable target.')


def _midi(reader, ws, uid, changes, deps):
    mode = _depend(reader, ws, uid, ['messageType'], deps)['messageType']
    names = (set(changes) - COMMON - {'midiPatchID'}) | ({'duration'} if 'duration' in changes else set())
    if 'messageType' in names:
        return
    if mode == 1:
        if names - VOICE:
            raise ValueError('Voice MIDI cue does not accept MSC or SysEx fields.')
        status = _depend(reader, ws, uid, ['status'], deps)['status']
        allowed = {'channel', 'status'}
        allowed |= {'byte1', 'note'} if status in (0, 1, 2) else {'byte1', 'programChange'} if status == 4 else {'byte1'} if status in (3, 5) else {'byteCombo', 'pitchBend'} if status == 6 else set()
        if status in (0, 1, 2, 3):
            allowed.add('byte2')
        if status in (0, 1):
            allowed.add('velocity')
        if status in (2, 3, 5, 6):
            allowed |= {'doFade', 'endValue', 'duration'}
        if names - allowed:
            raise ValueError('MIDI fields are incompatible with the current Voice status.')
        if changes.get('endValue', 0) > (16383 if status == 6 else 127):
            raise ValueError('MIDI endValue exceeds the current 7/14-bit status.')
    elif mode == 2:
        if names - MSC:
            raise ValueError('MSC cue does not accept Voice or SysEx fields.')
        command = _depend(reader, ws, uid, ['command'], deps)['command']
        if changes.get('command', command) not in MSC_COMMANDS:
            raise ValueError('Unknown documented MSC command.')
        # These fields depend on command-specific activation which OSC does not report.
        if names & {'controlNumber', 'controlValue', 'hours', 'minutes', 'seconds', 'frames', 'subframes', 'macro', 'qList', 'qNumber', 'qPath', 'timecodeString', 'timecodeFormat'}:
            raise ValueError('MSC command field activation needs validated metadata; field remains blocked.')
    elif mode == 3:
        if names - {'rawString'}:
            raise ValueError('SysEx mode only accepts rawString configuration.')
        text = re.sub(r'\s+', '', changes['rawString'])
        if not text or len(text) % 2 or re.fullmatch(r'[0-9a-fA-F]+', text) is None:
            raise ValueError('SysEx requires complete hexadecimal bytes.')
        if any(byte >= 128 for byte in bytes.fromhex(text)):
            raise ValueError('SysEx payload uses 7-bit bytes and omits F0/F7 delimiters.')
    else:
        raise ValueError('MIDI mode is unavailable.')
