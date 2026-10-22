"""Test audio handlers without importing server startup/network side effects."""
import ast
import json
import os
from pathlib import Path
import tempfile
import types
import unittest


class AudioApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'public').mkdir()
        self.config = root / 'public/audio_config.json'
        self.config.write_text(json.dumps({'screen1': {'global_mute': False, 'clip_settings': {}}}))
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'server.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SignageRequestHandler')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'handle_api_audio_global')
        self.state = {'mute': False, 'af': '', 'audio-device': 'alsa/sysdefault:CARD=vc4hdmi0'}
        self.commands = []
        self.replies = []
        self.ipc_failure = False
        self.disconnected = False
        def ipc(sock, cmd):
            self.commands.append(cmd)
            if self.disconnected or self.ipc_failure and cmd[0] == 'set_property':
                return {'error': 'unavailable'}
            if cmd == ['get_property', 'filename']:
                return {'error': 'success', 'data': 'clip.mp4'}
            if cmd[0] == 'set_property':
                self.state[cmd[1]] = cmd[2]
            return {'error': 'success', 'data': self.state.get(cmd[1])}
        ns = {'json': json, 'os': os, 'tempfile': tempfile,
              '__file__': str(root / 'server.py'), 'SOCK_1': str(root / 'socket'),
              'PLAYER_SERVICE': 'pi5-signage.service', 'get_service_status': lambda _: 'inactive',
              'send_mpv_command': ipc}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<audio-handler>', 'exec'), ns)
        self.handler = ns['handle_api_audio_global']
        self.params = {'screen': 1, 'global_mute': True, 'output_device': 'hdmi', 'channel_mode': 'stereo'}
        self.request = types.SimpleNamespace(player_params=lambda: self.params, player_response=lambda code, data: self.replies.append((code, data)))

    def run_handler(self):
        self.handler(self.request)
        return self.replies[-1]

    def test_mute_then_unmute_applied_and_persisted(self):
        for value in (True, False):
            self.params['global_mute'] = value
            code, reply = self.run_handler()
            self.assertEqual(code, 200)
            self.assertTrue(reply['applied'])
            self.assertIs(self.state['mute'], value)
            self.assertIs(json.loads(self.config.read_text())['screen1']['global_mute'], value)

    def test_clip_mute_takes_precedence(self):
        self.config.write_text(json.dumps({'screen1': {'global_mute': False, 'clip_settings': {'clip.mp4': {'mute': True}}}}))
        self.params['global_mute'] = False
        self.assertEqual(self.run_handler()[0], 200)
        self.assertTrue(self.state['mute'])

    def test_failed_ipc_not_reported_as_success_or_saved(self):
        self.ipc_failure = True
        self.assertEqual(self.run_handler()[0], 503)
        self.assertFalse(json.loads(self.config.read_text())['screen1']['global_mute'])

    def test_invalid_boolean_rejected(self):
        self.params['global_mute'] = 'false'
        self.assertEqual(self.run_handler()[0], 400)
        self.assertEqual(self.commands, [])

    def test_unsupported_screen_rejected(self):
        self.params['screen'] = 2
        self.assertEqual(self.run_handler()[0], 409)

    def test_unsupported_jack_rejected(self):
        self.params['output_device'] = 'jack'
        self.assertEqual(self.run_handler()[0], 409)

    def test_idle_player_setting_is_explicitly_pending(self):
        self.disconnected = True
        code, reply = self.run_handler()
        self.assertEqual(code, 200)
        self.assertFalse(reply['applied'])
        self.assertTrue(json.loads(self.config.read_text())['screen1']['global_mute'])


if __name__ == '__main__':
    unittest.main()
