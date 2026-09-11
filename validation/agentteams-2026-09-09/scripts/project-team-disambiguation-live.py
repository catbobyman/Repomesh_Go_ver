"""Bounded Controller/MinIO scope fixture; no model, runtime start or source edit."""
import datetime,hashlib,json,secrets,subprocess,urllib.request,urllib.error,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=secrets.token_hex(5); PID='scope-project-'+RUN
TEAMS=['coverage-scope-'+RUN+'-'+x for x in ('left','right')]
OUT=ROOT/'evidence'/('project-team-disambiguation-'+RUN+'.json')
E=dict(run_id=RUN,project_id=PID,teams=TEAMS,scope='Controller admin HTTP; new stopped unmanaged resource references and direct MinIO metadata fixtures; no Worker authorization claim',records=[],checks=[])
tokens={}; objects={}; refs=[]
def save():OUT.write_text(json.dumps(E,ensure_ascii=False,indent=2),encoding='utf8')
def record(kind,**kw):E['records'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save()
def check(name,condition,**kw):
 E['checks'].append(dict(name=name,passed=bool(condition),**kw));save()
 assert condition,name
def docker(args,data=None):
 p=subprocess.run(['docker',*args],input=data,capture_output=True,timeout=35)
 if p.returncode:raise RuntimeError('docker command failed: '+str(args[:3]))
 return p.stdout
def api(i,method,path,body=None,resource=False):
 req=urllib.request.Request('http://127.0.0.1:'+('28090' if i=='a' else '38090')+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+tokens[i],'Content-Type':'application/json'},method=method)
 try:r=urllib.request.urlopen(req,timeout=25)
 except urllib.error.HTTPError as x:r=x
 raw=r.read();v=json.loads(raw) if raw else None
 public={k:v[k] for k in ('name','teamName','state','containerManaged','phase','message') if k in v} if resource and isinstance(v,dict) else v
 record('controller_http',instance=i,method=method,path=path,request=body,status=r.code,response=public)
 return r.code,v
def target(i,t,p):return 'agentteams/rv-'+i+'-storage/teams/'+t+'/shared/projects/'+p+'/meta.json'
def write_fixture(i,t,p):
 key=target(i,t,p);value=dict(project_id=p,title='fixture:'+i+':'+t+':'+p,status='active',plan_type='dag',team_id=t,mode='fixture',source='validation',tasks=[],source_room_id='')
 data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
 local='/tmp/project-scope-'+RUN+'/'+t+'/'+p+'/meta.json'
 docker(['exec','-i','rv-'+i+'-controller','python3','-c','import sys,pathlib;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())',local],data)
 docker(['exec','rv-'+i+'-controller','mc','cp',local,key])
 label=i+'/'+t+'/'+p;objects[label]=(i,key)
 record('direct_minio_fixture_write',object=label,key=key,sha256=hashlib.sha256(data).hexdigest(),value=value)
def snapshot(label):
 result={}
 for obj,(i,key) in objects.items():
  raw=docker(['exec','rv-'+i+'-controller','mc','cat',key]);result[obj]=dict(sha256=hashlib.sha256(raw).hexdigest(),value=json.loads(raw))
 record('independent_minio_snapshot',label=label,objects=result);return result
def hashes(s):return {k:v['sha256'] for k,v in s.items()}
def route(p,action,team=None):return '/api/v1/projects/'+p+'/'+action+('' if team is None else '?team='+urllib.parse.quote(team,safe=''))
save()
try:
 for i in 'ab':
  tokens[i]=docker(['exec','rv-'+i+'-controller','cat','/var/run/agentteams/cli-token']).decode().strip()
  for n,t in enumerate(TEAMS):
   leader='coverage-scope-leader-'+RUN+'-'+str(n)
   c,w=api(i,'POST','/api/v1/workers',dict(name=leader,runtime='qwenpaw',model='deepseek-chat',state='Stopped',containerManaged=False),True)
   check(i+'/'+t+'/stopped-unmanaged-registration',c==201 and w.get('state')=='Stopped' and w.get('containerManaged') is False)
   refs.append(dict(instance=i,team=t,worker=leader))
   c,v=api(i,'POST','/api/v1/teams',dict(name=t,teamName=t,description='Dedicated Project scope metadata fixture; stopped unmanaged leader; no model tasks',workerMembers=[dict(name=leader,role='team_leader')]),True)
   check(i+'/'+t+'/team-registration',c==201 and v['name']==t)
   # Random names are new; no existing Project object is overwritten.
   c,_=api(i,'GET',route(PID,'workflow',t));check(i+'/'+t+'/new-project-absent',c==404)
   write_fixture(i,t,PID)
  write_fixture(i,TEAMS[0],PID+'-left-only')
 baseline=snapshot('baseline-six-new-objects')
 for i in 'ab':
  c,_=api(i,'GET',route(PID,'workflow'));check(i+'/unqualified-read-ambiguous',c==409)
  for t in TEAMS:
   c,v=api(i,'GET',route(PID,'workflow',t));expected=baseline[i+'/'+t+'/'+PID]['value']
   check(i+'/'+t+'/qualified-read-exact',c==200 and all(v[k]==expected[k] for k in ('project_id','title','team_id','status')))
  # Wrong existing team, nonexistent team, and nonexistent Project are distinct inputs.
  negatives=[(PID+'-left-only',TEAMS[1],'wrong-existing-team'),(PID,'coverage-scope-'+RUN+'-absent','nonexistent-team'),(PID+'-absent',TEAMS[0],'nonexistent-project')]
  for p,t,case in negatives:
   c,_=api(i,'GET',route(p,'workflow',t));check(i+'/'+case+'/read404',c==404)
   c,_=api(i,'POST',route(p,'pause',t),{'reason':'fixture-negative-'+RUN});check(i+'/'+case+'/write404',c==404)
  c,_=api(i,'GET',route(PID+'-absent','workflow'));check(i+'/nonexistent-project-unqualified404',c==404)
  c,_=api(i,'POST',route(PID,'pause'),{'reason':'fixture-ambiguous-'+RUN});check(i+'/unqualified-write-ambiguous',c==409)
 after=snapshot('after-read-and-rejected-write-probes')
 check('all-six-hashes-unchanged-after-reads-and-rejected-writes',hashes(after)==hashes(baseline))
 current=after
 for i in 'ab':
  for t in TEAMS:
   obj=i+'/'+t+'/'+PID
   for action,status in [('pause','paused'),('resume','active')]:
    c,v=api(i,'POST',route(PID,action,t),{'reason':'scope-fixture-'+RUN})
    check(obj+'/'+action+'/http200',c==200 and v['status']==status and v['team_id']==t and v['title']==baseline[obj]['value']['title'])
    newer=snapshot(obj+'/'+action)
    changed=[k for k in current if current[k]['sha256']!=newer[k]['sha256']]
    check(obj+'/'+action+'/only-exact-object-changed',changed==[obj],changed=changed)
    check(obj+'/'+action+'/remote-state',newer[obj]['value']['status']==status and newer[obj]['value']['title']==baseline[obj]['value']['title'])
    current=newer
 check('all-fixtures-final-active',all(o['value']['status']=='active' for o in current.values()))
 E['completed']=True
except Exception as exc:
 E['error']=str(exc);raise
finally:
 # Do not delete resources or mutate their lifecycle during cleanup.
 names=docker(['ps','-a','--format','{{.Names}}']).decode().splitlines()
 own_containers=[n for n in names if RUN in n]
 record('finally_registered_fixture_resources',resources=refs,own_runtime_containers=own_containers,objects=[dict(identity=k,minio_key=v[1]) for k,v in objects.items()],retained=True)
 E['no_fixture_runtime_container']=not own_containers
 save();print(json.dumps(dict(run_id=RUN,evidence=str(OUT),completed=E.get('completed',False),checks=len(E['checks']),no_fixture_runtime_container=E['no_fixture_runtime_container']),ensure_ascii=False))
