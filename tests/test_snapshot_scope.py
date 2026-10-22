"""Board isolation and snapshot safety: do not accidentally package Pi5 or user data."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]


class Pi4SnapshotScopeTests(unittest.TestCase):
    def test_explicit_pi4_profile_only(self):
        profile=json.loads((ROOT/'profile.json').read_text())
        self.assertEqual(profile['target'],'raspberry-pi-4-model-b')
        self.assertEqual(profile['branch'],'capibarra-lite-pi4')
        self.assertEqual(profile['gpu_context'],'drm')
        config=json.loads((ROOT/'candidate/config.json').read_text())
        self.assertEqual(config['renderer'],'drm-overlay')
        self.assertFalse((ROOT/'config.pi5.json').exists())
        self.assertFalse((ROOT/'candidate/labwc.service').exists())
        self.assertFalse((ROOT/'PI5_STABLE_SNAPSHOT.md').exists())

    def test_runtime_payload_hashes_match_manifest(self):
        files=json.loads((ROOT/'manifest.json').read_text())
        self.assertEqual(len(files),7)
        for item in files:
            p=ROOT/'candidate'/item['file']
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),item['sha256'],item['file'])

    def test_pi5_rejected_before_any_install_action(self):
        tree=ast.parse((ROOT/'install.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='preflight')
        forbidden=Mock(side_effect=AssertionError('Side effect before board validation'))
        namespace={'Path':Path,'run':forbidden,'is_active':forbidden,'FILES':[],
                   'ROOT':ROOT,'sys':sys,'hashlib':hashlib}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<model-guard>','exec'),namespace)
        with patch.object(Path,'read_text',return_value='Raspberry Pi 5 Model B Rev 1.0'):
            with self.assertRaises(AssertionError):namespace['preflight']()
        forbidden.assert_not_called()

    def test_no_operator_data_or_media_bundled(self):
        banned={'playlists.json','schedules.json','audio_config.json','operation_mode.json',
                'network_config.json','devices.json','.env','installed.json','acceptance.json'}
        for path in (ROOT/'candidate').rglob('*'):
            if not path.is_file():continue
            self.assertNotIn(path.name,banned,str(path))
            self.assertNotIn(path.suffix.lower(),{'.mp4','.mkv','.mov','.avi','.hevc','.h265'},str(path))
        self.assertEqual(list((ROOT/'candidate/public').glob('*.json')),[])

    def test_static_ui_assets_present(self):
        for name in ('app.js','app.css','index.html','operation-ui.js','logo.png','placeholder.jpg'):
            self.assertTrue((ROOT/'candidate/public'/name).is_file(),name)


if __name__=='__main__':unittest.main()
