import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bootstrap',ROOT/'bootstrap.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class BootstrapTests(unittest.TestCase):
 def test_detects_only_known_boards(self):
  self.assertEqual(mod.detect('Raspberry Pi 5 Model B'),'pi5'); self.assertEqual(mod.detect('Raspberry Pi 4 Model B'),'pi4')
  with self.assertRaises(SystemExit): mod.detect('Raspberry Pi 3 Model B')
if __name__=='__main__': unittest.main()
