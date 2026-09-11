"""Read-only confirmation of the already completed Matrix turn; never submits inference."""
import datetime,json,pathlib,urllib.parse,urllib.request,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
state=json.loads((ROOT/'private/control-manager-model-smoke-matrix-state.json').read_text())
initial=json.loads((ROOT/'evidence/control-manager-model-smoke-matrix.json').read_text())
assert state['attempted'] and state['request_event_id'] and state['response_event_id']
assert state['sender']=='@rv-c-admin:rv-c.matrix.invalid' and state['manager_user']=='@manager:rv-c.matrix.invalid'
def get(path):
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:48099'+path,headers={'X-Agent-Id':'default'}),timeout=15) as r:return json.load(r)
chats=get('/api/chats?'+urllib.parse.urlencode({'user_id':state['room'],'channel':'matrix'}))
assert len(chats)==1;chat=chats[0]
assert chat['user_id']==state['room'] and chat['session_id']=='matrix:'+state['room']
history=get('/api/chats/'+urllib.parse.quote(chat['id'],safe=''))
messages=history.get('messages',[])
starts=[i for i,m in enumerate(messages) if m.get('role')=='user' and any(state['marker'] in p.get('text','') for p in m.get('content',[]) if p.get('type')=='text')]
assert len(starts)==1;turn=messages[starts[0]:]
assert len(turn)==2 and turn[0]['role']=='user' and turn[1]['role']=='assistant'
assert turn[0]['content'][0]['text']==state['intended_body'] and turn[1]['content'][0]['text']==state['marker']
tool_events=[{'id':m.get('id'),'role':m.get('role'),'type':m.get('type')} for m in turn if m.get('role')=='tool' or m.get('type') in ['function_call','function_call_output','mcp_tool_call','mcp_tool_call_output','plugin_call','plugin_call_output']]
calls=get('/api/tool-calls/'+urllib.parse.quote(chat['session_id'],safe=''))
assert not tool_events and calls['total']==0
usage=turn[1]['metadata']['metadata']['qwenpaw_turn_usage']['usage']
assert usage['model_name']=='deepseek-chat' and usage['provider_id']=='agentteams-gateway' and usage['prompt_tokens']>0 and usage['completion_tokens']>0
aggregate=get('/api/token-usage?model=deepseek-chat&provider=agentteams-gateway')
before=next(r['usage_before'] for r in initial['records'] if r['kind']=='preflight')
active=get('/api/models/active?scope=global');assert active['active_llm']=={'provider_id':'agentteams-gateway','model':'deepseek-chat'}
p=subprocess.run(['docker','inspect','rv-c-manager'],capture_output=True,text=True,encoding='utf-8',timeout=15);assert p.returncode==0;ins=json.loads(p.stdout)[0]
out={'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_REAL_MODEL_RESPONSE_CORRELATED_TO_NATIVE_TURN','read_only_confirmation':True,'new_model_submissions':0,'prior_effective_model_submissions':1,'console_entry_rejections_before_model':1,'manager_container':{'name':'rv-c-manager','id':ins['Id'],'image_id':ins['Image'],'image':ins['Config']['Image'],'running':ins['State']['Running']},'matrix_identity':{'sender':state['sender'],'manager':state['manager_user'],'room':state['room'],'request_event_id':state['request_event_id'],'response_event_id':state['response_event_id']},'chat':{k:chat.get(k) for k in ['id','user_id','session_id','channel','status']},'turn':turn,'exact_marker_response':True,'request_scoped_usage':usage,'aggregate_before':before,'aggregate_after':aggregate,'aggregate_delta':{k:aggregate.get(k,0)-before.get(k,0) for k in ['total_prompt_tokens','total_completion_tokens','total_calls']},'observed_tool_events':tool_events,'tool_coordinator_total':calls['total'],'final_active_model':active['active_llm'],'history_probe_correction':'Matrix native chat.user_id is room ID; initial filter incorrectly used Matrix sender ID. No request was repeated.'}
path=ROOT/'evidence/control-manager-model-smoke-confirmed.json';path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':out['status'],'usage':usage,'model_calls_delta':out['aggregate_delta']['total_calls'],'tool_events':len(tool_events),'tool_coordinator_total':calls['total'],'evidence':str(path)},indent=2))
