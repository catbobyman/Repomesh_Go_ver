"""Real localhost Controller HTTP, embedded CR storage and MinIO experiments.

No fake network/store. Manager is disabled and fixture Worker is unmanaged.
Observed gaps are successful reproductions, never acceptance passes.
"""
from pathlib import Path
import datetime as dt
import json
import subprocess
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
RECORDS = []


def docker(*args, data=None, check=True):
    p = subprocess.run(['docker', *args], input=data, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=40)
    if check and p.returncode:
        raise RuntimeError(f'Docker command {args[:2]} failed ({p.returncode})')
    return p


TOKENS = {i: docker('exec', f'rv-{i}-controller', 'cat', '/var/run/agentteams/cli-token').stdout.strip() for i in 'ab'}


def api(instance, method, path, body=None, token='own'):
    headers = {'Content-Type': 'application/json'}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + TOKENS[instance if token == 'own' else token]
    port = 28090 if instance == 'a' else 38090
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
        data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        response = e
    raw = response.read().decode()
    try: value = json.loads(raw)
    except ValueError: value = raw
    record = {'instance': instance, 'method': method, 'path': path,
              'auth': 'none' if token is None else ('own' if token == 'own' else 'other-instance'),
              'request': body, 'status': response.code, 'response': value}
    RECORDS.append(record)
    return response.code, value


def put_object(key, value):
    fixture = ROOT/'runtime'/'live-object-input.json'
    fixture.parent.mkdir(parents=True,exist_ok=True)
    fixture.write_text(json.dumps(value),encoding='utf-8')
    docker('cp',str(fixture),'rv-a-controller:/tmp/live-object-input.json')
    docker('exec','rv-a-controller','mc','cp','/tmp/live-object-input.json','agentteams/rv-a-storage/'+key)


def get_object(key):
    return json.loads(docker('exec', 'rv-a-controller', 'mc', 'cat', 'agentteams/rv-a-storage/' + key).stdout)


def record(name, observation, **values):
    RECORDS.append({'experiment': name, 'observation': observation, **values})


def main():
    for instance in 'ab':
        assert api(instance, 'GET', '/api/v1/workers', token=None)[0] == 401
        assert api(instance, 'GET', '/api/v1/workers', token='b' if instance == 'a' else 'a')[0] == 401
        assert api(instance, 'GET', '/api/v1/workers')[0] == 200
    record('LIVE-C01', 'Own admin auth succeeds; absent and cross-instance admin tokens rejected', at=['AT-02', 'AT-09'])

    body = {'name': 'live-control-worker', 'runtime': 'qwenpaw', 'model': 'deepseek-chat',
            'state': 'Stopped', 'containerManaged': False,
            'resources': {'limits': {'cpu': '1', 'memory': '512Mi'}},
            'remoteSkills': [{'source': 'https://example.invalid/skills', 'skills': [{'name': 'validation-skill'}]}]}
    status, created = api('a', 'POST', '/api/v1/workers', body)
    assert status in (201, 409), (status, created)
    if status == 409:
        status, created = api('a', 'GET', '/api/v1/workers/live-control-worker')
        assert status == 200
    actual_name = created['name']
    kube_token = docker('exec', 'rv-a-controller', 'cat', '/data/agentteams-controller/admin-token').stdout.strip()
    TOKENS['kube-a'] = kube_token
    config = '\n'.join(['silent', 'show-error', 'fail', 'cacert = "/data/agentteams-controller/pki/ca.crt"',
                        f'header = "Authorization: Bearer {kube_token}"',
                        'url = "https://127.0.0.1:6443/apis/agentteams.io/v1beta1/workers"'])
    raw = docker('exec', '-i', 'rv-a-controller', 'curl', '--config', '-', data=config)
    worker = next(x for x in json.loads(raw.stdout)['items'] if x['metadata']['name'] == actual_name)
    spec = worker['spec']
    assert not spec.get('remoteSkills'), spec
    assert spec['resources']['limits']['cpu'] == '1'
    assert spec['runtime'] == 'qwenpaw' and spec['state'] == 'Stopped' and spec['containerManaged'] is False
    record('LIVE-C02', '201/CR persistence: remoteSkills ignored, resource/model/runtime/state preserved', at=['AT-01'],
           cr_name=actual_name, cr_spec=spec, raw_read_boundary='privileged container-local embedded Kubernetes read')

    pid = 'live-control-project'
    key = f'shared/projects/{pid}/meta.json'
    initial = {'project_id': pid, 'title': 'Live validation fixture', 'status': 'active', 'plan_type': 'dag',
               'tasks': [{'task_id': 'live-control-t1', 'title': 'Fixture', 'status': 'planned', 'depends_on': []}]}
    # Explicit transport contrast: mc pipe creates a multipart ETag even for
    # this small JSON; normal upstream PutObject uses a file + mc cp.
    docker('exec','-i','rv-a-controller','mc','pipe','agentteams/rv-a-storage/'+key,data=json.dumps(initial))
    stat = json.loads(docker('exec','rv-a-controller','mc','stat','--json','agentteams/rv-a-storage/'+key).stdout)
    code, result = api('a','POST',f'/api/v1/projects/{pid}/pause',{})
    assert code == 409 and stat['etag'].endswith('-1'), (code, stat)
    record('LIVE-C06','Multipart metadata rejects uncontended REST update; separate writer compatibility limitation',
           at=['AT-04'],etag=stat['etag'],response=result,
           boundary='mc pipe fixture, not native TeamHarness file-upload path; contrast below uses ordinary mc cp')
    put_object(key, initial)
    assert api('a', 'GET', f'/api/v1/projects/{pid}/workflow')[0] == 200
    assert api('b', 'GET', f'/api/v1/projects/{pid}/workflow')[0] == 404
    codes=[]
    for action, payload in [('pause',{}), ('replan', {'tasks':[{'taskId':'live-control-t2','title':'New','dependsOn':[]}]}),
                             ('resume',{}), ('replan', {'tasks':[{'taskId':'live-control-t2','title':'New','dependsOn':[]}]})]:
        code, _ = api('a', 'POST', f'/api/v1/projects/{pid}/{action}', payload)
        codes.append(code)
    assert codes == [200,409,200,200], codes
    persisted = get_object(key)
    assert persisted['tasks'][0]['task_id'] == 'live-control-t2'
    record('LIVE-C03', 'Real HTTP and MinIO confirm pause/replan contract and plan readback', at=['AT-03'], codes=codes, persisted=persisted)

    stale = get_object(key)
    assert api('a','POST',f'/api/v1/projects/{pid}/pause',{})[0] == 200
    paused = get_object(key)
    assert paused['status'] == 'paused'
    fixture = ROOT/'runtime'/'live-stale-meta.json'
    fixture.write_text(json.dumps(stale),encoding='utf-8')
    docker('cp',str(fixture),'rv-a-controller:/tmp/live-stale-meta.json')
    docker('exec','rv-a-controller','mc','cp','/tmp/live-stale-meta.json','agentteams/rv-a-storage/'+key)
    overwritten = get_object(key)
    assert overwritten['status'] == 'active'
    record('LIVE-C04', 'Actual mc unconditional upload overwrites newer REST pause', at=['AT-04'],
           before=paused, after=overwritten, boundary='explicit administrative stale writer; deployed Worker credential path not tested here')
    api('a','GET',f'/api/v1/projects/{pid}/history')
    record('LIVE-C05', 'Project visible only in instance a; independent instance b returned404', at=['AT-05','AT-09'])


if __name__ == '__main__':
    success = False
    error = None
    try:
        main()
        success=True
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        for token in TOKENS.values(): error=error.replace(token,'<REDACTED>')
    out={'time_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'all_observations_confirmed':success,
         'error':error,'records':RECORDS,'scope':'real Controller HTTP + MinIO + persisted CR; not runtime/model or RepoMesh acceptance'}
    text=json.dumps(out,ensure_ascii=False,indent=2)
    for token in TOKENS.values(): text=text.replace(token,'<REDACTED>')
    (ROOT/'evidence'/'controller-live-results.json').write_text(text,encoding='utf-8')
    print(json.dumps({'all_observations_confirmed':success,'records':len(RECORDS),'error':error},ensure_ascii=False))
    raise SystemExit(0 if success else 1)
