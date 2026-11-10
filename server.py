import hmac
import os
import re
import secrets
import sys
import json
import socket
import subprocess
import shutil
import tempfile
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time
import threading
from datetime import datetime, time as clock_time, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from media_check import ALLOWED_EXTENSIONS, check_upload, validate_upload_name

# Directory settings
if os.path.exists("/home/pi"):
    VIDEO_DIR_1 = "/home/pi/museum_video/layar1"
    VIDEO_DIR_2 = "/home/pi/museum_video/layar2"
    MEDIA_DIR = "/home/pi/museum_video/media"
    SOCK_1 = "/run/user/1000/capibarra-mpv.sock"
    SOCK_2 = "/tmp/mpv-layar2.sock"
    IS_PI = True
else:
    # Local Windows fallback for testing
    VIDEO_DIR_1 = os.path.join(os.getcwd(), "mock_museum_video", "layar1")
    VIDEO_DIR_2 = os.path.join(os.getcwd(), "mock_museum_video", "layar2")
    MEDIA_DIR = os.path.join(os.getcwd(), "mock_museum_video", "media")
    SOCK_1 = "\\\\.\\pipe\\mpv-layar1"  # Named pipe or mocked socket
    SOCK_2 = "\\\\.\\pipe\\mpv-layar2"
    IS_PI = False

SCHEDULES_FILE = os.path.join(os.path.dirname(__file__), "public", "schedules.json")
PLAYLISTS_FILE = os.path.join(os.path.dirname(__file__), "public", "playlists.json")
NETWORK_CONFIG_FILE = os.path.join(
    os.path.dirname(__file__), "public", "network_config.json"
)
OUTPUT_MODE_FILE = os.path.join(
    os.path.dirname(__file__), "public", "output_mode.json"
)
PLAYER_SERVICE = "pi5-signage.service"

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(APP_DIR, "public")
CONFIG_FILE = os.path.join(APP_DIR, "cms_config.json")
TOKEN_FILE = os.path.join(APP_DIR, ".cms_token")

# Operator-tunable settings (cms_config.json next to server.py; every key optional).
DEFAULT_CONFIG = {
    # Extra browser origins allowed to call this API (fleet dashboards on another
    # host), e.g. ["http://192.168.8.10:8080"]. The page's own origin is always allowed.
    "allowed_origins": [],
    # Require "Authorization: Bearer <token>" on every /api request.
    "require_auth": True,
    # Legacy layar1/layar2 players use playlist.txt + mpv "loadlist"; the Pi 5
    # supervisor reads playlists.json itself and must NOT be driven that way.
    "legacy_players": False,
    # Upload limits: biggest accepted file and free space that must remain afterwards.
    "max_upload_mb": 8192,
    "min_free_mb": 1024,
    # Video codecs the player can render (Pi 5 has hardware decode for HEVC only).
    "allowed_codecs": ["hevc"],
}
CONFIG = dict(DEFAULT_CONFIG)
TOKEN = ""
JSON_LOCK = threading.RLock()  # serialises read-modify-write of the shared JSON files
# Only these suffixes are served from public/; the *.json data files are API-only.
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}
STATIC_JSON_ALLOWED = {"devices.json"}  # the only data file the front end reads directly


def load_config():
    """Merge cms_config.json over the defaults; bad values fall back to defaults."""
    global CONFIG
    merged = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user = json.load(f)
        if isinstance(user, dict):
            for key, default in DEFAULT_CONFIG.items():
                if key in user and isinstance(user[key], type(default)) and not (
                    isinstance(default, int) and isinstance(user[key], bool) and not isinstance(default, bool)
                ):
                    merged[key] = user[key]
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        print(f"[Config] Ignoring unreadable {CONFIG_FILE}: {exc}")
    CONFIG = merged
    return CONFIG


def ensure_token():
    """Create the API access token on first start (file mode 0600) and load it."""
    global TOKEN
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            existing = f.read().strip()
        if len(existing) >= 16:
            TOKEN = existing
            return TOKEN
    except OSError:
        pass
    TOKEN = secrets.token_urlsafe(24)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(TOKEN + "\n")
    print(f"[Auth] New access token written to {TOKEN_FILE} (read it with: cat {TOKEN_FILE})")
    return TOKEN


def write_json_atomic(path, data):
    """Write JSON so concurrent readers (the player polls these files) never see a partial file."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


NO_CHANGE = object()  # return from a mutate() callback to skip the write


def update_json(path, mutate, default=None):
    """Locked read-modify-write: mutate(data) edits in place, returns a replacement,
    or returns NO_CHANGE to leave the file untouched."""
    with JSON_LOCK:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            if default is None:
                raise
            data = default() if callable(default) else default
        result = mutate(data)
        if result is NO_CHANGE:
            return data
        if result is not None:
            data = result
        write_json_atomic(path, data)
        return data


def ensure_dirs():
    for directory in (VIDEO_DIR_1, VIDEO_DIR_2, MEDIA_DIR):
        os.makedirs(directory, exist_ok=True)


def init_json_files():
    if not os.path.exists(SCHEDULES_FILE):
        default_schedules = {"timezone": read_device_timezone(), "events": [],
                             "windows": [{"days": list(DAYS), "start": "00:00", "end": "24:00"}]}
        write_json_atomic(SCHEDULES_FILE, default_schedules)

    if not os.path.exists(PLAYLISTS_FILE):
        default_playlists = {
            "playlists": {"Default": []},
            "assignments": {"screen1": "Default", "screen2": "Default"},
        }
        write_json_atomic(PLAYLISTS_FILE, default_playlists)
    else:
        try:
            with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "playlists" not in data or "assignments" not in data:
                migrated = {
                    "playlists": {},
                    "assignments": {"screen1": "Default", "screen2": "Default"},
                }
                if "screen1" in data:
                    for k, v in data["screen1"].items():
                        migrated["playlists"][
                            f"{k}_Screen1" if k == "Default" else k
                        ] = v
                        if k == "Default":
                            migrated["assignments"]["screen1"] = "Default_Screen1"
                if "screen2" in data:
                    for k, v in data["screen2"].items():
                        migrated["playlists"][
                            f"{k}_Screen2" if k == "Default" else k
                        ] = v
                        if k == "Default":
                            migrated["assignments"]["screen2"] = "Default_Screen2"
                if not migrated["playlists"]:
                    migrated["playlists"]["Default"] = []
                write_json_atomic(PLAYLISTS_FILE, migrated)
        except Exception as e:
            print(f"[Playlist Migration] Error: {e}")

    if not os.path.exists(NETWORK_CONFIG_FILE):
        write_json_atomic(NETWORK_CONFIG_FILE, {"selected": "eth"})

    if not os.path.exists(OUTPUT_MODE_FILE):
        write_json_atomic(OUTPUT_MODE_FILE, {"mode": "dual"})


def get_network_interfaces():
    if not IS_PI:
        return ["eth0"], ["wlan0"]
    try:
        interfaces = os.listdir("/sys/class/net/")
        eth_list = [i for i in interfaces if i.startswith(("eth", "en"))]
        wlan_list = [i for i in interfaces if i.startswith(("wlan", "wl"))]
        return eth_list, wlan_list
    except Exception:
        return [], []


def get_interface_ip(ifname):
    if not IS_PI:
        return "192.168.88.46" if "eth" in ifname else "192.168.88.100"
    try:
        res = subprocess.run(
            ["ip", "addr", "show", ifname], capture_output=True, text=True
        )
        for line in res.stdout.split("\n"):
            line = line.strip()
            if line.startswith("inet "):
                return line.split()[1].split("/")[0]
    except Exception:
        pass
    return None


def get_interface_status(ifname):
    ip = get_interface_ip(ifname)
    operstate = "down"
    if IS_PI:
        try:
            with open(f"/sys/class/net/{ifname}/operstate", "r") as f:
                operstate = f.read().strip()
        except Exception:
            pass
    else:
        operstate = "up"
    return {"name": ifname, "ip": ip if ip else "Not Connected", "status": operstate}


def apply_network_config():
    if not os.path.exists(NETWORK_CONFIG_FILE):
        return
    try:
        with open(NETWORK_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        selected = config.get("selected", "eth")

        eth_ifs, wlan_ifs = get_network_interfaces()

        if not IS_PI:
            print(
                f"[Network Mock] Applying {selected}: eth_ifs={eth_ifs}, wlan_ifs={wlan_ifs}"
            )
            return

        if selected == "eth":
            for eth in eth_ifs:
                subprocess.run(["sudo", "-n", "ip", "link", "set", "dev", eth, "up"], timeout=10)

        elif selected == "wlan":
            for wl in wlan_ifs:
                subprocess.run(["sudo", "-n", "ip", "link", "set", "dev", wl, "up"], timeout=10)

    except Exception as e:
        print(f"[Network] Error applying network config: {e}")


def migrate_existing_files():
    try:
        for source_dir in [VIDEO_DIR_1, VIDEO_DIR_2]:
            if os.path.exists(source_dir):
                for f in os.listdir(source_dir):
                    if (
                        f.lower().endswith((".mp4", ".mkv", ".avi", ".mov", ".webm"))
                        and f != "playlist.txt"
                    ):
                        src_path = os.path.join(source_dir, f)
                        dst_path = os.path.join(MEDIA_DIR, f)
                        if not os.path.exists(dst_path):
                            shutil.copy2(src_path, dst_path)
    except Exception as e:
        print(f"[Migration] Error migrating files: {e}")


def apply_playlist_assignments():
    """Legacy layar1/layar2 players only: write playlist.txt and tell mpv to loadlist.

    The Pi 5 supervisor reads playlists.json itself, and pushing "loadlist" into its
    mpv replaces what the supervisor is playing, so this is a no-op unless the
    operator enabled "legacy_players" in cms_config.json.
    """
    if not CONFIG.get("legacy_players"):
        return
    try:
        if not os.path.exists(PLAYLISTS_FILE):
            return
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        playlists = data.get("playlists", {})
        assignments = data.get("assignments", {})

        for screen_name, pl_name in assignments.items():
            screen_num = 1 if screen_name == "screen1" else 2
            files = playlists.get(pl_name, [])

            upload_dir = VIDEO_DIR_1 if screen_num == 1 else VIDEO_DIR_2
            playlist_path = os.path.join(upload_dir, "playlist.txt")

            with open(playlist_path, "w", encoding="utf-8") as pt:
                for fname in files:
                    f_path = os.path.join(MEDIA_DIR, fname)
                    if os.path.exists(f_path):
                        pt.write(f_path + "\n")

            # Apply to MPV if running
            sock_path = SOCK_1 if screen_num == 1 else SOCK_2
            if IS_PI and os.path.exists(sock_path):
                send_mpv_command(sock_path, ["loadlist", playlist_path])
    except Exception as e:
        print(f"[Assignments] Error applying playlist assignments: {e}")


# Generate default playlist if it doesn't exist
def init_playlist_file(video_dir):
    if not CONFIG.get("legacy_players"):
        return
    playlist_path = os.path.join(video_dir, "playlist.txt")
    if not os.path.exists(playlist_path):
        update_playlist_file(video_dir)


def update_playlist_file(video_dir):
    playlist_path = os.path.join(video_dir, "playlist.txt")
    # List all MP4 and common video files, excluding playlist.txt itself
    valid_exts = (".mp4", ".mkv", ".avi", ".mov", ".webm")
    files = [f for f in os.listdir(video_dir) if f.lower().endswith(valid_exts)]
    files.sort()  # Alphabetical by default

    with open(playlist_path, "w", encoding="utf-8") as pf:
        for f in files:
            # mpv requires absolute paths or paths relative to execution
            pf.write(os.path.join(video_dir, f) + "\n")
    return files


# --- MPV IPC helpers ---
def send_mpv_command(sock_path, command_args):
    """Read the matching IPC reply, ignoring asynchronous mpv events."""
    if not IS_PI:
        return {"error": "Player IPC unavailable on this platform"}
    try:
        request_id = time.monotonic_ns()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1.0)
            client.connect(sock_path)
            client.sendall((json.dumps({"command": command_args, "request_id": request_id}) + "\n").encode())
            pending = b""
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                chunk = client.recv(4096)
                if not chunk:
                    break
                pending += chunk
                if len(pending) > 1048576:
                    return {"error": "IPC response too large"}
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    message = json.loads(line)
                    if message.get("request_id") == request_id:
                        return message
        return {"error": "No matching IPC response"}
    except (OSError, ValueError, TypeError) as exc:
        return {"error": str(exc)}


# --- Background Schedule Worker ---
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


_CLOCK_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def validate_schedules(data):
    """Raise ValueError unless data is a schedules.json the player and scheduler can follow."""
    if not isinstance(data, dict):
        raise ValueError("schedules must be a JSON object")
    offset = data.get("timezone_offset", 7)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) or not -12 <= offset <= 14:
        raise ValueError("timezone_offset must be a number between -12 and 14")
    events = data.get("events", [])
    if not isinstance(events, list) or len(events) > 500:
        raise ValueError("events must be a list (max 500)")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("each event must be an object")
        if event.get("type") not in ("power", "playlist"):
            raise ValueError("event type must be power or playlist")
        if not isinstance(event.get("time"), str) or not _CLOCK_RE.match(event["time"]):
            raise ValueError("event time must be HH:MM")
        days = event.get("days")
        if not isinstance(days, list) or not days or any(d not in DAYS for d in days):
            raise ValueError("event days must be a non-empty list of Mon..Sun")
        if event["type"] == "power" and event.get("action") not in ("sleep", "wake"):
            raise ValueError("power event action must be sleep or wake")
    if "timezone" in data:
        load_zone(data["timezone"])
    if "windows" in data:
        parse_windows(data)


# --- Playback windows (same rules as the player's signage.py) ---
# A window belongs to the day it STARTS on and may run past midnight; a day with no window is off.
DAY_INDEX = {name: index for index, name in enumerate(DAYS)}
DEFAULT_TIMEZONE = "Asia/Jakarta"
OFFSET_ZONES = {7: "Asia/Jakarta", 8: "Asia/Makassar", 9: "Asia/Jayapura", 0: "UTC"}


def load_zone(name):
    if not isinstance(name, str) or not name:
        raise ValueError("timezone must be an IANA name such as Asia/Jakarta")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(f"unknown timezone {name!r}") from None


def zone_for_offset(offset):
    """Name of an IANA zone for a legacy whole-hour offset (UTC+7 -> Asia/Jakarta)."""
    try:
        hours = int(offset)
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_TIMEZONE
    if hours in OFFSET_ZONES:
        return OFFSET_ZONES[hours]
    return f"Etc/GMT{-hours:+d}" if -12 <= hours <= 14 else DEFAULT_TIMEZONE


def read_device_timezone():
    try:
        with open("/etc/timezone", "r", encoding="utf-8") as f:
            name = f.read().strip()
        load_zone(name)
        return name
    except (OSError, ValueError):
        return DEFAULT_TIMEZONE


def _window_minutes(text, allow_24=False):
    if allow_24 and text == "24:00":
        return 1440
    if not isinstance(text, str) or not _CLOCK_RE.match(text):
        raise ValueError(f"invalid time {text!r}; use HH:MM")
    return int(text[:2]) * 60 + int(text[3:])


def parse_windows(data):
    """Validate {'timezone', 'windows'}; returns (tzinfo or None, [(weekday indexes, start, duration)])."""
    tz = load_zone(data["timezone"]) if data.get("timezone") is not None else None
    raw = data.get("windows")
    if not isinstance(raw, list) or not raw or len(raw) > 200:
        raise ValueError("windows must be a non-empty list (max 200); a screen that is never on needs no schedule")
    windows, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each window must be an object with days, start, end")
        days = item.get("days")
        if not isinstance(days, list) or not days or any(d not in DAY_INDEX for d in days):
            raise ValueError("window days must be a non-empty list of Mon..Sun")
        start, end = _window_minutes(item.get("start")), _window_minutes(item.get("end"), allow_24=True)
        if start == end:
            raise ValueError("a window cannot start and end at the same time; use 00:00-24:00 for a full day")
        indexes = frozenset(DAY_INDEX[d] for d in days)
        if indexes & seen:
            raise ValueError("each day can have only one window")
        seen |= indexes
        windows.append((indexes, start, end - start if end > start else end + 1440 - start))
    return tz, windows


def _window_allowed(windows, tz, at):
    for back in (0, 1):
        day = at.date() - timedelta(days=back)
        for weekdays, start, duration in windows:
            if day.weekday() in weekdays:
                begin = datetime.combine(day, clock_time(0), tzinfo=tz) + timedelta(minutes=start)
                if begin <= at < begin + timedelta(minutes=duration):
                    return True
    return False


def schedule_state(data, now=None):
    """Is the display meant to be on right now, and when does that change next?"""
    now = now or datetime.now(timezone.utc)
    if "windows" not in data:
        return {"timezone": None, "now": None, "on": True, "next_change": None, "always": True}
    tz, windows = parse_windows(data)
    tz = tz or load_zone(read_device_timezone())
    local = now.astimezone(tz)
    on = _window_allowed(windows, tz, local)
    edges = []
    for offset in range(-1, 9):
        day = local.date() + timedelta(days=offset)
        for weekdays, start, duration in windows:
            if day.weekday() in weekdays:
                begin = datetime.combine(day, clock_time(0), tzinfo=tz) + timedelta(minutes=start)
                edges += [begin, begin + timedelta(minutes=duration)]
    next_change = None
    for edge in sorted(set(edges)):
        if edge > local and _window_allowed(windows, tz, edge) != on:
            next_change = {"day": DAYS[edge.weekday()], "time": edge.strftime("%H:%M"),
                           "date": edge.strftime("%Y-%m-%d")}
            break
    full = len(windows) and all(len(w[0]) == 7 and w[1] == 0 and w[2] == 1440 for w in windows)
    return {"timezone": str(getattr(tz, "key", tz)), "now": local.strftime("%Y-%m-%d %H:%M"), "day": DAYS[local.weekday()],
            "on": on, "next_change": next_change, "always": bool(full)}


def migrate_schedules(data):
    """Convert wake/sleep power events and timezone_offset to windows + timezone.

    Returns the new schedules dict, or None when the file is already in the window format.
    """
    events = data.get("events", []) if isinstance(data.get("events"), list) else []
    power = [e for e in events if isinstance(e, dict) and e.get("type") == "power"]
    if "windows" in data and not power and "timezone_offset" not in data:
        return None
    result = {k: v for k, v in data.items() if k not in ("timezone_offset", "events")}
    result["events"] = [e for e in events if e not in power]
    result["timezone"] = data.get("timezone") or zone_for_offset(data.get("timezone_offset", 7))
    if "windows" not in data:
        by_span = {}
        for day in DAYS:
            wake = sleep = None
            for event in power:
                if not event.get("enabled", True) or day not in (event.get("days") or []):
                    continue
                if not isinstance(event.get("time"), str) or not _CLOCK_RE.match(event["time"]):
                    continue
                if event.get("action") == "wake":
                    wake = event["time"] if wake is None or event["time"] < wake else wake
                elif event.get("action") == "sleep":
                    sleep = event["time"] if sleep is None or event["time"] > sleep else sleep
            start, end = wake or "00:00", sleep or "24:00"
            if start == end:
                start, end = "00:00", "24:00"
            by_span.setdefault((start, end), []).append(day)
        result["windows"] = [{"days": days, "start": s, "end": e} for (s, e), days in by_span.items()]
    return result


def validate_playlists(data):
    """Raise ValueError unless data is a playlists.json the player can follow."""
    if not isinstance(data, dict):
        raise ValueError("playlists must be a JSON object")
    playlists, assignments = data.get("playlists"), data.get("assignments")
    if not isinstance(playlists, dict) or not playlists or len(playlists) > 200:
        raise ValueError("playlists must be a non-empty object (max 200)")
    if not isinstance(assignments, dict):
        raise ValueError("assignments must be an object")
    for name, files in playlists.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("playlist names must be 1-100 characters")
        if not isinstance(files, list) or len(files) > 1000:
            raise ValueError(f'playlist "{name}" must be a list (max 1000 items)')
        for item in files:
            if not isinstance(item, str) or not item or os.path.basename(item) != item or item.startswith("."):
                raise ValueError(f'playlist "{name}" has an invalid file name')
    for screen, name in assignments.items():
        if screen not in ("screen1", "screen2") or name not in playlists:
            raise ValueError("assignments must map screen1/screen2 to an existing playlist")


def assigned_playlist(screen):
    """File names of the playlist assigned to a screen in playlists.json ([] if unreadable)."""
    try:
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("assignments", {}).get(f"screen{screen}")
        files = data.get("playlists", {}).get(name, [])
        return [x for x in files if isinstance(x, str)]
    except (OSError, ValueError, AttributeError):
        return []


def read_device_model():
    try:
        with open("/proc/device-tree/model", "rb") as f:
            return f.read().rstrip(b"\x00").decode("utf-8", "replace").strip()
    except OSError:
        return ""


def assign_playlist(screen, playlist_name, must_exist=False):
    """Point a screen at a playlist (atomic, locked) and notify legacy players."""

    def mutate(data):
        if not isinstance(data, dict):
            data = {}
        data.setdefault("playlists", {})
        if must_exist and playlist_name not in data["playlists"]:
            raise LookupError(playlist_name)
        data.setdefault("assignments", {})[f"screen{screen}"] = playlist_name

    update_json(PLAYLISTS_FILE, mutate, default=lambda: {"playlists": {"Default": []}, "assignments": {}})
    apply_playlist_assignments()


def schedule_tick(now=None):
    """Fire the schedule events that are due this minute once; returns the fired events."""
    fired = []

    def mutate(data):
        try:
            if data.get("timezone"):
                tz = load_zone(data["timezone"])
            else:
                tz = timezone(timedelta(hours=float(data.get("timezone_offset", 7))))
        except (TypeError, ValueError, OverflowError):
            tz = timezone(timedelta(hours=7))
        current = now.astimezone(tz) if now is not None else datetime.now(tz)
        stamp = current.strftime("%Y-%m-%d %H:%M")
        curr_time = current.strftime("%H:%M")
        curr_day = DAYS[current.weekday()]
        for event in data.get("events", []):
            if not event.get("enabled", True):
                continue
            if event.get("time") == curr_time and curr_day in event.get("days", []):
                # Prevent re-triggering in the same minute
                if event.get("_last_triggered") == stamp:
                    continue
                event["_last_triggered"] = stamp
                fired.append(dict(event))
        return None if fired else NO_CHANGE

    try:
        update_json(SCHEDULES_FILE, mutate)
    except FileNotFoundError:
        return []

    # Side effects happen outside the file lock.
    for event in fired:
        print(f"[Schedule] Triggering Event {event.get('id')} - {event.get('type')}")
        try:
            if event.get("type") == "playlist":
                assign_playlist(int(event.get("screen", 1)), event.get("playlist_name", "Default"))
            elif event.get("type") == "power" and CONFIG.get("legacy_players") and IS_PI:
                # Legacy players only; the Pi 5 supervisor follows schedules.json itself.
                subprocess.run(
                    ["sudo", "systemctl", "stop", "layar1.service", "layar2.service", "layar-gabungan.service"],
                    timeout=20,
                )
        except Exception as e:
            print(f"[Schedule] Event {event.get('id')} failed: {e}")
    return fired


def check_schedules():
    while True:
        try:
            schedule_tick()
        except Exception as e:
            print(f"[Schedule] Tick failed: {e}")
        time.sleep(30)


def migrate_schedule_file():
    """One-time upgrade of schedules.json from wake/sleep events to playback windows."""

    def mutate(data):
        upgraded = migrate_schedules(data) if isinstance(data, dict) else None
        return NO_CHANGE if upgraded is None else upgraded

    try:
        update_json(SCHEDULES_FILE, mutate)
    except (OSError, ValueError) as exc:
        print(f"[Schedule] Could not upgrade schedules.json: {exc}")


def startup():
    """Create folders/files, token and the schedule thread (kept out of import so tests can import)."""
    load_config()
    ensure_dirs()
    init_json_files()
    migrate_schedule_file()
    migrate_existing_files()
    apply_network_config()
    apply_playlist_assignments()
    init_playlist_file(VIDEO_DIR_1)
    init_playlist_file(VIDEO_DIR_2)
    if CONFIG.get("require_auth"):
        ensure_token()
    threading.Thread(target=check_schedules, daemon=True).start()


# --- System resource metrics (Linux/Pi) ---
def get_system_stats():
    if not IS_PI:
        return {
            "cpu_temp": 42.5,
            "cpu_percent": 12.4,
            "ram": {"total_mb": 4096.0, "used_mb": 1024.0, "percent": 25.0},
            "disk": {"total_gb": 32.0, "used_gb": 8.0, "percent": 25.0},
            "uptime": "1d 2h 3m",
        }

    stats = {}

    # 1. CPU Temp
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            stats["cpu_temp"] = round(int(f.readline().strip()) / 1000.0, 1)
    except Exception:
        stats["cpu_temp"] = 0.0

    # 2. CPU Usage (from /proc/stat)
    try:
        with open("/proc/stat", "r") as f:
            line = f.readline()
        parts = line.strip().split()
        if len(parts) >= 5:
            user, nice, sys_mode, idle = map(int, parts[1:5])
            total = user + nice + sys_mode + idle
            time.sleep(0.1)
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts2 = line.strip().split()
            user2, nice2, sys_mode2, idle2 = map(int, parts2[1:5])
            total2 = user2 + nice2 + sys_mode2 + idle2

            idle_diff = idle2 - idle
            total_diff = total2 - total
            if total_diff > 0:
                stats["cpu_percent"] = round((1.0 - (idle_diff / total_diff)) * 100, 1)
            else:
                stats["cpu_percent"] = 0.0
    except Exception:
        stats["cpu_percent"] = 0.0

    # 3. RAM Info
    try:
        total_mem = 0
        avail_mem = 0
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemTotal:" in line:
                    total_mem = int(line.split()[1])
                elif "MemAvailable:" in line:
                    avail_mem = int(line.split()[1])
        if total_mem > 0:
            used_mem = total_mem - avail_mem
            stats["ram"] = {
                "total_mb": round(total_mem / 1024.0, 0),
                "used_mb": round(used_mem / 1024.0, 0),
                "percent": round((used_mem / total_mem) * 100, 1),
            }
        else:
            stats["ram"] = {"total_mb": 0, "used_mb": 0, "percent": 0.0}
    except Exception:
        stats["ram"] = {"total_mb": 0, "used_mb": 0, "percent": 0.0}

    # 4. Disk Usage
    try:
        total, used, free = shutil.disk_usage("/")
        stats["disk"] = {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "percent": round((used / total) * 100, 1),
        }
    except Exception:
        stats["disk"] = {"total_gb": 0, "used_gb": 0, "percent": 0.0}

    # 5. Uptime
    try:
        with open("/proc/uptime", "r") as f:
            uptime_sec = float(f.readline().split()[0])
        hours = int(uptime_sec // 3600)
        mins = int((uptime_sec % 3600) // 60)
        if hours > 0:
            stats["uptime"] = f"{hours}h {mins}m"
        else:
            stats["uptime"] = f"{mins}m"
    except Exception:
        stats["uptime"] = "Unknown"

    return stats


def get_service_status(service_name):
    if not IS_PI:
        return "active"
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service_name], capture_output=True, text=True
        )
        return res.stdout.strip()
    except Exception:
        return "inactive"


# --- Custom Multipart Parser for streaming upload ---
class UploadRejected(Exception):
    """A validation failure that maps to an HTTP status (413, 415, 409, ...)."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


_FILENAME_RE = re.compile(r'filename=(?:"((?:[^"\\]|\\.)*)"|([^;]*))', re.IGNORECASE)


def extract_upload_filename(disposition):
    """File name from a Content-Disposition header (handles ';' and '=' inside names)."""
    match = _FILENAME_RE.search(disposition)
    if not match:
        return None
    raw = match.group(1) if match.group(1) is not None else (match.group(2) or "").strip()
    raw = raw.replace('\\"', '"').replace("%22", '"')  # browsers escape quotes this way
    return raw.replace("\\", "/").split("/")[-1]  # drop any client-side directory part


def parse_multipart_upload(
    rfile, content_length, boundary, upload_dir, check_name=None, check_file=None
):
    """Stream one multipart file part to upload_dir.

    check_name(name) runs before any body byte is stored, check_file(temp_path, name)
    after the whole part arrived but before it is published; both raise UploadRejected.
    """
    boundary_bytes = b"--" + boundary.encode("utf-8")
    closing_boundary = b"\r\n" + boundary_bytes + b"--"
    bytes_read = 0

    if content_length <= 0:
        return False, "Missing or invalid Content-Length"

    def read_request_line():
        nonlocal bytes_read
        request_line = rfile.readline()
        bytes_read += len(request_line)
        return request_line

    # Read first line - should be boundary
    line = read_request_line()
    if line.rstrip(b"\r\n") != boundary_bytes:
        return False, "Boundary mismatch"

    filename = None
    # Parse headers of the part
    while True:
        if bytes_read >= content_length or bytes_read > 65536:
            return False, "Invalid multipart headers"
        line = read_request_line().strip()
        if not line:
            break
        if line.lower().startswith(b"content-disposition:"):
            filename = extract_upload_filename(line.decode("utf-8", errors="replace"))

    if not filename:
        return False, "Filename not found in form data"

    if check_name:
        check_name(filename)
    dest_path = os.path.join(upload_dir, filename)

    # Stream into a temporary file. Only expose the final filename after the
    # complete request and closing multipart boundary have arrived.
    buffer = b""
    chunk_size = 65536
    remaining = content_length - bytes_read
    boundary_found = False
    temp_path = None

    try:
        temp_fd, temp_path = tempfile.mkstemp(
            prefix=f".{filename}.", suffix=".uploading", dir=upload_dir
        )
        with os.fdopen(temp_fd, "wb") as f:
            while remaining > 0:
                chunk = rfile.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)

                if boundary_found:
                    continue

                buffer += chunk
                idx = buffer.find(closing_boundary)
                if idx != -1:
                    f.write(buffer[:idx])
                    buffer = b""
                    boundary_found = True
                else:
                    # Retain enough overlap to detect a boundary split across chunks.
                    keep = len(closing_boundary) - 1
                    if len(buffer) > keep:
                        write_len = len(buffer) - keep
                        f.write(buffer[:write_len])
                        buffer = buffer[write_len:]

            f.flush()
            os.fsync(f.fileno())

        if remaining != 0:
            return False, "Upload interrupted before all bytes were received"
        if not boundary_found:
            return False, "Upload incomplete: closing multipart boundary not found"

        if check_file:
            check_file(temp_path, filename)
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, dest_path)
        temp_path = None
        return True, filename
    except (OSError, ValueError) as exc:
        return False, f"Could not save upload: {exc}"
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


class _CountingReader:
    """Wraps the request stream to learn how much of the body a handler consumed."""

    def __init__(self, raw):
        self._raw = raw
        self.count = 0

    def read(self, size=-1):
        data = self._raw.read(size)
        self.count += len(data)
        return data

    def readline(self, size=-1):
        data = self._raw.readline(size)
        self.count += len(data)
        return data

    def __getattr__(self, name):
        return getattr(self._raw, name)


DRAIN_LIMIT = 32 * 1024 * 1024  # most unread body bytes discarded so the client can read our error


# --- HTTP Request Handler ---
class SignageRequestHandler(BaseHTTPRequestHandler):

    def version_string(self):
        return "capibarra-cms"  # no Python/BaseHTTP version banner

    def _allowed_origin(self, origin):
        host = self.headers.get("Host", "")
        allowed = set(CONFIG.get("allowed_origins", []))
        if host:
            allowed.update((f"http://{host}", f"https://{host}"))
        return origin in allowed

    def send_cors_headers(self):
        """Headers for every response: CORS only for allowed origins, plus hardening."""
        origin = self.headers.get("Origin")
        if origin and self._allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status, message):
        body = json.dumps({"success": False, "error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if status == 401:
            self.send_header("WWW-Authenticate", "Bearer")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _is_authorized(self):
        if not CONFIG.get("require_auth"):
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not TOKEN:
            return False
        return hmac.compare_digest(header[7:].strip().encode("utf-8"), TOKEN.encode("utf-8"))

    def _gate(self, path, is_post):
        """True when the request may proceed; otherwise the error response was already sent."""
        origin = self.headers.get("Origin")
        if origin and (is_post or path.startswith("/api/")) and not self._allowed_origin(origin):
            self._json_error(403, "origin not allowed")
            return False
        if path.startswith("/api/") and not self._is_authorized():
            time.sleep(0.3)  # slow down token guessing
            self._json_error(401, "authentication required")
            return False
        if is_post:
            content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            expected = "multipart/form-data" if path == "/api/upload" else "application/json"
            if content_type != expected:
                self._json_error(415, f"Content-Type must be {expected}")
                return False
        return True

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if origin and not self._allowed_origin(origin):
            self._json_error(403, "origin not allowed")
            return
        self.send_response(204)
        self.send_cors_headers()
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        try:
            self._do_get()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:  # never drop the connection without an answer
            print(f"[GET {self.path}] {exc!r}")
            try:
                self._json_error(500, "internal error")
            except OSError:
                pass

    def _do_get(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if not self._gate(path, False):
            return

        # --- API Endpoints ---
        if path == "/api/status":
            self.handle_api_status()
            return

        elif path == "/api/screenshot":
            self.handle_api_screenshot(query)
            return

        elif path == "/api/audio/config":
            self.handle_api_audio_config()
            return

        elif path == "/api/schedule/config":
            self.handle_api_schedule_config()
            return
        elif path == "/api/schedule/status":
            self.handle_api_schedule_status()
            return

        elif path == "/api/playlists/list":
            self.handle_api_playlists_list()
            return

        elif path == "/api/network/config":
            self.handle_api_network_config()
            return

        elif path == "/api/operation-mode":
            self.handle_api_operation_mode()
            return
        elif path == "/api/output-mode":
            self.handle_api_output_mode()
            return

        self._serve_static(path)

    def _serve_static(self, path):
        """Serve UI assets from public/ only: known suffixes, no dotfiles, no data JSON."""
        if path == "/":
            path = "/index.html"
        relative = path.lstrip("/")
        base = os.path.realpath(PUBLIC_DIR)
        target_file = os.path.realpath(os.path.join(base, relative))

        try:
            inside = os.path.commonpath([target_file, base]) == base
        except ValueError:  # e.g. different drive on Windows
            inside = False
        if not inside or os.path.basename(target_file).startswith("."):
            self.send_error(403, "Access Forbidden")
            return

        extension = os.path.splitext(target_file)[1].lower()
        content_type = STATIC_TYPES.get(extension)
        if extension == ".json" and os.path.relpath(target_file, base).replace(os.sep, "/") in STATIC_JSON_ALLOWED:
            content_type = "application/json"
        if content_type is None or not os.path.isfile(target_file):
            self.send_error(404, "File Not Found")
            return

        with open(target_file, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # UI code must refresh after an update; only images may be reused from cache.
        self.send_header("Cache-Control", "max-age=3600" if extension in (".png", ".jpg", ".jpeg", ".ico", ".woff2") else "no-cache")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        """Health probes (and some browsers) use HEAD: answer like GET without the body."""
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/") and not self._is_authorized():
            self.send_response(401)
        elif path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", STATIC_TYPES[".html"])
        else:
            self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        reader = _CountingReader(self.rfile)
        self.rfile = reader
        try:
            self._do_post()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            print(f"[POST {self.path}] {exc!r}")
            try:
                self._json_error(500, "internal error")
            except OSError:
                pass
        self._drain_unread_body(reader)

    def _drain_unread_body(self, reader):
        """After answering early (401/413/415...), swallow the rest of a modest body.

        Closing with unread data makes the OS reset the connection, and the browser
        then reports a network error instead of showing our JSON error message.
        """
        try:
            declared = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            return
        remaining = declared - reader.count
        if remaining <= 0 or remaining > DRAIN_LIMIT:
            return
        try:
            self.connection.settimeout(3)
            while remaining > 0:
                chunk = reader.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass

    def _do_post(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if not self._gate(path, True):
            return

        if path == "/api/control":
            self.handle_api_control()
        elif path == "/api/upload":
            self.handle_api_upload()
        elif path == "/api/delete":
            self.handle_api_delete()
        elif path == "/api/playlist/save":
            self.handle_api_playlist_save()
        elif path == "/api/audio/global":
            self.handle_api_audio_global()
        elif path == "/api/audio/clip":
            self.handle_api_audio_clip()
        elif path == "/api/schedule/save":
            self.handle_api_schedule_save()
        elif path == "/api/playlists/save_all":
            self.handle_api_playlists_save_all()
        elif path == "/api/system/shutdown":
            self.handle_api_system_shutdown()
        elif path == "/api/network/save":
            self.handle_api_network_save()
        elif path == "/api/operation-mode":
            self.handle_api_operation_mode()
            return
        elif path == "/api/output-mode":
            self.handle_api_output_mode()
        elif path == "/api/playlists/assign":
            self.handle_api_playlists_assign()
        else:
            self.send_error(404, "Endpoint Not Found")

    # --- API Handlers ---
    def handle_api_status(self):
        # 1. System stats
        sys_stats = get_system_stats()

        # Helper to read state for a specific screen
        def get_screen_data(screen_num, video_dir, sock_path, service_name):
            status = get_service_status(service_name)

            # Query mpv for current state
            mpv_active = False
            playing_file = "None"
            time_pos = 0
            duration = 0
            paused = False

            # Ask mpv
            if IS_PI and os.path.exists(sock_path):
                filename_res = send_mpv_command(sock_path, ["get_property", "filename"])
                if filename_res.get("error") == "success":
                    mpv_active = True
                    playing_file = filename_res.get("data", "Unknown")

                    # Fetch extra details
                    pos_res = send_mpv_command(sock_path, ["get_property", "time-pos"])
                    time_pos = (
                        round(pos_res.get("data", 0), 1)
                        if pos_res.get("error") == "success"
                        else 0
                    )

                    dur_res = send_mpv_command(sock_path, ["get_property", "duration"])
                    duration = (
                        round(dur_res.get("data", 0), 1)
                        if dur_res.get("error") == "success"
                        else 0
                    )

                    pause_res = send_mpv_command(sock_path, ["get_property", "pause"])
                    paused = (
                        pause_res.get("data", False)
                        if pause_res.get("error") == "success"
                        else False
                    )

            elif not IS_PI:
                # Windows Mock
                mpv_active = True
                playing_file = "mock_video_A.mp4"
                time_pos = 45.2
                duration = 120.0
                paused = False

            # Read files in directory (Media Library)
            valid_exts = (".mp4", ".mkv", ".avi", ".mov", ".webm")
            all_files = (
                [f for f in os.listdir(MEDIA_DIR) if f.lower().endswith(valid_exts)]
                if os.path.exists(MEDIA_DIR)
                else []
            )

            # Playlist order: legacy players use playlist.txt, the Pi 5 player uses playlists.json
            playlist_order = []
            if CONFIG.get("legacy_players"):
                playlist_path = os.path.join(video_dir, "playlist.txt")
                if os.path.exists(playlist_path):
                    with open(playlist_path, "r", encoding="utf-8") as pf:
                        for line in pf:
                            f_path = line.strip()
                            if f_path:
                                fname = os.path.basename(f_path)
                                if fname in all_files:
                                    playlist_order.append(fname)
            else:
                playlist_order = [f for f in assigned_playlist(screen_num) if f in all_files]

            # Get file sizes
            files_data = []
            for f in playlist_order:
                f_path = os.path.join(MEDIA_DIR, f)
                size_mb = (
                    round(os.path.getsize(f_path) / (1024 * 1024), 1)
                    if os.path.exists(f_path)
                    else 0
                )
                files_data.append({"name": f, "size_mb": size_mb})

            return {
                "service_active": status == "active",
                "mpv_connected": mpv_active,
                "playing_file": playing_file,
                "time_pos": time_pos,
                "duration": duration,
                "paused": paused,
                "playlist": files_data,
                "all_files": all_files,
            }

        # Primary status from pi5-signage (single HDMI-A-1), fallback to legacy service for compatibility
        pi5_active = get_service_status("pi5-signage.service") == "active"
        # Try legacy sockets first, then fall back to pi5-signage process detection
        def pi5_screen_fallback(screen_num):
            # Detect pi5-signage mpv via pgrep when legacy IPC socket is absent
            try:
                import subprocess as _sp
                res = _sp.run(["pgrep", "-a", "mpv"], capture_output=True, text=True, timeout=2)
                for line in res.stdout.splitlines():
                    if "capibarra" in line or "dmabuf-wayland" in line or "pi5-signage" in line:
                        # parse -- /path/to/file.mp4 at end
                        parts = line.strip().split(" -- ")[-1] if " -- " in line else line
                        fname = parts.strip().split("/")[-1]
                        if fname.lower().endswith((".mp4",".mkv",".mov",".avi",".webm")):
                            # crude time_pos not available without IPC, keep 0
                            return {"service_active": pi5_active, "mpv_connected": True, "playing_file": fname, "time_pos": 0, "duration": 0, "paused": False}
                        return {"service_active": pi5_active, "mpv_connected": True, "playing_file": "Unknown", "time_pos": 0, "duration": 0, "paused": False}
                return {"service_active": pi5_active, "mpv_connected": False, "playing_file": "None", "time_pos": 0, "duration": 0, "paused": False}
            except Exception:
                return {"service_active": pi5_active, "mpv_connected": False, "playing_file": "None", "time_pos": 0, "duration": 0, "paused": False}

        # Use legacy get_screen_data but override service_active/mpv when pi5 is active and legacy shows inactive
        legacy_s1 = get_screen_data(1, VIDEO_DIR_1, SOCK_1, "layar-gabungan.service")
        legacy_s2 = get_screen_data(2, VIDEO_DIR_2, SOCK_2, "layar-gabungan.service")
        if pi5_active and not legacy_s1.get("mpv_connected"):
            fb = pi5_screen_fallback(1)
            # keep playlist/all_files from legacy but override playback status
            legacy_s1.update({k: fb[k] for k in ("service_active","mpv_connected","playing_file")})
        elif pi5_active:
            legacy_s1["service_active"] = True
        if pi5_active:
            # screen2 is not driven by pi5-signage (single HDMI-A-1) -> reflect real inactive
            legacy_s2["service_active"] = False
        screen1 = legacy_s1
        screen2 = legacy_s2

        # Load audio configuration to merge into status payload
        audio_cfg = {}
        config_path = os.path.join(
            os.path.dirname(__file__), "public", "audio_config.json"
        )
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    audio_cfg = json.load(f)
            except Exception:
                pass

        sys_stats["model"] = read_device_model()
        response_data = {
            "system": sys_stats,
            "screen1": screen1,
            "screen2": screen2,
            "audio": audio_cfg,
            # Lets the UI hide controls this device cannot honour.
            "capabilities": {
                "transport_controls": False,  # the Pi 5 player has no prev/next/play/pause IPC
                "dual_output": False,
                "max_upload_mb": CONFIG["max_upload_mb"],
                "allowed_codecs": CONFIG["allowed_codecs"],
                "allowed_extensions": list(ALLOWED_EXTENSIONS),
                "auth_required": CONFIG["require_auth"],
            },
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode("utf-8"))

    def player_response(self, status, response):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def player_params(self):
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= 4096:
            raise ValueError("Invalid request length")
        params = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(params, dict):
            raise ValueError("Expected JSON object")
        return params

    def handle_api_operation_mode(self):
        path = os.path.join(os.path.dirname(SCHEDULES_FILE), "operation_mode.json")
        try:
            with open("/proc/sys/kernel/random/boot_id") as f:
                boot = f.read().strip()
            if self.command == "POST":
                mode = self.player_params().get("mode")
                if mode not in ("auto", "on", "off"):
                    self.player_response(400, {"success": False, "error": "mode must be auto, on or off"})
                    return
                fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".operation-")
                try:
                    with os.fdopen(fd, "w") as f:
                        json.dump({"mode": mode, "boot_id": boot}, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            else:
                mode = "auto"
                try:
                    with open(path) as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("boot_id") == boot and data.get("mode") in ("auto", "on", "off"):
                        mode = data["mode"]
                except (OSError, ValueError):
                    pass
            self.player_response(200, {"success": True, "mode": mode, "manual": mode != "auto", "reset_on_reboot": True})
        except (ValueError, TypeError, UnicodeError) as e:
            self.player_response(400, {"success": False, "error": str(e)})
        except OSError:
            self.player_response(503, {"success": False, "error": "Operation mode storage unavailable"})

    def handle_api_output_mode(self):
        try:
            if self.command != "GET":
                mode = self.player_params().get("mode")
                if mode != "single":
                    self.player_response(409, {"success": False, "error": "Pi 5 supports single HDMI-A-1 only"})
                    return
                # This player is fixed to single; no restart or config mutation needed.
            self.player_response(200, {"success": True, "mode": "single", "supported_modes": ["single"]})
        except (ValueError, UnicodeError) as e:
            self.player_response(400, {"success": False, "error": str(e)})

    def handle_api_control(self):
        try:
            params = self.player_params()
            screen = int(params.get("screen", 1))
            action = params.get("action", "")
            if screen != 1:
                self.player_response(409, {"success": False, "error": "Only screen 1 is supported"})
                return
            if action in ("play", "pause", "next", "prev"):
                self.player_response(409, {"success": False, "error": "Pi 5 player IPC controls are not implemented; legacy control is disabled"})
                return
            if action not in ("restart_service", "start_service", "stop_service"):
                self.player_response(400, {"success": False, "error": "Unknown action"})
                return
            operation = action.split("_")[0]
            result = subprocess.run(["sudo", "-n", "systemctl", operation, PLAYER_SERVICE], capture_output=True, text=True, timeout=20)
            if result.returncode:
                self.player_response(503, {"success": False, "error": "Player service operation failed; check service permissions", "service": PLAYER_SERVICE})
                return
            self.player_response(200, {"success": True, "service": PLAYER_SERVICE, "message": operation + " succeeded"})
        except (ValueError, TypeError, UnicodeError) as e:
            self.player_response(400, {"success": False, "error": str(e)})
        except (OSError, subprocess.TimeoutExpired):
            self.player_response(503, {"success": False, "error": "Player service command unavailable or timed out"})

    def handle_api_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "Content-Type must be multipart/form-data")
            return

        boundary = None
        for parameter in content_type.split(";")[1:]:
            key, separator, value = parameter.strip().partition("=")
            if separator and key.lower() == "boundary":
                boundary = value.strip().strip('"')
                break

        if not boundary:
            self.send_error(400, "Multipart boundary is missing")
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._json_error(400, "Invalid Content-Length")
            return

        max_bytes = int(CONFIG["max_upload_mb"]) * 1024 * 1024
        reserve = int(CONFIG["min_free_mb"]) * 1024 * 1024
        if content_length <= 0:
            self._json_error(411, "Content-Length is required")
            return
        if content_length > max_bytes:
            self._json_error(413, f"File is larger than the {CONFIG['max_upload_mb']} MB upload limit")
            return
        try:
            free = shutil.disk_usage(MEDIA_DIR).free
        except OSError:
            free = None
        if free is not None and free - content_length < reserve:
            self._json_error(507, "Not enough free disk space for this upload")
            return

        def check_name(name):
            ok, message = validate_upload_name(name)
            if not ok:
                raise UploadRejected(415 if "type" in message else 400, message)
            if os.path.exists(os.path.join(MEDIA_DIR, name)):
                raise UploadRejected(409, f'"{name}" already exists; delete it first or rename the new file')

        def check_file(path, name):
            ok, message = check_upload(path, name, CONFIG["allowed_codecs"])
            if not ok:
                raise UploadRejected(415, message)

        try:
            success, info = parse_multipart_upload(
                self.rfile, content_length, boundary, MEDIA_DIR, check_name, check_file
            )
        except UploadRejected as rejected:
            self._json_error(rejected.status, rejected.message)
            return

        if success:
            res = {"success": True, "filename": info}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self._json_error(400, f"Upload failed: {info}")

    def handle_api_delete(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        try:
            params = json.loads(post_data)
            filename = params.get("filename", "")

            # Only a plain file name inside MEDIA_DIR is acceptable: no separators, no dotfiles.
            if (
                not isinstance(filename, str)
                or not filename
                or os.path.basename(filename) != filename
                or filename.startswith(".")
            ):
                self._json_error(400, "Invalid filename")
                return

            target_path = os.path.join(MEDIA_DIR, filename)

            res = {"success": False, "error": "File not found"}
            if os.path.isfile(target_path):
                os.remove(target_path)

                # Cleanup from playlists (atomic and locked: the player reads this file)
                def drop_from_playlists(data):
                    changed = False
                    for pl_name, files in data.get("playlists", {}).items():
                        if filename in files:
                            data["playlists"][pl_name] = [x for x in files if x != filename]
                            changed = True
                    return None if changed else NO_CHANGE

                try:
                    update_json(PLAYLISTS_FILE, drop_from_playlists)
                    # Re-apply assignments to keep legacy screens in sync
                    apply_playlist_assignments()
                except Exception as e:
                    print(f"[Delete cleanup] Error: {e}")

                res = {"success": True, "message": "File deleted"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Error deleting file: {e}")

    def handle_api_playlist_save(self):
        if not CONFIG.get("legacy_players"):
            self._json_error(409, "Legacy per-screen playlists are disabled; use /api/playlists/save_all")
            return
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        try:
            params = json.loads(post_data)
            screen = int(params.get("screen", 1))
            filenames = params.get("playlist", [])  # List of filenames in desired order

            upload_dir = VIDEO_DIR_1 if screen == 1 else VIDEO_DIR_2
            playlist_path = os.path.join(upload_dir, "playlist.txt")

            # Write new playlist.txt with complete paths in specified order
            with open(playlist_path, "w", encoding="utf-8") as pf:
                for fname in filenames:
                    # Clean filename path traversal
                    fname_clean = os.path.basename(fname)
                    f_path = os.path.join(upload_dir, fname_clean)
                    if os.path.exists(f_path):
                        pf.write(f_path + "\n")

            # Send reload to MPV
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            if IS_PI and os.path.exists(sock_path):
                send_mpv_command(sock_path, ["loadlist", playlist_path])

            res = {"success": True, "message": "Playlist order saved and applied"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Error saving playlist: {e}")

    def handle_api_screenshot(self, query):
        try:
            screen = int(query.get("screen", [1])[0])
        except (TypeError, ValueError):
            screen = 0
        if screen not in (1, 2):
            self._json_error(400, "screen must be 1 or 2")
            return
        sock_path = SOCK_1 if screen == 1 else SOCK_2

        # Temp preview path
        preview_path = (
            f"/tmp/layar{screen}-preview.jpg"
            if IS_PI
            else os.path.join(os.getcwd(), f"mock-preview-{screen}.jpg")
        )

        if IS_PI:
            # 1. Instruct mpv to save screenshot to preview_path
            # Sub-parameter 'video' takes screenshots of video frame directly, bypassing OSD
            send_mpv_command(sock_path, ["screenshot-to-file", preview_path, "video"])
        else:
            # Create a mock placeholder image if mock image doesn't exist
            if not os.path.exists(preview_path):
                # Generate simple 1x1 jpg or copy dummy file if we want,
                # let's just make it empty or serve a fallback if no file
                pass

        # 2. Read and stream the file
        if os.path.exists(preview_path):
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_cors_headers()
            self.end_headers()
            with open(preview_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            # Serve a fallback placeholder if screenshot is not ready/unsupported
            fallback_img = os.path.join(
                os.path.dirname(__file__), "public", "placeholder.jpg"
            )
            if os.path.exists(fallback_img):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_cors_headers()
                self.end_headers()
                with open(fallback_img, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Preview not available")

    def handle_api_audio_config(self):
        config_path = os.path.join(
            os.path.dirname(__file__), "public", "audio_config.json"
        )
        if not os.path.exists(config_path):
            default_config = {
                "screen1": {
                    "global_mute": True,
                    "output_device": "hdmi",
                    "channel_mode": "stereo",
                    "clip_settings": {},
                },
                "screen2": {
                    "global_mute": True,
                    "output_device": "hdmi",
                    "channel_mode": "stereo",
                    "clip_settings": {},
                },
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def handle_api_audio_global(self):
        try:
            params = self.player_params()
            screen = params.get("screen", 1)
            muted = params.get("global_mute")
            output = params.get("output_device", "hdmi")
            channel = params.get("channel_mode", "stereo")
            if type(screen) is not int or screen != 1:
                self.player_response(409, {"success": False, "error": "Only screen 1 is supported"})
                return
            if type(muted) is not bool or output not in ("hdmi", "jack") or channel not in ("stereo", "left", "right"):
                raise ValueError("Invalid audio settings")
            if output != "hdmi":
                self.player_response(409, {"success": False, "error": "This Pi uses HDMI audio; jack is not supported"})
                return
            config_path = os.path.join(os.path.dirname(__file__), "public", "audio_config.json")
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
            current = send_mpv_command(SOCK_1, ["get_property", "filename"])
            applied = current.get("error") == "success"
            if not applied and get_service_status(PLAYER_SERVICE) == "active" and os.path.exists(SOCK_1):
                self.player_response(503, {"success": False, "error": "Player IPC unavailable; audio was not changed"})
                return
            cfg = data.setdefault("screen1", {})
            clip_mute = cfg.get("clip_settings", {}).get(current.get("data", ""), {}).get("mute", False)
            effective_mute = muted or clip_mute
            if applied:
                af = {"stereo": "", "left": "lavfi=[pan=stereo|c0=c0|c1=0*c1]", "right": "lavfi=[pan=stereo|c0=0*c0|c1=c1]"}[channel]
                device = send_mpv_command(SOCK_1, ["get_property", "audio-device"])
                commands = []
                if device.get("data") != "alsa/sysdefault:CARD=vc4hdmi0":
                    commands.append(["set_property", "audio-device", "alsa/sysdefault:CARD=vc4hdmi0"])
                commands += [["set_property", "af", af], ["set_property", "mute", effective_mute]]
                for command in commands:
                    result = send_mpv_command(SOCK_1, command)
                    if result.get("error") != "success":
                        self.player_response(503, {"success": False, "error": "Player rejected audio setting", "detail": result.get("error")})
                        return
                actual = send_mpv_command(SOCK_1, ["get_property", "mute"])
                if actual.get("error") != "success" or actual.get("data") != effective_mute:
                    self.player_response(503, {"success": False, "error": "Mute verification failed"})
                    return
            cfg.update(global_mute=muted, output_device=output, channel_mode=channel)
            fd, temporary = tempfile.mkstemp(dir=os.path.dirname(config_path), prefix=".audio-")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, config_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self.player_response(200, {"success": True, "applied": applied, "global_mute": muted, "message": "Audio applied" if applied else "Saved for next playback"})
        except (ValueError, TypeError, UnicodeError) as exc:
            self.player_response(400, {"success": False, "error": str(exc)})
        except OSError:
            self.player_response(503, {"success": False, "error": "Audio settings could not be saved"})

    def handle_api_audio_clip(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        try:
            params = json.loads(post_data)
            screen = int(params.get("screen", 1))
            filename = params.get("filename", "")
            mute = params.get("mute", False)

            if not isinstance(filename, str) or not filename:
                self._json_error(400, "Filename missing")
                return
            if not isinstance(mute, bool):
                self._json_error(400, "mute must be true or false")
                return

            config_path = os.path.join(
                os.path.dirname(__file__), "public", "audio_config.json"
            )
            screen_key = f"screen{screen}"

            def set_clip_mute(data):
                if screen_key in data:
                    data[screen_key].setdefault("clip_settings", {})[filename] = {"mute": mute}

            data = update_json(config_path, set_clip_mute)

            # If currently playing this file, apply mute state
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            filename_res = send_mpv_command(sock_path, ["get_property", "filename"])
            if (
                filename_res.get("error") == "success"
                and filename_res.get("data") == filename
            ):
                global_mute = data[screen_key]["global_mute"]
                send_mpv_command(
                    sock_path, ["set_property", "mute", global_mute or mute]
                )

            res = {"success": True, "message": "Clip audio setting updated"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, f"Error processing clip audio: {e}")

    def handle_api_schedule_config(self):
        try:
            with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_schedule_status(self):
        try:
            with open(SCHEDULES_FILE, "r", encoding="utf-8") as f:
                state = schedule_state(json.load(f))
            self._send_json(200, state)
        except (OSError, ValueError) as exc:
            self._json_error(500, f"schedule unreadable: {exc}")

    def handle_api_schedule_save(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            params = json.loads(post_data)
            try:
                validate_schedules(params)
            except ValueError as exc:
                self._json_error(400, str(exc))
                return

            def replace_schedules(old):
                # The scheduler stamps events when they fire; keep those stamps so a save
                # from a stale page cannot make an event fire a second time.
                stamps = {e.get("id"): e.get("_last_triggered") for e in old.get("events", []) if isinstance(e, dict)}
                for event in params.get("events", []):
                    if event.get("id") in stamps and stamps[event["id"]] and "_last_triggered" not in event:
                        event["_last_triggered"] = stamps[event["id"]]
                return params

            update_json(SCHEDULES_FILE, replace_schedules, default=dict)

            res = {"success": True, "message": "Schedule saved"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_playlists_list(self):
        try:
            with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_playlists_save_all(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            params = json.loads(post_data)
            try:
                validate_playlists(params)
            except ValueError as exc:
                self._json_error(400, str(exc))
                return
            update_json(PLAYLISTS_FILE, lambda _old: params, default=dict)

            apply_playlist_assignments()

            res = {"success": True, "message": "Playlists saved"}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_system_shutdown(self):
        res = {"success": True, "message": "System is shutting down"}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(res).encode("utf-8"))

        # Shutdown after responding
        def run_shutdown():
            time.sleep(1)
            if IS_PI:
                subprocess.run(["sudo", "-n", "shutdown", "-h", "now"], timeout=20)

        threading.Thread(target=run_shutdown, daemon=True).start()

    def handle_api_network_config(self):
        try:
            with open(NETWORK_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            eth_ifs, wlan_ifs = get_network_interfaces()
            eth_status = [get_interface_status(eth) for eth in eth_ifs]
            wlan_status = [get_interface_status(wl) for wl in wlan_ifs]

            response_data = {
                "selected": data.get("selected", "eth"),
                "interfaces": {"eth": eth_status, "wlan": wlan_status},
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_network_save(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            params = json.loads(post_data)
            selected = params.get("selected", "eth")
            if selected not in ("eth", "wlan"):
                self._json_error(400, "selected must be eth or wlan")
                return

            write_json_atomic(NETWORK_CONFIG_FILE, {"selected": selected})

            def do_apply():
                time.sleep(0.5)
                apply_network_config()

            threading.Thread(target=do_apply, daemon=True).start()

            res = {
                "success": True,
                "message": f"Network path saved. Applying {selected.upper()}...",
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_playlists_assign(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            params = json.loads(post_data)
            screen = int(params.get("screen", 1))
            playlist_name = params.get("playlist_name", "Default")
            if screen not in (1, 2) or not isinstance(playlist_name, str):
                self._json_error(400, "screen must be 1 or 2 and playlist_name a string")
                return
            try:
                assign_playlist(screen, playlist_name, must_exist=True)
            except LookupError:
                self._json_error(404, f"Playlist {playlist_name!r} does not exist")
                return

            res = {
                "success": True,
                "message": f"Playlist {playlist_name} assigned to Screen {screen}",
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        except Exception as e:
            self.send_error(500, str(e))


def run_server(port=8080):
    startup()
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, SignageRequestHandler)
    print(f"Museum Signage CMS Backend serving on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
