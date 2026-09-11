"""Prepared only: run --execute after parent confirms c/d stability and time/CA health.
Two instances x two Teams, real admin and Controller-generated SA TeamLeaders.
Only independent metadata fixtures and stopped unmanaged CR references are created.
"""
import argparse,base64,datetime,hashlib,json,secrets,subprocess,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ISSUE=r'''
import base64,json,pathlib,ssl,sys,urllib.request,urllib.error,time
C=json.load(sys.stdin);admin=pathlib.Path('/data/agentteams-controller/admin-token').read_text().strip()
ctx=ssl.create_default_context(cafile='/data/agentteams-controller/pki/ca.crt')
def kube(path,body=None):
 req=urllib.request.Request('https://127.0.0.1:6443'+path,headers={'Authorization':'Bearer '+admin,'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
 try:r=urllib.request.urlopen(req,context=ctx,timeout=20)
 except urllib.error.HTTPError as e:r=e
 return r.code,json.loads(r.read())
try:
 if C.get('preflight'):
  code,v=kube('/api/v1/namespaces/default');assert code==200
  print(json.dumps({'ok':True,'kube_tls_verified':True}));raise SystemExit(0)
 name=C['worker'];team=C['team'];sa=C['instance']+'-worker-'+name
 for attempt in range(10):
  code,s=kube('/api/v1/namespaces/default/serviceaccounts/'+sa)
  if code==200:break
  time.sleep(1)
 assert code==200,'Controller-generated SA unavailable'
 code,w=kube('/apis/agentteams.io/v1beta1/namespaces/default/workers/'+name);assert code==200
 code,t=kube('/apis/agentteams.io/v1beta1/namespaces/default/teams/'+team);assert code==200
 role=next(m['role'] for m in t['spec']['workerMembers'] if m['name']==name)
 assert role=='team_leader' and s['metadata']['labels']['agentteams.io/worker']==name
 code,issued=kube('/api/v1/namespaces/default/serviceaccounts/'+sa+'/token',{'apiVersion':'authentication.k8s.io/v1','kind':'TokenRequest','spec':{'audiences':['agentteams-controller'],'expirationSeconds':1200}});assert code==201
 token=issued['status']['token'];claim=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='));assert claim['kubernetes.io']['serviceaccount']['uid']==s['metadata']['uid']
 code,v=kube('/apis/authentication.k8s.io/v1/tokenreviews',{'apiVersion':'authentication.k8s.io/v1','kind':'TokenReview','spec':{'token':token,'audiences':['agentteams-controller']}})
 st=v.get('status',{});assert st.get('authenticated') is True
 print(json.dumps({'token':token,'identity':{'worker':name,'worker_uid':w['metadata']['uid'],'state':w['spec'].get('state'),'container_managed':w['spec'].get('containerManaged'),'team':team,'team_uid':t['metadata']['uid'],'membership_role':role,'sa_name':sa,'sa_uid':s['metadata']['uid'],'sa_worker_label':s['metadata']['labels']['agentteams.io/worker'],'subject':claim.get('sub'),'iat':claim.get('iat'),'exp':claim.get('exp'),'aud':claim.get('aud'),'kube_tls_verified':True,'tokenreview_authenticated':st.get('authenticated'),'tokenreview_username':st.get('user',{}).get('username')}}))
except Exception as exc:
 print(json.dumps({'error_type':type(exc).__name__,'error':'Kube verified read/TokenRequest failed; credential-bearing responses withheld'}));raise SystemExit(1)
'''
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');a=parser.parse_args()
 if not a.execute:parser.error('Prepared only; explicit --execute requires c/d readiness confirmation')
 run=secrets.token_hex(5);project='matrix-project-'+run;teams=['matrix-'+run+'-'+s for s in ['left','right']]
 workers=['matrix-leader-'+run+'-'+str(i) for i in range(2)]
 tasks={k:'matrix-'+run+'-'+k for k in ['raw','missing','wrongproject','wrongtask','outside']}
 instances={'c':{'container':'rv-c-controller','api':'http://127.0.0.1:48090','bucket':'rv-c-storage'},'d':{'container':'rv-d-controller','api':'http://127.0.0.1:49090','bucket':'rv-d-storage'}}
 R={'run_id':run,'project_id':project,'teams':teams,'workers':workers,'tasks':tasks,'baseline':'517caff9280242a00a4d4c06365352b9e41659c6','scope':'Actual dual-instance admin/SA TeamLeader read matrix; seeded metadata not business creation, no ordinary-worker role or model/runtime claim','records':[],'checks':[]}
 out=ROOT/'evidence'/('controller-dual-instance-read-matrix-'+run+'.json');secret=[];tokens={};objects={i:{} for i in instances};before={};start=time.monotonic()
 def save():
  text=json.dumps(R,ensure_ascii=False,indent=2)
  for s in secret:text=text.replace(s,'[REDACTED]')
  out.write_text(text,encoding='utf8')
 def rec(kind,**kw):R['records'].append(dict(kind=kind,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save()
 def check(name,ok,**kw):R['checks'].append(dict(name=name,passed=bool(ok),**kw));save();return bool(ok)
 def dock(i,*cmd,data=None):
  assert time.monotonic()-start<600,'10-minute bound'
  p=subprocess.run(['docker',*cmd],input=data,capture_output=True,timeout=30)
  if p.returncode:raise RuntimeError('Docker operation failed: '+str(cmd[:3])+'; stdout/stderr withheld')
  return p.stdout
 def ident(i):
  d=json.loads(dock(i,'inspect',instances[i]['container']))[0]
  return dict(id=d['Id'],image=d['Image'],started_at=d['State']['StartedAt'],running=d['State']['Running'])
 def api(i,identity,path,method='GET',body=None,source=None,resource=False):
  token=tokens[source or i][identity]
  req=urllib.request.Request(instances[i]['api']+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
  try:r=urllib.request.urlopen(req,timeout=20)
  except urllib.error.HTTPError as e:r=e
  raw=r.read()
  try:v=json.loads(raw)
  except ValueError:v=raw.decode()
  public={k:v[k] for k in ['name','state','containerManaged','message','teamName'] if k in v} if resource and isinstance(v,dict) else ({'item_count':len(v)} if resource and isinstance(v,list) else v)
  rec('controller_http',instance=i,identity=identity,identity_instance=source or i,method=method,path=path,status=r.code,content_type=r.headers.get('Content-Type'),response=public)
  return r.code,v
 def route(action,team=None,**query):
  if team is not None:query['team']=team
  return '/api/v1/projects/'+project+'/'+action+('?' + urllib.parse.urlencode(query) if query else '')
 def put(i,key,value):
  raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode();local='/tmp/matrix-'+run+'/'+key;container=instances[i]['container']
  dock(i,'exec','-i',container,'python3','-c','import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())',local,data=raw)
  dock(i,'exec',container,'mc','cp',local,'agentteams/'+instances[i]['bucket']+'/'+key)
  objects[i][key]=hashlib.sha256(raw).hexdigest();rec('fixture_mc_cp',instance=i,key=key,sha256=objects[i][key],content=value)
 def hashes(i,label):
  values={}
  for key in objects[i]:
   raw=dock(i,'exec',instances[i]['container'],'mc','cat','agentteams/'+instances[i]['bucket']+'/'+key)
   values[key]=hashlib.sha256(raw).hexdigest()
  rec('independent_raw_hashes',instance=i,label=label,objects=values);return values
 endpoints=[('inspection','tasks/'+tasks['raw'],{}),('json','workflow',{}),('mermaid','workflow',{'format':'mermaid'}),('includeTasks','workflow',{'includeTasks':'true'}),('mermaid-includeTasks','workflow',{'format':'mermaid','includeTasks':'true'})]
 def correct(v,kind,i,team):
  marker=i+'|'+team
  if kind=='inspection':return isinstance(v,dict) and v.get('summary')=='meta:'+marker
  if kind.startswith('mermaid'):return isinstance(v,str) and 'title:'+marker in v
  if not isinstance(v,dict) or v.get('team_id')!=team:return False
  nodes=v.get('nodes',[])
  if not any(n.get('id')==tasks['raw'] and n.get('name')=='title:'+marker for n in nodes):return False
  if kind=='includeTasks':return any(t.get('task_id')==tasks['raw'] and t.get('summary')=='meta:'+marker for t in v.get('tasks_detail',[]))
  return 'tasks_detail' not in v
 save()
 try:
  # Verify both TLS/Kube endpoints before creating any fixture.
  for i,cfg in instances.items():
   before[i]=ident(i);assert before[i]['running'];rec('runtime_before',instance=i,**before[i])
   token=dock(i,'exec',cfg['container'],'cat','/var/run/agentteams/cli-token').decode().strip();secret.append(token);tokens[i]={'admin':token}
   claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='));rec('admin_claims_unverified',instance=i,subject=claims.get('sub'),iat=claims.get('iat'),exp=claims.get('exp'))
   assert api(i,'admin','/api/v1/teams',resource=True)[0]==200
   r=json.loads(dock(i,'exec','-i',cfg['container'],'python3','-c',ISSUE,data=json.dumps({'preflight':True}).encode()));rec('verified_kube_preflight',instance=i,**r);assert r.get('ok')
  for i,cfg in instances.items():
   for n,team in enumerate(teams):
    assert api(i,'admin','/api/v1/workers','POST',dict(name=workers[n],runtime='qwenpaw',model='deepseek-chat',state='Stopped',containerManaged=False),resource=True)[0]==201
    assert api(i,'admin','/api/v1/teams','POST',dict(name=team,teamName=team,description='Independent read matrix fixture',workerMembers=[dict(name=workers[n],role='team_leader')]),resource=True)[0]==201
    assert api(i,'admin',route('workflow',team))[0]==404
    marker=i+'|'+team
    graph=[dict(task_id=tasks[k],title='title:'+marker if k=='raw' else k,status='planned',depends_on=[]) for k in tasks if k!='outside']
    put(i,'teams/'+team+'/shared/projects/'+project+'/meta.json',dict(project_id=project,title='project:'+marker,status='active',plan_type='dag',team_id=team,tasks=graph,source_room_id=''))
    for k in ['raw','wrongproject','wrongtask','outside']:
     put(i,'teams/'+team+'/shared/tasks/'+tasks[k]+'/meta.json',dict(project_id=project+'-wrong' if k=='wrongproject' else project,task_id=tasks[k]+'-wrong' if k=='wrongtask' else tasks[k],status='submitted',summary=('meta:' if k=='raw' else 'BAIT:')+marker))
    issued=json.loads(dock(i,'exec','-i',cfg['container'],'python3','-c',ISSUE,data=json.dumps(dict(instance='rv-'+i,worker=workers[n],team=team)).encode()))
    tok=issued.pop('token');secret.append(tok);tokens[i]['leader'+str(n)]=tok;rec('actual_sa_teamleader_identity',instance=i,**issued['identity'])
   for k in ['raw','missing']:
    put(i,'shared/tasks/'+tasks[k]+'/meta.json',dict(project_id=project,task_id=tasks[k],status='completed',summary='GLOBAL-BAIT:'+i))
   check(i+'/initial-upload-hashes',hashes(i,'before-matrix')==objects[i])
  for i in instances:
   for identity in ['admin','leader0','leader1']:
    own=None if identity=='admin' else teams[int(identity[-1])]
    for kind,action,query in endpoints:
     for scope,team in [('left',teams[0]),('right',teams[1]),('omitted',None),('unknown','matrix-'+run+'-unknown')]:
      expected=(409 if team is None else 200 if team in teams else 404) if own is None else (200 if team in (own,None) else 404)
      code,v=api(i,identity,route(action,team,**query));label='/'.join([i,identity,kind,scope]);check(label+'/status',code==expected,expected=expected,actual=code)
      if expected==200:check(label+'/isolated-payload',correct(v,kind,i,team or own))
    # Valid metadata outside graph is not a visible task; matching graph with wrong/missing TaskMeta falls back.
    for team in (teams if own is None else [own]):
     for k in ['missing','wrongproject','wrongtask','outside']:
      code,v=api(i,identity,route('tasks/'+tasks[k],team));label='/'.join([i,identity,team,k])
      if k=='outside':check(label+'/graph-membership404',code==404)
      else:check(label+'/normalized-fallback-no-bait',code==200 and v.get('status')=='pending' and not v.get('summary'))
  # Both directions, all three actual callers, five new read variants. Source requests bracket replays.
  for source,target in [('c','d'),('d','c')]:
   for identity in ['admin','leader0','leader1']:
    team=teams[0] if identity=='admin' else teams[int(identity[-1])]
    for kind,action,query in endpoints:
     path=route(action,team,**query)
     check(source+'/'+identity+'/'+kind+'/source-before200',api(source,identity,path)[0]==200)
     check(source+'->'+target+'/'+identity+'/'+kind+'/wrong-instance401',api(target,identity,path,source=source)[0]==401)
     check(source+'/'+identity+'/'+kind+'/source-after200',api(source,identity,path)[0]==200)
  for i,cfg in instances.items():
   check(i+'/all-raw-hashes-unchanged',hashes(i,'after-matrix')==objects[i])
   for worker in workers:
    code,v=api(i,'admin','/api/v1/workers/'+worker,resource=True);check(i+'/'+worker+'/stopped-unmanaged',code==200 and v.get('state')=='Stopped' and v.get('containerManaged') is False)
  R['completed']=True
 except Exception as exc:R['error']=str(exc)
 finally:
  for i in before:
   try:
    now=ident(i);rec('runtime_after',instance=i,**now);check(i+'/same-container-startedAt-running',now==before[i] and now['running'])
   except Exception as e:rec('finally_error',instance=i,error=str(e))
  names=subprocess.run(['docker','ps','-a','--format','{{.Names}}'],capture_output=True,text=True,timeout=20)
  own=[s for s in names.stdout.splitlines() if run in s];check('no-fixture-runtime-containers',names.returncode==0 and not own)
  rec('retained_inventory',teams=teams,stopped_workers=workers,objects=objects,runtime_containers=own)
  R['elapsed_seconds']=round(time.monotonic()-start,3);R['exit_code']=0 if R.get('completed') and all(c['passed'] for c in R['checks']) else 1;save()
  print(json.dumps({'evidence':str(out),'run_id':run,'exit_code':R['exit_code'],'checks':len(R['checks']),'failures':[c['name'] for c in R['checks'] if not c['passed']],'error':R.get('error')}))
 return R['exit_code']
if __name__=='__main__':raise SystemExit(main())
