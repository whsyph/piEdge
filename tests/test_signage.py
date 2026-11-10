import json
import tempfile
import unittest
import unittest.mock
from datetime import datetime, time
from pathlib import Path

from signage import command_for, in_window, load_config, media_files, playlist_files, resolve_profile_name, load_profile
from splash import generate


class SignageTests(unittest.TestCase):
    def test_daytime_boundaries(self):
        start, end = time(8), time(20)
        self.assertFalse(in_window(datetime(2026, 9, 29, 7, 59), start, end))
        self.assertTrue(in_window(datetime(2026, 9, 29, 8), start, end))
        self.assertFalse(in_window(datetime(2026, 9, 29, 20), start, end))

    def test_overnight_window(self):
        start, end = time(20), time(8)
        self.assertTrue(in_window(datetime(2026, 9, 29, 23), start, end))
        self.assertTrue(in_window(datetime(2026, 9, 30, 7), start, end))
        self.assertFalse(in_window(datetime(2026, 9, 30, 8), start, end))

    def test_config_media_and_command(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "b.MP4").touch()
            (folder / "a.mkv").touch()
            (folder / "ignore.txt").touch()
            config_path = folder / "config.json"
            config_path.write_text(json.dumps({
                "profile": "pi5", "media_dir": str(folder), "start": "08:00", "end": "20:00",
                "display": "HDMI-A-1", "audio": False,
                "audio_device": "sysdefault:CARD=vc4hdmi0", "retry_seconds": 5,
            }), encoding="utf-8")
            config = load_config(config_path)
            files = media_files(folder)
            self.assertEqual([p.name for p in files], ["a.mkv", "b.MP4"])
            command = command_for(files[0], config)
            self.assertIn("--vo=dmabuf-wayland", command)
            self.assertIn("--mute=yes", command)
            self.assertEqual(command[-1], str(files[0]))

    def test_always_on_allows_every_minute_including_2359(self):
        import signage
        config = {"always_on": True, "start": time(0), "end": time(23, 59)}
        with unittest.mock.patch.object(signage, "operation_mode", return_value="auto"), \
             unittest.mock.patch.object(signage, "schedules_allow", return_value=True):
            self.assertTrue(signage.allowed_now(config))
            config["always_on"] = False
            with unittest.mock.patch.object(signage, "datetime") as fake:
                fake.now.return_value = datetime(2026, 9, 29, 23, 59)
                self.assertFalse(signage.allowed_now(config))

    def test_always_on_config_may_use_equal_start_end(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "c.json"
            base = {"profile": "pi5", "media_dir": temp, "start": "00:00", "end": "00:00",
                    "display": "HDMI-A-1", "audio": False, "audio_device": "x", "retry_seconds": 5}
            path.write_text(json.dumps({**base, "always_on": True}), encoding="utf-8")
            self.assertTrue(load_config(path)["always_on"])
            path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaises(ValueError): load_config(path)

    def test_single_file_loop_flag_only_when_requested(self):
        config = {"audio": False, "audio_device": "x", "schedules_file": "/nonexistent/schedules.json"}
        self.assertNotIn("--loop-file=inf", command_for(Path("a.mp4"), config))
        self.assertIn("--loop-file=inf", command_for(Path("a.mp4"), config, loop=True))

    def test_hdmi_output_changes_only_on_state_change(self):
        import signage
        states = iter([True, True, False, False, True])
        calls = []
        def fake_allowed(_config):
            try:
                return next(states)
            except StopIteration:
                signage.STOP = True
                return True
        signage.STOP = False
        try:
            with unittest.mock.patch.object(signage, "allowed_now", side_effect=fake_allowed), \
                 unittest.mock.patch.object(signage, "set_output", side_effect=lambda on, d: calls.append(on) or True), \
                 unittest.mock.patch.object(signage, "playlist_files", return_value=[]), \
                 unittest.mock.patch.object(signage, "wait_or_stop"), \
                 unittest.mock.patch.object(signage.time, "sleep"):
                signage.run({"display": "HDMI-A-1", "media_dir": Path("."), "retry_seconds": 5})
        finally:
            signage.STOP = False
        self.assertEqual(calls, [True, False, True])

    def test_player_only_config_ignores_cms_files(self):
        import signage
        config = {"audio": True}  # no schedules_file: nothing under /home/pi may be consulted
        with unittest.mock.patch.object(signage.Path, "read_text", side_effect=AssertionError("read")):
            self.assertFalse(signage.cms_mute("a.mp4", config))
            self.assertEqual(signage.operation_mode(config), "auto")

    def test_repeatedly_failing_file_is_set_aside(self):
        import signage
        bad, good = Path("bad.mp4"), Path("good.mp4")
        plays = []
        def fake_play(path, config, loop_playlist=None):
            plays.append(path.name)
            if len(plays) >= 8:
                signage.STOP = True
            return 1 if path == bad else 0
        signage.STOP = False
        try:
            with unittest.mock.patch.object(signage, "allowed_now", return_value=True), \
                 unittest.mock.patch.object(signage, "set_output", return_value=True), \
                 unittest.mock.patch.object(signage, "playlist_files", return_value=[bad, good]), \
                 unittest.mock.patch.object(signage, "play", side_effect=fake_play), \
                 unittest.mock.patch.object(signage, "wait_or_stop"), \
                 unittest.mock.patch.object(signage.time, "sleep"):
                signage.run({"display": "HDMI-A-1", "media_dir": Path("."), "retry_seconds": 5})
        finally:
            signage.STOP = False
        self.assertEqual(plays.count("bad.mp4"), signage.FAIL_LIMIT)
        self.assertGreater(plays.count("good.mp4"), signage.FAIL_LIMIT)

    @unittest.skipUnless(hasattr(__import__("socket"), "AF_UNIX"), "needs unix sockets")
    def test_mpv_time_pos_reads_ipc_reply(self):
        import signage, socket, threading, os
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "mpv.sock")
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(path); server.listen(1)
            def serve():
                conn, _ = server.accept()
                conn.recv(4096)
                conn.sendall(b'{"event":"tick"}\n{"data":12.5,"error":"success"}\n')
                conn.close()
            thread = threading.Thread(target=serve); thread.start()
            self.assertEqual(signage.mpv_time_pos(path), 12.5)
            thread.join(); server.close()
        self.assertIsNone(signage.mpv_time_pos("/nonexistent/mpv.sock"))

    def test_strict_playlist_read_reports_unknown_instead_of_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "a.mp4").touch()
            playlist = folder / "playlists.json"
            config = {"media_dir": folder, "playlist_file": str(playlist), "playlist_screen": "screen1"}
            for broken in ("{", "[]", '{"playlists": {"Default": "a.mp4"}, "assignments": {}}'):
                playlist.write_text(broken, encoding="utf-8")
                with self.assertLogs("pi5-signage", "WARNING"):
                    self.assertIsNone(playlist_files(config, strict=True), broken)
            self.assertEqual(playlist_files(config), [])  # non-strict keeps the old behaviour
            playlist.write_text('{"playlists": {"Default": []}, "assignments": {}}', encoding="utf-8")
            self.assertEqual(playlist_files(config, strict=True), [])  # truly empty is not "unknown"

    def test_loop_keeps_playing_when_playlist_is_unreadable_but_restarts_on_real_change(self):
        import itertools
        import signage
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            a, b = folder / "a.mp4", folder / "b.mp4"
            a.touch()
            b.touch()
            playlist = folder / "playlists.json"
            config = {"media_dir": folder, "playlist_file": str(playlist), "playlist_screen": "screen1",
                      "audio": False, "audio_device": "x"}

            def run_play(content):
                playlist.write_text(content, encoding="utf-8")
                process = unittest.mock.Mock()
                process.poll.side_effect = itertools.chain([None] * 4, itertools.repeat(0))
                process.returncode = 0
                clock = itertools.count(0, 6)  # each monotonic() call is 6 s later: the 5 s check fires
                with unittest.mock.patch.object(signage.subprocess, "Popen", return_value=process), \
                     unittest.mock.patch.object(signage, "allowed_now", return_value=True), \
                     unittest.mock.patch.object(signage, "mpv_time_pos", return_value=None), \
                     unittest.mock.patch.object(signage, "command_for", return_value=["mpv"]), \
                     unittest.mock.patch.object(signage.time, "sleep"), \
                     unittest.mock.patch.object(signage.time, "monotonic", side_effect=lambda: next(clock)), \
                     self.assertLogs("pi5-signage", level="INFO"):
                    signage.LOG.info("marker")  # assertLogs needs at least one record
                    signage.play(a, config, loop_playlist=[a])
                return process

            self.assertFalse(run_play("{").terminate.called)  # unreadable: keep playing
            self.assertTrue(run_play('{"playlists": {"Default": ["a.mp4", "b.mp4"]}, "assignments": {}}').terminate.called)

    def test_stable_read_retries_while_the_file_is_being_rewritten(self):
        import signage
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "a.mp4").touch()
            playlist = folder / "playlists.json"
            playlist.write_text("{", encoding="utf-8")
            config = {"media_dir": folder, "playlist_file": str(playlist), "playlist_screen": "screen1"}
            valid = '{"playlists": {"Default": ["a.mp4"]}, "assignments": {}}'
            sleeps = []

            def finish_write(delay):
                sleeps.append(delay)
                playlist.write_text(valid, encoding="utf-8")

            with unittest.mock.patch.object(signage.time, "sleep", side_effect=finish_write), \
                 self.assertLogs("pi5-signage", "ERROR"):
                files = signage.playlist_files_stable(config)
            self.assertEqual([p.name for p in files], ["a.mp4"])
            self.assertEqual(len(sleeps), 1)

    def test_profile_detection_is_strict(self):
        self.assertEqual(resolve_profile_name({}, "Raspberry Pi 5 Model B Rev 1.0"), "pi5")
        with self.assertRaises(ValueError): resolve_profile_name({}, "Raspberry Pi 4 Model B Rev 1.5")
        with self.assertRaises(ValueError): resolve_profile_name({}, "Raspberry Pi 4 Compute Module")
        with self.assertRaises(ValueError): resolve_profile_name({}, "unknown")

    def test_profile_schema_and_named_only_loading(self):
        self.assertEqual(load_profile("pi5")["target"], "pi5")
        with self.assertRaises(ValueError): load_profile("../profiles/pi5")

    def test_splash_is_valid_ppm(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "splash.ppm"
            generate(output)
            data = output.read_bytes()
            header = b"P6\n1920 1080\n255\n"
            self.assertTrue(data.startswith(header))
            self.assertEqual(len(data), len(header) + 1920 * 1080 * 3)
            self.assertIn(bytes((64, 210, 190)), data)  # accent bar drawn

    def test_command_flags_come_from_profile(self):
        import signage
        config = {"audio": False, "audio_device": "x"}
        profile = load_profile("pi5")["mpv"]
        command = command_for(Path("a.mp4"), config)
        self.assertIn(f"--vo={profile['vo']}", command)
        self.assertIn(f"--hwdec-extra-frames={profile['hwdec_extra_frames']}", command)
        changed = dict(load_profile("pi5"), mpv={**profile, "vo": "gpu"})
        with unittest.mock.patch.object(signage, "load_profile", return_value=changed):
            self.assertIn("--vo=gpu", command_for(Path("a.mp4"), config))
        bad = {**profile, "vo": "--evil"}
        with self.assertRaises(ValueError): signage.validate_profile("pi5", dict(load_profile("pi5"), mpv=bad))

    def test_cms_playlist_order_and_assignment(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "first.mp4").touch()
            (folder / "second.mp4").touch()
            playlist = folder / "playlists.json"
            playlist.write_text(json.dumps({
                "playlists": {"Snippet": ["second.mp4", "first.mp4"]},
                "assignments": {"screen1": "Snippet"},
            }), encoding="utf-8")
            config = {"media_dir": folder, "playlist_file": str(playlist), "playlist_screen": "screen1"}
            self.assertEqual([p.name for p in playlist_files(config)], ["second.mp4", "first.mp4"])


if __name__ == "__main__":
    unittest.main()
