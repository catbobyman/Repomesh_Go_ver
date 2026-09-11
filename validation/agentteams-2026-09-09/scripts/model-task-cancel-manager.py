"""Native TeamHarness using the actual Manager's projected Matrix/storage identity."""
import json,os,sys,pathlib,subprocess
C=json.load(sys.stdin);sys.path.insert(0,'/tmp/repomesh-modelcancel-mcp');import server
os.environ['AGENTTEAMS_WORKER_MATRIX_TOKEN']=os.environ['AGENTTEAMS_MANAGER_MATRIX_TOKEN']
os.environ['AGENTTEAMS_MATRIX_USER_ID']='@manager:'+os.environ['AGENTTEAMS_MATRIX_DOMAIN']
B=pathlib.Path('/root/manager-workspace/validation-modelcancel')/C['nonce'];B.mkdir(parents=True,exist_ok=True)
P='agentteams/'+os.environ['AGENTTEAMS_FS_BUCKET']+'/shared'
def mc(*args):
 r=subprocess.run(['mc',*args],capture_output=True,text=True,timeout=30)
 if r.returncode:raise RuntimeError('mc failed '+r.stderr[:300])
 return r.stdout
def invoke(action,**kw):return json.loads(server.call_tool('taskflow',dict(action=action,workspaceDir=str(B),storage={'sharedPrefix':P},role='leader',**kw))['content'][0]['text'])
if C['action']=='prepare':
 meta=dict(project_id=C['project'],title='Actual model task cancellation',status='active',plan_type='dag',source_room_id=C['room'],tasks=[dict(task_id=C['task'],status='planned',depends_on=[],assigned_to=C['target'])])
 p=B/'shared/projects'/C['project']/'meta.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(meta));mc('cp',str(p),P+'/projects/'+C['project']+'/meta.json');result={'prepared':True}
elif C['action']=='delegate':
 result=invoke('delegate_task',projectId=C['project'],taskId=C['task'],assignedTo=C['target'],roomId=C['room'],spec=C['spec'],title='本轮实际模型工具进程取消验证')
elif C['action']=='cancel':
 # Pull current task/project so cancellation applies to the model's current Task.
 for kind,key in [('projects',C['project']),('tasks',C['task'])]:
  r=json.loads(server.call_tool('filesync',dict(action='pull',workspaceDir=str(B),storage={'sharedPrefix':P},path=f'shared/{kind}/{key}/'))['content'][0]['text']);assert r['ok'],r
 result=invoke('cancel_task',taskId=C['task'],reason='Bounded real model task cancellation validation')
elif C['action']=='read':result={}
else:raise ValueError('unknown action')
if C['action']!='prepare':
 result={'response':result,'remote_task':json.loads(mc('cat',P+'/tasks/'+C['task']+'/meta.json')),'remote_project':json.loads(mc('cat',P+'/projects/'+C['project']+'/meta.json'))}
print(json.dumps(result,ensure_ascii=False))
