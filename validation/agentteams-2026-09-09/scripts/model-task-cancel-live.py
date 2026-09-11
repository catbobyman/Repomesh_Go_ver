"""One real delegated model task; observer never starts the heartbeat writer."""
from pathlib import Path
import datetime,importlib.util,json,secrets,subprocess,time
ROOT=Path(__file__).resolve().parents[1];private=ROOT/'private/model-task-cancel-live-state.json';evidence=ROOT/'evidence/model-task-cancel-live.json';W='rv-a-worker-live-runtime-worker-a'
s=json.loads(private.read_text()) if private.exists() else dict(nonce='MCANCEL_'+secrets.token_hex(5),results=[],events=[])
s.setdefault('task','modelcancel-task-'+s['nonce']);s.setdefault('project','modelcancel-project-'+s['nonce']);s['target']='@live-runtime-worker-a:rv-a.matrix.invalid'
rt=json.loads((ROOT/'evidence/worker-runtime-live.json').read_text());s['room']=next(r['result']['runtime_configs'][0]['member']['personalRoomId'] for r in rt if r['kind']=='post_ready_probe')
s['fixture']='/root/agentteams-fs/agents/live-runtime-worker-a/.qwenpaw/workspaces/default/validation-modelcancel-'+s['nonce']
s['spec']='隔离取消验证：仅执行这个Task，不派生任务、不联网、不访问仓库。请只调用一次execute_shell_command，前台启动Python进程：创建目录 '+s['fixture']+' ，把进程自己的PID写pid.txt，每1秒向heartbeat.txt追加一行 '+s['nonce']+'，循环25次即退出，最长不得超过30秒。把该绝对目录路径作为Python的argv参数，方便核验PID。不要后台启动、不要自动重试。结束后报告本Task ID和心跳行数。'
assert len(s['spec'])<=500
def save():private.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8');evidence.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf8')
def record(kind,**kw):s['results'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save()
def docker(*args,data=None):
 p=subprocess.run(['docker',*args],input=data,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=40)
 if p.returncode:raise RuntimeError('docker '+str(args[:2])+' failed: '+p.stderr[:250])
 return p.stdout
spec=importlib.util.spec_from_file_location('matrix',ROOT/'scripts/matrix-live-validation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=docker('exec','rv-a-manager','/opt/venv/qwenpaw/bin/python','-c','import os;print(os.environ["AGENTTEAMS_MANAGER_MATRIX_TOKEN"])').strip()
def call(action):
 data={k:s[k] for k in ('nonce','project','task','room','target','spec')};data['action']=action
 r=json.loads(docker('exec','-i','rv-a-manager','/opt/venv/qwenpaw/bin/python','/tmp/model-task-cancel-manager.py',data=json.dumps(data)));record(action,result=r);return r
def observe():
 code='''import pathlib,json,sys
p=pathlib.Path(sys.argv[1]);f=p/'pid.txt';h=p/'heartbeat.txt';out={'pid_file_exists':f.exists(),'heartbeat_exists':h.exists()}
if f.exists():
 try:pid=int(f.read_text().strip())
 except ValueError:pid=0
 q=pathlib.Path('/proc')/str(pid);cmd=q/'cmdline';out.update(pid=pid,alive=q.exists(),cmdline_matches=cmd.exists() and str(p).encode() in cmd.read_bytes())
if h.exists():out.update(lines=len(h.read_text().splitlines()),all_lines_match=all(x==sys.argv[2] for x in h.read_text().splitlines()))
print(json.dumps(out))'''
 return json.loads(docker('exec',W,'/opt/venv/qwenpaw/bin/python','-c',code,s['fixture'],s['nonce']))
def timeline():
 d=m.ok('a','GET','/_matrix/client/v3/rooms/'+m.q(s['room'])+'/messages',token,query={'dir':'b','limit':100})
 s['events']=[e for e in reversed(d['chunk']) if e.get('origin_server_ts',0)>=s['request_ts'] and e.get('sender') in (s['target'],'@manager:rv-a.matrix.invalid')];save()
 return s['events']
save()
docker('cp',str(ROOT/'upstream/plugins/teamharness/mcp'),'rv-a-manager:/tmp/repomesh-modelcancel-mcp')
docker('cp',str(ROOT/'scripts/model-task-cancel-manager.py'),'rv-a-manager:/tmp/model-task-cancel-manager.py')
if not s.get('prepared'):call('prepare');s['prepared']=True;save()
deadline=time.monotonic()+180
if not s.get('attempted'):
 s['attempted']=True;s['started_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
 r=call('delegate');s['delegate_response']=r;save()
 assert r['response']['ok'] and r['response']['synced'],r
 s['event_id']=r['response']['task']['eventId'];save()
elif not s.get('event_id'):raise RuntimeError('Prior native delegate outcome unknown; never resend')
e=m.ok('a','GET','/_matrix/client/v3/rooms/'+m.q(s['room'])+'/event/'+m.q(s['event_id']),token);s['request_ts']=e['origin_server_ts'];s['delegate_wire_event']=e;s['exact_spec_present']=s['spec'] in e['content']['body'];save();assert s['exact_spec_present']
observed=None
try:
 while time.monotonic()<deadline:
  obs=observe();record('writer_observation',observation=obs)
  events=timeline()
  if obs.get('lines',0)>=2 and obs.get('alive') and obs.get('cmdline_matches'):
   observed=obs;break
  text='\n'.join(e.get('content',{}).get('body','') for e in events if e.get('sender')==s['target'])
  if '没有访问此智能体的权限' in text:record('terminal_rejection',text=text);break
  time.sleep(1)
 if observed:
  record('same_task_pre_cancel',state=call('read'))
  cancelled=call('cancel');s['cancelled']=cancelled;save()
  assert cancelled['response']['ok'] and cancelled['remote_task']['status']=='cancelled',cancelled
  at=observe();time.sleep(3);after=observe();record('post_cancel_writer',at_cancel=at,after=after,continued=after.get('lines',0)>at.get('lines',0),same_pid=at.get('pid')==after.get('pid'))
 else:record('no_writer_started',scope='No harness writer was substituted; model tool cancellation not proven')
finally:
 obs=observe()
 if obs.get('alive') and obs.get('cmdline_matches'):
  code='import pathlib,os,signal,sys,json;p=pathlib.Path(sys.argv[1]);pid=int((p/"pid.txt").read_text());q=pathlib.Path("/proc")/str(pid)/"cmdline";assert str(p).encode() in q.read_bytes();os.kill(pid,signal.SIGTERM);print(json.dumps(dict(pid=pid,identity_checked=True,signal="SIGTERM")))'
  record('cleanup_own_model_process',result=json.loads(docker('exec',W,'/opt/venv/qwenpaw/bin/python','-c',code,s['fixture'])))
 else:record('cleanup_no_matching_live_writer',observation=obs)
 time.sleep(1);record('cleanup_verify',observation=observe());timeline()
record('finished',model_writer_observed=observed is not None,one_native_delegate=True,harness_started_writer=False)
print(json.dumps(s['results'][-1]))
