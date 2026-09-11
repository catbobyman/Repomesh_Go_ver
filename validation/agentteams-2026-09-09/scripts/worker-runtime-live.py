"""Create only the named real Worker; record sanitized live lifecycle/resources."""
from pathlib import Path
import datetime, json, subprocess, time, urllib.request, urllib.error

ROOT=Path(__file__).resolve().parents[1]
NAME='live-runtime-worker-a'
RECORDS=[]
def docker(*args,data=None,timeout=45):
    p=subprocess.run(['docker',*args],input=data,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=timeout)
    if p.returncode: raise RuntimeError(f'docker {args[:2]} failed code={p.returncode}: '+p.stderr[:300])
    return p.stdout
TOKEN=docker('exec','rv-a-controller','cat','/var/run/agentteams/cli-token').strip()
def save():
    (ROOT/'evidence/worker-runtime-live.json').write_text(json.dumps(RECORDS,ensure_ascii=False,indent=2).replace(TOKEN,'[REDACTED]'),encoding='utf8')
def record(kind,**kw):
    RECORDS.append(dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(),kind=kind,**kw));save()
def api(method,path,body=None):
    r=urllib.request.Request('http://127.0.0.1:28090'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'},method=method)
    try:p=urllib.request.urlopen(r,timeout=35)
    except urllib.error.HTTPError as e:p=e
    value=json.loads(p.read()) if p.code!=204 else None
    record('http',method=method,path=path,body=body,status=p.code,response=value)
    return p.code,value
body=dict(name=NAME,runtime='qwenpaw',image='repomesh-validation/qwenpaw-worker:eeaab643',model='deepseek-chat',state='Running',containerManaged=True,resources={'limits':{'cpu':'0.5','memory':'512Mi'}})
code,res=api('POST','/api/v1/workers',body)
assert code in (201,409),(code,res)
if code==409:code,res=api('GET','/api/v1/workers/'+NAME)
actual=res['name']
record('created',actual_name=actual)
api('GET','/api/v1/workers')
container=None
for attempt in range(36):
    code,status=api('GET',f'/api/v1/workers/{actual}/status')
    ids=docker('ps','-a','--filter',f'name={actual}','--format','{{.ID}}').splitlines()
    matches=[]
    for cid in ids:
        obj=json.loads(docker('inspect',cid))[0]
        if actual in obj['Name'] and obj['Config']['Image']==body['image']:matches.append(obj)
    if len(matches)==1 and matches[0]['State']['Running']:
        container=matches[0];break
    time.sleep(5)
if container is None:raise RuntimeError('Named Worker did not become Docker-running within 180s; partial evidence saved')
cid=container['Id'];hc=container['HostConfig']
record('docker',id=cid,name=container['Name'],image_id=container['Image'],image_ref=container['Config']['Image'],state={k:container['State'].get(k) for k in ['Status','Running','StartedAt','ExitCode','OOMKilled']},host_config={k:hc.get(k) for k in ['Memory','MemoryReservation','MemorySwap','NanoCpus','CpuQuota','CpuPeriod','CpuShares','PidsLimit','NetworkMode']},mounts=container['Mounts'],networks=list(container['NetworkSettings']['Networks']))
kube_token=docker('exec','rv-a-controller','cat','/data/agentteams-controller/admin-token').strip()
conf='\n'.join(['silent','show-error','fail','cacert = "/data/agentteams-controller/pki/ca.crt"',f'header = "Authorization: Bearer {kube_token}"','url = "https://127.0.0.1:6443/apis/agentteams.io/v1beta1/workers"'])
obj=json.loads(docker('exec','-i','rv-a-controller','curl','--config','-',data=conf))
cr=next(x for x in obj['items'] if x['metadata']['name']==actual)
record('persisted_cr',name=actual,spec={k:cr['spec'].get(k) for k in ['runtime','image','model','state','containerManaged','resources']},status={k:cr.get('status',{}).get(k) for k in ['phase','message','runtimeName']})
probe='''import os,json,pathlib,importlib.metadata as m
root=pathlib.Path('/root/agentteams-fs/agents')
cg={p:pathlib.Path('/sys/fs/cgroup/'+p).read_text().strip() for p in ('cpu.max','memory.max','pids.max','cpu.stat','cpu/cpu.cfs_quota_us','cpu/cpu.cfs_period_us','memory/memory.limit_in_bytes','pids/pids.max') if pathlib.Path('/sys/fs/cgroup/'+p).exists()}
configs=[]
for p in root.rglob('runtime.yaml'):
 import yaml
 d=yaml.safe_load(p.read_text()) or {}; desired=d.get('desired',{}); model=desired.get('model',{})
 configs.append({'path':str(p),'member':d.get('member',{}),'model':{k:model.get(k) for k in ('model','providerId','gatewayUrl')},'state':desired.get('state'),'top_level_keys':list(d)})
plugins=[str(p) for p in root.rglob('plugin.json')]
print(json.dumps({'packages':{n:m.version(n) for n in ('qwenpaw','qwenpaw-worker','agentscope')},'cgroup':cg,'runtime_configs':configs,'plugin_manifests':plugins},indent=2))
'''
record('container_probe',result=json.loads(docker('exec',cid,'/opt/venv/qwenpaw/bin/python','-c',probe)))
api('POST',f'/api/v1/workers/{actual}/ensure-ready',{})
for attempt in range(24):
    code,status=api('GET',f'/api/v1/workers/{actual}/status')
    if status.get('phase')=='Ready':break
    time.sleep(5)
record('final',actual_name=actual,container_name=container['Name'],phase=status.get('phase'),container_state=status.get('containerState'),readiness_scope='Actual worker report/status; no model message was sent by this probe')
print(json.dumps(RECORDS[-1],ensure_ascii=False))
