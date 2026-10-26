#!/usr/bin/env python3
"""Fresh, player-only Pi4 install. --check is read-only; install never starts playback."""
import argparse, hashlib, json, os, platform, re, subprocess, sys
from pathlib import Path
try:
    import grp, pwd
except ImportError:
    grp = pwd = None

def lookup_user():
    if pwd is None: raise ValueError('pi account lookup requires Linux')
    return pwd.getpwnam('pi')
def lookup_group(name):
    if grp is None: raise KeyError(name)
    return grp.getgrnam(name)

ROOT = Path(__file__).resolve().parent
APP = '/opt/pi5-signage'; CONFIG = '/etc/pi5-signage.json'; MEDIA = '/var/lib/pi5-signage/videos'
UNIT = 'pi5-signage.service'
PAYLOAD = ('signage.py', 'drm_power.py', 'drm_splash.py', 'splash.sh')
APT = ('mpv', 'ffmpeg', 'libdrm2', 'python3', 'kbd', 'libpam-systemd')
SYSTEMD_DIRS = ('/etc/systemd/system', '/run/systemd/system', '/usr/lib/systemd/system', '/lib/systemd/system')
COMPETITORS = ('labwc.service', 'layar-gabungan.service', 'layar1.service', 'layar2.service',
               'cms-signage.service', 'display-manager.service', 'lightdm.service', 'gdm.service',
               'sddm.service', 'weston.service')
DEPLOYMENTS = (APP, CONFIG, '/var/lib/pi5-signage', '/home/pi/museum_signage',
               '/home/pi/museum_video', '/opt/piEdge')


def run(args): return subprocess.run(args, check=True, text=True, capture_output=True)
def rooted(root, name): return root / name.lstrip('/')
def exists(path): return os.path.lexists(path)


def check(source=ROOT, root=Path('/'), machine=None, user=None):
    model = rooted(root, '/proc/device-tree/model').read_bytes().decode(errors='replace').strip('\0\n ')
    if not re.fullmatch(r'Raspberry Pi 4 Model B Rev 1\.[0-9]+', model): raise ValueError('Requires Raspberry Pi 4 Model B')
    release = dict(line.split('=', 1) for line in rooted(root, '/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') not in ('debian', 'raspbian') or release.get('VERSION_CODENAME', '').strip('"') != 'bookworm':
        raise ValueError('Requires Raspberry Pi OS Bookworm')
    if not rooted(root, '/etc/rpi-issue').is_file(): raise ValueError('Raspberry Pi OS marker /etc/rpi-issue required')
    if (machine or platform.machine()) != 'aarch64' or run(['dpkg', '--print-architecture']).stdout.strip() != 'arm64':
        raise ValueError('Requires arm64 OS and dpkg architecture')
    if not rooted(root, '/run/systemd/system').is_dir() or rooted(root, '/proc/1/comm').read_text().strip() != 'systemd':
        raise ValueError('A running systemd system is required')
    try: user = user or lookup_user()
    except KeyError: raise ValueError('Create user pi with UID 1000 first')
    if user.pw_uid != 1000: raise ValueError('Requires the pi account at UID 1000')
    for group in ('video', 'render', 'audio'):
        try: lookup_group(group)
        except KeyError: raise ValueError(f'Required group missing: {group}')
    for name in DEPLOYMENTS:
        if exists(rooted(root, name)): raise ValueError(f'Existing deployment/data: {name}; migration is not supported')
    for base in SYSTEMD_DIRS:
        for name in (UNIT,) + COMPETITORS:
            if exists(rooted(root, base) / name) or exists(rooted(root, base) / (name + '.d')):
                raise ValueError(f'Existing service path: {base}/{name}')
    for name in (UNIT,) + COMPETITORS:
        props = dict(line.split('=', 1) for line in run(['systemctl', 'show', name, '--property=ActiveState,UnitFileState']).stdout.splitlines() if '=' in line)
        if props.get('ActiveState') not in ('inactive', 'failed') or props.get('UnitFileState', '') in ('enabled','enabled-runtime','linked','linked-runtime','alias'):
            raise ValueError(f'Active/enabled display owner: {name}')
    if set(run(['ps', '-eo', 'comm=']).stdout.split()) & {'mpv','vlc','labwc','wayfire','weston','sway','Xorg','Xwayland'}:
        raise ValueError('Competing display process running')
    manifest = json.loads((source / 'manifest.json').read_text())
    hashes = {row['file']: row['sha256'] for row in manifest}
    for name in PAYLOAD:
        path = source / 'candidate' / name
        if path.is_symlink() or not path.is_file() or hashes.get(name) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f'Missing/unsafe/hash-mismatched payload: {name}')
    return user


def config_text():
    return json.dumps({'media_dir': MEDIA, 'start':'00:00', 'end':'23:59', 'display':'HDMI-A-1', 'audio':True,
        'audio_device':'alsa/sysdefault:CARD=vc4hdmi0', 'retry_seconds':5, 'renderer':'drm-overlay',
        'drm_device':'/dev/dri/card1', 'drm_mode':'1920x1080@60', 'splash_seconds':3}, indent=2)+'\n'


def unit_text():
    return '''[Unit]\nDescription=caPIbarra Pi4 standalone DRM player\nAfter=systemd-user-sessions.service sound.target\nConflicts=labwc.service layar-gabungan.service layar1.service layar2.service getty@tty8.service\n\n[Service]\nType=simple\nUser=pi\nPAMName=login\nSupplementaryGroups=video render audio\nWorkingDirectory=/opt/pi5-signage\nEnvironment=XDG_RUNTIME_DIR=/run/user/1000\nStandardInput=tty-force\nTTYPath=/dev/tty8\nExecStartPre=+/usr/bin/chvt 8\nExecStartPre=-/opt/pi5-signage/splash.sh\nExecStart=/usr/bin/python3 /opt/pi5-signage/signage.py --config /etc/pi5-signage.json\nRestart=always\nRestartSec=5\nKillMode=control-group\n\n[Install]\nWantedBy=multi-user.target\n'''


def exclusive(path, data, mode=0o644):
    with path.open('xb') as stream: stream.write(data)
    path.chmod(mode)


def install(source=ROOT, root=Path('/')):
    if getattr(os, 'geteuid', lambda:-1)() != 0: raise ValueError('Install requires root')
    user = check(source, root)
    run(['apt-get','update']); run(['apt-get','install','-y','--no-install-recommends',*APT])
    run(['usermod','-aG','video,render,audio','pi'])
    app = rooted(root, APP); app.mkdir(parents=True, mode=0o755, exist_ok=False)
    media = rooted(root, MEDIA)
    media.parent.mkdir(parents=True, mode=0o755, exist_ok=False)
    media.mkdir(mode=0o755, exist_ok=False)
    os.chown(media.parent, user.pw_uid, user.pw_gid); os.chown(media, user.pw_uid, user.pw_gid)
    for name in PAYLOAD: exclusive(app/name, (source/'candidate'/name).read_bytes(), 0o755 if name == 'splash.sh' else 0o644)
    exclusive(app/'splash.ppm', b'P6\n1 1\n255\n\0\0\0')
    exclusive(rooted(root, CONFIG), config_text().encode())
    exclusive(rooted(root, '/etc/systemd/system')/UNIT, unit_text().encode())
    run(['systemctl','daemon-reload'])


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--check', action='store_true'); args=p.parse_args(argv)
    try:
        if args.check: check(); print('Fresh-install preflight passed; no changes made.')
        else: install(); print('Installed but not enabled or started. Hardware-accept direct DRM card1/HDMI-A-1 at 1080p60 before starting.')
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Fresh install refused/failed: {exc}', file=sys.stderr); return 1
if __name__ == '__main__': raise SystemExit(main())
