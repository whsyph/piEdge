import json
import tempfile
import unittest
from datetime import datetime, time
from pathlib import Path

from signage import command_for, in_window, load_config, media_files, playlist_files
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
                "media_dir": str(folder), "start": "08:00", "end": "20:00",
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

    def test_splash_is_valid_ppm(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "splash.ppm"
            generate(output)
            header = output.read_text(encoding="ascii").splitlines()[:3]
            self.assertEqual(header, ["P3", "1920 1080", "255"])
            self.assertGreater(output.stat().st_size, 1000)

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
