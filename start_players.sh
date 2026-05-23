#!/bin/bash
# Script to launch dual MPV players side-by-side on a combined widescreen layout (2160x1080)
# Managed by labwc window rules for precise coordinates.

export XDG_RUNTIME_DIR=/run/user/1000
export WAYLAND_DISPLAY=wayland-0

# Terminate any existing mpv instances to avoid conflicts
pkill -f "mpv.*layar"

/usr/bin/mpv \
  --vo=dmabuf-wayland \
  --hwdec=v4l2m2m \
  --loop-playlist=inf \
  --mute=yes \
  --script-opts=screen=1 \
  --script=/home/pi/museum_signage/audio_sync.lua \
  --no-deinterlace \
  --input-ipc-server=/tmp/mpv-layar1.sock \
  --playlist=/home/pi/museum_video/layar1/playlist.txt \
  --fs \
  --fs-screen=1 \
  --title="layar1" \
  --wayland-app-id="layar1" &

/usr/bin/mpv \
  --vo=dmabuf-wayland \
  --hwdec=v4l2m2m \
  --loop-playlist=inf \
  --mute=yes \
  --script-opts=screen=2 \
  --script=/home/pi/museum_signage/audio_sync.lua \
  --no-deinterlace \
  --input-ipc-server=/tmp/mpv-layar2.sock \
  --playlist=/home/pi/museum_video/layar2/playlist.txt \
  --fs \
  --fs-screen=0 \
  --title="layar2" \
  --wayland-app-id="layar2" &

# Keep the script running to maintain the systemd service state
wait -n
pkill -P $$ # Terminate sibling players if one dies to trigger a clean service restart
