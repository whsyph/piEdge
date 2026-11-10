#!/usr/bin/env bash
# Install (or update) the caPIbarra CMS next to the capibarra-lite player on a Raspberry Pi 5.
#
#   Fresh install : bash install-cms.sh --allow 192.168.8.0/24
#                   (asks for the CMS login password; or pipe it with --password-stdin)
#   Update code   : bash install-cms.sh --update        (keeps playlists, schedules, password, media)
#
# Run as the normal user `pi` (not root); it uses sudo for the system parts.
# Prerequisite: the player is already installed (sudo python3 install-fresh.py in the player repo),
# so /etc/pi5-signage.json exists. This script points the player at the CMS files.
set -Eeuo pipefail

APP_DIR="/home/pi/museum_signage"
VIDEO_ROOT="/home/pi/museum_video"
PLAYER_CONFIG="/etc/pi5-signage.json"
FIREWALL_FILE="/etc/capibarra-firewall.nft"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="fresh"
ALLOW=""
PASSWORD_STDIN=""
usage() {
  cat <<'EOF'
Usage: bash install-cms.sh --allow <IP-or-CIDR>[,<IP-or-CIDR>...]   fresh install
       bash install-cms.sh --update                                   update code only
  --password-stdin   read the CMS login password from the first line of stdin (non-interactive)
  --allow   who may open the CMS on port 8080 (everyone else is dropped), e.g. 192.168.8.0/24
            or 192.168.8.128,192.168.8.103
EOF
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) MODE="update"; shift ;;
    --password-stdin) PASSWORD_STDIN=1; shift ;;
    --allow) ALLOW="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

die() { echo "ERROR: $*" >&2; exit 1; }

[[ "$(id -u)" -ne 0 ]] || die "run as the normal user pi, not root (the script calls sudo itself)"
[[ "$(id -un)" == "pi" ]] || die "this layout expects the user 'pi' (found $(id -un))"
for f in server.py cms_auth.py media_check.py cms-signage.service public/index.html public/app.js; do
  [[ -e "$SRC/$f" ]] || die "missing $f; run this from the CMS repository (branch claude/cms-hardening)"
done
command -v python3 >/dev/null || die "python3 not found"
python3 - <<'PY' || die "python 3.9+ with zoneinfo and timezone data is required"
import sys
from zoneinfo import ZoneInfo
assert sys.version_info >= (3, 9)
ZoneInfo("Asia/Jakarta")
PY
[[ -f "$PLAYER_CONFIG" ]] || die "$PLAYER_CONFIG not found: install the player first (sudo python3 install-fresh.py)"

if [[ "$MODE" == "fresh" ]]; then
  [[ -n "$ALLOW" ]] || { usage >&2; die "--allow is required for a fresh install"; }
  [[ "$ALLOW" =~ ^[0-9./,]+$ ]] || die "--allow must be IPs or CIDRs separated by commas, got '$ALLOW'"
  [[ ! -e "$APP_DIR/server.py" ]] || die "$APP_DIR already has a CMS. Use --update to refresh the code and keep the data."
else
  [[ -e "$APP_DIR/server.py" ]] || die "no CMS at $APP_DIR; do a fresh install instead"
fi

echo "== Copying CMS code to $APP_DIR ($MODE)"
install -d -m 0755 "$APP_DIR" "$APP_DIR/public"
install -d -m 0755 "$VIDEO_ROOT" "$VIDEO_ROOT/media" "$VIDEO_ROOT/layar1" "$VIDEO_ROOT/layar2"
if [[ "$MODE" == "update" ]]; then
  cp -a "$APP_DIR" "$HOME/museum_signage_backup_$(date +%Y%m%d-%H%M%S)"
fi
install -m 0644 "$SRC/server.py" "$SRC/cms_auth.py" "$SRC/media_check.py" "$APP_DIR/"
for f in app.js app.css index.html operation-ui.js logo.png placeholder.jpg; do
  if [[ -e "$SRC/public/$f" ]]; then
    install -m 0644 "$SRC/public/$f" "$APP_DIR/public/$f"
  fi
done
if [[ "$MODE" == "fresh" ]]; then
  # Default data files only on a fresh install; never overwrite an operator's playlists or schedules.
  # schedules.json is left out on purpose: the server writes an always-on schedule in the Pi's own timezone.
  for f in playlists.json devices.json network_config.json; do
    if [[ -e "$SRC/public/$f" && ! -e "$APP_DIR/public/$f" ]]; then
      install -m 0644 "$SRC/public/$f" "$APP_DIR/public/$f"
    fi
  done
fi

echo "== Pointing the player at the CMS files"
sudo python3 - "$PLAYER_CONFIG" "$APP_DIR" "$VIDEO_ROOT" <<'PY'
import json, shutil, sys, time
path, app, videos = sys.argv[1:4]
with open(path, encoding="utf-8") as f:
    config = json.load(f)
wanted = {
    "media_dir": f"{videos}/media",
    "playlist_file": f"{app}/public/playlists.json",
    "playlist_screen": "screen1",
    "schedules_file": f"{app}/public/schedules.json",
}
if all(config.get(k) == v for k, v in wanted.items()):
    print("player config already points at the CMS")
else:
    shutil.copy2(path, f"{path}.bak-{int(time.time())}")
    config.update(wanted)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    print("player config updated (backup kept)")
PY

echo "== Installing the CMS service"
sudo install -m 0644 "$SRC/cms-signage.service" /etc/systemd/system/cms-signage.service

if [[ "$MODE" == "fresh" ]]; then
  echo "== Installing the port 8080 allow-list ($ALLOW)"
  command -v nft >/dev/null || sudo apt-get install -y nftables
  TMP="$(mktemp)"
  SET="${ALLOW//,/, }"
  cat >"$TMP" <<EOF
# caPIbarra CMS: port 8080 hanya untuk IP operator dan localhost. Port lain tidak disentuh.
table inet capibarra_cms
delete table inet capibarra_cms
table inet capibarra_cms {
  chain input {
    type filter hook input priority -10; policy accept;
    iifname "lo" tcp dport 8080 accept
    ip saddr { $SET } tcp dport 8080 accept
    tcp dport 8080 drop
  }
}
EOF
  sudo nft -c -f "$TMP" || { rm -f "$TMP"; die "firewall rules did not validate; nothing was changed"; }
  sudo install -m 0644 "$TMP" "$FIREWALL_FILE"
  rm -f "$TMP"
  sudo tee /etc/systemd/system/capibarra-firewall.service >/dev/null <<'EOF'
[Unit]
Description=caPIbarra CMS port 8080 allow-list
Before=network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/capibarra-firewall.nft
ExecStop=/usr/sbin/nft delete table inet capibarra_cms

[Install]
WantedBy=multi-user.target
EOF
fi

sudo systemctl daemon-reload
if [[ "$MODE" == "fresh" ]]; then
  sudo systemctl enable --now capibarra-firewall.service
  sudo systemctl enable cms-signage.service
fi
sudo systemctl restart cms-signage.service

if [[ "$MODE" == "fresh" && ! -e "$APP_DIR/.cms_password" ]]; then
  echo "== CMS login password"
  PW=""
  if [[ -n "$PASSWORD_STDIN" ]]; then
    IFS= read -r PW || true
  elif [[ -t 0 ]]; then
    while true; do
      read -r -s -p "Password baru CMS (min. 6 karakter): " PW; echo
      read -r -s -p "Ulangi password: " PW2; echo
      if [[ "$PW" != "$PW2" ]]; then echo "Password tidak sama, ulangi."; continue; fi
      if [[ ${#PW} -lt 6 ]]; then echo "Minimal 6 karakter, ulangi."; continue; fi
      break
    done
  fi
  if [[ -n "$PW" ]]; then
    (cd "$APP_DIR" && printf '%s\n' "$PW" | python3 server.py --set-password --stdin) \
      || echo "WARNING: password not saved; set it later with: cd $APP_DIR && python3 server.py --set-password"
  else
    echo "Tidak ada password diberikan: CMS dapat dimasuki dengan token akses ($APP_DIR/.cms_token) sampai password diatur:"
    echo "  cd $APP_DIR && python3 server.py --set-password"
  fi
  unset PW PW2
fi

echo "== Checking"
ok=""
for _ in $(seq 1 20); do
  if curl -fsS -o /dev/null http://127.0.0.1:8080/; then ok=1; break; fi
  sleep 1
done
[[ -n "$ok" ]] || { sudo journalctl -u cms-signage -n 20 --no-pager; die "the CMS did not answer on port 8080"; }
code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/status)"
[[ "$code" == "401" ]] || echo "WARNING: /api/status answered $code without a token (expected 401)"
sudo systemctl try-restart pi5-signage.service 2>/dev/null || true   # only if the player is already running; never start a disabled one

IP="$(hostname -I | awk '{print $1}')"
cat <<EOF

CMS terpasang.
  Buka      : http://${IP}:8080/
  Login     : password yang kamu atur tadi (ganti di UI: Konfigurasi > Password)
  Lupa pw   : cd $APP_DIR && python3 server.py --set-password
  Cadangan  : token akses di $APP_DIR/.cms_token (hanya untuk skrip dan pemulihan)
  Jadwal    : tab Penjadwalan (default: selalu menyala)
  Update    : cd $SRC && git pull && bash install-cms.sh --update
EOF
