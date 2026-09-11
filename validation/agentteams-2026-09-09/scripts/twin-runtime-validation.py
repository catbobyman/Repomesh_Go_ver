"""Create same-name teams/members in the two isolated instances; save real API evidence."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('live', ROOT/'scripts/controller-live-validation.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
EVIDENCE = ROOT/'evidence/twin-runtime-results.json'
OUT = {'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'events': []}

def save():
    OUT['requests'] = live.RECORDS
    def scrub(value):
        if isinstance(value, dict):
            return {k:('[REDACTED]' if k.lower() in ('initialpassword','password','access_token','token') else scrub(v)) for k,v in value.items()}
        if isinstance(value,list):return [scrub(v) for v in value]
        return value
    content = json.dumps(scrub(OUT), ensure_ascii=False, indent=2)
    for token in live.TOKENS.values():
        content = content.replace(token, '[REDACTED]')
    EVIDENCE.write_text(content, encoding='utf-8')

def api(i, method, path, body=None):
    code, value = live.api(i, method, path, body)
    save()
    if not 200 <= code < 300:
        raise RuntimeError(f'{i} {method} {path}: HTTP {code}; evidence saved')
    return value

def create(i, path, body):
    code, value = live.api(i, 'GET', path+'/'+body['name'])
    if code == 404:
        return api(i, 'POST', path, body)
    if code != 200:
        raise RuntimeError('Unexpected fixture lookup status')
    for key in ('runtime', 'image', 'model', 'description'):
        if key in body and value.get(key) != body[key]:
            raise RuntimeError('Existing fixture has different configuration')
    return value

def main():
    started = time.monotonic()
    for i in 'ab':
        # Team.admin references a Human CR, not the bootstrap Matrix admin.
        human=create(i,'/api/v1/humans',{'name':'live-twin-human','displayName':'Isolated twin team human',
            'permissionLevel':2,'accessibleTeams':['live-twin-team']})
        for n in range(40):
            human=api(i,'GET','/api/v1/humans/live-twin-human')
            if human.get('matrixUserID'):break
            time.sleep(2)
        if not human.get('matrixUserID'):raise RuntimeError('Dedicated Human identity not ready')
        (ROOT/f'private/twin-human-{i}.json').write_text(json.dumps(human,ensure_ascii=False,indent=2),encoding='utf-8')
        for role in ('leader', 'worker'):
            create(i, '/api/v1/workers', {'name': 'live-twin-'+role,
                'runtime':'qwenpaw', 'image':'repomesh-validation/qwenpaw-worker:eeaab643',
                'model':'deepseek-chat', 'state':'Running', 'containerManaged':True,
                'resources':{'limits':{'cpu':'0.5','memory':'512Mi'}},
                'identity':'Isolated validation member. Only respond to explicit test requests. Do not create tasks or invoke tools on welcome notices.'})
        create(i, '/api/v1/teams', {'name':'live-twin-team', 'description':'Isolated same-name multi-instance validation',
            'admin':{'name':'live-twin-human','matrixUserId':human['matrixUserID']},
            'workerMembers':[{'name':'live-twin-leader','role':'team_leader'}, {'name':'live-twin-worker','role':'worker'}],
            'peerMentions':False})
    for attempt in range(48):
        states = {}
        for i in 'ab':
            states[i] = {'team':api(i,'GET','/api/v1/teams/live-twin-team'),
                'members':{role:api(i,'GET','/api/v1/workers/live-twin-'+role+'/status') for role in ('leader','worker')}}
        OUT['latest'] = states
        OUT['events'].append({'elapsed_seconds':round(time.monotonic()-started,3),
            'phases':{i:{'team':s['team'].get('phase'), **{r:v.get('phase') for r,v in s['members'].items()}} for i,s in states.items()}})
        save()
        if all(all(v.get('phase')=='Ready' for v in s['members'].values()) and s['team'].get('teamRoomID') for s in states.values()):
            break
        time.sleep(5)
    OUT['ready_observed'] = all(all(v.get('phase')=='Ready' for v in s['members'].values()) for s in states.values())
    OUT['elapsed_seconds'] = round(time.monotonic()-started,3)
    OUT['containers'] = []
    for i in 'ab':
        for role in ('leader','worker'):
            name=f'rv-{i}-worker-live-twin-{role}'
            p=live.docker('inspect',name,check=False)
            if p.returncode:
                OUT['containers'].append({'name':name,'found':False});continue
            obj=json.loads(p.stdout)[0]
            OUT['containers'].append({'name':name,'id':obj['Id'],'image':obj['Image'],
                'state':obj['State'], 'mounts':obj['Mounts'],'networks':list(obj['NetworkSettings']['Networks']),
                'ports':obj['HostConfig']['PortBindings'],
                'limits':{k:obj['HostConfig'].get(k) for k in ('Memory','NanoCpus','CpuQuota','PidsLimit')}})
    OUT['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save()
    print(json.dumps({'ready':OUT['ready_observed'],'elapsed_seconds':OUT['elapsed_seconds'], 'containers':len(OUT['containers'])}))
    return 0 if OUT['ready_observed'] else 1

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        OUT['harness_error']={'type':type(exc).__name__,'message':'details suppressed; inspect sanitized requests'}
        save()
        print(json.dumps(OUT['harness_error']))
        raise SystemExit(1)
