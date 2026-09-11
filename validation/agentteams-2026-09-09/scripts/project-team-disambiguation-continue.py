"""Continue only an existing failed fixture run; preserve first evidence and bytes."""
import datetime,hashlib,json,subprocess,sys,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUN=sys.argv[1]
assert len(RUN)==10 and all(c in '0123456789abcdef' for c in RUN)
old=json.loads((ROOT/'evidence'/('project-team-disambiguation-'+RUN+'.json')).read_text())
OUT=ROOT/'evidence'/('project-team-disambiguation-'+RUN+'-writes.json');assert not OUT.exists()
PID=old['project_id'];TEAMS=old['teams'];refs=old['records'][-1]['resources'];objects=old['records'][-1]['objects']
E=dict(run_id=RUN,first_evidence='project-team-disambiguation-'+RUN+'.json',records=[],checks=[]);tokens={}
def save():OUT.write_text(json.dumps(E,ensure_ascii=False,indent=2),encoding='utf8')
def rec(kind,**kw):E['records'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save()
def check(name,c,**kw):E['checks'].append(dict(name=name,passed=bool(c),**kw));save();assert c,name
def docker(args,data=None):
 p=subprocess.run(['docker',*args],input=data,capture_output=True,timeout=35)
 if p.returncode:raise RuntimeError('docker operation failed')
 return p.stdout
def snapshot(label):
 s={}
 for o in objects:
  i=o['identity'][0];raw=docker(['exec','rv-'+i+'-controller','mc','cat',o['minio_key']]);s[o['identity']]=dict(sha256=hashlib.sha256(raw).hexdigest(),value=json.loads(raw))
 rec('independent_minio_snapshot',label=label,objects=s);return s
def api(i,method,path,body=None):
 req=urllib.request.Request('http://127.0.0.1:'+('28090' if i=='a' else '38090')+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+tokens[i],'Content-Type':'application/json'},method=method)
 try:r=urllib.request.urlopen(req,timeout=25)
 except urllib.error.HTTPError as x:r=x
 raw=r.read();v=json.loads(raw) if raw else None
 rec('controller_http',instance=i,method=method,path=path,request=body,status=r.code,response=v);return r.code,v
try:
 before=snapshot('original-bytes-before-cp')
 original=next(r['objects'] for r in old['records'] if r.get('label')=='baseline-six-new-objects')
 check('all-six-original-content-hashes-preserved',all(before[k]['sha256']==original[k]['sha256'] for k in before))
 for o in objects:
  i=o['identity'][0];c='rv-'+i+'-controller';raw=docker(['exec',c,'mc','cat',o['minio_key']]);local='/tmp/project-scope-'+RUN+'/'+o['identity'][2:]+'/meta.json'
  docker(['exec','-i',c,'python3','-c','import sys,pathlib;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())',local],raw)
  docker(['exec',c,'mc','cp',local,o['minio_key']]);rec('same-byte-single-part-fixture-copy',object=o['identity'],sha256=hashlib.sha256(raw).hexdigest())
 current=snapshot('after-cp-before-http-write')
 check('all-six-cp-content-hashes-identical',all(current[k]['sha256']==before[k]['sha256'] for k in current))
 for i in 'ab':tokens[i]=docker(['exec','rv-'+i+'-controller','cat','/var/run/agentteams/cli-token']).decode().strip()
 for i in 'ab':
  for t in TEAMS:
   obj=i+'/'+t+'/'+PID
   for action,status in [('pause','paused'),('resume','active')]:
    c,v=api(i,'POST','/api/v1/projects/'+PID+'/'+action+'?team='+t,{'reason':'scope-fixture-'+RUN})
    check(obj+'/'+action+'/http200',c==200 and v['status']==status and v['team_id']==t and v['title']==before[obj]['value']['title'])
    newer=snapshot(obj+'/'+action)
    changed=[k for k in current if current[k]['sha256']!=newer[k]['sha256']]
    check(obj+'/'+action+'/only-target-hash-changed',changed==[obj],changed=changed)
    check(obj+'/'+action+'/remote-status',newer[obj]['value']['status']==status)
    current=newer
 check('all-six-final-active',all(v['value']['status']=='active' for v in current.values()))
 E['completed']=True
except Exception as x:E['error']=str(x);raise
finally:
 names=docker(['ps','-a','--format','{{.Names}}']).decode().splitlines();own=[n for n in names if RUN in n]
 rec('finally_fixture_resources',resources=refs,own_runtime_containers=own,retained=True)
 print(json.dumps(dict(run_id=RUN,completed=E.get('completed',False),checks=len(E['checks']),own_runtime_containers=own)))
