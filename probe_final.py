"""Final installed-profile probe, including repeated safe CMS preview requests."""
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.request

ROOT=Path('/home/pi/pi4-direct-drm-stage')
BASE='http://localhost:8080'

def api(path,data=None):
    req=urllib.request.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r:return json.load(r)

def get(prop):
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(3);s.connect('/run/user/1000/capibarra-mpv.sock')
        s.sendall((json.dumps({'command':['get_property',prop],'request_id':39})+'\n').encode())
        with s.makefile('r') as stream:
            for line in stream:
                r=json.loads(line)
                if r.get('request_id')==39:return r.get('data')
    raise RuntimeError('No IPC response')

assert api('/api/operation-mode')['mode']=='on'
response=api('/api/control',{'screen':1,'action':'restart_service'})
assert response['success'],response
for _ in range(40):
    try:
        if get('vo-configured') is True and get('time-pos') is not None:break
    except OSError:pass
    time.sleep(.25)
else:raise RuntimeError('No video after restart')
time.sleep(3)
records=[]
for i in range(7):
    started=time.monotonic()
    with urllib.request.urlopen(BASE+'/api/screenshot?screen=1',timeout=3) as r:
        assert r.headers.get('X-Preview-Available')=='false'
        assert r.headers.get('Content-Type','').startswith('image/svg+xml')
        assert b'Preview langsung dinonaktifkan' in r.read()
    record={'wall':time.monotonic(),'preview_seconds':time.monotonic()-started,
            'pid':subprocess.check_output(['pgrep','-x','mpv'],text=True).strip(),
            **{k:get(k) for k in ('path','time-pos','hwdec-current','frame-drop-count','decoder-frame-drop-count','avsync','mute')}}
    records.append(record);print(json.dumps(record),flush=True)
    if i<6:time.sleep(10)
a,b=records[0],records[-1]
assert a['pid']==b['pid'] and a['path']==b['path']
summary={'wall_delta':b['wall']-a['wall'],'video_delta':b['time-pos']-a['time-pos'],
         'drop_delta':b['frame-drop-count']-a['frame-drop-count'],
         'max_abs_avsync':max(abs(r['avsync']) for r in records if r['avsync'] is not None),
         'preview_requests':len(records),'all_previews_non_capturing':True}
print('FINAL SUMMARY',json.dumps(summary),flush=True)
(ROOT/'performance-final.json').write_text(json.dumps({'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                                                      'samples':records,'summary':summary},indent=2))
