#!/usr/bin/env python3
"""Build reproducible-ish target-isolated RC tarballs using Python stdlib."""
import argparse, hashlib, json, subprocess, tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ['signage.py','splash.py','splash.sh','install.sh','labwc.service','pi5-signage.service','scripts/preflight.py']
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(); p.add_argument('target', choices=['pi5']); p.add_argument('--version', default='0.2.0-rc1'); p.add_argument('--dist', type=Path, default=ROOT/'dist'); a=p.parse_args()
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 names=INCLUDE+['scripts/build-release.py']+[f'profiles/{a.target}.json',f'config.{a.target}.json']
 files={name:sha(ROOT/name) for name in names}
 manifest={'target':a.target,'version':a.version,'commit':commit,'files':files}
 stage=a.dist/f'capibarra-lite-{a.target}-{a.version}'
 if stage.exists():
  import shutil; shutil.rmtree(stage)
 for name in names:
  dst=stage/name; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes((ROOT/name).read_bytes())
 (stage/'release.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
 archive=a.dist/f'{stage.name}.tar.gz'; a.dist.mkdir(exist_ok=True)
 with tarfile.open(archive,'w:gz') as tf:
  for item in sorted(stage.rglob('*')): tf.add(item,arcname=item.relative_to(a.dist))
 print(archive); print(sha(archive))
if __name__=='__main__': main()
