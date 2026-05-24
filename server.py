import os
import sys
import json
import socket
import subprocess
import shutil
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time
import threading
from datetime import datetime, timezone, timedelta

# Directory settings
if os.path.exists('/home/pi'):
    VIDEO_DIR_1 = '/home/pi/museum_video/layar1'
    VIDEO_DIR_2 = '/home/pi/museum_video/layar2'
    SOCK_1 = '/tmp/mpv-layar1.sock'
    SOCK_2 = '/tmp/mpv-layar2.sock'
    IS_PI = True
else:
    # Local Windows fallback for testing
    VIDEO_DIR_1 = os.path.join(os.getcwd(), 'mock_museum_video', 'layar1')
    VIDEO_DIR_2 = os.path.join(os.getcwd(), 'mock_museum_video', 'layar2')
    SOCK_1 = '\\\\.\\pipe\\mpv-layar1'  # Named pipe or mocked socket
    SOCK_2 = '\\\\.\\pipe\\mpv-layar2'
    IS_PI = False

SCHEDULES_FILE = os.path.join(os.path.dirname(__file__), 'public', 'schedules.json')
PLAYLISTS_FILE = os.path.join(os.path.dirname(__file__), 'public', 'playlists.json')

# Ensure video directories exist
os.makedirs(VIDEO_DIR_1, exist_ok=True)
os.makedirs(VIDEO_DIR_2, exist_ok=True)

def init_json_files():
    if not os.path.exists(SCHEDULES_FILE):
        default_schedules = {"timezone_offset": 7, "events": []}
        with open(SCHEDULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_schedules, f, indent=2)
            
    if not os.path.exists(PLAYLISTS_FILE):
        default_playlists = {
            "screen1": {"Default": []},
            "screen2": {"Default": []}
        }
        with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_playlists, f, indent=2)

init_json_files()

# Generate default playlist if it doesn't exist
def init_playlist_file(video_dir):
    playlist_path = os.path.join(video_dir, 'playlist.txt')
    if not os.path.exists(playlist_path):
        update_playlist_file(video_dir)

def update_playlist_file(video_dir):
    playlist_path = os.path.join(video_dir, 'playlist.txt')
    # List all MP4 and common video files, excluding playlist.txt itself
    valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm')
    files = [f for f in os.listdir(video_dir) if f.lower().endswith(valid_exts)]
    files.sort()  # Alphabetical by default
    
    with open(playlist_path, 'w', encoding='utf-8') as pf:
        for f in files:
            # mpv requires absolute paths or paths relative to execution
            pf.write(os.path.join(video_dir, f) + '\n')
    return files

init_playlist_file(VIDEO_DIR_1)
init_playlist_file(VIDEO_DIR_2)


# --- MPV IPC helpers ---
def send_mpv_command(sock_path, command_args):
    """Send JSON-IPC command to MPV Unix domain socket."""
    if not IS_PI:
        # Mock responses on Windows
        return {"data": f"Mock MPV command {command_args} received", "error": None}
        
    if not os.path.exists(sock_path):
        return {"error": "Socket not found"}
        
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(sock_path)
        payload = json.dumps({"command": command_args}) + "\n"
        s.sendall(payload.encode('utf-8'))
        
        # Read response line
        response = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
            if b"\n" in chunk:
                break
        s.close()
        
        lines = response.decode('utf-8').strip().split('\n')
        if lines:
            return json.loads(lines[0])
        return {"error": "No response"}
    except Exception as e:
        return {"error": str(e)}

# --- Background Schedule Worker ---
def check_schedules():
    while True:
        try:
            with open(SCHEDULES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            tz_offset = data.get("timezone_offset", 7)
            tz = timezone(timedelta(hours=tz_offset))
            now = datetime.now(tz)
            
            curr_time = now.strftime("%H:%M")
            # Locale-independent mapping
            days_map = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
            curr_day = days_map[now.weekday()]
            
            changed = False
            
            for event in data.get("events", []):
                if not event.get("enabled", True):
                    continue
                    
                if event.get("time") == curr_time and curr_day in event.get("days", []):
                    last_triggered = event.get("_last_triggered", "")
                    # Prevent re-triggering in the same minute
                    if last_triggered == now.strftime("%Y-%m-%d %H:%M"):
                        continue
                        
                    event["_last_triggered"] = now.strftime("%Y-%m-%d %H:%M")
                    changed = True
                    print(f"[Schedule] Triggering Event {event.get('id')} - {event.get('type')}")
                    
                    if event.get("type") == "power":
                        action = event.get("action")
                        if action == "sleep":
                            if IS_PI: subprocess.run("sudo -u pi XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 wlr-randr --output HDMI-A-1 --off --output HDMI-A-2 --off", shell=True)
                        elif action == "wake":
                            if IS_PI: 
                                subprocess.run("sudo -u pi XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 wlr-randr --output HDMI-A-1 --on --output HDMI-A-2 --on", shell=True)
                                time.sleep(2)
                                subprocess.run("sudo systemctl restart layar1.service layar2.service", shell=True)
                                
                    elif event.get("type") == "playlist":
                        screen = int(event.get("screen", 1))
                        playlist_name = event.get("playlist_name", "Default")
                        
                        try:
                            with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as pf:
                                pl_data = json.load(pf)
                            screen_key = f"screen{screen}"
                            files = pl_data.get(screen_key, {}).get(playlist_name, [])
                            
                            upload_dir = VIDEO_DIR_1 if screen == 1 else VIDEO_DIR_2
                            playlist_path = os.path.join(upload_dir, 'playlist.txt')
                            
                            with open(playlist_path, 'w', encoding='utf-8') as pt:
                                for fname in files:
                                    f_path = os.path.join(upload_dir, fname)
                                    if os.path.exists(f_path):
                                        pt.write(f_path + '\n')
                                        
                            sock_path = SOCK_1 if screen == 1 else SOCK_2
                            if IS_PI and os.path.exists(sock_path):
                                send_mpv_command(sock_path, ["loadlist", playlist_path])
                                
                        except Exception as e:
                            print(f"[Schedule] Playlist error: {e}")
                            
            if changed:
                with open(SCHEDULES_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                
        except Exception as e:
            pass # Suppress file read/write errors if they occur concurrently
            
        time.sleep(30)

schedule_thread = threading.Thread(target=check_schedules, daemon=True)
schedule_thread.start()


# --- System resource metrics (Linux/Pi) ---
def get_system_stats():
    if not IS_PI:
        return {
            "cpu_temp": 42.5,
            "cpu_percent": 12.4,
            "ram": {"total_mb": 4096.0, "used_mb": 1024.0, "percent": 25.0},
            "disk": {"total_gb": 32.0, "used_gb": 8.0, "percent": 25.0},
            "uptime": "1d 2h 3m"
        }
        
    stats = {}
    
    # 1. CPU Temp
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            stats["cpu_temp"] = round(int(f.readline().strip()) / 1000.0, 1)
    except Exception:
        stats["cpu_temp"] = 0.0
        
    # 2. CPU Usage (from /proc/stat)
    try:
        with open('/proc/stat', 'r') as f:
            line = f.readline()
        parts = line.strip().split()
        if len(parts) >= 5:
            user, nice, sys_mode, idle = map(int, parts[1:5])
            total = user + nice + sys_mode + idle
            time.sleep(0.1)
            with open('/proc/stat', 'r') as f:
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
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal:' in line:
                    total_mem = int(line.split()[1])
                elif 'MemAvailable:' in line:
                    avail_mem = int(line.split()[1])
        if total_mem > 0:
            used_mem = total_mem - avail_mem
            stats["ram"] = {
                "total_mb": round(total_mem / 1024.0, 0),
                "used_mb": round(used_mem / 1024.0, 0),
                "percent": round((used_mem / total_mem) * 100, 1)
            }
        else:
            stats["ram"] = {"total_mb": 0, "used_mb": 0, "percent": 0.0}
    except Exception:
        stats["ram"] = {"total_mb": 0, "used_mb": 0, "percent": 0.0}
        
    # 4. Disk Usage
    try:
        total, used, free = shutil.disk_usage('/')
        stats["disk"] = {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "percent": round((used / total) * 100, 1)
        }
    except Exception:
        stats["disk"] = {"total_gb": 0, "used_gb": 0, "percent": 0.0}
        
    # 5. Uptime
    try:
        with open('/proc/uptime', 'r') as f:
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
        res = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
        return res.stdout.strip()
    except Exception:
        return "inactive"


# --- Custom Multipart Parser for streaming upload ---
def parse_multipart_upload(rfile, content_length, boundary, upload_dir):
    boundary_bytes = b'--' + boundary.encode('utf-8')
    
    # Read first line - should be boundary
    line = rfile.readline()
    if boundary_bytes not in line:
        return False, "Boundary mismatch"
        
    filename = None
    # Parse headers of the part
    while True:
        line = rfile.readline().strip()
        if not line:
            break
        if b'Content-Disposition:' in line:
            parts = line.decode('utf-8', errors='ignore').split(';')
            for p in parts:
                if 'filename=' in p:
                    filename = p.split('=')[1].strip(' "')
                    break
                    
    if not filename:
        return False, "Filename not found in form data"
        
    filename = os.path.basename(filename)
    dest_path = os.path.join(upload_dir, filename)
    
    # Read payload and stream to disk
    buffer = b""
    chunk_size = 65536
    remaining = content_length - len(line) - len(boundary_bytes)
    
    with open(dest_path, 'wb') as f:
        while True:
            chunk = rfile.read(min(chunk_size, max(0, remaining)))
            if not chunk:
                break
            remaining -= len(chunk)
            buffer += chunk
            
            # Look for boundary
            idx = buffer.find(boundary_bytes)
            if idx != -1:
                # Boundary found. Write data up to boundary (excluding trailing CRLF)
                data_to_write = buffer[:idx]
                if data_to_write.endswith(b'\r\n'):
                    data_to_write = data_to_write[:-2]
                f.write(data_to_write)
                break
            else:
                # Keep buffer overlap padding
                keep = len(boundary_bytes) + 8
                if len(buffer) > keep:
                    write_len = len(buffer) - keep
                    f.write(buffer[:write_len])
                    buffer = buffer[write_len:]
                    
    return True, filename


# --- HTTP Request Handler ---
class SignageRequestHandler(BaseHTTPRequestHandler):

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        
        # --- API Endpoints ---
        if path == '/api/status':
            self.handle_api_status()
            return
            
        elif path == '/api/screenshot':
            self.handle_api_screenshot(query)
            return
            
        elif path == '/api/audio/config':
            self.handle_api_audio_config()
            return
            
        elif path == '/api/schedule/config':
            self.handle_api_schedule_config()
            return
            
        elif path == '/api/playlists/list':
            self.handle_api_playlists_list()
            return

        # --- Static Files Router ---
        if path == '/':
            path = '/index.html'
            
        # Locate static files inside the 'public' subfolder
        local_base = os.path.join(os.path.dirname(__file__), 'public')
        target_file = os.path.abspath(os.path.join(local_base, path.lstrip('/')))
        
        # Security check to prevent directory traversal
        if not target_file.startswith(local_base):
            self.send_error(403, "Access Forbidden")
            return
            
        if os.path.exists(target_file) and os.path.isfile(target_file):
            self.send_response(200)
            self.send_cors_headers()
            
            # Content-Type Header
            if target_file.endswith('.html'):
                self.send_header('Content-Type', 'text/html')
            elif target_file.endswith('.css'):
                self.send_header('Content-Type', 'text/css')
            elif target_file.endswith('.js'):
                self.send_header('Content-Type', 'application/javascript')
            elif target_file.endswith('.json'):
                self.send_header('Content-Type', 'application/json')
            elif target_file.endswith('.png'):
                self.send_header('Content-Type', 'image/png')
            elif target_file.endswith('.jpg') or target_file.endswith('.jpeg'):
                self.send_header('Content-Type', 'image/jpeg')
            else:
                self.send_header('Content-Type', 'application/octet-stream')
                
            self.end_headers()
            with open(target_file, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == '/api/control':
            self.handle_api_control()
        elif path == '/api/upload':
            self.handle_api_upload()
        elif path == '/api/delete':
            self.handle_api_delete()
        elif path == '/api/playlist/save':
            self.handle_api_playlist_save()
        elif path == '/api/audio/global':
            self.handle_api_audio_global()
        elif path == '/api/audio/clip':
            self.handle_api_audio_clip()
        elif path == '/api/schedule/save':
            self.handle_api_schedule_save()
        elif path == '/api/playlists/save_all':
            self.handle_api_playlists_save_all()
        elif path == '/api/system/shutdown':
            self.handle_api_system_shutdown()
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
                    time_pos = round(pos_res.get("data", 0), 1) if pos_res.get("error") == "success" else 0
                    
                    dur_res = send_mpv_command(sock_path, ["get_property", "duration"])
                    duration = round(dur_res.get("data", 0), 1) if dur_res.get("error") == "success" else 0
                    
                    pause_res = send_mpv_command(sock_path, ["get_property", "pause"])
                    paused = pause_res.get("data", False) if pause_res.get("error") == "success" else False

                    # Keep audio device output path and channel mode in sync
                    config_path = os.path.join(os.path.dirname(__file__), 'public', 'audio_config.json')
                    if os.path.exists(config_path):
                        try:
                            with open(config_path, 'r', encoding='utf-8') as f:
                                cfg_data = json.load(f)
                                scr_cfg = cfg_data.get(f"screen{screen_num}")
                                if scr_cfg:
                                    dev = scr_cfg.get("output_device", "hdmi")
                                    dev_str = 'alsa/plughw:CARD=Headphones,DEV=0' if dev == 'jack' else f'alsa/plughw:CARD=vc4hdmi{screen_num-1},DEV=0'
                                    send_mpv_command(sock_path, ["set_property", "audio-device", dev_str])
                                    
                                    chan_mode = scr_cfg.get("channel_mode", "stereo")
                                    if chan_mode == "left":
                                        af_filter = "lavfi=[pan=stereo|c0=c0|c1=0*c1]"
                                    elif chan_mode == "right":
                                        af_filter = "lavfi=[pan=stereo|c0=0*c0|c1=c1]"
                                    else:
                                        af_filter = ""
                                    send_mpv_command(sock_path, ["set_property", "af", af_filter])
                        except Exception:
                            pass
            elif not IS_PI:
                # Windows Mock
                mpv_active = True
                playing_file = "mock_video_A.mp4"
                time_pos = 45.2
                duration = 120.0
                paused = False
                
            # Read files in directory
            valid_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm')
            all_files = [f for f in os.listdir(video_dir) if f.lower().endswith(valid_exts)]
            
            # Get actual playlist order from playlist.txt
            playlist_path = os.path.join(video_dir, 'playlist.txt')
            playlist_order = []
            if os.path.exists(playlist_path):
                with open(playlist_path, 'r', encoding='utf-8') as pf:
                    for line in pf:
                        f_path = line.strip()
                        if f_path:
                            fname = os.path.basename(f_path)
                            if fname in all_files:
                                playlist_order.append(fname)
            
            # Append any files that are on disk but not in playlist.txt
            for f in all_files:
                if f not in playlist_order:
                    playlist_order.append(f)
                    
            # Get file sizes
            files_data = []
            for f in playlist_order:
                f_path = os.path.join(video_dir, f)
                size_mb = round(os.path.getsize(f_path) / (1024 * 1024), 1) if os.path.exists(f_path) else 0
                files_data.append({"name": f, "size_mb": size_mb})

            return {
                "service_active": status == "active",
                "mpv_connected": mpv_active,
                "playing_file": playing_file,
                "time_pos": time_pos,
                "duration": duration,
                "paused": paused,
                "playlist": files_data,
                "all_files": all_files
            }

        screen1 = get_screen_data(1, VIDEO_DIR_1, SOCK_1, "layar-gabungan.service")
        screen2 = get_screen_data(2, VIDEO_DIR_2, SOCK_2, "layar-gabungan.service")
        
        # Load audio configuration to merge into status payload
        audio_cfg = {}
        config_path = os.path.join(os.path.dirname(__file__), 'public', 'audio_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    audio_cfg = json.load(f)
            except Exception:
                pass
                
        response_data = {
            "system": sys_stats,
            "screen1": screen1,
            "screen2": screen2,
            "audio": audio_cfg
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def handle_api_control(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            screen = int(params.get('screen', 1))
            action = params.get('action', '') # play, pause, next, prev, restart_service, stop_service, start_service
            
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            service_name = "layar-gabungan.service"
            
            res = {"success": True, "message": "Command processed"}
            
            if action == 'play':
                send_mpv_command(sock_path, ["set_property", "pause", False])
            elif action == 'pause':
                send_mpv_command(sock_path, ["set_property", "pause", True])
            elif action == 'next':
                send_mpv_command(sock_path, ["playlist-next"])
            elif action == 'prev':
                send_mpv_command(sock_path, ["playlist-prev"])
            elif action in ['restart_service', 'stop_service', 'start_service']:
                if IS_PI:
                    cmd_type = action.split('_')[0] # restart, stop, start
                    # Executing service command via sudo
                    # We pipe the password 'pi' to sudo
                    cmd = f"echo pi | sudo -S systemctl {cmd_type} {service_name}"
                    subprocess.run(cmd, shell=True, capture_output=True)
                    res["message"] = f"Service {service_name} {cmd_type}ed"
                else:
                    res["message"] = f"Mocked {action} on Windows"
            else:
                res = {"success": False, "error": f"Unknown action: {action}"}
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error processing control: {e}")

    def handle_api_upload(self):
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_error(400, "Content-Type must be multipart/form-data")
            return
            
        boundary = content_type.split('boundary=')[1].strip()
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Get query parameters to know which screen folder to upload to
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)
        screen = int(query.get('screen', [1])[0])
        
        upload_dir = VIDEO_DIR_1 if screen == 1 else VIDEO_DIR_2
        
        success, info = parse_multipart_upload(self.rfile, content_length, boundary, upload_dir)
        
        if success:
            # Rebuild playlist.txt automatically to include the new file
            update_playlist_file(upload_dir)
            
            # Reload playlist in mpv if active
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            playlist_path = os.path.join(upload_dir, 'playlist.txt')
            if IS_PI and os.path.exists(sock_path):
                # mpv command to reload playlist
                send_mpv_command(sock_path, ["loadlist", playlist_path])
                
            res = {"success": True, "filename": info}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        else:
            self.send_error(500, f"Upload failed: {info}")

    def handle_api_delete(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            screen = int(params.get('screen', 1))
            filename = params.get('filename', '')
            
            if not filename:
                self.send_error(400, "Filename parameter missing")
                return
                
            upload_dir = VIDEO_DIR_1 if screen == 1 else VIDEO_DIR_2
            target_path = os.path.abspath(os.path.join(upload_dir, filename))
            
            # Security check
            if not target_path.startswith(upload_dir):
                self.send_error(403, "Access Forbidden")
                return
                
            res = {"success": False, "error": "File not found"}
            if os.path.exists(target_path):
                os.remove(target_path)
                # Re-sync playlist.txt file
                update_playlist_file(upload_dir)
                
                # Force reload playlist in MPV if running
                sock_path = SOCK_1 if screen == 1 else SOCK_2
                playlist_path = os.path.join(upload_dir, 'playlist.txt')
                if IS_PI and os.path.exists(sock_path):
                    send_mpv_command(sock_path, ["loadlist", playlist_path])
                    
                res = {"success": True, "message": "File deleted"}
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error deleting file: {e}")

    def handle_api_playlist_save(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            screen = int(params.get('screen', 1))
            filenames = params.get('playlist', []) # List of filenames in desired order
            
            upload_dir = VIDEO_DIR_1 if screen == 1 else VIDEO_DIR_2
            playlist_path = os.path.join(upload_dir, 'playlist.txt')
            
            # Write new playlist.txt with complete paths in specified order
            with open(playlist_path, 'w', encoding='utf-8') as pf:
                for fname in filenames:
                    # Clean filename path traversal
                    fname_clean = os.path.basename(fname)
                    f_path = os.path.join(upload_dir, fname_clean)
                    if os.path.exists(f_path):
                        pf.write(f_path + '\n')
            
            # Send reload to MPV
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            if IS_PI and os.path.exists(sock_path):
                send_mpv_command(sock_path, ["loadlist", playlist_path])
                
            res = {"success": True, "message": "Playlist order saved and applied"}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error saving playlist: {e}")

    def handle_api_screenshot(self, query):
        screen = int(query.get('screen', [1])[0])
        sock_path = SOCK_1 if screen == 1 else SOCK_2
        
        # Temp preview path
        preview_path = f"/tmp/layar{screen}-preview.jpg" if IS_PI else os.path.join(os.getcwd(), f"mock-preview-{screen}.jpg")
        
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
            self.send_header('Content-Type', 'image/jpeg')
            self.send_cors_headers()
            self.end_headers()
            with open(preview_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            # Serve a fallback placeholder if screenshot is not ready/unsupported
            fallback_img = os.path.join(os.path.dirname(__file__), 'public', 'placeholder.jpg')
            if os.path.exists(fallback_img):
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_cors_headers()
                self.end_headers()
                with open(fallback_img, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Preview not available")

    def handle_api_audio_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'public', 'audio_config.json')
        if not os.path.exists(config_path):
            default_config = {
                "screen1": {"global_mute": True, "output_device": "hdmi", "channel_mode": "stereo", "clip_settings": {}},
                "screen2": {"global_mute": True, "output_device": "hdmi", "channel_mode": "stereo", "clip_settings": {}}
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
                
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def handle_api_audio_global(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            screen = int(params.get('screen', 1))
            global_mute = params.get('global_mute', True)
            output_device = params.get('output_device', 'hdmi')
            channel_mode = params.get('channel_mode', 'stereo')
            
            config_path = os.path.join(os.path.dirname(__file__), 'public', 'audio_config.json')
            with open(config_path, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                screen_key = f"screen{screen}"
                if screen_key in data:
                    data[screen_key]["global_mute"] = global_mute
                    data[screen_key]["output_device"] = output_device
                    data[screen_key]["channel_mode"] = channel_mode
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
            
            # Update MPV directly
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            send_mpv_command(sock_path, ["set_property", "mute", global_mute])
            
            if output_device == 'jack':
                device_str = 'alsa/plughw:CARD=Headphones,DEV=0'
            else:
                device_str = f'alsa/plughw:CARD=vc4hdmi{screen-1},DEV=0'
            send_mpv_command(sock_path, ["set_property", "audio-device", device_str])
            
            # Sync channel mode (af filter)
            if channel_mode == "left":
                af_filter = "lavfi=[pan=stereo|c0=c0|c1=0*c1]"
            elif channel_mode == "right":
                af_filter = "lavfi=[pan=stereo|c0=0*c0|c1=c1]"
            else:
                af_filter = ""
            send_mpv_command(sock_path, ["set_property", "af", af_filter])
            
            res = {"success": True, "message": "Global audio settings updated"}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error processing global audio: {e}")

    def handle_api_audio_clip(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            params = json.loads(post_data)
            screen = int(params.get('screen', 1))
            filename = params.get('filename', '')
            mute = params.get('mute', False)
            
            if not filename:
                self.send_error(400, "Filename missing")
                return
                
            config_path = os.path.join(os.path.dirname(__file__), 'public', 'audio_config.json')
            with open(config_path, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                screen_key = f"screen{screen}"
                if screen_key in data:
                    if "clip_settings" not in data[screen_key]:
                        data[screen_key]["clip_settings"] = {}
                    data[screen_key]["clip_settings"][filename] = {"mute": mute}
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
                
            # If currently playing this file, apply mute state
            sock_path = SOCK_1 if screen == 1 else SOCK_2
            filename_res = send_mpv_command(sock_path, ["get_property", "filename"])
            if filename_res.get("error") == "success" and filename_res.get("data") == filename:
                global_mute = data[screen_key]["global_mute"]
                send_mpv_command(sock_path, ["set_property", "mute", global_mute or mute])
                
            res = {"success": True, "message": "Clip audio setting updated"}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error processing clip audio: {e}")

    def handle_api_schedule_config(self):
        try:
            with open(SCHEDULES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))
            
    def handle_api_schedule_save(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            params = json.loads(post_data)
            # Basic conflict checking can be done here or in UI. We'll rely on UI for now or just save it.
            with open(SCHEDULES_FILE, 'w', encoding='utf-8') as f:
                json.dump(params, f, indent=2)
            
            res = {"success": True, "message": "Schedule saved"}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))
            
    def handle_api_playlists_list(self):
        try:
            with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))
            
    def handle_api_playlists_save_all(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            params = json.loads(post_data)
            with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(params, f, indent=2)
                
            res = {"success": True, "message": "Playlists saved"}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(res).encode('utf-8'))
        except Exception as e:
            self.send_error(500, str(e))

    def handle_api_system_shutdown(self):
        res = {"success": True, "message": "System is shutting down"}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(res).encode('utf-8'))
        
        # Shutdown after responding
        def run_shutdown():
            time.sleep(1)
            if IS_PI:
                subprocess.run("sudo shutdown -h now", shell=True)
        threading.Thread(target=run_shutdown, daemon=True).start()

def run_server(port=8080):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, SignageRequestHandler)
    print(f"Museum Signage CMS Backend serving on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    port = 8080
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run_server(port)
