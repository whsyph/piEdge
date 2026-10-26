#!/usr/bin/env python3
"""Fresh Pi 5 player installation; --check never mutates the target."""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
PAYLOAD = ('signage.py', 'splash.py', 'splash.sh', 'profiles/pi5.json')
UNITS = ('pi5-signage.service', 'labwc.service')
DEPLOYMENTS = ('/opt/pi5-signage', '/etc/pi5-signage.json', '/var/lib/pi5-signage',
               '/home/pi/museum_signage', '/home/pi/museum_video', '/opt/piEdge')
SYSTEMD_DIRS = ('/etc/systemd/system', '/run/systemd/system',
                '/usr/lib/systemd/system', '/lib/systemd/system')
# Ponytail: reject any existing seatd drop-in rather than merging operator policy.
COMPETITORS = ('layar1.service', 'layar2.service', 'layar-gabungan.service',
               'cms-signage.service', 'display-manager.service', 'lightdm.service',
               'gdm.service', 'sddm.service', 'weston.service')


def run(args):
    return subprocess.run(args, check=True, text=True, capture_output=True)


def validate_user(user):
    if user.pw_uid != 1000:
        raise ValueError('User pi must have UID 1000; reinstall/provision the OS explicitly.')
    return user


def pi_user():
    import pwd
    try:
        return validate_user(pwd.getpwnam('pi'))
    except KeyError:
        raise ValueError('Create user pi with UID 1000 using Raspberry Pi Imager first; no passwords are managed here.')


def check(source=ROOT, root=Path('/')):
    def path(name): return root / name.lstrip('/')
    model = path('/proc/device-tree/model').read_text().rstrip('\0\n')
    if not re.fullmatch(r'Raspberry Pi 5 Model B(?: Rev \d+\.\d+)?', model):
        raise ValueError('Only Raspberry Pi 5 Model B is supported.')
    release = dict(line.split('=', 1) for line in path('/etc/os-release').read_text().splitlines()
                   if '=' in line and not line.startswith('#'))
    release = {k: v.strip('"') for k, v in release.items()}
    if release.get('VERSION_CODENAME') != 'bookworm' or release.get('ID') not in ('debian', 'raspbian'):
        raise ValueError('Raspberry Pi OS Bookworm required.')
    if not path('/etc/rpi-issue').is_file():
        raise ValueError('Raspberry Pi OS image marker /etc/rpi-issue required.')
    if (platform.machine() != 'aarch64' and root == Path('/')) or run(['dpkg', '--print-architecture']).stdout.strip() != 'arm64':
        raise ValueError('Bookworm 64-bit arm64 required.')
    if not path('/run/systemd/system').is_dir() or path('/proc/1/comm').read_text().strip() != 'systemd':
        raise ValueError('A running systemd system is required.')
    user = pi_user()
    for base in SYSTEMD_DIRS:
        for name in UNITS + COMPETITORS[:4] + ('seatd.service',):
            if os.path.lexists(path(base) / name) or os.path.lexists(path(base) / (name + '.d')):
                raise ValueError(f'Existing service deployment: {base}/{name}')
    for name in DEPLOYMENTS:
        if os.path.lexists(path(name)):
            raise ValueError(f'Existing deployment/data: {name}; migration is not supported.')
    for name in UNITS + COMPETITORS:
        result = run(['systemctl', 'show', name, '--property=ActiveState,UnitFileState'])
        props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if props.get('ActiveState') not in ('inactive', 'failed') or props.get('UnitFileState', '') in ('enabled', 'enabled-runtime', 'linked', 'linked-runtime', 'alias'):
            raise ValueError(f'Active/enabled display owner: {name}')
    processes = run(['ps', '-eo', 'comm=']).stdout.splitlines()
    if set(p.strip() for p in processes) & {'mpv', 'vlc', 'labwc', 'wayfire', 'weston', 'sway', 'Xorg', 'Xwayland'}:
        raise ValueError('Competing display process running; stop it explicitly first.')
    for name in PAYLOAD + UNITS + ('config.pi5.json',):
        if (source / name).is_symlink() or not (source / name).is_file():
            raise ValueError(f'Missing/unsafe payload: {name}')
    # Parse templates before apt or any target writes; preserve the legacy template.
    config = json.loads((source / 'config.pi5.json').read_text())
    if config.get('profile') != 'pi5':
        raise ValueError('Wrong config profile')
    profile = json.loads((source / 'profiles/pi5.json').read_text())
    if profile.get('target') != 'pi5' or profile.get('mpv', {}).get('vo') != 'dmabuf-wayland':
        raise ValueError('Invalid pi5 hardware profile schema')
    return user, config


def exclusive(path, data, mode=0o644):
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(mode)


def install(source=ROOT, root=Path('/')):
    if getattr(os, 'geteuid', lambda: -1)() != 0:
        raise ValueError('Install requires root: sudo python3 install-fresh.py')
    user, config = check(source, root)
    # ponytail: fresh-only, not transactional; failure leaves evidence for manual recovery.
    run(['apt-get', 'update'])
    run(['apt-get', 'install', '-y', '--no-install-recommends', 'python3', 'mpv',
         'labwc', 'seatd', 'wlr-randr', 'dbus-user-session'])
    app = root / 'opt/pi5-signage'
    app.mkdir(mode=0o755, parents=True, exist_ok=False)
    (app / 'profiles').mkdir(mode=0o755)
    media = root / 'var/lib/pi5-signage/videos'
    media.mkdir(mode=0o755, parents=True, exist_ok=False)
    os.chown(media.parent, user.pw_uid, user.pw_gid)
    os.chown(media, user.pw_uid, user.pw_gid)
    for name in PAYLOAD:
        exclusive(app / name, (source / name).read_bytes(), 0o755 if name.endswith('.sh') else 0o644)
    run(['/usr/bin/python3', str(app / 'splash.py'), '--output', str(app / 'splash.ppm')])
    config.update(media_dir='/var/lib/pi5-signage/videos')
    for key in ('playlist_file', 'schedules_file'):
        config.pop(key, None)
    exclusive(root / 'etc/pi5-signage.json', (json.dumps(config, indent=2) + '\n').encode())
    for name in UNITS:
        text = (source / name).read_text()
        if name == 'labwc.service':
            text = text.replace('Requires=seatd.service', 'Requires=seatd.service user-runtime-dir@1000.service')
            text = text.replace('After=network.target', 'After=user-runtime-dir@1000.service network.target')
            text = text.replace('User=pi', 'User=pi\nSupplementaryGroups=video render audio\nEnvironment=LIBSEAT_BACKEND=seatd')
        # Keep the live/legacy units unchanged; fresh-only overrides are installed here.
        exclusive(root / 'etc/systemd/system' / name, text.encode())
    # seatd uses the video group explicitly, independent of distribution defaults.
    override = root / 'etc/systemd/system/seatd.service.d'
    if override.exists():
        raise ValueError(f'Existing service drop-in: {override}')
    override.mkdir(mode=0o755, exist_ok=False)
    exclusive(override / 'capibarra.conf', b'[Service]\nExecStart=\nExecStart=/usr/bin/seatd -g video\n')
    run(['systemctl', 'daemon-reload'])
    # Deliberately neither enable nor start: reboot must not begin playback either.
    print('Installed, disabled and not started. Review /etc/pi5-signage.json and add media before manually starting pi5-signage.service.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.check:
            check()
            print('Fresh-install preflight passed; no changes made.')
        else:
            install()
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Fresh install refused/failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
