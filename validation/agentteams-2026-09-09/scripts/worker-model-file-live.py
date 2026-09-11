"""One model request, durable send state, exact UTF-8 readback, read-only file check."""
import datetime,importlib.util,json,secrets,subprocess,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('matrix_live',ROOT/'scripts/matrix-live-validation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
manager_sender='--manager' in sys.argv
if manager_sender:
 p=subprocess.run(['docker','exec','rv-a-manager','/opt/venv/qwenpaw/bin/python','-c','import os; print(os.environ["AGENTTEAMS_MANAGER_MATRIX_TOKEN"])'],capture_output=True,text=True,encoding='utf8',timeout=15);assert p.returncode==0
 auth={'token':p.stdout.strip()};who=m.ok('a','GET','/_matrix/client/v3/account/whoami',auth['token']);assert who['user_id']=='@manager:rv-a.matrix.invalid';auth['user_id']=who['user_id']
else:auth=json.loads((ROOT/'private/manager-model-live-state.json').read_text(encoding='utf8'))
suffix='-manager' if manager_sender else ''
private=ROOT/f'private/worker-model-file-live{suffix}-state.json';evidence=ROOT/f'evidence/worker-model-file-live{suffix}.json'
runtime=json.loads((ROOT/'evidence/worker-runtime-live.json').read_text())
member=next(x['result']['runtime_configs'][0]['member'] for x in runtime if x['kind']=='post_ready_probe')
state=json.loads(private.read_text()) if private.exists() else dict(nonce='RV_FILE_'+secrets.token_hex(6),txn='worker-file-'+secrets.token_hex(8),room=member['personalRoomId'],target=member['matrixUserId'],events=[])
state['authenticated_sender']=auth['user_id'];state['sender_scope']='actual Manager identity positive control' if manager_sender else 'configured human administrator identity'
path='/root/agentteams-fs/agents/live-runtime-worker-a/.qwenpaw/workspaces/default/validation-model-'+state['nonce']+'.txt'
def save():private.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');evidence.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
def sync():
 query={'timeout':0,'filter':json.dumps({'room':{'rooms':[state['room']],'timeline':{'limit':100}}})}
 if state.get('cursor'):query['since']=state['cursor']
 d=m.ok('a','GET','/_matrix/client/v3/sync',auth['token'],query=query);state['cursor']=d['next_batch'];save()
 return d.get('rooms',{}).get('join',{}).get(state['room'],{}).get('timeline',{}).get('events',[])
if not state.get('attempted'):
 # This only joins the already-created personal room as the authorized admin sender.
 m.ok('a','POST','/_matrix/client/v3/join/'+m.q(state['room']),auth['token'],{})
 sync();state['body']='这是一次隔离文件工具验证。请实际调用你的文件工具，只在自己的工作区创建这个文件：'+path+'。文件内容必须严格等于 '+state['nonce']+'，不要加换行。完成后回复文件的绝对路径和内容。不要访问网络或仓库，不要修改其他文件，不要创建其他任务；如果安全策略不允许执行，请直接说明，不要声称已完成。'
 state.update(attempted=True,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
 r=m.ok('a','PUT','/_matrix/client/v3/rooms/'+m.q(state['room'])+'/send/m.room.message/'+m.q(state['txn']),auth['token'],{'msgtype':'m.text','body':state['body'],'m.mentions':{'user_ids':[state['target']]}})
 state['event_id']=r['event_id'];save()
elif not state.get('event_id'):raise RuntimeError('Prior send outcome unknown; will not resend')
read=m.ok('a','GET','/_matrix/client/v3/rooms/'+m.q(state['room'])+'/event/'+m.q(state['event_id']),auth['token'])
state['wire_readback']=read['content']['body'];state['exact_utf8_match']=state['wire_readback']==state['body'];save();assert state['exact_utf8_match']
seen={x['event_id'] for x in state['events']};start=time.monotonic()
while '--audit-only' not in sys.argv and time.monotonic()-start<180:
 for event in sync():
  if event.get('sender')==state['target'] and event['event_id'] not in seen:
   seen.add(event['event_id']);state['events'].append(event);save()
 if state['events']:
  # Allow tool events/final response to arrive; file inspection never creates it.
  text='\n'.join(e.get('content',{}).get('body','') for e in state['events'])
  if '没有访问此智能体的权限' in text or '需要审批' in text:
   state['terminal_result']='access_denied';save();break
  if state['nonce'] in text:break
 time.sleep(2)
code='import pathlib,json,hashlib; p=pathlib.Path('+repr(path)+'); print(json.dumps(dict(path=str(p),exists=p.is_file(),bytes_hex=p.read_bytes().hex() if p.is_file() else None,sha256=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)))'
p=subprocess.run(['docker','exec','rv-a-worker-live-runtime-worker-a','/opt/venv/qwenpaw/bin/python','-c',code],capture_output=True,text=True,encoding='utf8',timeout=20);assert p.returncode==0
state['file_readback']=json.loads(p.stdout);state['exact_bytes_match']=state['file_readback']['bytes_hex']==state['nonce'].encode().hex()
logs=subprocess.run(['docker','logs','--since',state['started_at'],'rv-a-worker-live-runtime-worker-a'],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=20)
state['runtime_trace_nonce_lines']=[l for l in (logs.stdout+logs.stderr).splitlines() if state['nonce'] in l]
state['poll_seconds']=round(time.monotonic()-start,3);state['harness_wrote_target']=False;save()
print(json.dumps(dict(request_event=state['event_id'],exact_utf8=state['exact_utf8_match'],bot_events=len(state['events']),file_exists=state['file_readback']['exists'],exact_file_bytes=state['exact_bytes_match'],trace_lines=len(state['runtime_trace_nonce_lines'])),ensure_ascii=False))
