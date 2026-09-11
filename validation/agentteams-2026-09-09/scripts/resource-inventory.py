"""Sanitized disk, port, identity and native token counters for the isolated deployment."""
import datetime as dt,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def cmd(*args):
    p=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=40)
    return p.returncode,p.stdout
names=['rv-'+i+'-'+s for i in 'ab' for s in ('controller','manager','worker-live-twin-leader','worker-live-twin-worker')]+['rv-a-worker-live-runtime-worker-a']
out={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'containers':[],
    'scope':'Native cumulative token counters are not provider billing; Docker image logical sizes overlap shared layers; du is in KiB.'}
for name in names:
    code,raw=cmd('inspect','--size',name)
    if code:
        out['containers'].append({'name':name,'inspect_exit':code});continue
    c=json.loads(raw)[0]
    row={'name':name,'id':c['Id'],'image_id':c['Image'],'running':c['State']['Running'],'started_at':c['State']['StartedAt'],
        'size_rw_bytes':c.get('SizeRw'),'size_rootfs_bytes':c.get('SizeRootFs'),'ports':c['HostConfig']['PortBindings'],
        'networks':list(c['NetworkSettings']['Networks']),'mounts':c['Mounts']}
    if name.endswith('-controller'):
        code,raw=cmd('exec',name,'du','-sk','/data','/root/agentteams-fs')
        row['disk']={'exit_code':code,'du_kib':raw.strip()}
    else:
        path='/root/manager-workspace/.qwenpaw/token_usage.json' if name.endswith('-manager') else '/root/agentteams-fs/agents/'+name.split('-worker-',1)[1]+'/.qwenpaw/token_usage.json'
        code,raw=cmd('exec',name,'cat',path)
        row['usage_read_exit']=code
        if not code:row['native_token_usage']=json.loads(raw)
    out['containers'].append(row)
code,raw=cmd('image','inspect','repomesh-validation/controller:eeaab643','repomesh-validation/embedded:eeaab643','repomesh-validation/qwenpaw-worker:eeaab643','repomesh-validation/manager-qwenpaw:eeaab643')
if not code:out['images']=[{'id':c['Id'],'tags':c['RepoTags'],'size_bytes':c['Size']} for c in json.loads(raw)]
(ROOT/'evidence/resource-inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'containers':len(out['containers']),'evidence':'resource-inventory.json'}))
