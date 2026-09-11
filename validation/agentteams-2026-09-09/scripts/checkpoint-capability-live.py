"""Read-only checkpoint proxy/direct endpoint shape check, not a restore experiment."""
import datetime as dt,hashlib,json,subprocess,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def docker(*args):return subprocess.check_output(['docker',*args],text=True,encoding='utf-8',timeout=30).strip()
token=docker('exec','rv-a-controller','cat','/var/run/agentteams/cli-token')
c=json.loads(docker('inspect','rv-a-worker-live-twin-worker'))[0]
port=c['NetworkSettings']['Ports']['8088/tcp'][0]['HostPort']
records=[]
def fetch(kind,url,auth=False):
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token} if auth else {})
    try:res=urllib.request.urlopen(req,timeout=15)
    except urllib.error.HTTPError as e:res=e
    raw=res.read(); row={'kind':kind,'url':url,'status':res.code,'content_type':res.headers.get('Content-Type'),
        'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    try:
        body=json.loads(raw)
        row['json']=body if kind!='openapi' else {'paths':[p for p in body.get('paths',{}) if 'checkpoint' in p], 'path_count':len(body.get('paths',{}))}
    except (ValueError,UnicodeDecodeError):row['non_json_prefix']=raw[:180].decode('utf-8',errors='replace')
    records.append(row)
for sub in ('status','graph?limit=5'):
    fetch('controller-proxy',f'http://127.0.0.1:28090/api/v1/workers/live-twin-worker/checkpoints/{sub}',True)
    fetch('direct-runtime',f'http://127.0.0.1:{port}/workspace/checkpoints/{sub}')
fetch('openapi',f'http://127.0.0.1:{port}/openapi.json')
fetch('openapi',f'http://127.0.0.1:{port}/api/openapi.json')
fetch('alternative-api-prefix',f'http://127.0.0.1:{port}/api/workspace/checkpoints/status')
inventory=json.loads(docker('exec','rv-a-worker-live-twin-worker','/opt/venv/qwenpaw/bin/python','-c',
    'import pathlib,json; p=pathlib.Path("/opt/venv/qwenpaw/lib/python3.11/site-packages/qwenpaw/app");fs=list(p.rglob("*.py"));print(json.dumps({"files_scanned":len(fs),"files_containing_checkpoint":[str(f) for f in fs if "checkpoint" in f.read_text(errors="replace").lower()]}))'))
out={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'qwenpaw':docker('exec','rv-a-worker-live-twin-worker','/opt/venv/qwenpaw/bin/python','-c','import importlib.metadata as m;print(m.version("qwenpaw"))'),
    'container_id':c['Id'],'image_id':c['Image'],'records':records,'installed_app_source_inventory':inventory,'scope':'Read-only response shape and route inventory; no snapshot or restoration performed'}
text=json.dumps(out,ensure_ascii=False,indent=2).replace(token,'[REDACTED]')
(ROOT/'evidence/checkpoint-capability-live.json').write_text(text,encoding='utf-8')
print(json.dumps([{'kind':r['kind'],'status':r['status'],'content_type':r['content_type'],'is_json':'json' in r} for r in records]))
