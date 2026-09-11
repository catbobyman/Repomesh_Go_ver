"""Six one-shot requests across real a/b Manager and team members; no runtime edits."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import threading
import time
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('matrix_live',ROOT/'scripts/matrix-live-validation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PRIVATE=ROOT/'private/twin-model-live-state.json'
STATE=json.loads(PRIVATE.read_text(encoding='utf-8')) if PRIVATE.exists() else {'instances':{},'cases':{}}
LOCK=threading.Lock()
HEALTH=[]
STOP=threading.Event()


def save():
    with LOCK:
        PRIVATE.write_text(json.dumps(STATE,ensure_ascii=False,indent=2),encoding='utf-8')


def inventory(instance,kind):
    p=subprocess.run(['docker','exec',f'rv-{instance}-controller','agt','get',kind,'-o','json'],capture_output=True,text=True,timeout=20)
    if p.returncode: raise RuntimeError('inventory failed')
    return json.loads(p.stdout)[kind]


def prepare(instance,kind):
    entry=STATE['instances'].setdefault(instance,{})
    if 'token' not in entry:
        env=dict(line.split('=',1) for line in (ROOT/f'private/rv-{instance}-controller.env').read_text(encoding='utf-8').splitlines() if '=' in line)
        sec=json.loads((ROOT/f'private/rv-{instance}-secrets.json').read_text(encoding='utf-8'))
        login=m.ok(instance,'POST','/_matrix/client/v3/login',data={'type':'m.login.password','identifier':{'type':'m.id.user','user':env['AGENTTEAMS_ADMIN_USER']},'password':sec['admin_password']})
        entry.update(token=login['access_token'],user_id=login['user_id']);save()
    if kind=='managers':
        manager=inventory(instance,'managers')[0]
        selections=[('manager',manager['matrixUserID'],manager['roomID'])]
    else:
        if 'team_token' not in entry:
            human=json.loads((ROOT/f'private/twin-human-{instance}.json').read_text(encoding='utf-8'))
            login=m.ok(instance,'POST','/_matrix/client/v3/login',data={'type':'m.login.password','identifier':{'type':'m.id.user','user':human['matrixUserID']},'password':human['initialPassword']})
            entry.update(team_token=login['access_token'],team_user_id=login['user_id']);save()
        team=next(v for v in inventory(instance,'teams') if v['name']=='live-twin-team')
        room=team.get('teamRoomID') or team.get('teamRoomId') or team.get('roomID')
        if not room: raise RuntimeError(f'Instance {instance} team room not ready')
        workers={v['name']:v for v in inventory(instance,'workers')}
        joined=m.ok(instance,'GET','/_matrix/client/v3/joined_rooms',entry['team_token'])['joined_rooms']
        if room not in joined: raise RuntimeError(f'Instance {instance} Human not joined to team room')
        selections=[(role,workers['live-twin-'+role]['matrixUserID'],room) for role in ['leader','worker']]
    for role,uid,room in selections:
        cid=instance+'-'+role
        STATE['cases'].setdefault(cid,{'instance':instance,'role':role,'target_user':uid,'room':room,
            'marker':'RV_TWIN_'+instance.upper()+'_'+role.upper()+'_'+secrets.token_hex(4),'tx_id':'twin-'+cid+'-'+secrets.token_hex(8)})
    save()
    return [instance+'-'+role for role,_,_ in selections]


def credentials(case):
    entry=STATE['instances'][case['instance']]
    return (entry['token'],entry['user_id']) if case['role']=='manager' else (entry['team_token'],entry['team_user_id'])


def sync(case):
    params={'timeout':0,'filter':json.dumps({'room':{'rooms':[case['room']],'timeline':{'limit':100}}})}
    if case.get('cursor'): params['since']=case['cursor']
    response=m.ok(case['instance'],'GET','/_matrix/client/v3/sync',credentials(case)[0],query=params)
    case['cursor']=response['next_batch'];save()
    return response.get('rooms',{}).get('join',{}).get(case['room'],{}).get('timeline',{}).get('events',[])


def execute(cid):
    case=STATE['cases'][cid]
    if case.get('attempted'):
        return {'id':cid,'status':'NOT_RESENT','previous_status':case.get('status'),'event_id':case.get('event_id')}
    sync(case)
    body=f"{case['target_user']} 这是隔离验证，只回复 {case['marker']}，不调用工具、不创建资源、不委派或联系其他成员。"
    case.update(attempted=True,sent_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),intended_body=body);save()
    started=time.monotonic()
    try:
        response=m.ok(case['instance'],'PUT','/_matrix/client/v3/rooms/'+m.q(case['room'])+'/send/m.room.message/'+m.q(case['tx_id']),credentials(case)[0],{'msgtype':'m.text','body':body,'m.mentions':{'user_ids':[case['target_user']]}})
        case['event_id']=response['event_id'];save()
        readback=m.ok(case['instance'],'GET','/_matrix/client/v3/rooms/'+m.q(case['room'])+'/event/'+m.q(case['event_id']),credentials(case)[0])
        case['actual_body']=readback['content']['body'];case['body_exact']=case['actual_body']==body;save()
        if not case['body_exact']: raise RuntimeError('UTF-8 wire mismatch')
        case['observed_bot_events']=[]
        while time.monotonic()-started<180:
            for event in sync(case):
                if event.get('sender')==credentials(case)[1]: continue
                content=event.get('content',{})
                text=content.get('m.new_content',content).get('body','')
                observed={'event_id':event['event_id'],'sender':event.get('sender'),'room':case['room'],
                          'origin_server_ts':event.get('origin_server_ts'),'content':content}
                case['observed_bot_events'].append(observed)
                if event.get('sender')==case['target_user'] and case['marker'] in text:
                    case.update(status='PASS_REAL_MODEL_REPLY',reply=observed,elapsed_seconds=round(time.monotonic()-started,3));save()
                    return {'id':cid,**{k:case[k] for k in ['status','marker','event_id','target_user','room','body_exact','elapsed_seconds','reply']}}
            time.sleep(2)
        case['status']='NO_MATCHING_REPLY_WITHIN_180S';save()
        return {'id':cid,'status':case['status'],'event_id':case['event_id'],'bot_events':case['observed_bot_events']}
    except Exception as exc:
        case['status']='FAILED_OR_UNKNOWN_SEND';save()
        return {'id':cid,'status':case['status'],'error':type(exc).__name__,'event_id':case.get('event_id')}


def health_sampler():
    while not STOP.is_set():
        for instance,port in [('a',28090),('b',38090)]:
            t=time.monotonic()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz',timeout=3) as response: status=response.status
            except urllib.error.HTTPError as exc: status=exc.code
            except Exception as exc: status=type(exc).__name__
            HEALTH.append({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'instance':instance,'path':'/healthz','status':status,'seconds':round(time.monotonic()-t,4)})
        STOP.wait(0.5)


def stats():
    names=['rv-a-controller','rv-b-controller','rv-a-manager','rv-b-manager',
           'rv-a-worker-live-twin-leader','rv-b-worker-live-twin-leader','rv-a-worker-live-twin-worker','rv-b-worker-live-twin-worker']
    result=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',*names],capture_output=True,text=True,timeout=15)
    rows=[]
    for line in result.stdout.splitlines():
        try: rows.append(json.loads(line))
        except ValueError: pass
    return {'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'samples':rows,'exit_code':result.returncode,
            'scope':'Docker instant sample, not peak/cgroup enforcement proof'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['managers','team']);args=parser.parse_args()
    ids=prepare('a',args.phase)+prepare('b',args.phase)
    before=stats()
    monitor=threading.Thread(target=health_sampler,daemon=True);monitor.start()
    try:
        with ThreadPoolExecutor(max_workers=len(ids)) as pool: results=list(pool.map(execute,ids))
    finally:
        STOP.set();monitor.join(timeout=5)
    after=stats()
    document={'phase':args.phase,'completed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'results':results,
              'health_samples':HEALTH,'resources_before':before,'resources_after':after,'submission_policy':'One per new case; unknown or previous sends never resent'}
    (ROOT/f'evidence/twin-model-live-{args.phase}.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for row in results: print(json.dumps(row,ensure_ascii=False),flush=True)
    print(json.dumps({'health_sample_count':len(HEALTH),'health_failures':[x for x in HEALTH if x['status']!=200]}))
    return 0 if all(r['status']=='PASS_REAL_MODEL_REPLY' for r in results) else 1


if __name__=='__main__': raise SystemExit(main())
