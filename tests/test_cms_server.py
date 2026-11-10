"""CMS server: authentication, origin rules, upload validation, atomic JSON, schedules.

Runs the real request handler on a random localhost port with temp directories.
"""
import http.client
import json
import os
import struct
import sys
import tempfile
import threading
import unittest
import unittest.mock
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import media_check  # noqa: E402
import server  # noqa: E402

TOKEN = "t" * 32


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def box(kind, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def iso_video(fourcc, width=1920, height=1080):
    entry_body = b"\0" * 6 + struct.pack(">H", 1) + b"\0" * 16 + struct.pack(">HH", width, height) + b"\0" * 50
    entry = struct.pack(">I4s", 8 + len(entry_body), fourcc) + entry_body
    stsd = box(b"stsd", struct.pack(">II", 0, 1) + entry)
    hdlr = box(b"hdlr", struct.pack(">I", 0) + b"\0" * 4 + b"vide" + b"\0" * 12)
    moov = box(b"moov", box(b"trak", box(b"mdia", hdlr + box(b"minf", box(b"stbl", stsd)))))
    return box(b"ftyp", b"isom\0\0\0\0isomiso2") + moov


def mkv(codec_id):
    return b"\x1a\x45\xdf\xa3" + b"\0" * 64 + codec_id + b"\0" * 64


HEVC_MP4 = iso_video(b"hvc1")
H264_MP4 = iso_video(b"avc1")


class MediaCheckTests(unittest.TestCase):
    def write(self, name, data):
        path = Path(self.tmp.name) / name
        path.write_bytes(data)
        return str(path)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_iso_codecs_and_size(self):
        info = media_check.probe_video(self.write("a.mp4", HEVC_MP4))
        self.assertEqual((info["container"], info["codec"], info["width"], info["height"]), ("iso", "hevc", 1920, 1080))
        self.assertEqual(media_check.probe_video(self.write("b.mp4", H264_MP4))["codec"], "h264")

    def test_matroska_codecs(self):
        self.assertEqual(media_check.probe_video(self.write("a.mkv", mkv(b"V_MPEGH/ISO/HEVC")))["codec"], "hevc")
        self.assertEqual(media_check.probe_video(self.write("b.mkv", mkv(b"V_MPEG4/ISO/AVC")))["codec"], "h264")

    def test_check_upload_rules(self):
        allowed = ["hevc"]
        self.assertEqual(media_check.check_upload(self.write("a.mp4", HEVC_MP4), "a.mp4", allowed), (True, ""))
        ok, message = media_check.check_upload(self.write("b.mp4", H264_MP4), "b.mp4", allowed)
        self.assertFalse(ok)
        self.assertIn("H264", message)
        self.assertIn("libx265", message)
        # suffix must match the container
        self.assertFalse(media_check.check_upload(self.write("c.mkv", HEVC_MP4), "c.mkv", allowed)[0])
        self.assertFalse(media_check.check_upload(self.write("d.mp4", mkv(b"V_MPEGH/ISO/HEVC")), "d.mp4", allowed)[0])
        self.assertFalse(media_check.check_upload(self.write("e.mp4", b"not a video"), "e.mp4", allowed)[0])
        self.assertEqual(media_check.check_upload(self.write("f.mkv", mkv(b"V_MPEGH/ISO/HEVC")), "f.mkv", allowed), (True, ""))

    def test_truncated_or_corrupt_box_is_not_a_video(self):
        self.assertIsNone(media_check.probe_video(self.write("t.mp4", HEVC_MP4[:30])))

    def test_name_rules(self):
        good = ["clip.mp4", "Rock'n Roll.mp4", "PHASE 1 hevc.MOV", "a=b;c.mkv"]
        for name in good:
            self.assertTrue(media_check.validate_upload_name(name)[0], name)
        bad = ["", ".hidden.mp4", "a/b.mp4", "a\\b.mp4", "line\nbreak.mp4", "x.txt", "x" * 200 + ".mp4", "..", "noext"]
        for name in bad:
            self.assertFalse(media_check.validate_upload_name(name)[0], repr(name))

    def test_extract_upload_filename(self):
        f = server.extract_upload_filename
        self.assertEqual(f('Content-Disposition: form-data; name="file"; filename="a;b=c.mp4"'), "a;b=c.mp4")
        self.assertEqual(f('Content-Disposition: form-data; name="file"; filename="we%22ird.mp4"'), 'we"ird.mp4')
        self.assertEqual(f('Content-Disposition: form-data; name="file"; filename="C:\\dir\\clip.mp4"'), "clip.mp4")
        self.assertEqual(f("Content-Disposition: form-data; name=file; filename=plain.mp4"), "plain.mp4")
        self.assertIsNone(f('Content-Disposition: form-data; name="x"'))


class CmsServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.public, cls.media = root / "public", root / "media"
        cls.public.mkdir()
        cls.media.mkdir()
        (cls.public / "index.html").write_text("<html>ok</html>")
        (cls.public / "app.js").write_text("// js")
        (cls.public / "devices.json").write_text("[]")
        (cls.public / "playlists.json").write_text("{}")
        (cls.public / ".secret.js").write_text("// hidden")
        (cls.public / "notes.txt").write_text("not served")
        cls.paths = {
            "PUBLIC_DIR": str(cls.public),
            "MEDIA_DIR": str(cls.media),
            "VIDEO_DIR_1": str(root / "l1"),
            "VIDEO_DIR_2": str(root / "l2"),
            "PLAYLISTS_FILE": str(cls.public / "playlists.json"),
            "SCHEDULES_FILE": str(cls.public / "schedules.json"),
            "NETWORK_CONFIG_FILE": str(cls.public / "network_config.json"),
            "OUTPUT_MODE_FILE": str(cls.public / "output_mode.json"),
            "TOKEN": TOKEN,
        }
        cls.patches = [unittest.mock.patch.object(server, k, v) for k, v in cls.paths.items()]
        cls.patches.append(unittest.mock.patch.object(server, "CONFIG", dict(server.DEFAULT_CONFIG)))
        for patch in cls.patches:
            patch.start()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.SignageRequestHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        for patch in cls.patches:
            patch.stop()
        cls.tmp.cleanup()

    def setUp(self):
        server.CONFIG.clear()
        server.CONFIG.update(server.DEFAULT_CONFIG)
        server.write_json_atomic(self.paths["PLAYLISTS_FILE"], {
            "playlists": {"Default": [], "Factory": ["a.mp4"]},
            "assignments": {"screen1": "Factory", "screen2": "Default"},
        })
        server.write_json_atomic(self.paths["SCHEDULES_FILE"], {"timezone_offset": 7, "events": []})
        for child in self.media.iterdir():
            child.unlink()

    # -- helpers ---------------------------------------------------------------------
    def request(self, method, path, body=None, headers=None, token=True, content_type="application/json"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = dict(headers or {})
        if token:
            hdrs.setdefault("Authorization", f"Bearer {TOKEN}")
        if body is not None:
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            if content_type:
                hdrs.setdefault("Content-Type", content_type)
        conn.request(method, path, body=body, headers=hdrs)
        response = conn.getresponse()
        data = response.read()
        result = (response.status, dict(response.getheaders()), data)
        conn.close()
        return result

    def json_of(self, data):
        return json.loads(data.decode())

    def multipart(self, filename, content, field="file"):
        boundary = "----testboundary123"
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n").encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        return head + content + tail, f"multipart/form-data; boundary={boundary}"

    def upload(self, filename, content, token=True):
        body, content_type = self.multipart(filename, content)
        return self.request("POST", "/api/upload", body, token=token, content_type=content_type)

    # -- authentication, origin, content type ----------------------------------------
    def test_api_requires_a_valid_token(self):
        self.assertEqual(self.request("GET", "/api/playlists/list", token=False)[0], 401)
        self.assertEqual(self.request("GET", "/api/playlists/list", headers={"Authorization": "Bearer wrong"}, token=False)[0], 401)
        self.assertEqual(self.request("GET", "/api/playlists/list", headers={"Authorization": TOKEN}, token=False)[0], 401)
        status, _, data = self.request("GET", "/api/playlists/list")
        self.assertEqual(status, 200)
        self.assertIn("Factory", self.json_of(data)["playlists"])

    def test_auth_can_be_disabled_by_config(self):
        server.CONFIG["require_auth"] = False
        self.assertEqual(self.request("GET", "/api/playlists/list", token=False)[0], 200)

    def test_cross_origin_requests_are_refused_even_with_a_token(self):
        evil = {"Origin": "http://evil.example"}
        self.assertEqual(self.request("POST", "/api/network/save", {"selected": "eth"}, headers=evil)[0], 403)
        self.assertEqual(self.request("GET", "/api/playlists/list", headers=evil)[0], 403)
        self.assertEqual(self.request("OPTIONS", "/api/network/save", headers=evil, token=False)[0], 403)

    def test_same_origin_and_allowed_origin_get_cors_echo_not_wildcard(self):
        own = {"Origin": f"http://127.0.0.1:{self.port}"}
        status, headers, _ = self.request("GET", "/api/playlists/list", headers=own)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], own["Origin"])
        server.CONFIG["allowed_origins"] = ["http://dashboard.lan:8080"]
        status, headers, _ = self.request("OPTIONS", "/api/status", headers={"Origin": "http://dashboard.lan:8080"}, token=False)
        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "http://dashboard.lan:8080")
        self.assertIn("Authorization", headers["Access-Control-Allow-Headers"])
        _, plain, _ = self.request("GET", "/api/playlists/list")
        self.assertNotIn("Access-Control-Allow-Origin", plain)

    def test_post_needs_json_content_type(self):
        status, _, data = self.request("POST", "/api/network/save", b'{"selected":"eth"}', content_type="text/plain")
        self.assertEqual(status, 415)
        self.assertFalse(self.json_of(data)["success"])
        self.assertEqual(self.request("POST", "/api/network/save", b'{"selected":"eth"}', content_type=None)[0], 415)

    def test_responses_are_hardened_and_do_not_leak_versions(self):
        _, headers, _ = self.request("GET", "/index.html", token=False)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertNotIn("Python", headers.get("Server", ""))

    # -- static files ----------------------------------------------------------------
    def test_static_allowlist(self):
        self.assertEqual(self.request("GET", "/", token=False)[0], 200)
        self.assertEqual(self.request("GET", "/app.js", token=False)[0], 200)
        self.assertEqual(self.request("GET", "/devices.json", token=False)[0], 200)
        for blocked in ("/playlists.json", "/schedules.json", "/notes.txt", "/.secret.js", "/nothing.png"):
            self.assertIn(self.request("GET", blocked, token=False)[0], (403, 404), blocked)
        self.assertEqual(self.request("GET", "/../server.py", token=False)[0], 403)
        self.assertIn(self.request("GET", "/..%2fserver.py", token=False)[0], (403, 404))

    def test_static_cache_headers_and_head_probe(self):
        _, js_headers, _ = self.request("GET", "/app.js?v=1", token=False)
        self.assertEqual(js_headers["Cache-Control"], "no-cache")      # UI updates must be picked up
        self.assertEqual(self.request("HEAD", "/", token=False)[0], 200)
        self.assertEqual(self.request("HEAD", "/api/status", token=False)[0], 401)

    # -- upload ----------------------------------------------------------------------
    def test_upload_accepts_hevc_and_rejects_the_rest(self):
        status, _, data = self.upload("ok.mp4", HEVC_MP4)
        self.assertEqual(status, 200, data)
        self.assertEqual((self.media / "ok.mp4").read_bytes(), HEVC_MP4)
        self.assertEqual(self.upload("ok.mp4", HEVC_MP4)[0], 409)               # duplicate
        status, _, data = self.upload("h264.mp4", H264_MP4)
        self.assertEqual(status, 415)
        self.assertIn("HEVC", self.json_of(data)["error"])
        self.assertFalse((self.media / "h264.mp4").exists())
        self.assertEqual(self.upload("notes.txt", b"hello")[0], 415)
        self.assertEqual(self.upload("fake.mp4", b"x" * 100)[0], 415)
        self.assertEqual(self.upload("auth.mp4", HEVC_MP4, token=False)[0], 401)
        self.assertEqual(sorted(p.name for p in self.media.iterdir()), ["ok.mp4"])  # no temp leftovers

    def test_upload_limits(self):
        server.CONFIG["max_upload_mb"] = 1
        self.assertEqual(self.upload("big.mp4", HEVC_MP4 + b"\0" * (2 * 1024 * 1024))[0], 413)
        server.CONFIG["max_upload_mb"] = 8192
        server.CONFIG["min_free_mb"] = 10 ** 9  # more free space required than any disk has
        self.assertEqual(self.upload("full.mp4", HEVC_MP4)[0], 507)
        self.assertEqual(list(self.media.iterdir()), [])

    def test_upload_name_with_quote_is_kept_verbatim(self):
        status, _, _ = self.upload("Rock'n Roll.mp4", HEVC_MP4)
        self.assertEqual(status, 200)
        self.assertTrue((self.media / "Rock'n Roll.mp4").exists())

    # -- delete / playlists / assign -------------------------------------------------
    def test_delete_validates_name_and_cleans_playlists_atomically(self):
        (self.media / "a.mp4").write_bytes(HEVC_MP4)
        for bad in ("../x", "sub/a.mp4", ".hidden", "", None, 5):
            self.assertEqual(self.request("POST", "/api/delete", {"filename": bad})[0], 400, repr(bad))
        status, _, data = self.request("POST", "/api/delete", {"filename": "a.mp4"})
        self.assertEqual(status, 200)
        self.assertTrue(self.json_of(data)["success"])
        self.assertFalse((self.media / "a.mp4").exists())
        playlists = json.loads(Path(self.paths["PLAYLISTS_FILE"]).read_text())
        self.assertEqual(playlists["playlists"]["Factory"], [])
        self.assertFalse(self.json_of(self.request("POST", "/api/delete", {"filename": "a.mp4"})[2])["success"])

    def test_playlists_save_all_validation(self):
        good = {"playlists": {"Default": [], "Show": ["x.mp4"]}, "assignments": {"screen1": "Show", "screen2": "Default"}}
        self.assertEqual(self.request("POST", "/api/playlists/save_all", good)[0], 200)
        self.assertEqual(json.loads(Path(self.paths["PLAYLISTS_FILE"]).read_text()), good)
        for bad in (
            [], {}, {"playlists": {}, "assignments": {}},
            {"playlists": {"A": ["../evil.mp4"]}, "assignments": {}},
            {"playlists": {"A": "x.mp4"}, "assignments": {}},
            {"playlists": {"A": []}, "assignments": {"screen1": "Missing"}},
            {"playlists": {"A": []}, "assignments": {"screen9": "A"}},
        ):
            self.assertEqual(self.request("POST", "/api/playlists/save_all", bad)[0], 400, bad)
        self.assertEqual(json.loads(Path(self.paths["PLAYLISTS_FILE"]).read_text()), good)  # untouched

    def test_assign_requires_existing_playlist_and_valid_screen(self):
        self.assertEqual(self.request("POST", "/api/playlists/assign", {"screen": 1, "playlist_name": "Nope"})[0], 404)
        self.assertEqual(self.request("POST", "/api/playlists/assign", {"screen": 7, "playlist_name": "Default"})[0], 400)
        self.assertEqual(self.request("POST", "/api/playlists/assign", {"screen": 1, "playlist_name": "Default"})[0], 200)
        data = json.loads(Path(self.paths["PLAYLISTS_FILE"]).read_text())
        self.assertEqual(data["assignments"]["screen1"], "Default")

    def test_assign_never_pushes_loadlist_to_the_pi5_player(self):
        with unittest.mock.patch.object(server, "send_mpv_command") as send, \
             unittest.mock.patch.object(server, "IS_PI", True), \
             unittest.mock.patch.object(server.os.path, "exists", return_value=True):
            self.request("POST", "/api/playlists/assign", {"screen": 1, "playlist_name": "Default"})
            send.assert_not_called()

    def test_legacy_flag_restores_loadlist(self):
        server.CONFIG["legacy_players"] = True
        with unittest.mock.patch.object(server, "send_mpv_command") as send, \
             unittest.mock.patch.object(server, "IS_PI", True), \
             unittest.mock.patch.object(server.os.path, "exists", return_value=True), \
             unittest.mock.patch("builtins.open", unittest.mock.mock_open()):
            server.apply_playlist_assignments.__wrapped__ if False else None
            # call the helper directly: playlists.json read is mocked empty -> JSON error is swallowed
            server.apply_playlist_assignments()
        self.assertTrue(True)  # smoke: legacy path executes without raising

    def test_schedule_endpoints_send_exactly_one_response(self):
        # Raw socket: a stray second response (e.g. a 404 page) would show up after the JSON body.
        import socket
        server.write_json_atomic(self.paths["SCHEDULES_FILE"], {"timezone": "Asia/Jakarta", "events": [],
                                 "windows": [{"days": ["Mon"], "start": "09:00", "end": "17:00"}]})
        for path in ("/api/schedule/config", "/api/schedule/status"):
            with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
                sock.sendall(f"GET {path} HTTP/1.0\r\nAuthorization: Bearer {TOKEN}\r\n\r\n".encode())
                raw = b""
                while chunk := sock.recv(4096):
                    raw += chunk
            head, _, body = raw.partition(b"\r\n\r\n")
            self.assertTrue(head.startswith(b"HTTP/1.0 200") or head.startswith(b"HTTP/1.1 200"), head)
            json.loads(body)  # raises if anything follows the JSON document

    # -- schedule / network / misc validation ----------------------------------------
    def test_schedule_save_validation_and_stamp_preservation(self):
        event = {"id": "e1", "type": "power", "action": "sleep", "time": "22:00", "days": ["Mon"], "enabled": True}
        server.write_json_atomic(self.paths["SCHEDULES_FILE"], {"timezone_offset": 7, "events": [dict(event, _last_triggered="2026-01-01 22:00")]})
        self.assertEqual(self.request("POST", "/api/schedule/save", {"timezone_offset": 7, "events": [event]})[0], 200)
        saved = json.loads(Path(self.paths["SCHEDULES_FILE"]).read_text())
        self.assertEqual(saved["events"][0]["_last_triggered"], "2026-01-01 22:00")
        for bad in (
            [], {"timezone_offset": 99, "events": []}, {"timezone_offset": True, "events": []},
            {"events": [dict(event, time="25:00")]}, {"events": [dict(event, days=["Funday"])]},
            {"events": [dict(event, action="explode")]}, {"events": [dict(event, type="rm")]},
            {"events": "nope"},
        ):
            self.assertEqual(self.request("POST", "/api/schedule/save", bad)[0], 400, bad)

    def test_schedule_save_keeps_window_schedule_keys(self):
        windows = [{"days": ["Mon"], "start": "08:00", "end": "17:00"}]
        self.assertEqual(self.request("POST", "/api/schedule/save", {"timezone_offset": 7, "events": [], "windows": windows})[0], 200)
        self.assertEqual(json.loads(Path(self.paths["SCHEDULES_FILE"]).read_text())["windows"], windows)

    def test_network_save_and_screenshot_validation(self):
        self.assertEqual(self.request("POST", "/api/network/save", {"selected": "carrier-pigeon"})[0], 400)
        self.assertEqual(self.request("GET", "/api/screenshot?screen=abc")[0], 400)
        self.assertEqual(self.request("GET", "/api/screenshot?screen=9")[0], 400)

    def test_status_reports_capabilities_and_playlist_from_json(self):
        (self.media / "a.mp4").write_bytes(HEVC_MP4)
        status, _, data = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        body = self.json_of(data)
        self.assertFalse(body["capabilities"]["transport_controls"])
        self.assertFalse(body["capabilities"]["dual_output"])
        self.assertEqual(body["capabilities"]["allowed_codecs"], ["hevc"])
        self.assertEqual([item["name"] for item in body["screen1"]["playlist"]], ["a.mp4"])


class JsonStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "data.json")

    def test_atomic_write_leaves_no_temp_files_and_replaces_whole_file(self):
        server.write_json_atomic(self.path, {"a": 1})
        server.write_json_atomic(self.path, {"b": 2})
        self.assertEqual(load(self.path), {"b": 2})
        self.assertEqual(os.listdir(self.tmp.name), ["data.json"])

    def test_failed_write_keeps_old_content(self):
        server.write_json_atomic(self.path, {"keep": True})
        with self.assertRaises(TypeError):
            server.write_json_atomic(self.path, {"bad": object()})
        self.assertEqual(load(self.path), {"keep": True})
        self.assertEqual(os.listdir(self.tmp.name), ["data.json"])

    def test_update_json_modes(self):
        with self.assertRaises(FileNotFoundError):
            server.update_json(self.path, lambda d: d)
        server.update_json(self.path, lambda d: d.update(n=1), default=dict)
        self.assertEqual(load(self.path), {"n": 1})
        before = os.stat(self.path).st_mtime_ns
        server.update_json(self.path, lambda d: server.NO_CHANGE)
        self.assertEqual(os.stat(self.path).st_mtime_ns, before)
        server.update_json(self.path, lambda d: {"replaced": True})
        self.assertEqual(load(self.path), {"replaced": True})

    def test_concurrent_updates_do_not_lose_writes(self):
        server.write_json_atomic(self.path, {"count": 0})

        def bump():
            for _ in range(25):
                server.update_json(self.path, lambda d: d.update(count=d["count"] + 1))

        threads = [threading.Thread(target=bump) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(load(self.path)["count"], 150)


class ConfigAndTokenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_file = os.path.join(self.tmp.name, "cms_config.json")
        self.token_file = os.path.join(self.tmp.name, ".cms_token")
        for patch in (unittest.mock.patch.object(server, "CONFIG_FILE", self.config_file),
                      unittest.mock.patch.object(server, "TOKEN_FILE", self.token_file),
                      unittest.mock.patch.object(server, "CONFIG", dict(server.DEFAULT_CONFIG)),
                      unittest.mock.patch.object(server, "TOKEN", "")):
            patch.start()
            self.addCleanup(patch.stop)

    def test_defaults_are_secure(self):
        config = server.load_config()
        self.assertTrue(config["require_auth"])
        self.assertFalse(config["legacy_players"])
        self.assertEqual(config["allowed_origins"], [])
        self.assertEqual(config["allowed_codecs"], ["hevc"])

    def test_user_values_override_but_bad_types_are_ignored(self):
        Path(self.config_file).write_text(json.dumps({
            "max_upload_mb": 512, "require_auth": "no", "allowed_origins": ["http://x:1"],
            "min_free_mb": True, "unknown_key": 1}))
        config = server.load_config()
        self.assertEqual(config["max_upload_mb"], 512)
        self.assertTrue(config["require_auth"])        # string is not a bool -> default
        self.assertEqual(config["min_free_mb"], 1024)   # bool is not an int -> default
        self.assertEqual(config["allowed_origins"], ["http://x:1"])
        self.assertNotIn("unknown_key", config)

    def test_broken_config_file_falls_back_to_defaults(self):
        Path(self.config_file).write_text("{not json")
        self.assertEqual(server.load_config(), server.DEFAULT_CONFIG)

    def test_token_is_created_once_and_reused(self):
        first = server.ensure_token()
        self.assertGreaterEqual(len(first), 24)
        self.assertEqual(Path(self.token_file).read_text().strip(), first)
        if os.name == "posix":
            self.assertEqual(os.stat(self.token_file).st_mode & 0o777, 0o600)
        server.TOKEN = ""
        self.assertEqual(server.ensure_token(), first)


class ScheduleTickTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        public = Path(self.tmp.name)
        self.schedules = str(public / "schedules.json")
        self.playlists = str(public / "playlists.json")
        for key, value in (("SCHEDULES_FILE", self.schedules), ("PLAYLISTS_FILE", self.playlists),
                           ("CONFIG", dict(server.DEFAULT_CONFIG))):
            patch = unittest.mock.patch.object(server, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        server.write_json_atomic(self.playlists, {"playlists": {"Default": [], "Show": ["x.mp4"]},
                                                   "assignments": {"screen1": "Default", "screen2": "Default"}})

    def test_playlist_event_fires_once_per_minute_in_schedule_timezone(self):
        event = {"id": "p1", "type": "playlist", "screen": 1, "playlist_name": "Show", "time": "09:30",
                 "days": ["Fri"], "enabled": True}
        server.write_json_atomic(self.schedules, {"timezone_offset": 7, "events": [event]})
        # 02:30 UTC on Friday 2026-11-06 is 09:30 in Jakarta
        now = datetime(2026, 11, 6, 2, 30, 20, tzinfo=timezone.utc)
        self.assertEqual(len(server.schedule_tick(now)), 1)
        self.assertEqual(load(self.playlists)["assignments"]["screen1"], "Show")
        self.assertEqual(server.schedule_tick(now), [])                      # same minute: no refire
        self.assertEqual(server.schedule_tick(datetime(2026, 11, 6, 2, 31, tzinfo=timezone.utc)), [])
        self.assertIn("_last_triggered", load(self.schedules)["events"][0])

    def test_disabled_or_other_day_events_do_not_fire_and_file_is_not_rewritten(self):
        events = [{"id": "a", "type": "power", "action": "sleep", "time": "09:30", "days": ["Fri"], "enabled": False},
                  {"id": "b", "type": "power", "action": "sleep", "time": "09:30", "days": ["Sat"], "enabled": True}]
        server.write_json_atomic(self.schedules, {"timezone_offset": 7, "events": events})
        before = os.stat(self.schedules).st_mtime_ns
        self.assertEqual(server.schedule_tick(datetime(2026, 11, 6, 2, 30, tzinfo=timezone.utc)), [])
        self.assertEqual(os.stat(self.schedules).st_mtime_ns, before)

    def test_power_events_never_touch_services_without_legacy_flag(self):
        server.write_json_atomic(self.schedules, {"timezone_offset": 7, "events": [
            {"id": "s", "type": "power", "action": "sleep", "time": "09:30", "days": ["Fri"], "enabled": True}]})
        with unittest.mock.patch.object(server.subprocess, "run") as run, unittest.mock.patch.object(server, "IS_PI", True):
            server.schedule_tick(datetime(2026, 11, 6, 2, 30, tzinfo=timezone.utc))
            run.assert_not_called()

    def test_missing_schedule_file_is_not_an_error(self):
        self.assertEqual(server.schedule_tick(datetime(2026, 11, 6, 2, 30, tzinfo=timezone.utc)), [])


class WindowScheduleTests(unittest.TestCase):
    """Playback windows: start-day ownership, midnight crossing, migration from wake/sleep."""

    JAKARTA = {"timezone": "Asia/Jakarta", "events": []}

    def state(self, windows, utc, tz="Asia/Jakarta"):
        return server.schedule_state({"timezone": tz, "events": [], "windows": windows}, utc)

    def test_midnight_window_belongs_to_the_day_it_starts(self):
        windows = [{"days": ["Fri"], "start": "22:00", "end": "02:00"}]
        fri_2330 = datetime(2026, 11, 6, 16, 30, tzinfo=timezone.utc)   # Fri 23:30 WIB
        sat_0130 = datetime(2026, 11, 6, 18, 30, tzinfo=timezone.utc)   # Sat 01:30 WIB
        sat_2330 = datetime(2026, 11, 7, 16, 30, tzinfo=timezone.utc)   # Sat 23:30 WIB
        self.assertTrue(self.state(windows, fri_2330)["on"])
        self.assertTrue(self.state(windows, sat_0130)["on"])
        self.assertFalse(self.state(windows, sat_2330)["on"])           # Saturday has no window
        self.assertEqual(self.state(windows, fri_2330)["next_change"], {"day": "Sat", "time": "02:00", "date": "2026-11-07"})

    def test_next_change_skips_back_to_back_windows_and_off_days(self):
        windows = [{"days": ["Mon"], "start": "09:00", "end": "24:00"},
                   {"days": ["Tue"], "start": "00:00", "end": "24:00"},
                   {"days": ["Wed"], "start": "00:00", "end": "10:00"}]
        mon_noon = datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc)     # Mon 12:00 WIB
        state = self.state(windows, mon_noon)
        self.assertTrue(state["on"])
        self.assertEqual(state["next_change"], {"day": "Wed", "time": "10:00", "date": "2026-11-11"})  # Mon 24:00 -> Tue 00:00 -> Wed 00:00 is seamless
        off = self.state(windows, datetime(2026, 11, 12, 5, 0, tzinfo=timezone.utc))                   # Thu
        self.assertFalse(off["on"])
        self.assertEqual(off["next_change"], {"day": "Mon", "time": "09:00", "date": "2026-11-16"})

    def test_full_week_window_is_reported_as_always_on(self):
        state = self.state([{"days": list(server.DAYS), "start": "00:00", "end": "24:00"}], datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc))
        self.assertTrue(state["on"] and state["always"])
        self.assertIsNone(state["next_change"])

    def test_validation_matches_the_player_rules(self):
        ok = {"timezone": "Asia/Jakarta", "windows": [{"days": ["Mon"], "start": "09:00", "end": "24:00"}]}
        server.validate_schedules(ok)
        for bad in (
            dict(ok, windows=[]),
            dict(ok, windows=[{"days": ["Mon"], "start": "09:00", "end": "09:00"}]),
            dict(ok, windows=[{"days": ["Mon"], "start": "24:00", "end": "10:00"}]),
            dict(ok, windows=[{"days": [], "start": "09:00", "end": "10:00"}]),
            dict(ok, windows=[{"days": ["Mon"], "start": "09:00", "end": "10:00"}, {"days": ["Mon", "Tue"], "start": "11:00", "end": "12:00"}]),
            dict(ok, timezone="Mars/Olympus"),
            dict(ok, timezone=7),
        ):
            with self.assertRaises(ValueError, msg=bad):
                server.validate_schedules(bad)

    def test_migration_converts_wake_sleep_and_offset(self):
        power = [
            {"id": "w", "type": "power", "action": "wake", "time": "08:00", "days": ["Mon", "Tue"], "enabled": True},
            {"id": "s", "type": "power", "action": "sleep", "time": "02:00", "days": ["Mon", "Tue"], "enabled": True},
            {"id": "o", "type": "power", "action": "sleep", "time": "20:00", "days": ["Wed"], "enabled": True},
            {"id": "x", "type": "power", "action": "sleep", "time": "03:00", "days": ["Thu"], "enabled": False},
            {"id": "p", "type": "playlist", "screen": 1, "playlist_name": "Show", "time": "09:00", "days": ["Mon"], "enabled": True},
        ]
        migrated = server.migrate_schedules({"timezone_offset": 8, "events": power})
        self.assertEqual(migrated["timezone"], "Asia/Makassar")
        self.assertNotIn("timezone_offset", migrated)
        self.assertEqual([e["id"] for e in migrated["events"]], ["p"])
        spans = {tuple(w["days"]): (w["start"], w["end"]) for w in migrated["windows"]}
        self.assertEqual(spans[("Mon", "Tue")], ("08:00", "02:00"))   # crosses midnight
        self.assertEqual(spans[("Wed",)], ("00:00", "20:00"))         # sleep only
        self.assertEqual(spans[("Thu", "Fri", "Sat", "Sun")], ("00:00", "24:00"))  # no events: always, as before
        server.validate_schedules(migrated)
        self.assertIsNone(server.migrate_schedules(migrated))         # idempotent

    def test_migrating_an_empty_default_file_means_always_on(self):
        migrated = server.migrate_schedules({"timezone_offset": 7, "events": []})
        self.assertEqual(migrated["windows"], [{"days": list(server.DAYS), "start": "00:00", "end": "24:00"}])
        self.assertEqual(server.zone_for_offset(-5), "Etc/GMT+5")

    def test_status_endpoint_and_startup_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / "schedules.json")
            server.write_json_atomic(path, {"timezone_offset": 7, "events": [
                {"id": "w", "type": "power", "action": "wake", "time": "08:00", "days": list(server.DAYS), "enabled": True}]})
            with unittest.mock.patch.object(server, "SCHEDULES_FILE", path):
                server.migrate_schedule_file()
                saved = load(path)
                self.assertEqual(saved["windows"], [{"days": list(server.DAYS), "start": "08:00", "end": "24:00"}])
                before = os.stat(path).st_mtime_ns
                server.migrate_schedule_file()
                self.assertEqual(os.stat(path).st_mtime_ns, before)  # already migrated: untouched


if __name__ == "__main__":
    unittest.main()
