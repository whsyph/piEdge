#!/bin/bash
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/1000
export XDG_SESSION_TYPE=wayland
export WAYLAND_DISPLAY=wayland-0
# Splash must never block the signage supervisor: wlshm is reliable for PPM images.
# Keep the same 5s timeout contract but treat any mpv init failure as non-fatal.
set +e
# Skip the splash when it already ran in the last 2 minutes (crash-restart loop);
# the marker lives on tmpfs, so a reboot always shows it again.
marker=/run/user/1000/capibarra-splash-done
if [ -n "$(find "$marker" -mmin -2 2>/dev/null)" ]; then exit 0; fi
touch "$marker" 2>/dev/null
timeout --signal=TERM --kill-after=2s 5s mpv --vo=wlshm --fullscreen --fs-screen=0 --no-audio --osd-level=0 --no-osc --keep-open=no /opt/pi5-signage/splash.ppm >/dev/null 2>&1
status=$?
# 124 = timeout completed the 5s display, 0 = immediate success, other = init/format failure -> still hand over to signage
exit 0
