import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'candidate'))
import signage as player
from drm_splash import splash_command
from drm_power import connector_id


class DirectDrmTests(unittest.TestCase):
    def setUp(self):
        self.config=player.load_config(ROOT/'candidate/config.json')
        self.audio_patch=patch.object(player,'cms_audio',return_value={'mute':False,'device':'alsa/sysdefault:CARD=vc4hdmi0','filter':''})
        self.audio_patch.start();self.addCleanup(self.audio_patch.stop)
        player.POWER_LEASE=None

    def test_exact_proven_renderer(self):
        cmd=player.command_for(Path('clip.mp4'),self.config)
        for option in ('--no-config','--vo=gpu','--gpu-context=drm','--gpu-hwdec-interop=drmprime-overlay',
                       '--hwdec=drm','--drm-draw-plane=overlay','--drm-drmprime-video-plane=primary',
                       '--video-sync=audio','--input-ipc-server=/run/user/1000/capibarra-mpv.sock'):
            self.assertIn(option,cmd)
        self.assertNotIn('--gpu-context=wayland',cmd)
        self.assertNotIn('--audio-device',cmd)

    def test_audio_settings_and_filter(self):
        with patch.object(player,'cms_audio',return_value={'mute':True,'device':'alsa/sysdefault:CARD=Headphones','filter':'lavfi=[pan=stereo|c0=c0|c1=0*c1]'}):
            cmd=player.command_for(Path('clip.mp4'),self.config)
        self.assertIn('--mute=yes',cmd)
        self.assertIn('--audio-device=alsa/sysdefault:CARD=Headphones',cmd)
        self.assertIn('--af=lavfi=[pan=stereo|c0=c0|c1=0*c1]',cmd)

    def test_off_retains_same_lease_until_wake(self):
        lease=Mock()
        with patch.object(player,'PowerLease',return_value=lease) as factory:
            self.assertTrue(player.set_output(False,self.config))
            self.assertIs(player.POWER_LEASE,lease)
            lease.close.assert_not_called()
            self.assertTrue(player.set_output(False,self.config))
            self.assertEqual(factory.call_count,1)
            self.assertTrue(player.set_output(True,self.config))
        lease.close.assert_called_once()
        self.assertIsNone(player.POWER_LEASE)
        self.assertEqual([c.args[0] for c in lease.set_enabled.call_args_list],[False,False,True])

    def test_wake_without_lease_releases_master_before_mpv(self):
        lease=Mock()
        with patch.object(player,'PowerLease',return_value=lease):
            self.assertTrue(player.set_output(True,self.config))
        lease.set_enabled.assert_called_once_with(True)
        lease.close.assert_called_once()

    def test_failed_power_operation_is_not_cached_success(self):
        lease=Mock();lease.set_enabled.side_effect=OSError('no DRM master')
        with patch.object(player,'PowerLease',return_value=lease):
            self.assertFalse(player.set_output(False,self.config))
        self.assertIsNone(player.POWER_LEASE)
        lease.close.assert_called_once()

    def test_lease_release_on_stop(self):
        lease=Mock();player.POWER_LEASE=lease
        player.release_output_lease()
        lease.set_enabled.assert_called_once_with(True)
        lease.close.assert_called_once()
        self.assertIsNone(player.POWER_LEASE)

    def test_no_compositor_or_wayland_dependency(self):
        source=(ROOT/'candidate/signage.py').read_text()
        unit=(ROOT/'candidate/pi5-signage.service').read_text()
        self.assertNotIn('wlr-randr',source)
        self.assertNotIn('Requires=labwc',unit)
        self.assertIn('Conflicts=labwc.service',unit)
        self.assertIn('TTYPath=/dev/tty8',unit)
        self.assertIn('User=pi',unit)
        self.assertIn('ExecStartPre=+/usr/bin/chvt 8',unit)

    def test_unix_splash_script_has_lf_shebang(self):
        data=(ROOT/'candidate/splash.sh').read_bytes()
        self.assertTrue(data.startswith(b'#!/bin/sh\n'))
        self.assertNotIn(b'\r',data)

    def test_splash_is_finite_and_software_image_decode(self):
        cmd=splash_command(self.config)
        self.assertIn('--gpu-context=drm',cmd)
        self.assertIn('--hwdec=no',cmd)
        self.assertIn('--gpu-hwdec-interop=no',cmd)
        self.assertIn('--image-display-duration=3',cmd)

    def test_hevc_profile_acceptance_and_h264_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'clip.mp4';p.touch()
            player.MEDIA_PROBES={}
            good=Mock(returncode=0,stdout='{"streams":[{"codec_name":"hevc"}]}')
            with patch.object(player.subprocess,'run',return_value=good):self.assertTrue(player.playable_media(p))
            player.MEDIA_PROBES={}
            bad=Mock(returncode=0,stdout='{"streams":[{"codec_name":"h264"}]}')
            with patch.object(player.subprocess,'run',return_value=bad):self.assertFalse(player.playable_media(p))

    def test_native_preview_does_not_capture_from_mpv(self):
        import ast, io, types
        from unittest.mock import mock_open
        source=(ROOT/'candidate/server.py').read_text()
        tree=ast.parse(source)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SignageRequestHandler')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='handle_api_screenshot')
        forbidden=Mock(side_effect=AssertionError('Direct preview must not issue an mpv screenshot'))
        namespace={'json':json,'send_mpv_command':forbidden}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<preview-test>','exec'),namespace)
        headers={}; codes=[]; body=io.BytesIO()
        request=types.SimpleNamespace(send_response=codes.append,send_header=lambda k,v:headers.update({k:v}),
                                      send_cors_headers=lambda:None,end_headers=lambda:None,wfile=body)
        with patch('builtins.open',mock_open(read_data='{"renderer":"drm-overlay"}')):
            namespace['handle_api_screenshot'](request,{'screen':['1']})
        self.assertEqual(codes,[200])
        self.assertEqual(headers['X-Preview-Available'],'false')
        self.assertIn(b'Preview langsung dinonaktifkan',body.getvalue())
        forbidden.assert_not_called()

    def test_connector_validation(self):
        for device,display in [('/tmp/card','HDMI-A-1'),('/dev/dri/card1','../tty1')]:
            with self.assertRaises(ValueError):connector_id(device,display)

    def test_operation_mode_preserved(self):
        with patch.object(player,'operation_mode',return_value='on'):self.assertTrue(player.allowed_now({}))
        with patch.object(player,'operation_mode',return_value='off'):self.assertFalse(player.allowed_now({}))

    def test_invalid_renderer_config_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            d=json.loads((ROOT/'candidate/config.json').read_text());d['renderer']='wayland'
            p=Path(temp)/'bad.json';p.write_text(json.dumps(d))
            with self.assertRaises(ValueError):player.load_config(p)


if __name__=='__main__':unittest.main()
