"""One same-container stop/start; replay only its own still-valid SA token."""
import subprocess,json,urllib.request,urllib.error,datetime,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];NAME='rv-a-worker-live-runtime-worker-a';WORKER='live-runtime-worker-a';R=[]
def docker(*args):
 p=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
 if p.returncode:raise RuntimeError('docker '+str(args[:2])+' failed')
 return p.stdout
def state():
 x=json.loads(docker('inspect',NAME))[0];return dict(id=x['Id'],running=x['State']['Running'],status=x['State']['Status'],started_at=x['State']['StartedAt'],finished_at=x['State']['FinishedAt'])
def record(kind,**kw):
 R.append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));(ROOT/'evidence/worker-ready-restart-live.json').write_text(json.dumps(R,indent=2),encoding='utf8')
old=docker('exec',NAME,'cat','/var/run/secrets/agentteams/token').strip()
def api(method,path):
 q=urllib.request.Request('http://127.0.0.1:28090'+path,data=b'{}' if method=='POST' else None,headers={'Authorization':'Bearer '+old,'Content-Type':'application/json'},method=method)
 try:r=urllib.request.urlopen(q,timeout=15)
 except urllib.error.HTTPError as e:r=e
 raw=r.read().decode();v=json.loads(raw) if raw else None
 if isinstance(v,dict):v={k:v[k] for k in ('name','phase','containerState','message','state') if k in v}
 record('old_token_http',method=method,path=path,status=r.code,response=v,container=state());return r.code
before=state();record('before',container=before,token_source='actual Worker projected SA token, retained in memory only')
try:
 docker('stop','-t','5',NAME);stopped=state();record('after_one_stop',container=stopped,valid_stopped_window=not stopped['running'])
 api('GET',f'/api/v1/workers/{WORKER}/status')
 api('POST',f'/api/v1/workers/{WORKER}/ready')
 api('GET',f'/api/v1/workers/{WORKER}/status')
finally:
 if not state()['running']:docker('start',NAME)
 after=state();record('restored',container=after,same_container_id=after['id']==before['id'],started_at_changed=after['started_at']!=before['started_at'])
current=docker('exec',NAME,'cat','/var/run/secrets/agentteams/token').strip()
record('token_comparison',same_projected_token=current==old)
api('POST',f'/api/v1/workers/{WORKER}/ready')
api('GET',f'/api/v1/workers/{WORKER}/status')
record('finished',container=state(),scope='same container runtime restart only; no deletion/recreation, expired token, rotation or CR state changes')
print(json.dumps(R[-1]))
