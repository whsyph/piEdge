#!/bin/bash
set -euo pipefail
# Semua pemeriksaan dilakukan sebelum perubahan sistem.
[ "$#" -eq 0 ] || { echo "Tidak ada opsi; migrasikan config lama secara eksplisit sebelum instalasi." >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { echo "Jalankan dengan sudo" >&2; exit 1; }
src_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$src_dir/scripts/preflight.py" "$src_dir"
for old_service in layar1.service layar2.service layar-gabungan.service pi5-signage.service; do
  if systemctl is-active --quiet "$old_service"; then
    echo "Hentikan $old_service sendiri dalam maintenance window; installer tidak restart playback." >&2; exit 1
  fi
  if [[ "$old_service" != pi5-signage.service ]] && systemctl is-enabled --quiet "$old_service"; then
    echo "Nonaktifkan $old_service dahulu." >&2; exit 1
  fi
done
[ "$(id -u pi)" -eq 1000 ] || { echo "Unit mengharuskan pi UID 1000" >&2; exit 1; }
for group in video render audio; do getent group "$group" >/dev/null || exit 1; done
# Backup sebelum apt atau penulisan file. Lokasi dicetak untuk rollback manual.
backup="/var/backups/pi5-signage/$(date +%Y%m%dT%H%M%S)-$$"
install -d -m 700 "$backup"
for item in /opt/pi5-signage /etc/pi5-signage.json /etc/systemd/system/pi5-signage.service /etc/systemd/system/labwc.service; do
  if [ -e "$item" ]; then cp -a --parents "$item" "$backup/"; fi
done
echo "Backup: $backup"
apt-get update
apt-get install -y --no-install-recommends python3 mpv labwc seatd wlr-randr
release_target=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["target"])' "$src_dir/release.json")
install -d -m 755 /opt/pi5-signage/profiles /var/lib/pi5-signage/videos
for file in signage.py splash.py splash.sh; do install -m 755 "$src_dir/$file" "/opt/pi5-signage/$file"; done
install -m 644 "$src_dir/profiles/$release_target.json" "/opt/pi5-signage/profiles/$release_target.json"
python3 /opt/pi5-signage/splash.py --output /opt/pi5-signage/splash.ppm
if [ ! -e /etc/pi5-signage.json ]; then install -m 644 "$src_dir/config.$release_target.json" /etc/pi5-signage.json; fi
# Tidak menimpa unit compositor milik operator.
if [ ! -e /etc/systemd/system/labwc.service ]; then install -m 644 "$src_dir/labwc.service" /etc/systemd/system/labwc.service; fi
install -m 644 "$src_dir/pi5-signage.service" /etc/systemd/system/pi5-signage.service
systemctl daemon-reload
systemctl enable seatd.service labwc.service pi5-signage.service
echo "Terpasang; tidak dimulai. Tinjau config/media lalu sudo systemctl start pi5-signage.service"
