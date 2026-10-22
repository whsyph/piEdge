#!/usr/bin/env python3
"""Native KMS connector DPMS control; requires a free DRM master, not sudo."""
import argparse
import ctypes as C
import ctypes.util
import json
import os
from pathlib import Path
import re

CONNECTOR = 0xc0c0c0c0


class ObjectProperties(C.Structure):
    _fields_ = [('count_props', C.c_uint32), ('props', C.POINTER(C.c_uint32)),
                ('prop_values', C.POINTER(C.c_uint64))]


class PropertyPrefix(C.Structure):
    # Stable prefix of libdrm's allocated drmModePropertyRes. Do not allocate it.
    _fields_ = [('prop_id', C.c_uint32), ('flags', C.c_uint32), ('name', C.c_char * 32)]


def connector_id(device, display):
    if not re.fullmatch(r'/dev/dri/card[0-9]+', device):
        raise ValueError('Expected a DRM card device')
    if not re.fullmatch(r'HDMI-A-[12]', display):
        raise ValueError('Expected HDMI-A-1 or HDMI-A-2')
    path = Path('/sys/class/drm') / (Path(device).name + '-' + display) / 'connector_id'
    return int(path.read_text().strip())


def library():
    name = ctypes.util.find_library('drm')
    if not name:
        raise RuntimeError('libdrm unavailable')
    lib = C.CDLL(name, use_errno=True)
    lib.drmModeObjectGetProperties.argtypes = [C.c_int, C.c_uint32, C.c_uint32]
    lib.drmModeObjectGetProperties.restype = C.POINTER(ObjectProperties)
    lib.drmModeFreeObjectProperties.argtypes = [C.POINTER(ObjectProperties)]
    lib.drmModeGetProperty.argtypes = [C.c_int, C.c_uint32]
    lib.drmModeGetProperty.restype = C.POINTER(PropertyPrefix)
    lib.drmModeFreeProperty.argtypes = [C.POINTER(PropertyPrefix)]
    lib.drmModeConnectorSetProperty.argtypes = [C.c_int, C.c_uint32, C.c_uint32, C.c_uint64]
    lib.drmModeConnectorSetProperty.restype = C.c_int
    lib.drmSetMaster.argtypes = [C.c_int]
    lib.drmSetMaster.restype = C.c_int
    lib.drmDropMaster.argtypes = [C.c_int]
    return lib


def properties(lib, fd, identifier):
    props = lib.drmModeObjectGetProperties(fd, identifier, CONNECTOR)
    if not props:
        raise OSError(C.get_errno(), 'Cannot read connector properties')
    result = {}
    try:
        if props.contents.count_props > 256:
            raise RuntimeError('Unexpected DRM property count')
        for i in range(props.contents.count_props):
            info = lib.drmModeGetProperty(fd, props.contents.props[i])
            if not info:
                continue
            try:
                result[info.contents.name.decode()] = (int(info.contents.prop_id), int(props.contents.prop_values[i]))
            finally:
                lib.drmModeFreeProperty(info)
    finally:
        lib.drmModeFreeObjectProperties(props)
    return result


class PowerLease:
    """Keep the DRM FD/master alive during sleep: last-close can restore console DPMS."""
    def __init__(self, device, display):
        self.identifier = connector_id(device, display)
        self.display = display
        self.lib = library()
        self.fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
        self.acquired = False

    def status(self):
        props = properties(self.lib, self.fd, self.identifier)
        if 'DPMS' not in props:
            raise RuntimeError('Connector has no DPMS property')
        value = props['DPMS'][1]
        return {'display': self.display, 'connector_id': self.identifier,
                'dpms': value, 'powered': value == 0}

    def set_enabled(self, enabled):
        if not self.acquired:
            if self.lib.drmSetMaster(self.fd) != 0:
                raise OSError(C.get_errno(), 'Cannot acquire DRM master; a renderer may still own display')
            self.acquired = True
        props = properties(self.lib, self.fd, self.identifier)
        desired = 0 if enabled else 3
        if self.lib.drmModeConnectorSetProperty(self.fd, self.identifier, props['DPMS'][0], desired) != 0:
            raise OSError(C.get_errno(), 'DRM DPMS update failed')
        state = self.status()
        if state['dpms'] != desired:
            raise RuntimeError('DPMS readback mismatch')
        return state

    def close(self):
        if self.fd is not None:
            if self.acquired:
                self.lib.drmDropMaster(self.fd)
            os.close(self.fd)
            self.fd = None
            self.acquired = False


def output_power(device, display):
    lease = PowerLease(device, display)
    try:
        return lease.status()
    finally:
        lease.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['status', 'on', 'off'])
    parser.add_argument('--device', default='/dev/dri/card1')
    parser.add_argument('--display', default='HDMI-A-1')
    parser.add_argument('--hold-seconds', type=int, default=0)
    args = parser.parse_args()
    try:
        if args.mode == 'status':
            print(json.dumps(output_power(args.device, args.display)), flush=True)
        else:
            if args.mode == 'off' and not 1 <= args.hold_seconds <= 30:
                parser.error('off requires --hold-seconds 1..30; persistent sleep is managed by supervisor lease')
            lease = PowerLease(args.device, args.display)
            try:
                print(json.dumps(lease.set_enabled(args.mode == 'on')), flush=True)
                if args.hold_seconds:
                    import time
                    time.sleep(args.hold_seconds)
            finally:
                lease.set_enabled(True)
                lease.close()
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')
