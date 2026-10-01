#!/bin/bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash install.sh" >&2
  exit 1
fi

src_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
for old_service in layar1.service layar2.service layar-gabungan.service; do
  if systemctl is-active --quiet "$old_service" || systemctl is-enabled --quiet "$old_service"; then
    echo "Disable the old player first: sudo systemctl disable --now $old_service" >&2
    exit 1
  fi
done

apt-get update
apt-get install -y --no-install-recommends python3 mpv labwc seatd

for group in video render audio; do
  getent group "$group" >/dev/null || { echo "Missing group: $group" >&2; exit 1; }
done

if ! id pi5-signage >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/pi5-signage --shell /usr/sbin/nologin --groups video,render,audio pi5-signage
fi
install -d -o pi5-signage -g pi5-signage -m 755 /var/lib/pi5-signage/videos
install -d -o root -g root -m 755 /opt/pi5-signage
install -o root -g root -m 755 "$src_dir/signage.py" /opt/pi5-signage/signage.py
install -o root -g root -m 755 "$src_dir/splash.py" /opt/pi5-signage/splash.py
install -o root -g root -m 755 "$src_dir/splash.sh" /opt/pi5-signage/splash.sh
python3 /opt/pi5-signage/splash.py --output /opt/pi5-signage/splash.ppm
install -o root -g root -m 644 "$src_dir/labwc.service" /etc/systemd/system/labwc.service
if [ ! -e /etc/pi5-signage.json ]; then
  install -o root -g root -m 644 "$src_dir/config.json" /etc/pi5-signage.json
fi
install -o root -g root -m 644 "$src_dir/pi5-signage.service" /etc/systemd/system/pi5-signage.service
systemctl daemon-reload
systemctl enable seatd.service labwc.service
systemctl enable pi5-signage.service
python3 /opt/pi5-signage/signage.py --config /etc/pi5-signage.json --check
echo "Installed. Add video files, then run: sudo systemctl start pi5-signage.service"
