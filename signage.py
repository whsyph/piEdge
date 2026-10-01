#!/usr/bin/env python3
"""Small scheduled mpv supervisor for a single Raspberry Pi Wayland output."""

import argparse
import json
import logging
import signal
import subprocess
import time
from datetime import datetime, time as clock_time, timedelta, timezone
from pathlib import Path

LOG = logging.getLogger("pi5-signage")
EXTENSIONS = {".mp4", ".mkv", ".mov"}
STOP = False


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


def command_for(path, config):
    command = [
        "mpv", "--vo=dmabuf-wayland", "--hwdec=auto-safe",
        "--hwdec-codecs=hevc,h264,vp9,av1", "--hwdec-extra-frames=16",
        "--msg-level=all=info",
        "--term-status-msg=",
        "--video-sync=audio", "--framedrop=vo", "--no-osc", "--osd-level=0",
        "--no-border", "--fullscreen", "--fs-screen=0", "--keep-open=no",
        "--no-input-default-bindings", "--wayland-app-id=capibarra",
    ]
    if config["audio"]:
        command.extend(["--audio-device", config["audio_device"]])
    else:
        command.append("--mute=yes")
    return command + ["--", str(path)]


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    config["media_dir"] = Path(config["media_dir"])
    config["start"] = parse_clock(config["start"])
    config["end"] = parse_clock(config["end"])
    if config["start"] == config["end"]:
        raise ValueError("start and end must differ")
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


def allowed_now(config):
    if not in_window(datetime.now(), config["start"], config["end"]):
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
        import subprocess
        subprocess.run(cmd, env=env, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def play(path, config):
    LOG.info("Playing %s", path.name)
    process = subprocess.Popen(command_for(path, config), start_new_session=True)
    try:
        while process.poll() is None and not STOP:
            if not allowed_now(config):
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
    return process.returncode


def run(config):
    hdmi_on=True
    while not STOP:
        if not allowed_now(config):
            if hdmi_on:
                set_output(False, config["display"])
                hdmi_on=False
            time.sleep(1)
            continue
        if not hdmi_on:
            set_output(True, config["display"])
            hdmi_on=True
        files = playlist_files(config)
        if not files:
            LOG.warning("No media in %s", config["media_dir"])
            wait_or_stop(30, config)
            continue
        for path in files:
            if STOP or not allowed_now(config):
                break
            started = time.monotonic()
            try:
                code = play(path, config)
            except OSError:
                LOG.exception("Unable to start VLC")
                code = 1
            if code and not STOP and allowed_now(config):
                LOG.warning("Playback failed for %s", path.name)
            # Avoid spinning on a corrupt file or a VLC/DRM startup failure.
            if time.monotonic() - started < config["retry_seconds"]:
                wait_or_stop(config["retry_seconds"], config)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("/etc/pi5-signage.json"))
    parser.add_argument("--check", action="store_true", help="validate config and list media")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    if args.check:
        print(f"Display: {config['display']}; files: {[p.name for p in playlist_files(config)]}")
        return
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    run(config)


if __name__ == "__main__":
    main()
