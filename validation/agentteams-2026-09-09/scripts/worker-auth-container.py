"""Run inside the real Worker; use only its actually projected credentials."""
import os,sys,json,pathlib,secrets,subprocess,urllib.request,urllib.error,base64
W=pathlib.Path('/root/agentteams-fs/agents/live-runtime-worker-a')
sys.path.insert(0,str(W/'.qwenpaw/plugins/teamharness/teamharness/mcp'))
import server
run=secrets.token_hex(5);project='auth-project-'+run;task='auth-task-'+run
records=[]
token_path=os.environ.get('AGENTTEAMS_AUTH_TOKEN_FILE','/var/run/secrets/agentteams/token');token=pathlib.Path(token_path).read_text().strip()
claims={}
try:
 raw=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='));claims={k:raw[k] for k in ('sub','aud','iss','exp') if k in raw}
except Exception:claims={'format':'opaque'}
records.append(dict(kind='identity',name=os.environ.get('AGENTTEAMS_WORKER_CR_NAME'),runtime_role=server._runtime_role(),token_source=token_path,claims=claims,matrix_user=os.environ.get('AGENTTEAMS_WORKER_NAME'),storage_identity='Actual Worker projected environment and mc wrapper; no Controller admin token loaded'))
base=os.environ['AGENTTEAMS_CONTROLLER_URL'].rstrip('/')
def api(method,path,body=None):
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
 try:r=urllib.request.urlopen(req,timeout=20)
 except urllib.error.HTTPError as e:r=e
 text=r.read().decode();value=json.loads(text) if text else None
 # Record only response fields relevant to permission/result, not projected credentials.
 if isinstance(value,dict):value={k:v for k,v in value.items() if k in ('name','phase','state','model','runtime','message','error','total','containerState','project_id','status')}
 records.append(dict(kind='controller_http',method=method,path=path,status=r.code,response=value));return r.code
for method,path,body in [('GET','/api/v1/workers/live-runtime-worker-a',None),('GET','/api/v1/workers/live-runtime-worker-a/status',None),('GET','/api/v1/workers/live-control-worker',None),('GET','/api/v1/workers',None),('POST',f'/api/v1/projects/{project}/pause',{}),('POST',f'/api/v1/projects/{project}/replan',{'tasks':[{'taskId':task}]}),('POST','/api/v1/workers/live-runtime-worker-a/ready',{})]:api(method,path,body)
bucket=os.environ['AGENTTEAMS_FS_BUCKET'];target='agentteams/'+bucket
fixture=W/'validation-auth'/run;fixture.mkdir(parents=True,exist_ok=True)
def put(key,value):
 p=fixture/('input-'+secrets.token_hex(3)+'.json');p.write_text(json.dumps(value))
 cmd=['mc','cp',str(p),target+'/'+key];r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
 records.append(dict(kind='actual_worker_storage_put',key=key,returncode=r.returncode,error=r.stderr[:500] if r.returncode else None))
 if r.returncode==0:
  check=subprocess.run(['mc','cat',target+'/'+key],capture_output=True,text=True,timeout=30)
  records.append(dict(kind='storage_readback',key=key,returncode=check.returncode,matches=check.returncode==0 and json.loads(check.stdout)==value))
 return r.returncode
meta=dict(project_id=project,title='Actual Worker auth fixture',status='active',plan_type='dag',tasks=[dict(task_id=task,status='in_progress',depends_on=[])])
taskmeta=dict(task_id=task,project_id=project,status='in_progress')
a=put(f'shared/projects/{project}/meta.json',meta);b=put(f'shared/tasks/{task}/meta.json',taskmeta)
put(f'agents/validation-foreign-{run}/auth-probe.json',{'fixture':run,'scope':'nonexistent foreign member, no existing member modified'})
put(f'teams/validation-auth-{run}/shared/auth-probe.json',{'fixture':run,'scope':'new nonexistent team fixture only'})
if a==0 and b==0:
 def invoke(role=None):
  args=dict(action='cancel_task',workspaceDir=str(W),storage={'sharedPrefix':target+'/shared'},taskId=task,reason='Own isolated permissions fixture')
  if role is not None:args['role']=role
  result=json.loads(server.call_tool('taskflow',args)['content'][0]['text'])
  records.append(dict(kind='actual_packaged_native_tool',tool='taskflow',role_argument=role,runtime_role=server._runtime_role(),result=result));return result
 invoke();invoke('leader')
 # cancel_task expects a local task cache; pull through the actual packaged
 # filesync tool, then repeat with identical actual Worker credentials.
 for path in (f'shared/projects/{project}/',f'shared/tasks/{task}/'):
  pulled=json.loads(server.call_tool('filesync',dict(action='pull',workspaceDir=str(W),storage={'sharedPrefix':target+'/shared'},path=path))['content'][0]['text'])
  records.append(dict(kind='actual_packaged_filesync_pull',path=path,result=pulled))
 invoke();invoke('leader')
 r=subprocess.run(['mc','cat',target+f'/shared/tasks/{task}/meta.json'],capture_output=True,text=True,timeout=30)
 records.append(dict(kind='final_task_readback',returncode=r.returncode,task=json.loads(r.stdout) if r.returncode==0 else None))
print(json.dumps(dict(run_id=run,records=records),ensure_ascii=False).replace(token,'[REDACTED]'))
