#!/usr/bin/env python3
"""Read-only installation validation; no bytecode writes when called by installer."""
import hashlib
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signage import detect_device_model, resolve_profile_name, load_config, load_profile


def validate(source, model=None, config=Path('/etc/pi5-signage.json'), labwc=Path('/etc/systemd/system/labwc.service')):
    manifest = json.loads((source / 'release.json').read_text(encoding='utf-8'))
    target = manifest['target']
    if target not in {'pi5'}:
        raise ValueError('Unknown release target')
    if resolve_profile_name({}, detect_device_model() if model is None else model) != target:
        raise ValueError('Package/board mismatch')
    required = {'install.sh', 'signage.py', 'splash.py', 'splash.sh', 'labwc.service', 'pi5-signage.service',
                f'profiles/{target}.json', f'config.{target}.json', 'scripts/preflight.py', 'scripts/build-release.py'}
    hashes = manifest['files']
    if not required <= hashes.keys():
        raise ValueError('Incomplete manifest')
    for name, digest in hashes.items():
        path = source / name
        if not path.resolve().is_relative_to(source.resolve()) or path.is_symlink():
            raise ValueError('Unsafe manifest path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Checksum mismatch: {name}')
    load_profile(target)
    template = load_config(source / f'config.{target}.json')
    if template['_profile_name'] != target:
        raise ValueError('Template profile mismatch')
    if config.exists():
        raw = json.loads(config.read_text(encoding='utf-8'))
        if raw.get('profile') != target:
            raise ValueError('Existing config has missing/different profile. Back up and explicitly migrate; no files changed.')
        load_config(config)
    if labwc.exists() and labwc.read_bytes() != (source / 'labwc.service').read_bytes():
        raise ValueError('Operator labwc unit differs; review and reconcile explicitly before install')
    return target

if __name__ == '__main__':
    try:
        print('Preflight OK:', validate(Path(sys.argv[1])))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Preflight refused: {exc}', file=sys.stderr)
        raise SystemExit(1)
