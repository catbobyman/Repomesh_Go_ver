"""One real c/default console model submission, unique owned session, no retries/config edits."""
import datetime,hashlib,json,pathlib,re,secrets,subprocess,time,urllib.error,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE='http://127.0.0.1:48099'
STATE=ROOT/'private/control-manager-model-smoke-new-state.json';EVIDENCE=ROOT/'evidence/control-manager-model-smoke-new.json'
if STATE.exists():raise SystemExit('Existing one-shot state retained; no resubmission allowed')
nonce=secrets.token_hex(6);marker='RV_MODEL_NEW_'+nonce
state={'nonce':nonce,'session_id':'rv-c-smoke-session-'+nonce,'user_id':'rv-c-smoke-user-'+nonce,'marker':marker,'attempted':False}
out={'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'agent_id':'default','nonce':nonce,'session_id':state['session_id'],'user_id':state['user_id'],'marker':marker,'records':[],'boundary':'One real request to deployed c/default QwenPaw native console task endpoint; no model override/config edit or fake provider. Native startup welcome activity is separate.'}
redactions=[]
for name in ['provider.json','rv-c-secrets.json']:
 d=json.loads((ROOT/'private'/name).read_text(encoding='utf-8-sig'))
 redactions.extend(v for k,v in d.items() if isinstance(v,str) and len(v)>=20 and any(t in k.lower() for t in ['key','token','password']))
def safe(v):
 if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
 if isinstance(v,list):return [safe(x) for x in v]
 if isinstance(v,str):
  for secret in redactions:v=v.replace(secret,'[REDACTED]')
  return re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~-]+',r'\1[REDACTED]',v)
 return v
def persist():
 STATE.write_text(json.dumps(state,indent=2),encoding='utf-8')
 EVIDENCE.write_text(json.dumps(safe(out),ensure_ascii=False,indent=2),encoding='utf-8')
def record(kind,**v):out['records'].append({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':kind,**v});persist()
def request(method,path,body=None,timeout=15):
 req=urllib.request.Request(BASE+path,data=json.dumps(body,ensure_ascii=False).encode() if body is not None else None,method=method,headers={'Content-Type':'application/json','X-Agent-Id':'default'})
 try:response=urllib.request.urlopen(req,timeout=timeout)
 except urllib.error.HTTPError as e:response=e
 with response:status=response.status;raw=response.read();d=json.loads(raw)
 return status,d
def get(path):
 code,d=request('GET',path)
 if code!=200:raise RuntimeError('GET '+path+' HTTP '+str(code)+' '+str(safe(d)))
 return d
def inspect(name):
 p=subprocess.run(['docker','inspect',name],capture_output=True,text=True,encoding='utf-8',timeout=15);assert p.returncode==0
 return json.loads(p.stdout)[0]
controller=inspect('rv-c-controller');manager=inspect('rv-c-manager')
assert controller['Config']['Labels']['repomesh.validation.run']=='agentteams-2026-09-10' and controller['Config']['Labels']['repomesh.validation.instance']=='c'
assert manager['Config']['Image']=='repomesh-validation/manager-qwenpaw:517caff9' and manager['State']['Running']
assert any(x.get('HostIp')=='127.0.0.1' and x.get('HostPort')=='48099' for x in manager['HostConfig']['PortBindings']['18799/tcp'])
before=get('/api/models/active?scope=global');assert before['active_llm']=={'provider_id':'agentteams-gateway','model':'deepseek-chat'}
record('preflight',controller_id=controller['Id'],manager_container_id=manager['Id'],manager_image_id=manager['Image'],active_model=before['active_llm'],runtime_endpoint=BASE,ownership='Unique local console identity/session on dedicated c validation instance')
usage_path='/api/token-usage?model=deepseek-chat&provider=agentteams-gateway'
usage_before=get(usage_path);record('usage_aggregate_before',value=usage_before,note='Runtime aggregate; only contextual corroboration, not automatically session-exclusive')
query=urllib.parse.urlencode({'user_id':state['user_id'],'channel':'console'})
assert get('/api/chats?'+query)==[], 'Unique session identity unexpectedly already exists'
prompt='This is a local isolated inference smoke test. Reply with exactly '+marker+'. Do not call any tools, read or write files, inspect repositories, create resources, delegate work, or contact anyone. Return only that exact marker.'
payload={'input':[{'role':'user','content':[{'type':'text','text':prompt}]}],'session_id':state['session_id'],'user_id':state['user_id'],'channel':'console','timeout':90,'stream':True}
record('request_prepared',method='POST',path='/api/console/chat/task',body=payload,submission_attempts=1)
state['attempted']=True;state['attempted_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();persist()
start=time.monotonic();failure=None
try:
 code,d=request('POST','/api/console/chat/task',payload,timeout=20)
 record('submission',http=code,response=d)
 assert code==200 and isinstance(d.get('task_id'),str)
 state['task_id']=d['task_id'];persist()
 final=None
 for index in range(55):
  d=get('/api/console/chat/task/'+urllib.parse.quote(state['task_id'],safe=''))
  record('task_poll',index=index,status=d.get('status'),elapsed_seconds=round(time.monotonic()-start,3))
  if d.get('status')=='finished':final=d;break
  time.sleep(2)
 assert final is not None,'Bounded native task did not finish; request not resubmitted'
 (ROOT/'private/control-manager-model-smoke-new-task-result.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
 chats=get('/api/chats?'+query);assert len(chats)==1 and chats[0]['session_id']==state['session_id'];chat=chats[0]
 state['chat_id']=chat['id'];persist()
 history=get('/api/chats/'+urllib.parse.quote(chat['id'],safe=''))
 (ROOT/'private/control-manager-model-smoke-new-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
 messages=history.get('messages',[]);summary=[];tool_events=[];assistant_texts=[]
 for msg in messages:
  role=msg.get('role');typ=msg.get('type');row={k:msg.get(k) for k in ['id','role','type','status','metadata'] if k in msg}
  parts=msg.get('content',[]);texts=[p['text'] for p in parts if p.get('type')=='text' and isinstance(p.get('text'),str)]
  if role=='assistant' and typ in [None,'message']:assistant_texts.extend(texts);row['texts']=texts
  elif role=='user':row['request_text_exact']=texts==[prompt]
  if role=='tool' or typ in ['function_call','function_call_output','mcp_tool_call','mcp_tool_call_output','plugin_call','plugin_call_output']:
   tool_events.append({'role':role,'type':typ,'id':msg.get('id')})
  summary.append(row)
 calls=get('/api/tool-calls/'+urllib.parse.quote(state['session_id'],safe=''))
 record('real_session_history',chat_id=chat['id'],session_id=chat['session_id'],user_id=chat['user_id'],channel=chat['channel'],status=history.get('status'),messages=summary,observed_tool_events=tool_events,tool_coordinator_total=calls.get('total'))
 result=final.get('result',{});record('native_task_result',status=result.get('status'),error=result.get('error'),response_id=result.get('id'),output_message_count=len(result.get('output',[])),task_status=final['status'],elapsed_seconds=round(time.monotonic()-start,3))
 # Aggregate usage flushes periodically; one bounded post-completion wait, no model retry.
 time.sleep(11)
 usage_after=get(usage_path);record('usage_aggregate_after',value=usage_after,delta={k:usage_after.get(k,0)-usage_before.get(k,0) for k in ['total_prompt_tokens','total_completion_tokens','total_calls']},note='Aggregate delta alone is not session-exclusive; use own assistant metadata when available')
 after=get('/api/models/active?scope=global');record('final_configuration',active_model=after['active_llm'],manager_container_id=inspect('rv-c-manager')['Id'])
 exact=any(text.strip()==marker for text in assistant_texts)
 assert exact,'No exact assistant marker in owned native session'
 assert not tool_events and calls.get('total')==0,'Observed native tool activity; no-tool constraint not satisfied'
 assert result.get('status')=='completed','Native task did not complete'
 assert after['active_llm']==before['active_llm'],'Default model configuration changed unexpectedly'
 out['status']='PASS_REAL_MANAGER_MODEL_RESPONSE_NO_OBSERVED_TOOL_CALLS';out['exact_marker_response']=True
except Exception as exc:
 failure=type(exc).__name__+': '+str(exc);record('failure',classification=type(exc).__name__,message=failure);out['status']='FAILED_NO_RESUBMISSION'
finally:
 out['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();persist();print(json.dumps({'status':out['status'],'evidence':str(EVIDENCE),'session_id':state['session_id'],'task_id':state.get('task_id'),'submission_attempts':1}),flush=True)
if failure:raise SystemExit(1)
