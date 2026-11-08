#!/usr/bin/env python3
"""Small scheduled mpv supervisor for a single Raspberry Pi Wayland output."""

import argparse
import os
import re
import json
import logging
import signal
import socket
import subprocess
import time
from datetime import datetime, time as clock_time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOG = logging.getLogger("pi5-signage")
EXTENSIONS = {".mp4", ".mkv", ".mov"}
STOP = False
IPC_SOCKET = "/run/user/1000/capibarra-mpv.sock"
STALL_SECONDS = 30      # mpv position frozen this long => treat the player as hung
FAST_FAIL_SECONDS = 10  # a non-zero exit sooner than this counts as a failed start
FAIL_LIMIT = 3          # consecutive fast failures before a file is set aside
BLOCK_SECONDS = 600     # how long a repeatedly failing file is skipped


def detect_device_model(device_tree_path=Path("/proc/device-tree/model")):
    """Read the board model from device-tree, or return empty string."""
    try:
        content = Path(device_tree_path).read_bytes().rstrip(b"\x00").decode("utf-8", errors="replace")
        return content.strip()
    except OSError:
        return ""


def resolve_profile_name(config, model_name=None):
    """Resolve only known named profiles; unknown boards require an explicit profile."""
    configured = config.get("profile")
    if configured:
        name = str(configured).lower()
        if name not in {"pi5"}:
            raise ValueError(f"Unknown profile: {configured}")
        return name
    model = (model_name if model_name is not None else detect_device_model()).strip().lower()
    if re.fullmatch(r"raspberry pi 5(?: model b)?(?: rev \d+\.\d+)?", model):
        return "pi5"
    raise ValueError(f"Unsupported or unknown Raspberry Pi model: {model or 'unavailable'}; set profile explicitly")


def load_profile(profile_name):
    """Load a strictly named profile only from profiles/ beside this module."""
    if profile_name not in {"pi5"}:
        raise ValueError(f"Unknown profile: {profile_name}")
    profile_path = Path(__file__).resolve().parent / "profiles" / f"{profile_name}.json"
    if not profile_path.is_file():
        raise ValueError(f"Missing profile file: {profile_path}")
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    validate_profile(profile_name, data)
    return data


def validate_profile(name, data):
    if not isinstance(data, dict) or data.get("target") != name or not isinstance(data.get("mpv"), dict):
        raise ValueError(f"Invalid profile schema for {name}")
    mpv = data["mpv"]
    text_keys = ("vo", "hwdec", "hwdec_codecs", "video_sync", "framedrop")
    if not all(isinstance(mpv.get(k), str) and mpv[k] and not mpv[k].startswith("-") and "\n" not in mpv[k] for k in text_keys) \
            or not isinstance(mpv.get("hwdec_extra_frames"), int) or isinstance(mpv["hwdec_extra_frames"], bool) \
            or not 0 <= mpv["hwdec_extra_frames"] <= 64:
        raise ValueError(f"Invalid mpv output settings in {name}")


def profile_mpv_args(config):
    """mpv renderer flags come from the validated hardware profile (single source of truth)."""
    mpv = load_profile(config.get("_profile_name", "pi5"))["mpv"]
    return [
        f"--vo={mpv['vo']}", f"--hwdec={mpv['hwdec']}",
        f"--hwdec-codecs={mpv['hwdec_codecs']}", f"--hwdec-extra-frames={mpv['hwdec_extra_frames']}",
        f"--video-sync={mpv['video_sync']}", f"--framedrop={mpv['framedrop']}",
    ]


def parse_clock(value):
    return clock_time.fromisoformat(value)


def in_window(now, start, end):
    """A half-open daily time window; supports crossing midnight."""
    current = now.time().replace(tzinfo=None)
    if start == end:
        raise ValueError("start and end must differ")
    if start < end:
        return start <= current < end
    return current >= start or current < end


def media_files(directory):
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS),
        key=lambda p: p.name.casefold(),
    ) if directory.is_dir() else []


def playlist_files(config):
    """Resolve the CMS-assigned playlist while keeping paths inside media_dir."""
    directory = config["media_dir"]
    playlist_file = config.get("playlist_file")
    if not playlist_file:
        return media_files(directory)
    try:
        data = json.loads(Path(playlist_file).read_text(encoding="utf-8"))
        screen = config.get("playlist_screen", "screen1")
        playlist_name = config.get("playlist_name") or data.get("assignments", {}).get(screen, "Default")
        names = data.get("playlists", {}).get(playlist_name, [])
    except (OSError, json.JSONDecodeError, TypeError):
        LOG.exception("Unable to read CMS playlist %s", playlist_file)
        return []
    resolved = []
    for name in names:
        candidate = directory / Path(str(name)).name
        if candidate.is_file() and candidate.suffix.lower() in EXTENSIONS:
            resolved.append(candidate)
        else:
            LOG.warning("Playlist item is unavailable: %s", name)
    return resolved


def cms_mute(path, config):
    """Persist CMS global/per-clip mute across player launches."""
    fallback = not config.get("audio", False)
    if not config.get("schedules_file"):
        return fallback  # player-only install: no CMS files to consult
    try:
        source = Path(config["schedules_file"]).with_name("audio_config.json")
        data = json.loads(source.read_text())
        audio = data.get(config.get("playlist_screen", "screen1"), {})
        global_mute = audio.get("global_mute", fallback)
        clip_mute = audio.get("clip_settings", {}).get(Path(path).name, {}).get("mute", False)
        if not isinstance(global_mute, bool) or not isinstance(clip_mute, bool):
            return fallback
        return fallback or global_mute or clip_mute
    except (OSError, ValueError, TypeError, AttributeError):
        return fallback


def command_for(path, config, loop=False):
    command = [
        "mpv", *profile_mpv_args(config),
        "--msg-level=all=info",
        "--term-status-msg=",
        "--no-osc", "--osd-level=0",
        "--no-border", "--fullscreen", "--fs-screen=0", "--keep-open=no",
        "--no-input-default-bindings", "--wayland-app-id=capibarra",
        "--input-ipc-server=" + IPC_SOCKET,
        "--mute=" + ("yes" if cms_mute(path, config) else "no"),
    ]
    if loop:
        # Single-item playlist: let mpv loop in-process so there is no relaunch gap.
        command.append("--loop-file=inf")
    if config["audio"]:
        command.append("--audio-device=" + config["audio_device"])
    else:
        command.append("--mute=yes")
    return command + ["--", str(path)]


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config must contain a JSON object")
    profile_name = resolve_profile_name(config)
    load_profile(profile_name)
    config["_profile_name"] = profile_name
    config["media_dir"] = Path(config["media_dir"])
    if not isinstance(config.get("always_on", False), bool):
        raise ValueError("always_on must be true or false")
    if "windows" in config:
        if config.get("always_on"):
            raise ValueError("always_on cannot be combined with windows")
        parse_windows(config)  # validate now; start/end are then optional
    if "windows" not in config or "start" in config or "end" in config:
        config["start"] = parse_clock(config["start"])
        config["end"] = parse_clock(config["end"])
        if "windows" not in config and not config.get("always_on") and config["start"] == config["end"]:
            raise ValueError("start and end must differ (or set always_on)")
    if config["retry_seconds"] < 1:
        raise ValueError("retry_seconds must be >= 1")
    if not config["display"].startswith("HDMI-A-"):
        raise ValueError("display must be an HDMI-A-* connector")
    schedules_file = config.get("schedules_file")
    if schedules_file:
        config["schedules_file"] = Path(schedules_file)
    return config


def schedules_allow(config):
    """Return True when the CMS schedules.json window allows playback."""
    schedules_file = config.get("schedules_file")
    if not schedules_file:
        return True
    path = Path(schedules_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOG.warning("Unable to read schedules %s; allowing playback", path)
        return True
    tz_offset = data.get("timezone_offset", 7)
    try:
        tz = timezone(timedelta(hours=int(tz_offset)))
    except (TypeError, ValueError):
        tz = timezone(timedelta(hours=7))
    now = datetime.now(tz)
    curr_time = now.time().replace(tzinfo=None)
    days_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    curr_day = days_map[now.weekday()]
    wake = None
    sleep = None
    for event in data.get("events", []):
        if not event.get("enabled", True):
            continue
        if event.get("type") != "power":
            continue
        if curr_day not in event.get("days", []):
            continue
        try:
            t = parse_clock(event.get("time", ""))
        except (ValueError, TypeError):
            continue
        action = event.get("action")
        if action == "wake":
            wake = t if wake is None or t < wake else wake
        elif action == "sleep":
            sleep = t if sleep is None or t > sleep else sleep
    if wake is None and sleep is None:
        return True
    if wake is None:
        return curr_time < sleep
    if sleep is None:
        return curr_time >= wake
    if wake < sleep:
        return wake <= curr_time < sleep
    return curr_time >= wake or curr_time < sleep


DAY_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
_LOGGED = set()
_LAST_GOOD = {}  # schedules_file path -> last successfully parsed window schedule


def log_once(key, level, message, *args):
    """Log a condition only the first time it appears (allowed_now runs every second)."""
    if key not in _LOGGED:
        _LOGGED.add(key)
        LOG.log(level, message, *args)


class WindowSchedule:
    """Playback windows: each belongs to the day it STARTS on and may cross midnight."""

    def __init__(self, tz, windows):
        self.tz = tz  # None = the Pi's local timezone
        self.windows = windows  # list of (frozenset(weekday), start_minute, duration_minutes)


def _minutes(text, allow_24=False):
    if not isinstance(text, str):
        raise ValueError(f"time must be a string like 08:00, got {text!r}")
    if allow_24 and text == "24:00":
        return 1440
    try:
        parsed = clock_time.fromisoformat(text)
    except ValueError:
        raise ValueError(f"invalid time {text!r}; use HH:MM") from None
    if parsed.second or parsed.microsecond or len(text) != 5:
        raise ValueError(f"invalid time {text!r}; use HH:MM")
    return parsed.hour * 60 + parsed.minute


@lru_cache(maxsize=16)
def _parse_windows(spec_json):
    spec = json.loads(spec_json)
    tz = None
    if spec["timezone"] is not None:
        if not isinstance(spec["timezone"], str):
            raise ValueError("timezone must be an IANA name such as Asia/Jakarta")
        try:
            tz = ZoneInfo(spec["timezone"])
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError(f"unknown timezone {spec['timezone']!r}") from None
    raw = spec["windows"]
    if not isinstance(raw, list) or not raw or len(raw) > 200:
        raise ValueError("windows must be a non-empty list (max 200)")
    windows, covered = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each window must be an object with days, start, end")
        days = item.get("days")
        if not isinstance(days, list) or not days or any(d not in DAY_INDEX for d in days):
            raise ValueError(f"days must be a non-empty list of {sorted(DAY_INDEX, key=DAY_INDEX.get)}")
        start, end = _minutes(item.get("start")), _minutes(item.get("end"), allow_24=True)
        if start == end:
            raise ValueError(f"window {item.get('start')}-{item.get('end')} has zero length; use 00:00-24:00 for a full day")
        duration = end - start if end > start else end + 1440 - start
        indexes = frozenset(DAY_INDEX[d] for d in days)
        covered |= indexes
        windows.append((indexes, start, duration))
    missing = [name for name, index in DAY_INDEX.items() if index not in covered]
    if missing:
        log_once(("nowindow", spec_json), logging.WARNING,
                 "No playback window starts on %s; the display stays off on those days unless a window from the previous day runs past midnight",
                 ", ".join(missing))
    return WindowSchedule(tz, windows)


def parse_windows(spec):
    """Validate a {'timezone': ..., 'windows': [...]} mapping; raises ValueError."""
    try:
        text = json.dumps({"timezone": spec.get("timezone"), "windows": spec.get("windows")}, sort_keys=True)
    except (TypeError, ValueError, AttributeError):
        raise ValueError("windows/timezone must be plain JSON values") from None
    return _parse_windows(text)


def windows_allow(schedule, now=None):
    """True when `now` falls inside a window that started today or (overflowing midnight) yesterday."""
    tz = schedule.tz or datetime.now().astimezone().tzinfo
    now = datetime.now(tz) if now is None else now.astimezone(tz)
    for back in (0, 1):
        day = now.date() - timedelta(days=back)
        for weekdays, start, duration in schedule.windows:
            if day.weekday() not in weekdays:
                continue
            begin = datetime.combine(day, clock_time(0), tzinfo=tz) + timedelta(minutes=start)
            if begin <= now < begin + timedelta(minutes=duration):
                return True
    return False


def active_windows(config):
    """Window schedule in force: the CMS schedules file wins, then config, else None (legacy rules)."""
    source = config.get("schedules_file")
    if source:
        key = str(source)
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
            if key in _LAST_GOOD:
                log_once(("unreadable", key), logging.WARNING, "Cannot read %s; keeping the last valid window schedule", key)
                return _LAST_GOOD[key]
        if isinstance(data, dict) and "windows" in data:
            try:
                schedule = parse_windows(data)
            except ValueError as exc:
                log_once(("invalid", key, str(exc)), logging.ERROR, "Invalid window schedule in %s: %s", key, exc)
                if key in _LAST_GOOD:
                    return _LAST_GOOD[key]
            else:
                _LAST_GOOD[key] = schedule
                return schedule
        else:
            _LAST_GOOD.pop(key, None)
    if "windows" in config:
        return parse_windows(config)
    return None


def operation_mode(config):
    if not config.get("schedules_file"):
        return "auto"  # player-only install: no CMS operation_mode.json
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        path = Path(config["schedules_file"]).with_name("operation_mode.json")
        data = json.loads(path.read_text())
        mode = data.get("mode")
        return mode if data.get("boot_id") == boot and mode in ("auto", "on", "off") else "auto"
    except (OSError, ValueError, AttributeError, TypeError):
        return "auto"


def allowed_now(config):
    mode = operation_mode(config)
    if mode != "auto":
        return mode == "on"
    schedule = active_windows(config)
    if schedule is not None:
        return windows_allow(schedule)
    if not config.get("always_on") and not in_window(datetime.now(), config["start"], config["end"]):
        return False
    if not schedules_allow(config):
        return False
    return True


def request_stop(_signum, _frame):
    global STOP
    STOP = True


def wait_or_stop(seconds, config):
    deadline = time.monotonic() + seconds
    while not STOP and time.monotonic() < deadline:
        if not allowed_now(config):
            return
        time.sleep(min(1, max(0, deadline - time.monotonic())))


def set_output(enabled: bool, display: str):
    """Toggle Wayland output via wlr-randr; best-effort, never crash signage."""
    try:
        cmd=["wlr-randr","--output",display,"--on" if enabled else "--off"]
        env=dict(os.environ)
        env.setdefault("XDG_RUNTIME_DIR","/run/user/1000")
        env.setdefault("WAYLAND_DISPLAY","wayland-0")
        result = subprocess.run(cmd, env=env, timeout=5, capture_output=True, text=True)
        if result.returncode:
            LOG.error("Output command failed: %s", result.stderr)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        LOG.exception("Output command unavailable")
        return False

def mpv_time_pos(sock_path=None):
    """Ask the running mpv for its playback position; None if unavailable."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            sock.connect(sock_path or IPC_SOCKET)
            sock.sendall(b'{"command":["get_property","time-pos"]}\n')
            buffer = b""
            while buffer.count(b"\n") < 8:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                for line in buffer.split(b"\n")[:-1]:  # complete lines only
                    reply = json.loads(line)
                    if "error" in reply:  # events carry "event", the reply carries "error"
                        value = reply.get("data")
                        ok = reply["error"] == "success" and isinstance(value, (int, float))
                        return float(value) if ok else None
    except (OSError, ValueError, AttributeError):
        pass
    return None


def play(path, config, loop_playlist=None):
    """Play one file. With loop_playlist (the single-item list), mpv loops the
    file itself and we restart only when the playlist or schedule changes."""
    LOG.info("Playing %s", path.name)
    loop = loop_playlist is not None
    process = subprocess.Popen(command_for(path, config, loop=loop), start_new_session=True)
    replaced = False
    last_check = last_poll = last_move = time.monotonic()
    last_pos = None
    try:
        while process.poll() is None and not STOP:
            if not allowed_now(config):
                break
            now = time.monotonic()
            if now - last_poll >= 5:
                last_poll = now
                pos = mpv_time_pos()
                if pos is None or pos != last_pos:
                    last_pos, last_move = pos, now
                elif now - last_move >= STALL_SECONDS:
                    LOG.error("mpv position frozen at %.1fs for %ss; killing hung player", pos, STALL_SECONDS)
                    break
            if loop and time.monotonic() - last_check >= 5:
                last_check = time.monotonic()
                if playlist_files(config) != loop_playlist:
                    LOG.info("Playlist changed; restarting player")
                    replaced = True
                    break
            time.sleep(1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        LOG.info("mpv exited with code %s", process.returncode)
    return 0 if replaced else process.returncode


def run(config):
    hdmi_on = None
    next_output_try = 0.0
    failures, blocked = {}, {}
    while not STOP:
        wanted = allowed_now(config)
        # Only touch the output when its state must change; retry failures at most every 30 s.
        if hdmi_on is not wanted and time.monotonic() >= next_output_try:
            if set_output(wanted, config["display"]):
                hdmi_on = wanted
            else:
                next_output_try = time.monotonic() + 30
        if not wanted:
            time.sleep(1)
            continue
        all_files = playlist_files(config)
        if not all_files:
            LOG.warning("No media in %s", config["media_dir"])
            wait_or_stop(30, config)
            continue
        files = [p for p in all_files if blocked.get(p, 0) <= time.monotonic()]
        if not files:
            LOG.warning("All playlist items are temporarily set aside after repeated failures")
            wait_or_stop(30, config)
            continue
        for path in files:
            if STOP or not allowed_now(config):
                break
            started = time.monotonic()
            try:
                code = play(path, config, all_files if len(all_files) == 1 else None)
            except OSError:
                LOG.exception("Unable to start mpv")
                code = 1
            real_failure = bool(code) and not STOP and allowed_now(config)
            if real_failure:
                LOG.warning("Playback failed for %s", path.name)
            if real_failure and time.monotonic() - started < FAST_FAIL_SECONDS:
                failures[path] = failures.get(path, 0) + 1
                if failures[path] >= FAIL_LIMIT:
                    blocked[path] = time.monotonic() + BLOCK_SECONDS
                    failures.pop(path)
                    LOG.error("Setting %s aside for %ss after %s quick failures", path.name, BLOCK_SECONDS, FAIL_LIMIT)
            elif not code:
                failures.pop(path, None)
            # Avoid spinning on a corrupt file or an mpv/DRM startup failure.
            if time.monotonic() - started < config["retry_seconds"]:
                wait_or_stop(config["retry_seconds"], config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("/etc/pi5-signage.json"))
    parser.add_argument("--check", action="store_true", help="validate config and list media")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    if not args.check:
        resolve_profile_name({}, detect_device_model())
    if args.check:
        print(f"Display: {config['display']}; files: {[p.name for p in playlist_files(config)]}")
        return
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    run(config)


if __name__ == "__main__":
    main()
