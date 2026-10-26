#!/usr/bin/env python3
"""Fetch the matching board branch, check it, then optionally install it."""
import argparse, os, pathlib, re, subprocess, sys

BRANCHES = {'pi5': 'capibarra-lite', 'pi4': 'capibarra-lite-pi4'}
def run(args, cwd=None): return subprocess.run(args, cwd=cwd, check=True, text=True)
def detect(model):
    if re.fullmatch(r'Raspberry Pi 5 Model B(?: Rev \d+\.\d+)?', model): return 'pi5'
    if re.fullmatch(r'Raspberry Pi 4 Model B(?: Rev \d+\.\d+)?', model): return 'pi4'
    raise SystemExit('Only Raspberry Pi 4 or Raspberry Pi 5 is supported.')
def main():
    p=argparse.ArgumentParser(); p.add_argument('--check', action='store_true'); p.add_argument('--model-file'); p.add_argument('--dir', default=str(pathlib.Path.home()/'capibarra-bootstrap')); p.add_argument('--repo-url', default='https://github.com/whsyph/piEdge.git', help='Source repository (default: official piEdge GitHub repository).')
    a=p.parse_args()
    if getattr(os, 'geteuid', lambda: -1)() == 0: raise SystemExit('Run bootstrap as an ordinary user; sudo is requested only after preflight.')
    if not a.repo_url: raise SystemExit('Bootstrap URL is unavailable until publish; supply --repo-url after publication.')
    if not a.repo_url.startswith(('https://','ssh://','git@')): raise SystemExit('A trusted HTTPS/SSH repository URL is required.')
    if 'example.invalid' in a.repo_url: raise SystemExit('Bootstrap URL is unavailable until publish.')
    model=pathlib.Path(a.model_file or '/proc/device-tree/model').read_text(errors='replace').rstrip('\0\n')
    board=detect(model); branch=BRANCHES[board]; root=pathlib.Path(a.dir)
    if root.exists():
        raise SystemExit(f'{root} already exists; choose an unused --dir (no existing checkout is overwritten).')
    run(['git','clone','--no-checkout',a.repo_url,str(root)])
    run(['git','fetch','origin',branch], root)
    run(['git','checkout','--detach',f'origin/{branch}'],root)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(); print(f'{board} {branch} {commit}',flush=True)
    if not (root/'install-fresh.py').is_file(): raise SystemExit(f'{branch} has no install-fresh.py; nothing executed.')
    run([sys.executable,'install-fresh.py','--check'],root)
    if not a.check: run(['sudo','/usr/bin/python3',str(root.resolve()/'install-fresh.py')],root)
if __name__ == '__main__': main()
