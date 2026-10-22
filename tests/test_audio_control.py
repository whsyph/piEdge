import json
import tempfile
import unittest
from pathlib import Path

from signage import cms_mute, command_for


class AudioControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {
            'audio': True,
            'audio_device': 'alsa/sysdefault:CARD=vc4hdmi0',
            'schedules_file': str(self.root / 'schedules.json'),
            'playlist_screen': 'screen1',
        }

    def save(self, global_mute=False, clip_mute=False):
        (self.root / 'audio_config.json').write_text(json.dumps({
            'screen1': {'global_mute': global_mute,
                        'clip_settings': {'clip.mp4': {'mute': clip_mute}}}
        }))

    def test_global_and_clip_mute_truth_table(self):
        for global_mute in (False, True):
            for clip_mute in (False, True):
                with self.subTest(global_mute=global_mute, clip_mute=clip_mute):
                    self.save(global_mute, clip_mute)
                    self.assertEqual(cms_mute('clip.mp4', self.config), global_mute or clip_mute)

    def test_audio_disabled_cannot_be_overridden(self):
        self.save(False, False)
        self.config['audio'] = False
        self.assertTrue(cms_mute('clip.mp4', self.config))

    def test_audio_device_uses_single_argument(self):
        self.save()
        command = command_for('clip.mp4', self.config)
        self.assertIn('--audio-device=alsa/sysdefault:CARD=vc4hdmi0', command)
        self.assertNotIn('--audio-device', command)
        self.assertIn('--input-ipc-server=/run/user/1000/capibarra-mpv.sock', command)
        self.assertIn('--mute=no', command)

    def test_missing_or_malformed_config_uses_fallback(self):
        self.assertFalse(cms_mute('clip.mp4', self.config))
        (self.root / 'audio_config.json').write_text('{bad json')
        self.assertFalse(cms_mute('clip.mp4', self.config))
        self.config['audio'] = False
        self.assertTrue(cms_mute('clip.mp4', self.config))

    def test_setting_reloaded_on_each_launch(self):
        self.save(True)
        self.assertIn('--mute=yes', command_for('clip.mp4', self.config))
        self.save(False)
        self.assertIn('--mute=no', command_for('clip.mp4', self.config))

    def test_invalid_boolean_uses_fallback(self):
        (self.root / 'audio_config.json').write_text('{"screen1":{"global_mute":"false"}}')
        self.assertFalse(cms_mute('clip.mp4', self.config))


if __name__ == '__main__':
    unittest.main()
