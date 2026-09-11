"""Restart only the two labeled validation controllers and record recovery."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
RUN='agentteams-2026-09-09'
result={'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'experiments':[]}


def inspect(i):
    x=json.loads(subprocess.check_output(['docker','inspect',f'rv-{i}-controller'],text=True))[0]
    if x['Config']['Labels'].get('repomesh.validation.run')!=RUN:
        raise RuntimeError('Unexpected ownership; no restart allowed')
    return x


def http(i,path='/healthz',token=None):
    port=28090 if i=='a' else 38090
    headers={'Authorization':'Bearer '+token} if token else {}
    t=time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}'+path,headers=headers),timeout=3) as r:
            return {'status':r.status,'body':r.read().decode(),'seconds':round(time.monotonic()-t,3)}
    except urllib.error.HTTPError as e:
        return {'status':e.code,'seconds':round(time.monotonic()-t,3)}
    except OSError:
        return {'status':None,'seconds':round(time.monotonic()-t,3)}


def save():
    (ROOT/'evidence'/'infrastructure-restart-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


try:
    for i,other in [('a','b'),('b','a')]:
        before=inspect(i)
        other_before=inspect(other)
        token=subprocess.check_output(['docker','exec',f'rv-{i}-controller','cat','/var/run/agentteams/cli-token'],text=True).strip()
        start=time.monotonic()
        p=subprocess.Popen(['docker','restart','--timeout','10',f'rv-{i}-controller'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        samples=[]
        while p.poll() is None:
            samples.append(http(other))
            time.sleep(0.3)
        stdout,stderr=p.communicate()
        if p.returncode: raise RuntimeError(f'{i} restart failed ({p.returncode})')
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            recovered=http(i,'/api/v1/workers',token)
            if recovered['status']==200: break
            samples.append(http(other))
            time.sleep(1)
        after=inspect(i)
        other_after=inspect(other)
        data={'instance_restarted':i,'same_container_id':before['Id']==after['Id'],
              'started_at_before':before['State']['StartedAt'],'started_at_after':after['State']['StartedAt'],
              'recovery_seconds':round(time.monotonic()-start,3),'old_token_response':recovered,
              'other_instance':other,'other_started_at_unchanged':other_before['State']['StartedAt']==other_after['State']['StartedAt'],
              'other_health_samples':samples}
        result['experiments'].append(data);save()
        assert recovered['status']==200, recovered
        assert before['State']['StartedAt']!=after['State']['StartedAt']
        assert data['other_started_at_unchanged'] and samples and all(x['status']==200 for x in samples)
        print(f'instance {i}: recovered in {data["recovery_seconds"]}s; other instance {other} health remained200',flush=True)
    old_token=subprocess.check_output(['docker','exec','rv-a-controller','cat','/var/run/agentteams/cli-token'],text=True).strip()
    project=http('a','/api/v1/projects/live-control-project/workflow',old_token)
    result['persisted_project']=project
    assert project['status']==200 and json.loads(project['body'])['status']=='active'
    result['observations_confirmed']=True
except Exception as e:
    result['observations_confirmed']=False
    result['error']=f'{type(e).__name__}: {e}'
finally:
    result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    result['scope']='Real infrastructure restart and HTTP persistence only; no Manager/Worker runtime or RepoMesh recovery guarantee'
    save()
print(json.dumps({'observations_confirmed':result['observations_confirmed'],'error':result.get('error')}))
raise SystemExit(0 if result['observations_confirmed'] else 1)
