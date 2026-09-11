"""Real default Manager provider binding/clear, storage/bridge/runtime convergence in c only."""
import argparse,datetime,hashlib,importlib.util,json,pathlib,re,secrets,subprocess,time,urllib.error,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('contract',ROOT/'scripts/control-manager-config-live.py');contract=importlib.util.module_from_spec(sp);sp.loader.exec_module(contract)
CONTROLLER='rv-c-controller';MANAGER='rv-c-manager';UID='b8aaa1f5-b2c6-45be-b50c-dcc643704acf'
nonce=secrets.token_hex(5);missing='fixture-missing-provider-'+nonce
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--resume-missing-provider',help='Resume only the precise pre-existing fixture provider after external interruption; do not repeat setup')
parser.add_argument('--finish-restored-default',action='store_true',help='Only idempotent real CLI clear and convergence check after already completed REST recovery')
args=parser.parse_args()
if args.resume_missing_provider:
 assert re.fullmatch(r'fixture-missing-provider-[0-9a-f]{10}',args.resume_missing_provider)
 missing=args.resume_missing_provider
path=ROOT/'evidence'/('control-manager-projection-live-'+nonce+'.json')
out={'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'nonce':nonce,'controller':CONTROLLER,'manager':'default','manager_uid':UID,'records':[], 'boundary':'Real REST/CLI/Kube/MinIO/QwenPaw APIs; no fake projection or runtime monkeypatch. No explicit model task submitted; native startup welcome may use configured provider.'}
def record(kind,**fields):
 out['records'].append({'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':kind,**fields});path.write_text(json.dumps(out,indent=2),encoding='utf-8')
def dx(*args,data=None):return contract.docker(*args,data=data,timeout=40)
token=dx('exec',CONTROLLER,'cat','/var/run/agentteams/cli-token').strip()
def api(method,body=None):
 r=urllib.request.Request('http://127.0.0.1:48090/api/v1/managers/default',data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:response=urllib.request.urlopen(r,timeout=20)
 except urllib.error.HTTPError as e:response=e
 with response:code=response.code;d=json.load(response)
 record('controller_request',method=method,request=body,status=code,safe_response={k:d.get(k) for k in ['name','model','phase','state']})
 assert code==200
 return d
def cr():
 d=json.loads(dx('exec','-i',CONTROLLER,'python3','-c',contract.KUBE_READ,data=json.dumps({'name':'default','namespace':'default','provider_marker':missing})))
 assert d['metadata']['uid']==UID
 return d
READ_CONFIG=r'''
import hashlib,json,pathlib,subprocess,sys
c=json.load(sys.stdin)
if c['kind']=='storage':
 p=subprocess.run(['mc','cat','agentteams/rv-c-storage/agents/manager/openclaw.json'],capture_output=True,text=True,timeout=15)
 if p.returncode:print(json.dumps({'available':False,'exit_code':p.returncode}));sys.exit(0)
 raw=p.stdout;d=json.loads(raw);out={'available':True,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'active_model':d.get('agents',{}).get('defaults',{}).get('model',{}).get('primary'),'providers':{k:{x:v.get(x) for x in ['baseUrl','api']} for k,v in d.get('models',{}).get('providers',{}).items()}}
else:
 p=pathlib.Path('/root/manager-workspace/.qwenpaw/providers.json')
 if not p.is_file():print(json.dumps({'available':False}));sys.exit(0)
 raw=p.read_text();d=json.loads(raw);out={'available':True,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'active_llm':d.get('active_llm'),'providers':{k:{x:v.get(x) for x in ['base_url','chat_model']} for k,v in d.get('custom_providers',{}).items()}}
print(json.dumps(out))
'''
def runtime():
 result={}
 for scope in ['global','effective']:
  try:
   with urllib.request.urlopen('http://127.0.0.1:48099/api/models/active?scope='+scope+'&agent_id=default',timeout=8) as r:d=json.load(r);code=r.status
   result[scope]={'http':code,'active_llm':d.get('active_llm'),'effective_max_input_length':d.get('effective_max_input_length')}
  except Exception as e:result[scope]={'error_type':type(e).__name__,'http':getattr(e,'code',None)}
 return result
def snapshot(stage):
 c=cr();storage=json.loads(dx('exec','-i',CONTROLLER,'python3','-c',READ_CONFIG,data=json.dumps({'kind':'storage'})))
 try:
  ins=json.loads(dx('inspect',MANAGER))[0]
  child={'id':ins['Id'],'running':ins['State']['Running'],'image_id':ins['Image']}
  bridged=json.loads(dx('exec','-i',MANAGER,'/opt/venv/qwenpaw/bin/python3','-c',READ_CONFIG,data=json.dumps({'kind':'bridge'})))
 except (RuntimeError,ValueError) as e:
  child={'available':False,'error_type':type(e).__name__};bridged={'available':False,'error_type':type(e).__name__}
 run=runtime();record('snapshot',stage=stage,cr=c,storage=storage,bridge=bridged,runtime=run,child=child)
 return c,storage,bridged,run
def await_convergence(stage,provider,model,seconds=155):
 deadline=time.monotonic()+seconds;start=time.monotonic();count=0
 while True:
  c,s,b,r=snapshot(stage);count+=1
  success=(c['model_provider']==provider and c['spec']['model']==model and c['status']['observedGeneration']==c['metadata']['generation'] and s.get('active_model')=='agentteams-gateway/'+model and b.get('active_llm',{}).get('model')==model and all(r.get(scope,{}).get('active_llm',{}).get('model')==model for scope in ['global','effective']))
  if success:record('convergence',stage=stage,passed=True,elapsed_seconds=round(time.monotonic()-start,3),snapshots=count);print(stage+': converged',flush=True);return
  if time.monotonic()>=deadline:record('convergence',stage=stage,passed=False,elapsed_seconds=round(time.monotonic()-start,3),snapshots=count);raise AssertionError(stage+': bounded convergence timeout')
  time.sleep(10)
initial=cr();assert initial['spec']['model']=='deepseek-chat'
assert initial['model_provider']==(missing if args.resume_missing_provider else '')
if args.resume_missing_provider or args.finish_restored_default:record('resume_existing_fixture',provider=initial['model_provider'],cr=initial,setup_repeated=False)
for name,image in [(CONTROLLER,'repomesh-validation/embedded:517caff9'),(MANAGER,'repomesh-validation/manager-qwenpaw:517caff9')]:
 ins=json.loads(dx('inspect',name))[0];expected=json.loads(dx('image','inspect',image))[0]['Id'];assert ins['Image']==expected and ins['State']['Running']
 record('container_provenance',name=name,id=ins['Id'],image_id=ins['Image'],image_reference=ins['Config']['Image'],mounts=[{k:m.get(k) for k in ['Type','Name','Source','Destination','RW']} for m in ins['Mounts']],ports=ins['HostConfig']['PortBindings'])
failure=None
try:
 if not args.resume_missing_provider and not args.finish_restored_default:
  await_convergence('baseline','', 'deepseek-chat',155)
  api('PUT',{'modelProvider':'openai-compat','model':'deepseek-reasoner'})
  await_convergence('valid_nonempty_binding','openai-compat','deepseek-reasoner')
  api('PUT',{'modelProvider':missing,'model':'deepseek-chat'})
  for index in range(3):
   time.sleep(5);c,s,b,r=snapshot('missing_binding_blocked')
   assert c['model_provider']==missing and c['spec']['model']=='deepseek-chat'
   assert c['status']['observedGeneration']!=c['metadata']['generation'] and s['active_model']=='agentteams-gateway/deepseek-reasoner'
   assert b['active_llm']['model']=='deepseek-reasoner' and r['global']['active_llm']['model']=='deepseek-reasoner'
  # Real CR status is the error evidence; embedded logs need not go to Docker stdout.
  assert c['fixture_provider_error'], 'Expected fixture provider resolution error in real CR status'
 else:snapshot('resumed_before_cli_clear')
 cfg={'name':'default','upstream':'http://127.0.0.1:8090','args':['--name','default','--model-provider=']}
 result=json.loads(dx('exec','-i',CONTROLLER,'python3','-c',contract.CLI_OBSERVER,data=json.dumps(cfg)))
 record('real_cli_clear',result=result)
 assert result['exit_code']==0 and len(result['forwarded_requests'])==1 and result['forwarded_requests'][0]['body']=={'modelProvider':''}
 await_convergence('cleared_restores_default','', 'deepseek-chat')
 out['status']='PASS_REAL_CONFIG_PROJECTION_AND_RUNTIME_ACTIVE_MODEL'
except Exception as exc:
 failure=type(exc).__name__+': '+str(exc);out['status']='FAILED';record('failure',error=failure)
finally:
 # Restore only our new default Manager's known model/binding. Do not manipulate runtime files or other resources.
 try:
  current=cr()
  if current['model_provider']!='' or current['spec']['model']!='deepseek-chat':api('PUT',{'modelProvider':'','model':'deepseek-chat'});record('restore_requested',model='deepseek-chat',model_provider='')
 except Exception as exc:record('restore_unverified',error_type=type(exc).__name__)
 out['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();path.write_text(json.dumps(out,indent=2),encoding='utf-8')
 print('evidence='+str(path),flush=True)
if failure:raise SystemExit(1)
