"""Passive macOS video metadata, isolated in a bounded subprocess.

Only metadata getters are called. No capture inputs/sessions, configuration
locks, permission requests, NDI finders or output senders are constructed.
"""
from __future__ import annotations

import ctypes as C
import json
import sys
from datetime import datetime, timezone

LIMIT = 1000
MAX_BYTES = 2 * 1024 * 1024


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


def inputs():
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
    return dict(status='ready' if rows or authorization == 3 else 'permission_not_authorized',
                authorization_status=authorization, devices=rows, formats=formats, device_count=total,
                truncated=truncated, effective_capture_format_observed=False)


def main():
    try:
        if sys.platform != 'darwin':
            result = dict(status='unsupported_platform', devices=[], formats=[])
        elif sys.argv[1:] == ['devices']:
            result = displays()
        elif sys.argv[1:] == ['inputs']:
            result = inputs()
        else:
            raise ValueError('Expected devices or inputs.')
        result['observed_at'] = datetime.now(timezone.utc).isoformat()
        while len(json.dumps(result, allow_nan=False).encode()) > MAX_BYTES:
            result['truncated'] = True
            key = 'formats' if result.get('formats') else 'devices'
            result[key].pop()
        print(json.dumps(result, allow_nan=False))
    except (OSError, ValueError, AttributeError, OverflowError) as exc:
        print(json.dumps(dict(status='unavailable', devices=[], formats=[], message=str(exc)[:512])))


if __name__ == '__main__':
    main()
