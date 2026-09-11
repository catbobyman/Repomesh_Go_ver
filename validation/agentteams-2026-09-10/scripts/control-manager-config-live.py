"""Prepared Manager update matrix for rv-c only; no execution without --execute.

Creates one uniquely named Stopped Manager, never a runtime/model task. A
temporary localhost observer forwards actual agt PUTs to the real Controller.
CR readback is independent through embedded Kubernetes; secrets stay private.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = 'rv-c-controller'
BASE_URL = 'http://127.0.0.1:48090'
INTERNAL_URL = 'http://127.0.0.1:8090'

KUBE_READ = r'''
import json,ssl,sys,pathlib,urllib.request,urllib.parse
c=json.load(sys.stdin)
url='https://127.0.0.1:6443/apis/agentteams.io/v1beta1/namespaces/'+urllib.parse.quote(c['namespace'],safe='')+'/managers/'+urllib.parse.quote(c['name'],safe='')
token=pathlib.Path('/data/agentteams-controller/admin-token').read_text().strip()
context=ssl.create_default_context(cafile='/data/agentteams-controller/pki/ca.crt')
r=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
with urllib.request.urlopen(r,context=context,timeout=15) as response:d=json.load(response)
spec=d.get('spec',{});meta=d['metadata'];status=d.get('status',{})
print(json.dumps({'metadata':{k:meta.get(k) for k in ('name','namespace','uid','resourceVersion','generation')},
 'spec':{k:spec.get(k) for k in ('model','runtime','image','state')},
 'model_provider_field_present':'modelProvider' in spec,'model_provider':spec.get('modelProvider',''),
 'status':{k:status.get(k) for k in ('phase','observedGeneration','welcomeSent')},
 'fixture_provider_error':c['provider_marker'] in str(status.get('message',''))}))
'''

CLI_OBSERVER = r'''
import http.server,json,os,pathlib,subprocess,sys,threading,urllib.request,urllib.error
c=json.load(sys.stdin); observed=[]
class Observer(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_PUT(self):
  raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
  body=json.loads(raw)
  if self.path!='/api/v1/managers/'+c['name'] or not isinstance(body,dict) or set(body)-{'model','modelProvider'}:
   self.send_error(403);return
  observed.append({'method':'PUT','path':self.path,'body':body})
  request=urllib.request.Request(c['upstream']+self.path,data=raw,method='PUT',headers={'Content-Type':'application/json','Authorization':self.headers.get('Authorization','')})
  try:response=urllib.request.urlopen(request,timeout=20)
  except urllib.error.HTTPError as e:response=e
  with response:
   result=response.read();code=response.code
  observed[-1]['upstream_status']=code
  self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(result)));self.end_headers();self.wfile.write(result)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Observer)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
env=dict(os.environ);env['AGENTTEAMS_CONTROLLER_URL']='http://127.0.0.1:'+str(server.server_port)
env['AGENTTEAMS_AUTH_TOKEN']='';env['AGENTTEAMS_AUTH_TOKEN_FILE']='/var/run/agentteams/cli-token'
try:
 process=subprocess.run(['agt','update','manager',*c['args']],capture_output=True,text=True,timeout=35,env=env)
 secrets=[pathlib.Path('/var/run/agentteams/cli-token').read_text().strip()]
 def safe(text):
  for secret in secrets:
   if secret:text=text.replace(secret,'[REDACTED]')
  return text
 print(json.dumps({'args':c['args'],'exit_code':process.returncode,'stdout':safe(process.stdout),'stderr':safe(process.stderr),'forwarded_requests':observed,'boundary':'Observer only records safe JSON body and forwards real request; no fake responses or model'}))
finally:
 server.shutdown();server.server_close();thread.join(timeout=3)
'''


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def docker(*args, data=None, timeout=45):
    result = subprocess.run(['docker', *args], input=data, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        raise RuntimeError('Docker ' + args[0] + ' failed; raw output suppressed')
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-image', help='Exact reviewed rv-c embedded image tag; required to execute')
    parser.add_argument('--validation-label-value', default='agentteams-2026-09-10')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'mode': 'prepared-not-executed', 'controller': CONTAINER, 'url': BASE_URL,
                          'fixture': 'new unique cfg-clear-* Manager, state Stopped, retained after test',
                          'writes': 'Only this Manager via real Controller REST and current container agt',
                          'excluded': ['default Manager', 'a/b instances', 'runtime startup', 'model calls', 'provider credentials'],
                          'required': '--execute --expected-image <reviewed-new-embedded-tag>'}, indent=2))
        return 0
    if not args.expected_image:
        parser.error('--expected-image is required with --execute')
    inspected = json.loads(docker('inspect', CONTAINER))[0]
    expected_id = json.loads(docker('image', 'inspect', args.expected_image))[0]['Id']
    assert inspected['Name'] == '/' + CONTAINER and inspected['Image'] == expected_id
    assert inspected['State']['Running']
    labels = inspected['Config'].get('Labels') or {}
    assert labels.get('repomesh.validation.run') == args.validation_label_value, 'Wrong validation run label'
    assert labels.get('repomesh.validation.instance') == 'c', 'Wrong validation instance label'
    env = dict(item.split('=', 1) for item in inspected['Config']['Env'] if '=' in item)
    assert env.get('AGENTTEAMS_MANAGER_ENABLED', '').lower() == 'false', 'Expected fresh Manager-disabled c instance'
    bindings = inspected['HostConfig']['PortBindings'].get('8090/tcp') or []
    assert any(p['HostPort'] == '48090' and p.get('HostIp') == '127.0.0.1' for p in bindings)
    namespace = env.get('AGENTTEAMS_NAMESPACE', 'default')
    token = docker('exec', CONTAINER, 'cat', '/var/run/agentteams/cli-token').strip()
    assert token
    nonce = secrets.token_hex(5)
    name = 'cfg-clear-' + nonce
    provider_a, provider_b = 'fixture-provider-a-' + nonce, 'fixture-provider-b-' + nonce
    model_a, model_b, model_c = 'fixture-model-a-' + nonce, 'fixture-model-b-' + nonce, 'fixture-model-c-' + nonce
    path = ROOT / 'evidence' / ('control-manager-config-' + nonce + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {'started_at_utc': utc(), 'nonce': nonce, 'manager': name, 'controller': CONTAINER,
           'controller_id': inspected['Id'], 'controller_image_id': inspected['Image'], 'records': [],
           'boundary': 'Stopped CR contract only; no containerManaged field for Manager, no model requests or runtime start; in-container observer forwards actual CLI PUTs'}
    created = False
    uid = None

    def record(kind, **values):
        out['records'].append({'at_utc': utc(), 'kind': kind, **values})
        text = json.dumps(out, indent=2, ensure_ascii=False).replace(token, '[REDACTED]')
        path.write_text(text + '\n', encoding='utf-8')

    binary_probe = "import hashlib,json,pathlib,shutil; p=pathlib.Path(shutil.which('agt')); print(json.dumps({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
    record('actual_container_agt_binary', **json.loads(docker('exec', CONTAINER, 'python3', '-c', binary_probe)))

    def api(method, body=None, collection=False):
        route = '/api/v1/managers' + ('' if collection else '/' + name)
        request = urllib.request.Request(BASE_URL + route,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}, method=method)
        try:response = urllib.request.urlopen(request, timeout=25)
        except urllib.error.HTTPError as exc:response = exc
        with response:
            code = response.code
            value = json.loads(response.read())
        # Manager DTO and error strings contain only fixture-derived input here;
        # retain a strict safe allowlist anyway, never arbitrary config/headers.
        safe = {k: value.get(k) for k in ('name','model','state','phase','runtime','image','error') if k in value}
        record('controller', method=method, path=route, request=body, status=code,
               response_safe=safe, response_has_model_provider='modelProvider' in value)
        return code, value

    def read_cr(stage):
        nonlocal uid
        cfg = {'name': name, 'namespace': namespace, 'provider_marker': 'fixture-provider-'}
        result = json.loads(docker('exec', '-i', CONTAINER, 'python3', '-c', KUBE_READ, data=json.dumps(cfg)))
        assert result['metadata']['name'] == name and result['spec']['state'] == 'Stopped'
        if uid is None:uid = result['metadata']['uid']
        assert uid == result['metadata']['uid'], 'Fixture identity changed'
        record('independent_kube_cr', stage=stage, result=result)
        return result

    def expect(stage, provider, model):
        result = read_cr(stage)
        assert result['model_provider'] == provider, stage + ': provider mismatch'
        assert result['spec']['model'] == model and result['spec']['runtime'] == 'qwenpaw'
        child = 'rv-c-manager-' + name
        names = docker('ps', '-a', '--format', '{{.Names}}').splitlines()
        assert child not in names, 'Unexpected fixture runtime container; no automatic deletion performed'
        record('fixture_runtime_absent', stage=stage, child_name=child, absent=True)
        return result

    def update(body):
        assert api('PUT', body)[0] == 200

    def cli(stage, cli_args, expected_body=None, expected_success=True):
        cfg = {'name': name, 'upstream': INTERNAL_URL, 'args': cli_args}
        result = json.loads(docker('exec', '-i', CONTAINER, 'python3', '-c', CLI_OBSERVER,
                                   data=json.dumps(cfg), timeout=50))
        record('actual_cli_via_forward_observer', stage=stage, result=result)
        requests = result['forwarded_requests']
        if expected_success:
            assert result['exit_code'] == 0 and len(requests) == 1
            assert requests[0]['body'] == expected_body and requests[0]['upstream_status'] == 200
        else:
            assert result['exit_code'] != 0 and not requests

    failure = None
    try:
        assert api('GET')[0] == 404, 'Unique fixture name unexpectedly exists'
        body = {'name': name, 'model': model_a, 'modelProvider': provider_a, 'runtime': 'qwenpaw', 'state': 'Stopped'}
        assert api('POST', body, collection=True)[0] == 201
        created = True
        expect('create-nonempty-provider', provider_a, model_a)
        update({'model': model_b})
        expect('omitted-provider-preserves', provider_a, model_b)
        update({'modelProvider': None})
        expect('null-provider-preserves', provider_a, model_b)
        for wrong in (17, True, {}, []):
            assert api('PUT', {'modelProvider': wrong})[0] == 400
            expect('invalid-type-' + type(wrong).__name__, provider_a, model_b)
        update({'modelProvider': provider_b})
        expect('nonempty-provider-replaced', provider_b, model_b)
        update({'modelProvider': ''})
        expect('explicit-empty-only-clears', '', model_b)
        update({'modelProvider': ''})
        expect('explicit-empty-repeat', '', model_b)
        update({'modelProvider': provider_a})
        update({'model': model_c, 'modelProvider': ''})
        expect('model-and-provider-clear-together', '', model_c)
        update({'modelProvider': provider_a})
        cli('explicit-empty-only', ['--name', name, '--model-provider='], {'modelProvider': ''})
        expect('cli-explicit-empty-only', '', model_c)
        update({'modelProvider': provider_a})
        cli('provider-omitted', ['--name', name, '--model', model_b], {'model': model_b})
        expect('cli-provider-omitted', provider_a, model_b)
        cli('nonempty-provider', ['--name', name, '--model-provider', provider_b], {'modelProvider': provider_b})
        expect('cli-nonempty-provider', provider_b, model_b)
        cli('missing-name', ['--model-provider='], expected_success=False)
        expect('cli-missing-name-no-write', provider_b, model_b)
        cli('missing-update', ['--name', name], expected_success=False)
        expect('cli-missing-update-no-write', provider_b, model_b)
        record('result', rest_and_cli_matrix=True, actual_cr_readback=True,
               configured_projection_tested=False, runtime_actual_loading_tested=False, model_requested=False)
    except Exception as exc:
        failure = exc
        record('error', type=type(exc).__name__, message=str(exc))
    finally:
        if created:
            # Keep the same stopped fixture and all evidence. Do not DELETE a
            # Manager: its infrastructure may use shared per-instance identity.
            try:
                read_cr('before-final-fixture-reset')
                update({'model': model_a, 'modelProvider': '', 'state': 'Stopped'})
                expect('retained-stopped-fixture-final', '', model_a)
                record('cleanup', temporary_observers_closed=True, fixture_retained=True,
                       fixture_state='Stopped', provider_binding='', no_resource_deleted=True)
            except Exception as exc:
                failure = failure or exc
                record('cleanup_error', type=type(exc).__name__, message=str(exc))
    out['completed_at_utc'] = utc()
    out['success'] = failure is None
    record('finished', success=failure is None)
    print(json.dumps({'evidence': str(path), 'manager': name, 'success': failure is None}))
    return 0 if failure is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
