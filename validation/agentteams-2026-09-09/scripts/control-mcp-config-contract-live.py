"""Correct QwenPaw-native MCP probe; preserve prior mcporter probe evidence."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('live', ROOT / 'scripts/controller-live-validation.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
WORKER = 'coverage-mcp-ab69215252'
CONTAINER = 'rv-a-worker-' + WORKER
NONCE = secrets.token_hex(5)
HELPER = 'rv-mcp-contract-native-' + NONCE
IMAGE = 'repomesh-validation/qwenpaw-worker:eeaab643'
OUT = {'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'nonce': NONCE,
       'worker': WORKER, 'helper': HELPER, 'records': []}
EVIDENCE = ROOT / 'evidence' / ('control-mcp-config-native-' + NONCE + '.json')


def record(kind, **values):
    OUT['records'].append({'kind': kind, **values})
    EVIDENCE.write_text(json.dumps(OUT, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def docker(*args, timeout=45):
    p = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if p.returncode:
        raise RuntimeError('Docker operation failed: ' + args[0] + '; output suppressed')
    return p.stdout


def api(method, payload=None):
    code, value = live.api('a', method, '/api/v1/workers/' + WORKER, payload)
    record('controller', method=method, status=code, worker=value.get('name'), runtime=value.get('runtime'),
           image=value.get('image'), mcp_servers=value.get('mcpServers', []))
    if not 200 <= code < 300:
        raise RuntimeError('Controller HTTP ' + str(code))
    return value


PROBE = r'''
import json,pathlib,urllib.request,urllib.error,yaml
root=pathlib.Path.home(); name='validation-contract'
runtime=yaml.safe_load((root/'runtime/runtime.yaml').read_text())
def get(path):
 try:
  with urllib.request.urlopen('http://127.0.0.1:8088'+path,timeout=12) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,None
 except Exception as e:return type(e).__name__,None
status,entry=get('/api/mcp/'+name)
out={'desired_servers':runtime.get('desired',{}).get('mcpServers',[]),'client_http':status}
if entry:
 out['client']={k:entry.get(k) for k in ('key','name','enabled','transport','url')}
 status,tools=get('/api/mcp/tools/'+name)
 out['tools_http']=status
 out['tools']=[{'name':x.get('name'),'enabled':x.get('enabled')} for x in (tools or [])]
card=root/'.qwenpaw/workspaces/default/drivers/mcp/validation-contract.yaml'
out['driver_card_path']=str(card);out['driver_card_exists']=card.is_file()
if card.is_file():
 d=yaml.safe_load(card.read_text());out['driver_card']={k:d.get(k) for k in ('name','protocol','enabled')};out['driver_endpoint']={k:d.get('endpoint',{}).get(k) for k in ('url','transport')}
out['mcporter_paths']=[str(p) for p in root.rglob('mcporter.json')]
print(json.dumps(out))
'''

CALL = r'''
import asyncio,json,sys,urllib.request
from qwenpaw.drivers.handlers.mcp_stateful_client import HttpStatefulClient
nonce=sys.argv[1]
entry=json.load(urllib.request.urlopen('http://127.0.0.1:8088/api/mcp/validation-contract'))
async def main():
 # Fixture accepts no credentials. Do not copy, print or test stored headers.
 client=HttpStatefulClient(name='validation-contract',transport=entry['transport'],url=entry['url'],timeout=10)
 try:
  await client.connect()
  tools=await client.list_tools()
  result=await client.call_tool('validation_echo',{'nonce':nonce})
  value=result.model_dump(mode='json') if hasattr(result,'model_dump') else result
  print(json.dumps({'client_class':'qwenpaw.drivers.handlers.mcp_stateful_client.HttpStatefulClient','loaded_url':entry['url'],'loaded_transport':entry['transport'],'tools':[t.name for t in tools],'result':value,'new_client_process':True,'credentials_required_by_fixture':False}))
 finally:await client.close()
asyncio.run(main())
'''

folder = ROOT / 'runtime' / ('mcp-native-contract-' + NONCE)
folder.mkdir()
(folder / 'server.py').write_text('from mcp.server.fastmcp import FastMCP\nm=FastMCP("ValidationFixture",host="0.0.0.0",port=8123,stateless_http=True,json_response=True)\n@m.tool()\ndef validation_echo(nonce:str)->str:\n print("VALIDATION_ECHO:"+nonce,flush=True)\n return nonce\nm.run(transport="streamable-http")\n', encoding='utf-8')
existing = api('GET')
assert existing['image'] == IMAGE and existing['runtime'] == 'qwenpaw' and not existing.get('mcpServers')
cid = docker('create', '--name', HELPER, '--label', 'repomesh.validation=agentteams-2026-09-09',
             '--network', 'rv-a-net', '--read-only', '--cpus', '0.25', '--memory', '128m', '--cap-drop', 'ALL',
             '--security-opt', 'no-new-privileges', '--mount', f'type=bind,source={folder.resolve()},target=/fixture,readonly',
             '--entrypoint', '/opt/venv/qwenpaw/bin/python', IMAGE, '/fixture/server.py').strip()
failure = None
try:
    docker('start', cid)
    servers = [{'name': 'validation-contract', 'url': f'http://{HELPER}:8123/mcp', 'transport': 'http'}]
    api('PUT', {'mcpServers': servers})
    assert api('GET')['mcpServers'] == servers
    for attempt in range(20):
        snapshot = json.loads(docker('exec', CONTAINER, '/opt/venv/qwenpaw/bin/python', '-c', PROBE))
        record('qwenpaw_native_projection', attempt=attempt, **snapshot)
        if snapshot.get('tools_http') == 200 and any(t['name'] == 'validation_echo' for t in snapshot.get('tools', [])):
            break
        time.sleep(3)
    else:
        raise RuntimeError('Native runtime client/tools did not converge')
    assert snapshot['desired_servers'] == servers
    assert snapshot['client']['enabled'] and snapshot['client']['transport'] == 'streamable_http'
    assert snapshot['driver_card_exists']
    result = json.loads(docker('exec', CONTAINER, '/opt/venv/qwenpaw/bin/python', '-c', CALL, NONCE))
    record('actual_installed_native_client_call', **result)
    assert NONCE in json.dumps(result['result']) and not result['result'].get('isError', False)
    logs = docker('logs', cid)
    assert 'VALIDATION_ECHO:' + NONCE in logs
    record('fixture_echo_observed', exact_nonce=True, call_count=logs.count('VALIDATION_ECHO:' + NONCE))
    record('result', controller_saved=True, desired_projected=True, native_driver_materialized=True,
           runtime_tools_loaded=True, installed_client_echo=True, model_requested=False,
           agent_policy_call_exercised=False, credentials_contract_exercised=False,
           no_product_files_edited=True, no_service_restart=True)
except Exception as exc:
    failure = exc
    record('error', type=type(exc).__name__, message=str(exc))
finally:
    try:
        api('PUT', {'mcpServers': []})
        for attempt in range(20):
            snapshot = json.loads(docker('exec', CONTAINER, '/opt/venv/qwenpaw/bin/python', '-c', PROBE))
            if snapshot.get('client_http') == 404 and not snapshot['driver_card_exists'] and not snapshot['desired_servers']:
                record('native_client_cleanup', removed=True, attempts=attempt + 1)
                break
            time.sleep(3)
        else:
            record('native_client_cleanup', removed=False, last_safe_snapshot=snapshot)
    finally:
        obj = json.loads(docker('inspect', cid))[0]
        assert obj['Name'] == '/' + HELPER and obj['Config']['Labels'].get('repomesh.validation') == 'agentteams-2026-09-09'
        docker('stop', '--time', '5', cid)
        docker('rm', cid)
        record('helper_cleanup', removed=True, exact_owned_helper_only=True)
print(json.dumps({'evidence': str(EVIDENCE), 'success': failure is None}))
if failure:
    raise SystemExit(1)
