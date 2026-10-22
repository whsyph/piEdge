"""Live acceptance for the installed Pi4 direct DRM profile; preserve original preferences."""
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0,'/opt/pi5-signage')
from drm_power import output_power
BASE='http://localhost:8080'
ROOT=Path('/home/pi/pi4-direct-drm-stage')
records=[]

def api(path,data=None):
    req=urllib.request.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

def cmd(args):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(3);s.connect('/run/user/1000/capibarra-mpv.sock')
        s.sendall((json.dumps({'command':args,'request_id':93})+'\n').encode())
        with s.makefile('r') as f:
            for line in f:
                r=json.loads(line)
                if r.get('request_id')==93:return r
    raise RuntimeError('No IPC reply')

def get(k):return cmd(['get_property',k]).get('data')

def pids():return subprocess.run(['pgrep','-x','mpv'],capture_output=True,text=True).stdout.split()

def active():
    return {u:subprocess.run(['systemctl','is-active','--quiet',u]).returncode==0 for u in ('pi5-signage.service','cms-signage.service','labwc.service','layar-gabungan.service','layar1.service','layar2.service')}

def mode(value):
    r=api('/api/operation-mode',{'mode':value});assert r['success'] and api('/api/operation-mode')['mode']==value
    print('MODE',value,flush=True)

def ready():
    for _ in range(50):
        try:
            if get('vo-configured') is True and get('time-pos') is not None:
                assert get('hwdec-current')=='drm';return
        except OSError:pass
        time.sleep(.3)
    raise RuntimeError('Renderer not ready')

def asleep():
    for _ in range(30):
        if not pids() and output_power('/dev/dri/card1','HDMI-A-1')['dpms']==3:
            time.sleep(2)
            assert output_power('/dev/dri/card1','HDMI-A-1')['dpms']==3
            print('PASS retained DPMS OFF, no mpv',flush=True);return
        time.sleep(.3)
    raise RuntimeError('Did not enter native DRM sleep')

def audio(settings):
    r=api('/api/audio/global',dict(screen=1,**settings));assert r['success'] and r['applied'],r
    expected=settings['global_mute']
    assert get('mute')==expected
    assert api('/api/audio/config')['screen1']['global_mute']==expected
    print('PASS live/saved mute',expected,flush=True)

original_mode=api('/api/operation-mode')['mode']
original_audio=api('/api/audio/config')['screen1']
settings={k:original_audio[k] for k in ('global_mute','output_device','channel_mode')}
try:
    mode('on');ready()
    before=pids();assert len(before)==1
    argv=Path('/proc/'+before[0]+'/cmdline').read_bytes().decode().split('\x00')
    for value in ('--gpu-context=drm','--gpu-hwdec-interop=drmprime-overlay','--video-sync=audio'):assert value in argv
    topology=active();assert topology['pi5-signage.service'] and topology['cms-signage.service']
    assert not any(topology[u] for u in ('labwc.service','layar-gabungan.service','layar1.service','layar2.service'))
    print('PASS one direct DRM renderer; CMS active; compositor and legacy players inactive',flush=True)
    audio(dict(settings,global_mute=True))
    mode('off');asleep()
    mode('on');ready();assert get('mute') is True
    print('PASS mute persisted across sleep/wake',flush=True)
    audio(dict(settings,global_mute=False))
    old_pid=pids()[0]
    result=api('/api/control',{'screen':1,'action':'restart_service'});assert result['success'],result
    ready();assert pids()[0]!=old_pid
    print('PASS actual CMS HTTP restart and new direct renderer',flush=True)
    # Seek to EOF without mutating the operator playlist; supervisor must launch the next cycle.
    old_pid=pids()[0];name=get('filename');duration=get('duration')
    r=cmd(['seek',max(0,duration-.3),'absolute+exact']);assert r['error']=='success',r
    for _ in range(50):
        time.sleep(.3)
        if pids() and pids()[0]!=old_pid:
            try:
                if get('filename')==name and get('vo-configured') is True:break
            except OSError:pass
    else:raise RuntimeError('Playlist did not loop into a new renderer')
    print('PASS playlist EOF / next cycle; file retained',flush=True)
    mode('auto');asleep()
    result=api('/api/control',{'screen':1,'action':'restart_service'});assert result['success']
    asleep()
    print('PASS AUTO outside schedule and restart remain asleep',flush=True)
finally:
    mode('on');ready();audio(settings)
    if original_mode!='on':mode(original_mode)
    print('FINAL original operation mode and global audio preferences restored',flush=True)
    records.append({'final_mode':api('/api/operation-mode'),'topology':active(),'audio':api('/api/audio/config')})
    (ROOT/'acceptance.json').write_text(json.dumps(records,indent=2))
