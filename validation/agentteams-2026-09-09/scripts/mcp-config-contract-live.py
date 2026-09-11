"""Create a dedicated configured Worker and query a local real MCP fixture via its installed CLI."""
import argparse,datetime as dt,importlib.util,json,secrets,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('live',ROOT/'scripts/controller-live-validation.py');live=importlib.util.module_from_spec(s);s.loader.exec_module(live)
parser=argparse.ArgumentParser();parser.add_argument('--reuse',action='store_true');args=parser.parse_args()
prior=json.loads((ROOT/'evidence/mcp-config-contract-live.json').read_text()) if args.reuse else None
nonce=secrets.token_hex(5);helper='rv-mcp-contract-'+nonce;worker=prior['worker'] if prior else 'coverage-mcp-'+nonce
assert worker.startswith('coverage-mcp-') and worker.replace('-','').isalnum()
folder=ROOT/'runtime'/('mcp-contract-'+nonce);folder.mkdir()
(folder/'server.py').write_text('from mcp.server.fastmcp import FastMCP\nm=FastMCP("ValidationFixture",host="0.0.0.0",port=8123,stateless_http=True,json_response=True)\n@m.tool()\ndef validation_echo(nonce:str)->str:\n print("VALIDATION_ECHO:"+nonce,flush=True)\n return nonce\nm.run(transport="streamable-http")\n',encoding='utf-8')
out={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'nonce':nonce,'worker':worker,'helper':helper,'records':[]}
def save():
    text=json.dumps(out,ensure_ascii=False,indent=2)
    for token in live.TOKENS.values():text=text.replace(token,'[REDACTED]')
    (ROOT/'evidence/mcp-config-contract-live.json').write_text(text,encoding='utf-8')
def record(kind,**kw):out['records'].append({'kind':kind,**kw});save()
def docker(*args,timeout=45):
    p=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    return p.returncode,p.stdout,p.stderr
def required(*args):
    code,stdout,stderr=docker(*args)
    if code:raise RuntimeError(f'Docker command {args[:2]} failed; details suppressed')
    return stdout
def api(method,path,body=None):
    code,value=live.api('a',method,path,body)
    record('controller',method=method,path=path,status=code,request=body,response=value)
    if not 200<=code<300:raise RuntimeError(f'Controller HTTP {code}')
    return value
cid=required('create','--name',helper,'--label','repomesh.validation=agentteams-2026-09-09','--network','rv-a-net',
    '--read-only','--cpus','0.25','--memory','128m','--cap-drop','ALL','--security-opt','no-new-privileges',
    '--mount',f'type=bind,source={folder.resolve()},target=/fixture,readonly','--entrypoint','/opt/venv/qwenpaw/bin/python',
    'repomesh-validation/qwenpaw-worker:eeaab643','/fixture/server.py').strip()
try:
    required('start',cid)
    servers=[{'name':'validation-contract','url':f'http://{helper}:8123/mcp','transport':'http'}]
    if prior:
        existing=api('GET',f'/api/v1/workers/{worker}')
        assert existing['image']=='repomesh-validation/qwenpaw-worker:eeaab643' and not existing.get('mcpServers')
        api('PUT',f'/api/v1/workers/{worker}',{'mcpServers':servers})
    else:
        api('POST','/api/v1/workers',{'name':worker,'runtime':'qwenpaw','image':'repomesh-validation/qwenpaw-worker:eeaab643',
            'model':'deepseek-chat','state':'Running','containerManaged':True,'mcpServers':servers})
    for n in range(45):
        status=api('GET',f'/api/v1/workers/{worker}/status')
        if status.get('phase')=='Ready':break
        time.sleep(3)
    name='rv-a-worker-'+worker
    probe='''import pathlib,json,yaml,sys
p=pathlib.Path('/root/agentteams-fs/agents')/sys.argv[1]
d=yaml.safe_load((p/'runtime/runtime.yaml').read_text())
out={'desired_mcpServers':d.get('desired',{}).get('mcpServers'),'mcporter':[]}
for f in p.rglob('mcporter.json'):
 try:cfg=json.loads(f.read_text());entry=cfg.get('mcpServers',{}).get('validation-contract')
 except Exception:continue
 if entry:out['mcporter'].append({'path':str(f),'entry':{k:entry.get(k) for k in ('url','transport')},'authorization_header_present':any(k.lower()=='authorization' for k in entry.get('headers',{}))})
print(json.dumps(out))'''
    for n in range(20):
        projection=json.loads(required('exec',name,'/opt/venv/qwenpaw/bin/python','-c',probe,worker))
        record('runtime_projection',result=projection)
        if projection.get('desired_mcpServers')==servers and projection['mcporter']:break
        time.sleep(3)
    if not projection['mcporter']:raise RuntimeError('Requested server not present in runtime mcporter config')
    config=projection['mcporter'][0]['path']
    for args in [('list','validation-contract','--schema','--json'),('call','validation-contract.validation_echo','nonce='+nonce)]:
        code,stdout,stderr=docker('exec',name,'mcporter','--config',config,*args)
        record('actual_worker_cli',args=list(args),exit_code=code,stdout=stdout,stderr=stderr)
    logs=required('logs',cid)
    record('fixture_invocation',echo_observed=('VALIDATION_ECHO:'+nonce) in logs)
    record('boundary',model_requested=False,config_file_edited_by_harness=False,fixture_has_no_business_side_effect=True)
except Exception as exc:
    record('error',type=type(exc).__name__,message=str(exc));raise
finally:
    # Restore only the Worker created here to an empty remote MCP list before retiring the fixture.
    try:api('PUT',f'/api/v1/workers/{worker}',{'mcpServers':[]})
    finally:
        obj=json.loads(required('inspect',cid))[0]
        assert obj['Name']=='/'+helper and obj['Config']['Labels'].get('repomesh.validation')=='agentteams-2026-09-09'
        required('stop','--time','5',cid);required('rm',cid)
        record('cleanup',helper_removed=True,new_worker_remote_mcp_reset=True)
print(json.dumps({'evidence':'mcp-config-contract-live.json','worker':worker}))
