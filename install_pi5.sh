#!/usr/bin/env bash
set -Eeuo pipefail

# Install piEdge's Raspberry Pi 5 player profile on Raspberry Pi OS Bookworm.
# Run from the project directory: sudo bash install_pi5.sh

APP_DIR="/home/pi/museum_signage"
VIDEO_ROOT="/home/pi/museum_video"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Jalankan dengan sudo: sudo bash install_pi5.sh" >&2
  exit 1
fi

install -d -o pi -g pi "$APP_DIR" "$VIDEO_ROOT/layar1" "$VIDEO_ROOT/layar2" "$VIDEO_ROOT/media"
cp -a . "$APP_DIR/"
chown -R pi:pi "$APP_DIR" "$VIDEO_ROOT"
chmod +x "$APP_DIR/start_players_pi5.sh" "$APP_DIR/validate_media.sh"

apt-get update
apt-get install -y python3 mpv labwc ffmpeg

install -m 0644 pi5-signage.service /etc/systemd/system/pi5-signage.service
install -m 0644 cms-signage.service /etc/systemd/system/cms-signage.service
systemctl daemon-reload
systemctl enable cms-signage.service pi5-signage.service
systemctl restart cms-signage.service pi5-signage.service

cat <<'EOF'
Pi 5 profile terpasang.
CMS:    http://<IP-PI>:8080
Status: systemctl status cms-signage pi5-signage
Logs:   journalctl -u pi5-signage -f
EOF
