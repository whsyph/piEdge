import collections, importlib.util, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fresh', ROOT / 'install-fresh.py')
assert spec and spec.loader
fresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh)

User = collections.namedtuple('User', 'pw_name pw_uid pw_gid')

class FreshInstallTests(unittest.TestCase):
    def make_tree(self, tmp, model='Raspberry Pi 5 Model B Rev 1.0\0', codename='bookworm', arch='arm64', uid=1000):
        root = Path(tmp) / 'root'
        (root / 'proc/device-tree').mkdir(parents=True)
        (root / 'proc/device-tree/model').write_text(model)
        (root / 'proc/1').mkdir(parents=True)
        (root / 'proc/1/comm').write_text('systemd\n')
        (root / 'etc').mkdir(parents=True)
        (root / 'etc/os-release').write_text(f'ID=debian\nVERSION_CODENAME={codename}\n')
        (root / 'etc/rpi-issue').write_text('Raspberry Pi reference 2024-03-15\n')
        (root / 'run/systemd/system').mkdir(parents=True)
        (root / 'etc/systemd/system').mkdir(parents=True)
        return root

    def test_pi_user_contract(self):
        saved = fresh.pi_user
        try:
            fresh.pi_user = lambda: User('pi', 1000, 1000)
            self.assertEqual(fresh.pi_user().pw_uid, 1000)
            with self.assertRaisesRegex(ValueError, 'User pi must have UID 1000'):
                fresh.validate_user(User('pi', 1001, 1001))
        finally:
            fresh.pi_user = saved

    def test_rejects_wrong_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(tmp, model='Raspberry Pi 4 Model B Rev 1.5\0')
            saved = fresh.pi_user
            fresh.pi_user = lambda: User('pi', 1000, 1000)
            try:
                with self.assertRaisesRegex(ValueError, 'Only Raspberry Pi 5'):
                    fresh.check(source=ROOT, root=root)
            finally:
                fresh.pi_user = saved

    def test_rejects_non_bookworm(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(tmp, codename='bullseye')
            saved = fresh.pi_user
            fresh.pi_user = lambda: User('pi', 1000, 1000)
            try:
                with self.assertRaisesRegex(ValueError, 'Raspberry Pi OS Bookworm required'):
                    fresh.check(source=ROOT, root=root)
            finally:
                fresh.pi_user = saved

    def test_rejects_existing_deployment_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(tmp)
            (root / 'opt').mkdir(parents=True)
            (root / 'opt/pi5-signage').mkdir()
            saved_user = fresh.pi_user
            saved_run = fresh.run
            fresh.pi_user = lambda: User('pi', 1000, 1000)
            fresh.run = lambda args: collections.namedtuple('R', 'stdout')(
                'arm64\n' if 'dpkg' in args else 'ActiveState=inactive\nUnitFileState=disabled\n' if 'systemctl' in args else 'bash\n'
            )
            try:
                with self.assertRaisesRegex(ValueError, 'Existing deployment/data: /opt/pi5-signage'):
                    fresh.check(source=ROOT, root=root)
            finally:
                fresh.pi_user = saved_user
                fresh.run = saved_run

    def test_seatd_override_collision_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(tmp)
            collision = root / 'etc/systemd/system/seatd.service.d'
            collision.mkdir()
            saved_user, saved_run = fresh.pi_user, fresh.run
            fresh.pi_user = lambda: User('pi', 1000, 1000)
            commands = []
            fresh.run = lambda args: (commands.append(args) or collections.namedtuple('R', 'stdout')('arm64\n' if 'dpkg' in args else 'ActiveState=inactive\nUnitFileState=disabled\n' if 'systemctl' in args else 'bash\n'))
            try:
                with self.assertRaisesRegex(ValueError, 'Existing service deployment'):
                    fresh.check(source=ROOT, root=root)
                self.assertEqual(commands, [['dpkg', '--print-architecture']])
                self.assertEqual(list(collision.iterdir()), [])
            finally:
                fresh.pi_user, fresh.run = saved_user, saved_run

    def test_units_have_fresh_boot_runtime_contract(self):
        player = (ROOT / 'pi5-signage.service').read_text()
        compositor = (ROOT / 'labwc.service').read_text()
        self.assertIn('User=pi', player)
        self.assertIn('XDG_RUNTIME_DIR=/run/user/1000', player)
        self.assertIn('Requires=seatd.service', compositor)

    def test_mocked_install_creates_paths_and_never_starts_playback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_tree(tmp)
            saved_user = fresh.pi_user
            saved_run = fresh.run
            saved_euid = getattr(fresh.os, 'geteuid', None)
            saved_chown = getattr(fresh.os, 'chown', None)
            commands = []
            fresh.pi_user = lambda: User('pi', 1000, 1000)
            fresh.os.geteuid = lambda: 0
            fresh.os.chown = lambda p, u, g: None
            def mock_run(args):
                commands.append(args)
                out = 'arm64\n' if 'dpkg' in args else 'ActiveState=inactive\nUnitFileState=disabled\n' if 'systemctl' in args else 'bash\n'
                return collections.namedtuple('R', 'stdout')(out)
            fresh.run = mock_run
            try:
                fresh.install(source=ROOT, root=root)
                self.assertTrue((root / 'opt/pi5-signage/signage.py').exists())
                self.assertTrue((root / 'opt/pi5-signage/profiles/pi5.json').exists())
                self.assertTrue((root / 'var/lib/pi5-signage/videos').is_dir())
                self.assertTrue((root / 'etc/pi5-signage.json').exists())
                self.assertTrue((root / 'etc/systemd/system/pi5-signage.service').exists())
                self.assertTrue((root / 'etc/systemd/system/seatd.service.d/capibarra.conf').exists())
                # Verify neither systemctl start nor enable was called!
                flat_cmds = [' '.join(str(x) for x in c) for c in commands]
                for c in flat_cmds:
                    self.assertNotIn('systemctl start', c)
                    self.assertNotIn('systemctl enable', c)
            finally:
                fresh.pi_user = saved_user
                fresh.run = saved_run
                if saved_euid: fresh.os.geteuid = saved_euid
                if saved_chown: fresh.os.chown = saved_chown

if __name__ == '__main__':
    unittest.main()
