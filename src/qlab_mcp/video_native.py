"""Passive macOS video metadata, isolated in a bounded subprocess.

Only metadata getters are called. No capture inputs/sessions, configuration
locks, permission requests, NDI finders or output senders are constructed.
"""
from __future__ import annotations

import ctypes as C
import json
import plistlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LIMIT = 1000
MAX_BYTES = 2 * 1024 * 1024
QLAB_BUNDLE_ID = 'com.figure53.QLab.5'
SYPHON_SETTLE_SECONDS = 1


def _verify_syphon_framework(framework):
    """Authenticate the code being loaded, rather than trusting a bundle identifier."""
    requirement = ('=identifier "info.v002.Syphon" and anchor apple generic '
                   'and certificate leaf[subject.OU] = "7672N4CCJM"')
    result = subprocess.run(
        ['/usr/bin/codesign', '--verify', '--strict', '--test-requirement', requirement, str(framework)],
        capture_output=True, timeout=3, check=False)
    if result.returncode:
        raise ValueError('Syphon framework signature could not be verified as Figure 53 code.')


class DisplayRect(C.Structure):
    _fields_ = [('x', C.c_double), ('y', C.c_double), ('width', C.c_double), ('height', C.c_double)]


class Dimensions(C.Structure):
    _fields_ = [('width', C.c_int32), ('height', C.c_int32)]


def _function(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, args
    return fn


class _Objects:
    def __init__(self):
        self.lib = C.CDLL('/usr/lib/libobjc.A.dylib')
        self.cls = _function(self.lib, 'objc_getClass', C.c_void_p, C.c_char_p)
        self.sel = _function(self.lib, 'sel_registerName', C.c_void_p, C.c_char_p)
        self.address = C.cast(self.lib.objc_msgSend, C.c_void_p).value

    def send(self, obj, name, result=C.c_void_p, *args):
        fn = C.CFUNCTYPE(result, C.c_void_p, C.c_void_p, *[t for t, _ in args])(self.address)
        return fn(obj, self.sel(name.encode()), *[v for _, v in args])

    def text(self, obj):
        value = self.send(obj, 'UTF8String', C.c_char_p) if obj else None
        return value.decode('utf-8', errors='replace')[:4096] if value else None

    def string(self, value):
        return self.send(self.cls(b'NSString'), 'stringWithUTF8String:', C.c_void_p, (C.c_char_p, value.encode()))

    def array(self, obj):
        count = self.send(obj, 'count', C.c_ulong) if obj else 0
        return [self.send(obj, 'objectAtIndex:', C.c_void_p, (C.c_ulong, i)) for i in range(min(count, LIMIT))], count


def _optional_get(o, obj, selector, result, errors, field):
    try:
        if not o.send(obj, 'respondsToSelector:', C.c_bool,
                      (C.c_void_p, o.sel(selector.encode()))):
            errors[field] = 'getter_unavailable'
            return None
        return o.send(obj, selector, result)
    except (OSError, ValueError, AttributeError, OverflowError) as exc:
        errors[field] = str(exc)[:512]
        return None


def displays():
    cg = C.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    online = _function(cg, 'CGGetOnlineDisplayList', C.c_int32, C.c_uint32, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32))
    count = C.c_uint32()
    if online(0, None, C.byref(count)):
        raise ValueError('CoreGraphics display enumeration failed.')
    ids = (C.c_uint32 * min(count.value, LIMIT))()
    total = count.value
    if online(len(ids), ids, C.byref(count)):
        raise ValueError('CoreGraphics display enumeration failed.')
    names = {}
    try:
        C.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
        o = _Objects()
        screens, _ = o.array(o.send(o.cls(b'NSScreen'), 'screens'))
        key = o.string('NSScreenNumber')
        for screen in screens:
            description = o.send(screen, 'deviceDescription')
            number = o.send(description, 'objectForKey:', C.c_void_p, (C.c_void_p, key))
            names[o.send(number, 'unsignedIntValue', C.c_uint)] = o.text(o.send(screen, 'localizedName'))
    except (OSError, ValueError, AttributeError):
        pass  # CoreGraphics identities remain useful without AppKit display names.
    copy_mode = _function(cg, 'CGDisplayCopyDisplayMode', C.c_void_p, C.c_uint32)
    release_mode = _function(cg, 'CGDisplayModeRelease', None, C.c_void_p)
    width = _function(cg, 'CGDisplayModeGetPixelWidth', C.c_size_t, C.c_void_p)
    height = _function(cg, 'CGDisplayModeGetPixelHeight', C.c_size_t, C.c_void_p)
    rate = _function(cg, 'CGDisplayModeGetRefreshRate', C.c_double, C.c_void_p)
    bounds = _function(cg, 'CGDisplayBounds', DisplayRect, C.c_uint32)
    rows = []
    for identity in ids[:count.value]:
        row = dict(screen_id=identity, name=names.get(identity), type='Display', online=True)
        row['metadata_errors'] = {}
        try:
            frame = bounds(identity)
            row['screen_frame'] = [frame.x, frame.y, frame.width, frame.height]
        except (OSError, ValueError, AttributeError) as exc:
            row['screen_frame'] = None
            row['metadata_errors']['screen_frame'] = str(exc)[:512]
        for field, method in [('active', 'CGDisplayIsActive'), ('asleep', 'CGDisplayIsAsleep'),
                              ('mirrored', 'CGDisplayIsInMirrorSet')]:
            try:
                row[field] = bool(_function(cg, method, C.c_uint32, C.c_uint32)(identity))
            except (OSError, ValueError, AttributeError) as exc:
                row[field] = None
                row['metadata_errors'][field] = str(exc)[:512]
        for field, method in [('vendor', 'CGDisplayVendorNumber'), ('model', 'CGDisplayModelNumber'),
                              ('serial', 'CGDisplaySerialNumber'), ('builtin', 'CGDisplayIsBuiltin')]:
            row[field] = _function(cg, method, C.c_uint32, C.c_uint32)(identity)
        mode = copy_mode(identity)
        if mode:
            try:
                row.update(width=width(mode), height=height(mode), refresh_rate=rate(mode) or None)
            finally:
                release_mode(mode)
        rows.append(row)
    return dict(status='ready', devices=rows, formats=[], device_count=total,
                truncated=total > len(rows), identity_scope='current_macos_display_session')


def audio_inputs():
    """Read CoreAudio input identities and channel counts without opening capture."""
    core = C.CDLL('/System/Library/Frameworks/CoreAudio.framework/CoreAudio')
    cf = C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    size_fn = _function(core, 'AudioObjectGetPropertyDataSize', C.c_int32, C.c_uint32,
                        C.c_void_p, C.c_uint32, C.c_void_p, C.POINTER(C.c_uint32))
    get_fn = _function(core, 'AudioObjectGetPropertyData', C.c_int32, C.c_uint32,
                       C.c_void_p, C.c_uint32, C.c_void_p, C.POINTER(C.c_uint32), C.c_void_p)
    get_string = _function(cf, 'CFStringGetCString', C.c_bool, C.c_void_p, C.c_char_p,
                           C.c_long, C.c_uint32)
    code = lambda value: int.from_bytes(value.encode('ascii'), 'big')

    class Address(C.Structure):
        _fields_ = [('selector', C.c_uint32), ('scope', C.c_uint32), ('element', C.c_uint32)]

    class AudioBuffer(C.Structure):
        _fields_ = [('channels', C.c_uint32), ('byte_size', C.c_uint32), ('data', C.c_void_p)]

    class BufferListHeader(C.Structure):
        _fields_ = [('count', C.c_uint32), ('buffers', AudioBuffer * 1)]

    def property_data(object_id, selector, scope='glob', *, allow_empty=False):
        address = Address(code(selector), code(scope), 0)
        size = C.c_uint32()
        status = size_fn(object_id, C.byref(address), 0, None, C.byref(size))
        if status or size.value > 64 * 1024 or not size.value and not allow_empty:
            raise ValueError(f'CoreAudio property {selector!r} is unavailable.')
        if not size.value:
            return C.create_string_buffer(1), 0
        data = C.create_string_buffer(size.value)
        status = get_fn(object_id, C.byref(address), 0, None, C.byref(size), data)
        if status:
            raise ValueError(f'CoreAudio property {selector!r} could not be read.')
        return data, size.value

    def string_property(object_id, selector):
        data, size = property_data(object_id, selector)
        if size != C.sizeof(C.c_void_p):
            raise ValueError(f'CoreAudio string property {selector!r} has an unknown shape.')
        value = C.cast(data, C.POINTER(C.c_void_p)).contents.value
        if not value:
            return None
        text = C.create_string_buffer(4096)
        if not get_string(value, text, len(text), 0x08000100):
            raise ValueError(f'CoreAudio string property {selector!r} is not UTF-8 readable.')
        return text.value.decode('utf-8')

    devices_data, devices_size = property_data(1, 'dev#', allow_empty=True)
    if devices_size % C.sizeof(C.c_uint32):
        raise ValueError('CoreAudio device inventory has an invalid size.')
    device_ids = list(C.cast(devices_data, C.POINTER(C.c_uint32 * (devices_size // 4))).contents)
    if len(device_ids) > LIMIT:
        raise ValueError('CoreAudio device inventory exceeds its limit.')
    default_data, default_size = property_data(1, 'dIn ')
    if default_size != C.sizeof(C.c_uint32):
        raise ValueError('CoreAudio default input identity has an invalid size.')
    default_id = C.cast(default_data, C.POINTER(C.c_uint32)).contents.value
    rows = []
    for device_id in device_ids:
        data, size = property_data(device_id, 'slay', 'inpt')
        if size < BufferListHeader.buffers.offset:
            raise ValueError('CoreAudio input stream configuration has an invalid size.')
        header = C.cast(data, C.POINTER(BufferListHeader)).contents
        needed = BufferListHeader.buffers.offset + header.count * C.sizeof(AudioBuffer)
        if header.count > 128 or needed > size:
            raise ValueError('CoreAudio input stream configuration exceeds its bounds.')
        channels = sum(AudioBuffer.from_buffer(data, BufferListHeader.buffers.offset + index * C.sizeof(AudioBuffer)).channels
                       for index in range(header.count))
        rows.append(dict(id=device_id, uid=string_property(device_id, 'uid '),
                         name=string_property(device_id, 'lnam'),
                         model_uid=string_property(device_id, 'muid'),
                         input_channels=channels, source='macos_coreaudio'))
    return dict(status='ready', devices=rows, formats=[], device_count=len(rows),
                default_input_id=default_id, identity_scope='current_macos_audio_session',
                capture_started=False)


def inputs(include_syphon=False):
    C.CDLL('/System/Library/Frameworks/AVFoundation.framework/AVFoundation')
    cm = C.CDLL('/System/Library/Frameworks/CoreMedia.framework/CoreMedia')
    size = _function(cm, 'CMVideoFormatDescriptionGetDimensions', Dimensions, C.c_void_p)
    subtype = _function(cm, 'CMFormatDescriptionGetMediaSubType', C.c_uint32, C.c_void_p)
    o = _Objects()
    cls = o.cls(b'AVCaptureDevice')
    media = o.string('vide')
    authorization = o.send(cls, 'authorizationStatusForMediaType:', C.c_long, (C.c_void_p, media))
    devices, total = o.array(o.send(cls, 'devicesWithMediaType:', C.c_void_p, (C.c_void_p, media)))
    rows, formats = [], []
    truncated = total > len(devices)
    for device in devices:
        uid = o.text(o.send(device, 'uniqueID'))
        row = dict(id=uid, name=o.text(o.send(device, 'localizedName')), type='AVCaptureDevice',
                   metadata_errors={}, observed_format=None)
        for field, selector in [('connected', 'isConnected'), ('suspended', 'isSuspended'),
                                ('in_use_by_another_application', 'isInUseByAnotherApplication')]:
            value = _optional_get(o, device, selector, C.c_bool, row['metadata_errors'], field)
            row[field] = bool(value) if value is not None else None
        observed = _optional_get(o, device, 'activeFormat', C.c_void_p,
                                 row['metadata_errors'], 'observed_format')
        if observed:
            try:
                desc = o.send(observed, 'formatDescription')
                if not desc:
                    raise ValueError('format_description_unavailable')
                dimensions = size(desc)
                row['observed_format'] = dict(width=dimensions.width, height=dimensions.height,
                    pixel_format=subtype(desc), source='macos_avfoundation',
                    qlab_attribution='unverified', capture_verified=False)
            except (OSError, ValueError, AttributeError, OverflowError) as exc:
                row['metadata_errors']['observed_format'] = str(exc)[:512]
        elif 'observed_format' not in row['metadata_errors']:
            row['metadata_errors']['observed_format'] = 'no_observed_format'
        supported, count = o.array(o.send(device, 'formats'))
        row['format_count'] = count
        truncated |= count > len(supported)
        for index, fmt in enumerate(supported):
            if len(formats) >= LIMIT:
                truncated = True
                break
            desc = o.send(fmt, 'formatDescription')
            dimensions = size(desc)
            ranges, range_count = o.array(o.send(fmt, 'videoSupportedFrameRateRanges'))
            formats.append(dict(source_id=uid, index=index, width=dimensions.width, height=dimensions.height,
                pixel_format=subtype(desc), frame_rates=[dict(
                    min=o.send(r, 'minFrameRate', C.c_double), max=o.send(r, 'maxFrameRate', C.c_double)) for r in ranges[:64]],
                frame_rates_truncated=range_count > 64))
        rows.append(row)
    result = dict(status='ready' if rows or authorization == 3 else 'permission_not_authorized',
                  authorization_status=authorization, devices=rows, formats=formats, device_count=total,
                  truncated=truncated, effective_capture_format_observed=False)
    if include_syphon:
        try:
            syphon = _syphon_inventory(o)
        except Exception as exc:
            syphon = dict(status='unavailable', source='public_SyphonServerDirectory', servers=[],
                          count=0, truncated=False, bounded_observation=False,
                          settle_budget_seconds=SYPHON_SETTLE_SECONDS, message=str(exc)[:512])
        result.update(syphon_status=syphon['status'], syphon_servers=syphon['servers'],
                      syphon_server_count=syphon['count'], syphon_truncated=syphon['truncated'],
                      syphon_bounded_observation=syphon['bounded_observation'],
                      syphon_settle_budget_seconds=syphon['settle_budget_seconds'],
                      syphon_source=syphon['source'],
                      **({'syphon_message': syphon['message']} if syphon.get('message') else {}))
    return result


def _syphon_inventory(o):
    """Read the public Syphon directory using an authenticated bundled framework."""
    C.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
    C.CDLL('/System/Library/Frameworks/AppKit.framework/AppKit')
    workspace = o.send(o.cls(b'NSWorkspace'), 'sharedWorkspace')
    applications, total = o.array(o.send(workspace, 'runningApplications'))
    if total != len(applications):
        raise ValueError('Running application inventory was truncated; QLab uniqueness cannot be verified.')
    matches = [application for application in applications
               if o.text(o.send(application, 'bundleIdentifier')) == QLAB_BUNDLE_ID]
    if not matches:
        return dict(status='qlab_not_running', source='public_SyphonServerDirectory', servers=[],
                    count=0, truncated=False, bounded_observation=False,
                    settle_budget_seconds=SYPHON_SETTLE_SECONDS)
    if len(matches) != 1:
        return dict(status='ambiguous_qlab_processes', source='public_SyphonServerDirectory', servers=[],
                    count=0, truncated=False, bounded_observation=False,
                    settle_budget_seconds=SYPHON_SETTLE_SECONDS)
    path = o.text(o.send(o.send(matches[0], 'bundleURL'), 'path'))
    if not path:
        raise ValueError('The running QLab process did not report its bundle URL.')
    bundle = Path(path).resolve(strict=True)
    with (bundle / 'Contents' / 'Info.plist').open('rb') as stream:
        if plistlib.load(stream).get('CFBundleIdentifier') != QLAB_BUNDLE_ID:
            raise ValueError('Running QLab bundle identity did not match its Info.plist.')
    framework = (bundle / 'Contents' / 'Frameworks' / 'Syphon.framework').resolve(strict=True)
    library_path = (framework / 'Syphon').resolve(strict=True)
    if not library_path.is_file():
        raise OSError('Syphon.framework is unavailable in the running QLab bundle.')
    if not framework.is_relative_to(bundle) or not library_path.is_relative_to(bundle):
        raise ValueError('Syphon framework resolves outside the running QLab bundle.')
    _verify_syphon_framework(framework)
    library = C.CDLL(str(library_path))
    keys = {name: C.c_void_p.in_dll(library, symbol).value for name, symbol in (
        ('uuid', 'SyphonServerDescriptionUUIDKey'), ('name', 'SyphonServerDescriptionNameKey'),
        ('application', 'SyphonServerDescriptionAppNameKey'))}
    pool = o.send(o.cls(b'NSAutoreleasePool'), 'new')
    try:
        directory = o.send(o.cls(b'SyphonServerDirectory'), 'sharedDirectory')
        if not directory:
            raise ValueError('Public Syphon server directory is unavailable.')
        loop = o.send(o.cls(b'NSRunLoop'), 'currentRunLoop')
        until = o.send(o.cls(b'NSDate'), 'dateWithTimeIntervalSinceNow:', C.c_void_p,
                       (C.c_double, float(SYPHON_SETTLE_SECONDS)))
        o.send(loop, 'runUntilDate:', None, (C.c_void_p, until))
        servers, total = o.array(o.send(directory, 'servers'))
        rows = [dict(server_uuid=o.text(o.send(server, 'objectForKey:', C.c_void_p, (C.c_void_p, keys['uuid']))),
                     name=o.text(o.send(server, 'objectForKey:', C.c_void_p, (C.c_void_p, keys['name']))),
                     application=o.text(o.send(server, 'objectForKey:', C.c_void_p, (C.c_void_p, keys['application']))),
                     type='SyphonServer', source='public_SyphonServerDirectory', capture_verified=False,
                     assignment_supported=False, observed_in_qlab=False) for server in servers]
        truncated = total > len(rows)
        return dict(status='ready', source='public_SyphonServerDirectory', servers=rows, count=total,
                    truncated=truncated, bounded_observation=True,
                    settle_budget_seconds=SYPHON_SETTLE_SECONDS)
    finally:
        if pool:
            o.send(pool, 'drain', None)


def main():
    try:
        if sys.platform != 'darwin':
            result = dict(status='unsupported_platform', devices=[], formats=[])
        elif sys.argv[1:] == ['devices']:
            result = displays()
        elif sys.argv[1:] == ['audio']:
            result = audio_inputs()
        elif sys.argv[1:] in (['inputs'], ['inputs', '--include-syphon']):
            result = inputs(include_syphon=sys.argv[1:] != ['inputs'])
        else:
            raise ValueError('Expected devices or inputs.')
        result['observed_at'] = datetime.now(timezone.utc).isoformat()
        while len(json.dumps(result, allow_nan=False).encode()) > MAX_BYTES:
            result['truncated'] = True
            key = next((key for key in ('formats', 'syphon_servers', 'devices') if result.get(key)), None)
            if key is None:
                break
            result[key].pop()
            if key == 'syphon_servers':
                result['syphon_truncated'] = True
        print(json.dumps(result, allow_nan=False))
    except (OSError, ValueError, AttributeError, OverflowError) as exc:
        print(json.dumps(dict(status='unavailable', devices=[], formats=[], message=str(exc)[:512])))


if __name__ == '__main__':
    main()
