#!/usr/bin/env bash
set -Eeuo pipefail

# Raspberry Pi 5 signage player profile.
# Uses the Bookworm Wayland/DRM stack and mpv's automatic hardware decoder.
# Keep this separate from start_players.sh so the existing Pi 4 deployment remains intact.

APP_DIR="/home/pi/museum_signage"
VIDEO_ROOT="/home/pi/museum_video"
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
WAYLAND_DISPLAY_NAME="${WAYLAND_DISPLAY:-wayland-0}"
SOCK_1="/tmp/mpv-layar1.sock"
SOCK_2="/tmp/mpv-layar2.sock"
MODE_FILE="$APP_DIR/public/output_mode.json"

export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export WAYLAND_DISPLAY="$WAYLAND_DISPLAY_NAME"

command -v mpv >/dev/null || { echo "mpv tidak ditemukan" >&2; exit 1; }

# Do not leave stale players or IPC sockets after a service restart.
pkill -f 'mpv.*--title=layar[12]' 2>/dev/null || true
rm -f "$SOCK_1" "$SOCK_2"

mode="dual"
if [[ -f "$MODE_FILE" ]]; then
  mode="$(python3 - "$MODE_FILE" <<'PY'
import json, sys
try:
    value = json.load(open(sys.argv[1], encoding='utf-8')).get('mode', 'dual')
    print(value if value in {'single', 'dual'} else 'dual')
except Exception:
    print('dual')
PY
)"
fi

common_args=(
  --vo=dmabuf-wayland
  --hwdec=auto-safe
  --hwdec-codecs=hevc,h264,vp9,av1
  --hwdec-extra-frames=auto
  --video-sync=audio
  --framedrop=vo
  --loop-playlist=inf
  --no-osc
  --osd-level=0
  --no-border
  --no-input-default-bindings
  --no-deinterlace
  --keep-open=no
)

start_player() {
  local screen="$1" output="$2" socket="$3" playlist="$4"
  mkdir -p "$(dirname "$playlist")"
  touch "$playlist"
  mpv "${common_args[@]}" \
    --input-ipc-server="$socket" \
    --playlist="$playlist" \
    --fs \
    --fs-screen="$output" \
    --title="layar${screen}" \
    --wayland-app-id="layar${screen}" \
    --mute=yes &
}

if [[ "$mode" == "single" ]]; then
  start_player 1 0 "$SOCK_1" "$VIDEO_ROOT/layar1/playlist.txt"
else
  start_player 1 0 "$SOCK_1" "$VIDEO_ROOT/layar1/playlist.txt"
  start_player 2 1 "$SOCK_2" "$VIDEO_ROOT/layar2/playlist.txt"
fi

# If either player exits, systemd restarts the complete pair.
wait -n
exit 1
