"""Exactly one effective Matrix inference request on c's existing isolated Manager DM."""
import datetime,json,pathlib,secrets,subprocess,time,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1];PRIVATE=ROOT/'private/control-manager-model-smoke-matrix-state.json';EVIDENCE=ROOT/'evidence/control-manager-model-smoke-matrix.json'
assert not PRIVATE.exists(),'One-shot Matrix state already exists; never resend'
prior=json.loads((ROOT/'evidence/control-manager-model-smoke-new.json').read_text())
refusal=next(r for r in prior['records'] if r['kind']=='submission')
assert refusal['http']==503 and refusal['response']=={'detail':'Channel Console not found'}
nonce=secrets.token_hex(6);marker='RV_MODEL_MATRIX_NEW_'+nonce
state={'nonce':nonce,'marker':marker,'attempted':False};out={'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nonce':nonce,'marker':marker,'agent_id':'default','records':[],'boundary':'One effective real model request after Console entry rejected before creating a task; existing c-owned admin/Manager DM only, no configuration edits or provider override.'}
def save():PRIVATE.write_text(json.dumps(state,indent=2),encoding='utf-8');EVIDENCE.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
def record(kind,**v):out['records'].append({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':kind,**v});save()
RPC=r'''
import json,sys,urllib.request,urllib.error,os
c=json.load(sys.stdin);body=c.get('body');headers={'Content-Type':'application/json'}
if c.get('login'):body={'type':'m.login.password','identifier':{'type':'m.id.user','user':os.environ['AGENTTEAMS_ADMIN_USER']},'password':os.environ['AGENTTEAMS_ADMIN_PASSWORD']}
if c.get('token'):headers['Authorization']='Bearer '+c['token']
r=urllib.request.Request('http://127.0.0.1:6167'+c['path'],data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,headers=headers,method=c['method'])
try:response=urllib.request.urlopen(r,timeout=15)
except urllib.error.HTTPError as e:response=e
with response:print(json.dumps({'http':response.status,'body':json.load(response)}))
'''
def matrix(method,path,body=None,login=False):
 assert path.startswith('/_matrix/')
 p=subprocess.run(['docker','exec','-i','rv-c-controller','python3','-c',RPC],input=json.dumps({'method':method,'path':path,'body':body,'token':state.get('token'),'login':login}),capture_output=True,text=True,encoding='utf-8',timeout=22)
 if p.returncode:raise RuntimeError('Matrix transport error; no resend; raw output suppressed')
 d=json.loads(p.stdout)
 if not 200<=d['http']<300:raise RuntimeError('Matrix HTTP '+str(d['http'])+' '+str(d['body'].get('errcode')))
 return d['body']
def q(s):return urllib.parse.quote(s,safe='')
def runtime(path):
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:48099'+path,headers={'X-Agent-Id':'default'}),timeout=15) as r:return json.load(r)
def sync():
 params={'timeout':0,'filter':json.dumps({'room':{'rooms':[state['room']],'timeline':{'limit':50}}})}
 if state.get('cursor'):params['since']=state['cursor']
 d=matrix('GET','/_matrix/client/v3/sync?'+urllib.parse.urlencode(params));state['cursor']=d['next_batch'];save()
 return d.get('rooms',{}).get('join',{}).get(state['room'],{}).get('timeline',{}).get('events',[])
inventory=subprocess.run(['docker','exec','rv-c-controller','agt','get','managers','-o','json'],capture_output=True,text=True,encoding='utf-8',timeout=20);assert inventory.returncode==0
manager=next(x for x in json.loads(inventory.stdout)['managers'] if x['name']=='default');assert manager['model']=='deepseek-chat'
state['room']=manager['roomID'];state['manager_user']=manager['matrixUserID']
assert state['manager_user']=='@manager:rv-c.matrix.invalid' and state['room'].endswith(':rv-c.matrix.invalid')
login=matrix('POST','/_matrix/client/v3/login',login=True);state['token']=login['access_token'];state['sender']=login['user_id'];assert state['sender']=='@rv-c-admin:rv-c.matrix.invalid';save()
members=matrix('GET','/_matrix/client/v3/rooms/'+q(state['room'])+'/joined_members')['joined'];assert set(members)=={state['sender'],state['manager_user']}
before=runtime('/api/models/active?scope=global');assert before['active_llm']=={'provider_id':'agentteams-gateway','model':'deepseek-chat'}
usagepath='/api/token-usage?model=deepseek-chat&provider=agentteams-gateway';usage_before=runtime(usagepath)
record('preflight',manager='default',sender=state['sender'],manager_user=state['manager_user'],room=state['room'],joined_users=sorted(members),active_model=before['active_llm'],usage_before=usage_before,console_api_rejections_before_model=1)
sync()
prompt=state['manager_user']+' This is an isolated inference test. Reply with exactly '+marker+'. Do not call tools, read or write files, inspect repositories, delegate work, create resources, or contact anyone. Return only the exact marker.'
state.update(attempted=True,tx_id='rv-c-model-smoke-'+nonce,intended_body=prompt);save();start=time.monotonic();events=[];failure=None
try:
 result=matrix('PUT','/_matrix/client/v3/rooms/'+q(state['room'])+'/send/m.room.message/'+q(state['tx_id']),{'msgtype':'m.text','body':prompt,'m.mentions':{'user_ids':[state['manager_user']]}})
 state['request_event_id']=result['event_id'];save()
 request_event=matrix('GET','/_matrix/client/v3/rooms/'+q(state['room'])+'/event/'+q(result['event_id']))
 assert request_event['sender']==state['sender'] and request_event['content']['body']==prompt
 record('effective_submission',event_id=result['event_id'],sender=state['sender'],room=state['room'],body=prompt,wire_exact=True,effective_model_submissions=1)
 match=None;seen=set()
 while time.monotonic()-start<140:
  for event in sync():
   if event.get('sender')!=state['manager_user'] or event.get('event_id') in seen:continue
   seen.add(event['event_id']);events.append(event)
   content=event.get('content',{});actual=content.get('m.new_content',content).get('body','')
   record('manager_event',event_id=event.get('event_id'),sender=event['sender'],room=state['room'],type=event.get('type'),msgtype=content.get('msgtype'),body=actual,content_field_names=list(content),elapsed_seconds=round(time.monotonic()-start,3))
   if actual.strip()==marker:match=event
  if match:break
  time.sleep(2)
 (ROOT/'private/control-manager-model-smoke-matrix-events.json').write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
 assert match is not None,'No exact Manager marker reply in bounded window; no resend'
 state['response_event_id']=match['event_id'];save()
 # The runtime may still finish persistence immediately after emitting Matrix's final event.
 time.sleep(4)
 chats=runtime('/api/chats?'+urllib.parse.urlencode({'user_id':state['sender'],'channel':'matrix'}))
 candidates=[]
 for chat in chats:
  hist=runtime('/api/chats/'+q(chat['id']));messages=hist.get('messages',[])
  indices=[i for i,m in enumerate(messages) if m.get('role')=='user' and any(marker in p.get('text','') for p in m.get('content',[]) if p.get('type')=='text')]
  if indices:candidates.append((chat,hist,messages[indices[-1]:]))
 assert len(candidates)==1,'Unable to uniquely correlate owned Matrix turn to native runtime history'
 chat,hist,turn=candidates[0];state.update(chat_id=chat['id'],runtime_session_id=chat['session_id']);save()
 (ROOT/'private/control-manager-model-smoke-matrix-turn.json').write_text(json.dumps(turn,ensure_ascii=False,indent=2),encoding='utf-8')
 summaries=[];tool_events=[];assistant=[]
 for msg in turn:
  row={k:msg.get(k) for k in ['id','role','type','status','metadata'] if k in msg}
  if msg.get('role')=='assistant' and msg.get('type') in [None,'message']:
   row['texts']=[p['text'] for p in msg.get('content',[]) if p.get('type')=='text'];assistant+=row['texts']
  if msg.get('role')=='tool' or msg.get('type') in ['function_call','function_call_output','mcp_tool_call','mcp_tool_call_output','plugin_call','plugin_call_output']:tool_events.append(row)
  summaries.append(row)
 calls=runtime('/api/tool-calls/'+q(chat['session_id']))
 record('correlated_runtime_turn',chat_id=chat['id'],session_id=chat['session_id'],user_id=chat['user_id'],channel=chat['channel'],messages=summaries,observed_tool_events=tool_events,tool_coordinator_total=calls.get('total'))
 time.sleep(11)
 usage_after=runtime(usagepath);record('usage_after',value=usage_after,delta={k:usage_after.get(k,0)-usage_before.get(k,0) for k in ['total_prompt_tokens','total_completion_tokens','total_calls']},boundary='Aggregate is corroboration; own turn metadata gives request-scoped attribution when present')
 after=runtime('/api/models/active?scope=global');record('final_configuration',active_llm=after['active_llm'])
 assert any(t.strip()==marker for t in assistant),'Matrix reply not matched by own native assistant history'
 assert not tool_events and calls.get('total')==0,'Tool activity observed in owned turn'
 assert after['active_llm']==before['active_llm']
 out.update(status='PASS_REAL_MANAGER_INFERENCE_MATRIX_AND_RUNTIME_HISTORY',exact_marker_response=True,effective_model_submissions=1,console_rejected_before_model=1,request_event_id=state['request_event_id'],response_event_id=state['response_event_id'])
except Exception as e:
 failure=type(e).__name__+': '+str(e);record('failure',classification=type(e).__name__,message=failure);out['status']='FAILED_NO_RESUBMISSION'
finally:
 out['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();print(json.dumps({'status':out['status'],'evidence':str(EVIDENCE),'request_event_id':state.get('request_event_id'),'response_event_id':state.get('response_event_id')}),flush=True)
if failure:raise SystemExit(1)
