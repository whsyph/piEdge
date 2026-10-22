#!/usr/bin/env python3
"""Small scheduled mpv supervisor for a single Raspberry Pi Wayland output."""
import argparse
from drm_power import PowerLease
import os
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
POWER_LEASE = None
MEDIA_PROBES = {}
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
def cms_audio(path, config):
    """Resolve CMS audio preferences at each launch; keep config audio safety gate."""
    result = {"mute": not config.get("audio", False),
              "device": config.get("audio_device", "alsa/sysdefault:CARD=vc4hdmi0"),
              "filter": ""}
    try:
        source = Path(config.get("schedules_file", "/home/pi/museum_signage/public/schedules.json")).with_name("audio_config.json")
        data = json.loads(source.read_text())
        audio = data.get(config.get("playlist_screen", "screen1"), {})
        global_mute = audio.get("global_mute", result["mute"])
        clip_mute = audio.get("clip_settings", {}).get(Path(path).name, {}).get("mute", False)
        if not isinstance(global_mute, bool) or not isinstance(clip_mute, bool):
            raise ValueError("Mute must be boolean")
        route = audio.get("output_device", "hdmi")
        channel = audio.get("channel_mode", "stereo")
        if route not in ("hdmi", "jack") or channel not in ("stereo", "left", "right"):
            raise ValueError("Invalid audio route/channel")
        result["mute"] = result["mute"] or global_mute or clip_mute
        result["device"] = "alsa/sysdefault:CARD=Headphones" if route == "jack" else "alsa/sysdefault:CARD=vc4hdmi0"
        result["filter"] = {"stereo": "", "left": "lavfi=[pan=stereo|c0=c0|c1=0*c1]", "right": "lavfi=[pan=stereo|c0=0*c0|c1=c1]"}[channel]
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return result


def command_for(path, config):
    audio = cms_audio(path, config)
    command = [
        "mpv", "--no-config", "--vo=gpu", "--gpu-context=drm",
        "--gpu-hwdec-interop=drmprime-overlay", "--hwdec=drm", "--hwdec-codecs=hevc",
        "--hwdec-extra-frames=32", "--drm-device=" + config["drm_device"],
        "--drm-connector=" + config["display"], "--drm-mode=" + config["drm_mode"],
        "--drm-draw-plane=overlay", "--drm-drmprime-video-plane=primary",
        "--drm-draw-surface-size=1920x1080", "--profile=fast",
        "--video-sync=audio", "--framedrop=vo", "--no-osc", "--osd-level=0",
        "--no-border", "--fullscreen", "--keep-open=no", "--no-input-default-bindings",
        "--msg-level=all=info", "--term-status-msg=", "--title=capibarra-pi4-drm",
        "--input-ipc-server=/run/user/1000/capibarra-mpv.sock",
        "--mute=" + ("yes" if audio["mute"] else "no"),
        "--audio-device=" + audio["device"],
    ]
    if audio["filter"]:
        command.append("--af=" + audio["filter"])
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
    if config.get("renderer") != "drm-overlay":
        raise ValueError("This Pi4 profile requires renderer=drm-overlay")
    if not __import__("re").fullmatch(r"/dev/dri/card[0-9]+", config.get("drm_device", "")):
        raise ValueError("Invalid drm_device")
    if not __import__("re").fullmatch(r"[0-9]+x[0-9]+@[0-9]+(?:[.][0-9]+)?", config.get("drm_mode", "")):
        raise ValueError("Invalid drm_mode")
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
def operation_mode(config):
    try:
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        path = Path(config.get("schedules_file", "/home/pi/museum_signage/public/schedules.json")).with_name("operation_mode.json")
        data = json.loads(path.read_text())
        mode = data.get("mode")
        return mode if data.get("boot_id") == boot and mode in ("auto", "on", "off") else "auto"
    except (OSError, ValueError, AttributeError, TypeError):
        return "auto"

def allowed_now(config):
    mode = operation_mode(config)
    if mode != "auto":
        return mode == "on"
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
def release_output_lease():
    global POWER_LEASE
    if POWER_LEASE is not None:
        lease, POWER_LEASE = POWER_LEASE, None
        try:
            lease.set_enabled(True)
        finally:
            lease.close()


def set_output(enabled, config):
    """Retain DRM master while asleep; release it before mpv takes the connector."""
    global POWER_LEASE
    try:
        if enabled:
            if POWER_LEASE is not None:
                release_output_lease()
            else:
                lease = PowerLease(config["drm_device"], config["display"])
                try:
                    lease.set_enabled(True)
                finally:
                    lease.close()
        else:
            if POWER_LEASE is None:
                POWER_LEASE = PowerLease(config["drm_device"], config["display"])
            POWER_LEASE.set_enabled(False)
        return True
    except (OSError, ValueError, RuntimeError, KeyError):
        LOG.exception("DRM output power operation failed")
        if POWER_LEASE is not None:
            POWER_LEASE.close()
            POWER_LEASE = None
        return False


def playable_media(path):
    """This hardware-plane profile accepts HEVC, not arbitrary software-decoded uploads."""
    try:
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns)
        if key not in MEDIA_PROBES:
            result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                     "-show_entries", "stream=codec_name", "-of", "json", str(path)],
                                    capture_output=True, text=True, timeout=8)
            data = json.loads(result.stdout) if result.returncode == 0 else {}
            MEDIA_PROBES[key] = bool(data.get("streams")) and data["streams"][0].get("codec_name") == "hevc"
        if not MEDIA_PROBES[key]:
            LOG.error("Unsupported media for Pi4 DRM profile (HEVC required): %s", path.name)
        return MEDIA_PROBES[key]
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyError, TypeError):
        LOG.exception("Unable to probe media %s", path)
        return False

def play(path, config):
    LOG.info("Playing %s", path.name)
    process = subprocess.Popen(command_for(path, config), start_new_session=False)
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
    hdmi_on = None
    while not STOP:
        if not allowed_now(config):
            if hdmi_on is not False:
                if set_output(False, config):
                    hdmi_on = False
            time.sleep(1)
            continue
        if hdmi_on is not True:
            if not set_output(True, config):
                wait_or_stop(config["retry_seconds"], config)
                continue
            hdmi_on = True
        files = [path for path in playlist_files(config) if playable_media(path)]
        if not files:
            LOG.warning("No supported HEVC media in assigned playlist")
            wait_or_stop(10, config)
            continue
        for path in files:
            if STOP or not allowed_now(config):
                break
            started = time.monotonic()
            try:
                code = play(path, config)
            except OSError:
                LOG.exception("Unable to start DRM mpv")
                code = 1
            if code and not STOP and allowed_now(config):
                LOG.warning("Playback failed for %s", path.name)
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
    try:
        run(config)
    finally:
        release_output_lease()
if __name__ == "__main__":
    main()
