#!/usr/bin/env python3
"""Guarded Pi4 DRM cutover; exact backups, external rollback timer, no CMS/data replacement."""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent
FILES=json.loads((ROOT/'manifest.json').read_text())
UNIT='pi5-signage.service'


def run(*args,check=True):
    return subprocess.run(args,check=check,timeout=40)


def state(unit,field):
    return subprocess.check_output(['systemctl',field,unit],text=True).strip()


def is_active(unit):
    return subprocess.run(['systemctl','is-active','--quiet',unit]).returncode==0


def write_atomic(target,data,uid,gid,mode):
    fd,name=tempfile.mkstemp(dir=target.parent,prefix='.pi4-drm-')
    try:
        with os.fdopen(fd,'wb') as f:
            os.fchown(f.fileno(),uid,gid);os.fchmod(f.fileno(),mode)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)


def rollback(backup):
    saved=json.loads((backup/'state.json').read_text())
    run('systemctl','stop',UNIT,'labwc.service',check=False)
    for item in saved['files']:
        target=Path(item['target'])
        if item['existed']:
            write_atomic(target,(backup/item['backup']).read_bytes(),item['uid'],item['gid'],item['mode'])
        elif target.exists():target.unlink()
    # Compatibility with the initial six-file backup: preview safety was applied
    # afterward as the CMS owner. Restore it too, but never overwrite later edits.
    cms_target=Path('/home/pi/museum_signage/server.py')
    cms_saved=any(x['target']==str(cms_target) for x in saved['files'])
    preview_backup=ROOT/'cms-preview-backup'
    if not cms_saved and (preview_backup/'metadata.json').exists():
        metadata=json.loads((preview_backup/'metadata.json').read_text())
        current=hashlib.sha256(cms_target.read_bytes()).hexdigest()
        original=(preview_backup/'server.py').read_bytes()
        assert hashlib.sha256(original).hexdigest()==metadata['original_sha256']
        if current==metadata['sha256']:
            st=cms_target.stat()
            write_atomic(cms_target,original,st.st_uid,st.st_gid,st.st_mode&0o777)
        elif current!=metadata['original_sha256']:
            print('CMS has later edits; retaining them. Renderer guard falls back safely to Wayland.',flush=True)
    if cms_saved or preview_backup.exists():
        run('systemctl','restart','cms-signage.service')
    run('systemctl','daemon-reload')
    for unit,info in saved['units'].items():
        run('systemctl','enable' if info['enabled'] else 'disable',unit)
    run('/usr/bin/chvt',saved['vt'][3:],check=False)
    if saved['units']['labwc.service']['active']:run('systemctl','start','labwc.service')
    if saved['units'][UNIT]['active']:run('systemctl','start',UNIT)
    if saved.get('timer'):run('systemctl','stop',saved['timer']+'.timer',check=False)
    print('ROLLBACK COMPLETE:',backup,flush=True)


def preflight():
    assert 'Raspberry Pi 4 Model B' in Path('/proc/device-tree/model').read_text()
    for item in FILES:
        p=ROOT/'candidate'/item['file']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'], 'Candidate hash mismatch '+str(p)
        if p.suffix=='.py':compile(p.read_text(),str(p),'exec')
        live=Path(item['target'])
        if item['original_sha256'] is None:assert not live.exists(),'Unexpected pre-existing file '+str(live)
        else:assert hashlib.sha256(live.read_bytes()).hexdigest()==item['original_sha256'],'Live source changed '+str(live)
    for unit in ('layar-gabungan.service','layar1.service','layar2.service'):
        assert not is_active(unit),'Legacy owner active '+unit
    run(sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-v')
    run('systemd-analyze','verify',str(ROOT/'candidate/pi5-signage.service'))
    print('PREFLIGHT PASS',flush=True)


def ipc(command):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(2);s.connect('/run/user/1000/capibarra-mpv.sock')
        s.sendall((json.dumps({'command':command,'request_id':76})+'\n').encode())
        with s.makefile('r') as f:
            for line in f:
                r=json.loads(line)
                if r.get('request_id')==76:return r
    raise RuntimeError('No IPC reply')


def smoke():
    assert is_active(UNIT) and is_active('cms-signage.service')
    assert not is_active('labwc.service')
    sys.path.insert(0,'/opt/pi5-signage')
    spec=importlib.util.spec_from_file_location('installed_drm','/opt/pi5-signage/signage.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=module.load_config(Path('/etc/pi5-signage.json'))
    if module.allowed_now(config):
        ready=False
        for _ in range(50):
            try:
                r=ipc(['get_property','vo-configured'])
                if r.get('data') is True and ipc(['get_property','hwdec-current']).get('data')=='drm':
                    ready=True;break
            except OSError:pass
            time.sleep(.3)
        assert ready,'Direct video did not become ready'
        before=ipc(['get_property','time-pos'])['data'];time.sleep(2)
        after=ipc(['get_property','time-pos'])['data'];assert after>before,(before,after)
        print('SMOKE direct DRM + progressing video:',before,after,flush=True)
    else:
        from drm_power import output_power
        for _ in range(15):
            if output_power(config['drm_device'],config['display'])['dpms']==3:
                print('SMOKE AUTO sleep DPMS off',flush=True);return
            time.sleep(.3)
        raise RuntimeError('Sleep DPMS did not turn off')


def install():
    preflight()
    if os.geteuid()!=0:raise SystemExit('Validated. Root required to install; live files unchanged.')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=Path('/home/pi/pi4-direct-drm-backups')/stamp;backup.mkdir(parents=True)
    saved={'files':[],'units':{},'vt':Path('/sys/class/tty/tty0/active').read_text().strip(),
           'timer':'pi4-drm-install-recover-'+stamp}
    for unit in ('labwc.service',UNIT):
        result=subprocess.run(['systemctl','is-enabled',unit],capture_output=True,text=True)
        saved['units'][unit]={'enabled':result.stdout.strip()=='enabled','active':is_active(unit)}
    for i,item in enumerate(FILES):
        target=Path(item['target']);info={'target':str(target),'existed':target.exists(),'backup':str(i)}
        if target.exists():
            st=target.stat();info.update(uid=st.st_uid,gid=st.st_gid,mode=st.st_mode&0o777)
            shutil.copy2(target,backup/str(i))
        saved['files'].append(info)
    (backup/'state.json').write_text(json.dumps(saved,indent=2))
    run('systemd-run','--quiet','--unit='+saved['timer'],'--on-active=180s','--timer-property=AccuracySec=1s',
        '/usr/bin/python3',str(Path(__file__).resolve()),'--rollback',str(backup))
    def interrupted(signum,frame):raise RuntimeError('Interrupted '+str(signum))
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,interrupted)
    try:
        run('systemctl','stop',UNIT,'labwc.service')
        for item in FILES:
            target=Path(item['target'])
            st=target.stat() if target.exists() else None
            mode=(st.st_mode&0o777) if st else 0o644
            write_atomic(target,(ROOT/'candidate'/item['file']).read_bytes(),st.st_uid if st else 0,st.st_gid if st else 0,mode)
        run('systemctl','daemon-reload')
        if any(x['target']=='/home/pi/museum_signage/server.py' for x in FILES):
            run('systemctl','restart','cms-signage.service')
        run('systemctl','disable','labwc.service')
        run('systemctl','enable',UNIT)
        run('systemctl','start',UNIT)
        smoke()
        for item in FILES:assert hashlib.sha256(Path(item['target']).read_bytes()).hexdigest()==item['sha256']
        run('systemctl','stop',saved['timer']+'.timer')
        (ROOT/'installed.json').write_text(json.dumps({'backup':str(backup),'installed_at':stamp,'files':FILES},indent=2))
        print('INSTALLED:',backup,flush=True)
        print('Rollback: sudo python3 '+str(Path(__file__).resolve())+' --rollback '+str(backup),flush=True)
    except Exception:
        rollback(backup)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--rollback',type=Path)
    args=parser.parse_args()
    if args.rollback:
        if os.geteuid()!=0:raise SystemExit('Rollback requires root')
        rollback(args.rollback)
    elif args.check:preflight()
    else:install()
