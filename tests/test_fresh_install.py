import hashlib, importlib.util, json, tempfile, types, unittest
from pathlib import Path
from unittest.mock import patch
SPEC=importlib.util.spec_from_file_location('fresh', Path(__file__).parents[1]/'install-fresh.py'); fresh=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(fresh)
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name)
  for n,v in {'proc/device-tree/model':'Raspberry Pi 4 Model B Rev 1.5\0','etc/os-release':'ID=debian\nVERSION_CODENAME=bookworm\n','etc/rpi-issue':'Raspberry Pi OS','proc/1/comm':'systemd\n'}.items():
   p=self.root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v)
  (self.root/'run/systemd/system').mkdir(parents=True); self.source=self.root/'src';(self.source/'candidate').mkdir(parents=True); rows=[]
  for n in fresh.PAYLOAD:
   b=(n+'data').encode();(self.source/'candidate'/n).write_bytes(b);rows.append({'file':n,'sha256':hashlib.sha256(b).hexdigest()})
  (self.source/'manifest.json').write_text(json.dumps(rows));self.user=types.SimpleNamespace(pw_uid=1000,pw_gid=1000)
 def tearDown(self):self.t.cleanup()
 def command(self,a):
  if a[:2]==['dpkg','--print-architecture']:return types.SimpleNamespace(stdout='arm64\n')
  if a[:2]==['ps','-eo']:return types.SimpleNamespace(stdout='')
  return types.SimpleNamespace(stdout='ActiveState=inactive\nUnitFileState=disabled\n')
 def runcheck(self, missing=False):
  with patch.object(fresh,'run',side_effect=self.command),patch.object(fresh,'lookup_user',return_value=self.user),patch.object(fresh,'lookup_group',side_effect=KeyError if missing else lambda n:object()):return fresh.check(self.source,self.root,'aarch64')
 def test_ok(self):self.assertIs(self.runcheck(),self.user)
 def test_group_missing(self):
  with self.assertRaisesRegex(ValueError,'Required group'):self.runcheck(True)
 def test_tamper_rejected(self):
  (self.source/'candidate/signage.py').write_text('bad')
  with self.assertRaisesRegex(ValueError,'hash-mismatched'):self.runcheck()
 def test_competitor_dropin_refused(self):
  (self.root/'etc/systemd/system/labwc.service.d').mkdir(parents=True)
  with self.assertRaisesRegex(ValueError,'Existing service path'):self.runcheck()
 def test_preexisting_media_parent_refused_unchanged(self):
  p=self.root/'var/lib/pi5-signage';p.mkdir(parents=True);(p/'videos').write_text('keep')
  with self.assertRaisesRegex(ValueError,'Existing deployment'):self.runcheck()
  self.assertEqual((p/'videos').read_text(),'keep')
 @patch.object(fresh,'check')
 @patch.object(fresh,'run')
 def test_apt_failure_no_writes(self,run,check):
  check.return_value=self.user;run.side_effect=__import__('subprocess').CalledProcessError(1,['apt-get'])
  with patch.object(fresh.os,'geteuid',return_value=0,create=True),patch.object(fresh.Path,'mkdir') as mkdir:
   with self.assertRaises(__import__('subprocess').CalledProcessError):fresh.install(self.source,self.root)
  mkdir.assert_not_called()
 @patch.object(fresh,'check')
 @patch.object(fresh,'run')
 def test_no_autostart_and_splash_mode(self,run,check):
  check.return_value=self.user
  (self.root/'etc/systemd/system').mkdir(parents=True)
  with patch.object(fresh.os,'geteuid',return_value=0,create=True),patch.object(fresh.os,'chown',create=True),patch.object(fresh.Path,'chmod',autospec=True) as chmod:fresh.install(self.source,self.root)
  cmds=[c.args[0] for c in run.call_args_list];self.assertFalse(any(c[:2] in (['systemctl','start'],['systemctl','enable']) for c in cmds))
  self.assertIn((self.root/'opt/pi5-signage/splash.sh',0o755),[(c.args[0],c.args[1]) for c in chmod.call_args_list])
if __name__=='__main__':unittest.main()
