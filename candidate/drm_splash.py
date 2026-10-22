#!/usr/bin/env python3
"""Finite splash on the direct DRM drawing plane; failure is non-fatal."""
import argparse
from pathlib import Path
import subprocess
from signage import allowed_now, load_config


def splash_command(config):
    duration = max(1, min(int(config.get('splash_seconds', 3)), 5))
    return [
        'mpv', '--no-config', '--vo=gpu', '--gpu-context=drm',
        '--gpu-hwdec-interop=no', '--hwdec=no',
        '--drm-device='+config['drm_device'], '--drm-connector='+config['display'],
        '--drm-mode='+config['drm_mode'], '--drm-draw-plane=primary',
        '--image-display-duration='+str(duration), '--keep-open=no', '--no-audio',
        '--fullscreen', '--no-osc', '--osd-level=0', '--msg-level=all=warn',
        '--term-status-msg=', '--', '/opt/pi5-signage/splash.ppm'
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('/etc/pi5-signage.json'))
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if not allowed_now(config):
            print('DRM splash skipped: operation/schedule sleep', flush=True)
            return
        result = subprocess.run(splash_command(config), timeout=8, check=False)
        print('DRM splash finished; exit='+str(result.returncode), flush=True)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print('DRM splash non-fatal error: '+str(exc), flush=True)


if __name__ == '__main__':
    main()
