import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from preflight import validate


class ReleaseTests(unittest.TestCase):
    def prepared_release(self, temp):
        subprocess.run([sys.executable, str(ROOT/'scripts/build-release.py'), 'pi5', '--dist', str(Path(temp)/'dist')], check=True, capture_output=True)
        archive = Path(temp)/'dist/capibarra-lite-pi5-0.2.0-rc1.tar.gz'
        with tarfile.open(archive, 'r:gz') as tf: tf.extractall(Path(temp), filter='data')
        return Path(temp)/'capibarra-lite-pi5-0.2.0-rc1'

    def test_preflight_rejects_package_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.prepared_release(tmp)
            with self.assertRaises(ValueError):
                validate(source, model='Raspberry Pi 4 Model B', config=Path(tmp)/'missing-config', labwc=Path(tmp)/'missing-unit')

    def test_labwc_mismatch_refuses_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.prepared_release(tmp)
            unit = Path(tmp)/'labwc.service'
            unit.write_text('operator-owned')
            with self.assertRaisesRegex(ValueError, 'labwc unit differs'):
                validate(source, model='Raspberry Pi 5 Model B', config=Path(tmp)/'missing-config', labwc=unit)

    def test_config_without_profile_is_refused_before_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.prepared_release(tmp)
            config = Path(tmp) / 'config.json'
            config.write_text(json.dumps({'media_dir':'/tmp','start':'00:00','end':'23:59','display':'HDMI-A-1','audio':False,'audio_device':'x','retry_seconds':5}))
            before = config.read_bytes()
            with self.assertRaises(ValueError):
                validate(source, model='Raspberry Pi 5 Model B', config=config, labwc=Path(tmp)/'absent')
            self.assertEqual(config.read_bytes(), before)

    def test_build_artifacts_are_profile_isolated_and_checkable(self):
        with tempfile.TemporaryDirectory() as tmp:
            for target in ('pi5',):
                subprocess.run([sys.executable, str(ROOT/'scripts/build-release.py'), target, '--dist', tmp], check=True, capture_output=True, text=True)
                archive = Path(tmp) / f'capibarra-lite-{target}-0.2.0-rc1.tar.gz'
                with tarfile.open(archive, 'r:gz') as tar:
                    tar.extractall(Path(tmp)/target, filter='data')
                root = Path(tmp)/target/f'capibarra-lite-{target}-0.2.0-rc1'
                manifest = json.loads((root/'release.json').read_text())
                self.assertEqual(manifest['target'], target)
                self.assertTrue((root/f'profiles/{target}.json').exists())
                self.assertEqual([p.name for p in (root/'profiles').iterdir()], ['pi5.json'])
                self.assertFalse((root/'config.pi4b.json').exists())
                result = subprocess.run([sys.executable, str(root/'signage.py'), '--config', str(root/f'config.{target}.json'), '--check'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
