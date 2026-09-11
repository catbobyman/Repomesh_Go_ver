"""Real native TeamHarness/MinIO/Matrix fixture, executed in controller container."""
import json,os,sys,subprocess
from pathlib import Path
C=json.load(sys.stdin);sys.path.insert(0,'/tmp/repomesh-sidefx-mcp');import server
B=Path('/tmp/repomesh-worker-side-effects')/C['id'];B.mkdir(parents=True,exist_ok=True)
P='agentteams/rv-a-storage/teams/live-harness/shared/'+C['run_id']+'/worker-side-effects-'+C['id']
os.environ.update(AGENTTEAMS_AGENT_ROLE='worker',AGENTTEAMS_MATRIX_URL='http://127.0.0.1:6167',AGENTTEAMS_MATRIX_USER_ID=C['user_id'],AGENTTEAMS_WORKER_MATRIX_TOKEN=C['token'])
trace=[]
def mc(*args):
 p=subprocess.run(['mc',*args],capture_output=True,text=True,timeout=30)
 if p.returncode:raise RuntimeError('mc operation failed '+p.stderr)
 return p.stdout
def remote(kind,ident):return json.loads(mc('cat',f'{P}/{kind}/{ident}/meta.json'))
def invoke(tool,action,**kw):
 args=dict(action=action,workspaceDir=str(B),storage={'sharedPrefix':P},**kw)
 result=json.loads(server.call_tool(tool,args)['content'][0]['text']);trace.append(dict(tool=tool,arguments=args,result=result));return result
pid='sidefx-project-'+C['id'];tids={k:'sidefx-'+k+'-'+C['id'] for k in ('cancel','missing','upload')}
if C['action']=='setup':
 meta=dict(project_id=pid,title=pid,team_id='live-harness',source_room_id=C['room'],plan_type='dag',status='active',tasks=[dict(task_id=t,title=t,status='planned',depends_on=[],assigned_to=C['user_id']) for t in tids.values()])
 p=B/'shared/projects'/pid/'meta.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(meta));mc('cp',str(p),f'{P}/projects/{pid}/meta.json')
 for t in tids.values():
  assert invoke('taskflow','delegate_task',projectId=pid,taskId=t,assignedTo=C['user_id'],roomId=C['room'],role='leader',spec='Isolated runtime side-effect fixture; no model work')['ok']
  assert invoke('taskflow','ack_task',taskId=t)['ok']
 result=dict(project=pid,tasks=tids,prefix=P)
elif C['action']=='cancel':
 t=tids['cancel'];cancel=invoke('taskflow','cancel_task',taskId=t,role='leader',reason='Validation fixture cancellation')
 result=dict(cancel=cancel,task=remote('tasks',t),project=remote('projects',pid))
elif C['action']=='late':
 t=tids['cancel'];ack=invoke('taskflow','ack_task',taskId=t);submit=invoke('taskflow','submit_task',taskId=t,summary='late fixture result',status='SUCCESS')
 accept=invoke('projectflow','accept_task_result',projectId=pid,taskId=t,accepted=True,summary='late fixture acceptance')
 result=dict(ack=ack,submit=submit,accept=accept,task=remote('tasks',t),project=remote('projects',pid))
elif C['action']=='artifacts':
 t=tids['missing'];missing=invoke('taskflow','submit_task',taskId=t,summary='claims success but declared file is absent',status='SUCCESS',deliverables=[f'shared/tasks/{t}/missing.txt'])
 accepted=invoke('projectflow','accept_task_result',projectId=pid,taskId=t,accepted=True)
 missing_meta=remote('tasks',t)
 t=tids['upload'];f=B/'shared/tasks'/t/'deliverable.txt';f.write_text('Only fixture artifact, no user data\n')
 os.environ['AGENTTEAMS_WORKER_MATRIX_TOKEN']='validation-invalid-upload-token'
 try:upload=invoke('taskflow','submit_task',taskId=t,summary='valid local fixture, upload authorization injected failure',status='SUCCESS',deliverables=[f'shared/tasks/{t}/deliverable.txt'])
 finally:os.environ['AGENTTEAMS_WORKER_MATRIX_TOKEN']=C['token']
 result=dict(missing=missing,missing_accept=accepted,missing_task=missing_meta,upload=upload,upload_task=remote('tasks',t),project=remote('projects',pid))
else:raise ValueError('unknown action')
print(json.dumps(dict(result=result,trace=trace)))
