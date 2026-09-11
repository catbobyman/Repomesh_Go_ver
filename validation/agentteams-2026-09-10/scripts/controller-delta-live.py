"""Prepared bounded real Controller/MinIO regression; requires explicit --execute.

Creates only nonce-scoped Team/Stopped unmanaged Worker references and direct
metadata fixtures. No model task, process startup, service restart, or mc pipe.
Admin reads and unauthenticated denial are not Worker-role authorization proof.
"""
import argparse,datetime,hashlib,json,secrets,subprocess,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--execute',action='store_true',help='Run only after rv-c environment readiness is confirmed')
 parser.add_argument('--container',default='rv-c-controller')
 parser.add_argument('--api',default='http://127.0.0.1:48090')
 parser.add_argument('--bucket',default='rv-c-storage')
 args=parser.parse_args()
 if not args.execute:parser.error('Preparation only. Explicit --execute is required after environment readiness.')
 # Deliberately restrict this runner to the new c instance.
 assert args.container=='rv-c-controller' and args.api=='http://127.0.0.1:48090' and args.bucket=='rv-c-storage'
 run=secrets.token_hex(5);project='delta-project-'+run;teams=['delta-'+run+'-'+v for v in ('left','right')]
 ids={k:'delta-'+run+'-'+k for k in ('raw','missing','badjson','wrongowner','wrongtask','historytype','nostatus','absent')}
 out=ROOT/'evidence'/('controller-delta-live-'+run+'.json');out.parent.mkdir(exist_ok=True)
 result={'run_id':run,'expected_source_head':'517caff9280242a00a4d4c06365352b9e41659c6','container':args.container,'api':args.api,'bucket':args.bucket,'project_id':project,'teams':teams,'task_ids':ids,'identity':'Controller-local admin token from /var/run/agentteams/cli-token, never emitted','boundary':'Direct MinIO metadata fixtures plus real CR registration; not business Project creation; no model or Worker runtime; anonymous and invalid-token denial do not prove Worker RBAC','records':[],'checks':[]}
 token='';objects={};refs=[];start=time.monotonic()
 def clean(value):
  s=json.dumps(value,ensure_ascii=False)
  if token:s=s.replace(token,'[REDACTED]')
  return json.loads(s)
 def save():out.write_text(json.dumps(clean(result),ensure_ascii=False,indent=2),encoding='utf8')
 def rec(kind,**kw):result['records'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save()
 def check(name,passed,**kw):result['checks'].append(dict(name=name,passed=bool(passed),**kw));save();return bool(passed)
 def bounded():
  if time.monotonic()-start>300:raise TimeoutError('Five-minute fixture execution bound exceeded')
 def docker(*parts,data=None,required=True):
  bounded();p=subprocess.run(['docker',*parts],input=data,capture_output=True,timeout=35)
  if required and p.returncode:raise RuntimeError('Docker operation failed: '+str(parts[:3]))
  return p
 def api(method,path,body=None,identity='admin',resource=False):
  bounded();headers={'Content-Type':'application/json'}
  if identity!='anonymous':headers['Authorization']='Bearer '+(token if identity=='admin' else 'fixture-invalid-'+run)
  req=urllib.request.Request(args.api+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
  try:r=urllib.request.urlopen(req,timeout=25)
  except urllib.error.HTTPError as e:r=e
  raw=r.read();text=raw.decode('utf8',errors='replace')
  try:value=json.loads(text)
  except ValueError:value=text
  public={k:value[k] for k in ('name','teamName','state','containerManaged','phase','message') if k in value} if resource and isinstance(value,dict) else value
  rec('real_controller_http',identity=identity,method=method,path=path,request=body,status=r.code,content_type=r.headers.get('Content-Type'),allow=r.headers.get('Allow'),response=public)
  return r.code,value,r.headers.get('Content-Type','')
 def path(action,p=project,team=teams[0],**query):
  if team is not None:query={'team':team,**query}
  return '/api/v1/projects/'+urllib.parse.quote(p,safe='')+'/'+action+('?' + urllib.parse.urlencode(query) if query else '')
 def inspect_task(kind,team=teams[0],p=project,method='GET',identity='admin'):
  return api(method,path('tasks/'+urllib.parse.quote(ids.get(kind,kind),safe=''),p=p,team=team),identity=identity)
 def put(relative,value):
  bounded();key='agentteams/'+args.bucket+'/'+relative;local='/tmp/controller-delta-'+run+'/'+relative
  data=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
  docker('exec','-i',args.container,'python3','-c','import sys,pathlib;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())',local,data=data)
  docker('exec',args.container,'mc','cp',local,key)
  objects[key]=hashlib.sha256(data).hexdigest()
  rec('direct_minio_fixture_mc_cp',key=key,sha256=objects[key],content=data.decode('utf8'))
 def snapshot(label):
  values={}
  for key in objects:
   raw=docker('exec',args.container,'mc','cat',key).stdout
   values[key]={'sha256':hashlib.sha256(raw).hexdigest(),'content':raw.decode('utf8',errors='replace')}
  rec('independent_minio_readback',label=label,objects=values)
  return {k:v['sha256'] for k,v in values.items()}
 save()
 try:
  raw=json.loads(docker('inspect',args.container).stdout)[0]
  rec('controller_runtime_provenance',container_id=raw['Id'],image_id=raw['Image'],image_reference=raw['Config']['Image'],running=raw['State']['Running'],started_at=raw['State']['StartedAt'])
  token=docker('exec',args.container,'cat','/var/run/agentteams/cli-token').stdout.decode().strip()
  assert token,'Controller admin credential file is empty'
  c,_,_=api('GET','/healthz');assert check('controller-health',c==200)
  for index,team in enumerate(teams):
   name='delta-leader-'+run+'-'+str(index)
   c,w,_=api('POST','/api/v1/workers',dict(name=name,runtime='qwenpaw',model='deepseek-chat',state='Stopped',containerManaged=False),resource=True)
   assert check(team+'/stopped-unmanaged-created',c==201 and w.get('state')=='Stopped' and w.get('containerManaged') is False)
   refs.append({'team':team,'worker':name})
   c,v,_=api('POST','/api/v1/teams',dict(name=team,teamName=team,description='Delta read-only API metadata fixture; no runtime or model',workerMembers=[dict(name=name,role='team_leader')]),resource=True)
   assert check(team+'/team-created',c==201 and v.get('name')==team)
   c,_,_=api('GET',path('workflow',team=team));assert check(team+'/new-project-absent',c==404)
   tasks=[dict(task_id=ids[k],title=('raw title "quoted"\nsecond line' if k=='raw' else k),status=('completed' if k=='raw' else 'in_progress'),assigned_to='fixture-graph-'+team,depends_on=[]) for k in ids if k!='absent']
   tasks[1]['depends_on']=[ids['raw']]
   put('teams/'+team+'/shared/projects/'+project+'/meta.json',dict(project_id=project,title='fixture:'+team,status='active',plan_type='dag',team_id=team,tasks=tasks,source_room_id=''))
   history=[dict(ts='2026-09-10T00:00:00Z',action='fixture',**{'from':'planned','to':'assigned'}),'malformed',{'note':'no ts or action'},{'action':'fixture-without-ts'},{'ts':'fixture-non-date'}]
   rawmeta=dict(task_id=ids['raw'],project_id=project,status='in_progress',assigned_to='fixture-meta-'+team,summary='owned-by:'+team,spec_path='fixture/spec.md',result_status='SUCCESS',result_path='fixture/nonexistent-result.md',deliverables=[{'path':'fixture/nonexistent-result.md'}],history=history)
   put('teams/'+team+'/shared/tasks/'+ids['raw']+'/meta.json',rawmeta)
   put('teams/'+team+'/shared/tasks/'+ids['badjson']+'/meta.json',b'{broken JSON fixture')
   put('teams/'+team+'/shared/tasks/'+ids['wrongowner']+'/meta.json',dict(task_id=ids['wrongowner'],project_id=project+'-other',status='completed',summary='wrong-project-no-leak'))
   put('teams/'+team+'/shared/tasks/'+ids['wrongtask']+'/meta.json',dict(task_id=ids['wrongtask']+'-other',project_id=project,status='completed',summary='wrong-task-no-leak'))
   put('teams/'+team+'/shared/tasks/'+ids['historytype']+'/meta.json',dict(task_id=ids['historytype'],project_id=project,status='assigned',history={'action':'wrong-container-type'}))
   put('teams/'+team+'/shared/tasks/'+ids['nostatus']+'/meta.json',dict(task_id=ids['nostatus'],project_id=project,summary='matching-meta-without-status'))
  # A global same-task/project bait must never satisfy a team-owned missing TaskMeta.
  put('shared/tasks/'+ids['missing']+'/meta.json',dict(task_id=ids['missing'],project_id=project,status='completed',summary='GLOBAL-BAIT-'+run))
  end_project=project+'-reserved-end'
  put('teams/'+teams[0]+'/shared/projects/'+end_project+'/meta.json',dict(project_id=end_project,title='Reserved ID fixture',status='active',plan_type='dag',team_id=teams[0],tasks=[dict(task_id='end',title='Ordinary task',status='planned',depends_on=[])],source_room_id=''))
  baseline=snapshot('before-http-inspection')
  check('all-copied-fixture-bytes-match',baseline==objects)
  c,end_json,_=api('GET',path('workflow',p=end_project));check('reserved-end-workflow-json200',c==200 and any(n.get('id')=='end' for n in end_json.get('nodes',[])))
  c,end_task,_=inspect_task('end',p=end_project);check('reserved-end-inspection200',c==200 and end_task.get('task_id')=='end')
  c,end_mmd,end_ct=api('GET',path('workflow',p=end_project,format='mermaid'))
  check('reserved-end-mermaid200-unsanitized-keyword',c==200 and 'text/plain' in end_ct and isinstance(end_mmd,str) and '    end[' in end_mmd)
  if isinstance(end_mmd,str):
   mmd=ROOT/'evidence'/('controller-delta-live-'+run+'-reserved-end.mmd');mmd.write_bytes(end_mmd.encode('utf8'));rec('reserved_end_api_artifact',file=mmd.name,sha256=hashlib.sha256(end_mmd.encode('utf8')).hexdigest(),browser_validation='pending independent browser parse; API200 does not establish valid Mermaid')
  c,default,ct=api('GET',path('workflow'));check('workflow-default-json',c==200 and 'application/json' in ct and default.get('team_id')==teams[0] and 'tasks_detail' not in default)
  c,empty,ct=api('GET',path('workflow',format=''));check('workflow-empty-format-json-equivalent',c==200 and empty==default)
  c,mermaid,ct=api('GET',path('workflow',format='mermaid'));check('workflow-mermaid-text',c==200 and ct.startswith('text/plain') and isinstance(mermaid,str) and mermaid.startswith('flowchart LR'))
  check('mermaid-label-escaping',isinstance(mermaid,str) and '#quot;quoted#quot;<br>second line' in mermaid)
  c,mm,_=api('GET',path('workflow',format='mermaid',includeTasks='true'));check('mermaid-includeTasks-output-equivalent',c==200 and mm==mermaid)
  for fmt in ('bogus','json'):
   c,_,_=api('GET',path('workflow',format=fmt));check('invalid-format-'+fmt,c==400)
  c,detail,_=api('GET',path('workflow',includeTasks='true'))
  indexed={x['task_id']:x for x in detail.get('tasks_detail',[])} if isinstance(detail,dict) else {}
  check('workflow-includeTasks-raw-status-history',c==200 and indexed.get(ids['raw'],{}).get('status')=='in_progress' and len(indexed.get(ids['raw'],{}).get('history',[]))==3)
  for t in teams:
   c,v,_=inspect_task('raw',team=t)
   check(t+'/inspection-own-content',c==200 and v.get('summary')=='owned-by:'+t and v.get('assigned_to')=='fixture-meta-'+t)
   check(t+'/inspection-raw-history-trace',c==200 and v.get('status')=='in_progress' and len(v.get('history',[]))==3 and v.get('trace')=={'project_id':project,'task_id':ids['raw']})
  check('graph-node-status-is-distinct',any(n.get('id')==ids['raw'] and n.get('status')=='completed' for n in default.get('nodes',[])))
  for k in ('missing','badjson','wrongowner','wrongtask'):
   c,v,_=inspect_task(k);check('inspection-fallback-'+k,c==200 and v.get('status')=='in-progress' and not v.get('summary') and not v.get('history'))
   if k=='missing':check('inspection-dependencies-from-graph',v.get('dependencies')==[ids['raw']])
  c,v,_=inspect_task('historytype');check('wrong-history-container-ignored',c==200 and v.get('status')=='assigned' and 'history' not in v)
  c,v,_=inspect_task('nostatus');check('matching-meta-absent-status-is-empty',c==200 and v.get('status','')=='' and v.get('summary')=='matching-meta-without-status')
  for action in ('workflow','tasks/'+ids['raw']):
   c,_,_=api('GET',path(action,team=None));check(action+'/ambiguous409',c==409)
   c,_,_=api('GET',path(action,team='delta-'+run+'-absent'));check(action+'/wrong-team404',c==404)
   c,_,_=api('GET',path(action,p=project+'-absent'));check(action+'/missing-project404',c==404)
   for identity in ('anonymous','invalid'):
    c,_,_=api('GET',path(action),identity=identity);check(action+'/'+identity+'/denied401',c==401)
  c,_,_=api('GET',path('workflow',team=None,format='mermaid'));check('mermaid-ambiguous409',c==409)
  c,_,_=api('GET',path('workflow',p=project+'-absent',format='bogus'));check('missing-project-before-format404',c==404)
  c,_,_=inspect_task('absent');check('task-not-in-graph404',c==404)
  c,_,_=inspect_task('bad!id');check('invalid-task-id400',c==400)
  for method in ('POST','DELETE'):
   c,_,_=inspect_task('raw',method=method);check('inspection-'+method+'-method405',c==405)
  after=snapshot('after-all-read-and-denial-probes');check('all-fixture-hashes-unchanged',after==baseline)
  for ref in refs:
   c,w,_=api('GET','/api/v1/workers/'+ref['worker'],resource=True)
   check(ref['worker']+'/finally-stopped-unmanaged',c==200 and w.get('state')=='Stopped' and w.get('containerManaged') is False)
  result['completed']=True
 except Exception as exc:result['error']=str(exc)
 finally:
  try:
   names=docker('ps','-a','--format','{{.Names}}').stdout.decode().splitlines();own=[n for n in names if run in n]
   rec('finally_fixture_inventory',resources=refs,minio_objects=list(objects),own_runtime_containers=own,retained=True)
   check('no-fixture-runtime-containers',not own)
  except Exception as exc:result['finally_error']=str(exc)
  result['elapsed_seconds']=round(time.monotonic()-start,3)
  result['exit_code']=0 if result.get('completed') and not result.get('finally_error') and all(c['passed'] for c in result['checks']) else 1
  save();print(json.dumps({'evidence':str(out),'run_id':run,'exit_code':result['exit_code'],'checks':len(result['checks']),'failed_checks':[c['name'] for c in result['checks'] if not c['passed']]},ensure_ascii=False))
 return result['exit_code']

if __name__=='__main__':raise SystemExit(main())
