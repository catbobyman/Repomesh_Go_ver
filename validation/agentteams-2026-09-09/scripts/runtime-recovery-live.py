"""Stop/start only the two explicitly authorized a runtime containers, one at a time.
Single durable marker send per runtime; restore same immutable ID in finally.
"""
import argparse
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
twin=json.loads((ROOT/'private/twin-model-live-state.json').read_text(encoding='utf-8'))
private=ROOT/'private/runtime-recovery-live-state.json'
state=json.loads(private.read_text(encoding='utf-8')) if private.exists() else {}
STOP=threading.Event();SAMPLES=[]
B_NAMES=['rv-b-controller','rv-b-manager','rv-b-worker-live-twin-leader','rv-b-worker-live-twin-worker']


def save():
    private.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')


def inspect(*names):
    p=subprocess.run(['docker','inspect',*names],capture_output=True,text=True,encoding='utf-8',timeout=15)
    if p.returncode: raise RuntimeError('Authorized container inspect failed')
    return [{'name':v['Name'].lstrip('/'),'id':v['Id'],'running':v['State']['Running'],
             'started_at':v['State']['StartedAt'],'finished_at':v['State']['FinishedAt'],
             'restart_count':v['RestartCount']} for v in json.loads(p.stdout)]


def command(action,identifier):
    args=['docker',action]
    if action=='stop':args+=['--time','5']
    args.append(identifier)
    done=subprocess.run(args,capture_output=True,text=True,timeout=30)
    if done.returncode:raise RuntimeError(f'Authorized docker {action} failed')


def monitor():
    last_b=0
    while not STOP.is_set():
        record={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'health':[]}
        for instance,port in [('a',28090),('b',38090)]:
            t=time.monotonic()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz',timeout=3) as r:status=r.status
            except urllib.error.HTTPError as exc:status=exc.code
            except Exception as exc:status=type(exc).__name__
            record['health'].append({'instance':instance,'status':status,'elapsed_seconds':round(time.monotonic()-t,4)})
        if time.monotonic()-last_b>2:
            try:record['b_containers']=inspect(*B_NAMES)
            except Exception:record['b_inspect_error']=True
            last_b=time.monotonic()
        SAMPLES.append(record);STOP.wait(0.5)


def sync(case):
    query={'timeout':0,'filter':json.dumps({'room':{'rooms':[case['room']],'timeline':{'limit':100}}})}
    if case.get('cursor'):query['since']=case['cursor']
    value=m.ok('a','GET','/_matrix/client/v3/sync',case['token'],query=query)
    case['cursor']=value['next_batch'];save()
    return value.get('rooms',{}).get('join',{}).get(case['room'],{}).get('timeline',{}).get('events',[])


def send(case,txid,body,mention):
    content={'msgtype':'m.text','body':body}
    if mention:content['m.mentions']={'user_ids':[case['user']]}
    result=m.ok('a','PUT','/_matrix/client/v3/rooms/'+m.q(case['room'])+'/send/m.room.message/'+m.q(txid),case['token'],content)
    identifier=result['event_id']
    read=m.ok('a','GET','/_matrix/client/v3/rooms/'+m.q(case['room'])+'/event/'+m.q(identifier),case['token'])
    if read['content']['body']!=body:raise RuntimeError('Actual message body mismatch')
    return identifier


def run(kind):
    name='rv-a-worker-live-twin-worker' if kind=='worker' else 'rv-a-manager'
    old=state.get(kind)
    if old and old.get('stop_attempted'):raise RuntimeError('Previous recovery already attempted; no automatic repeat or resend')
    t=twin['cases']['a-'+kind]
    token=twin['instances']['a']['team_token' if kind=='worker' else 'token']
    case=state.setdefault(kind,{'name':name,'room':t['room'],'user':t['target_user'],'token':token,
                               'marker':'RV_RECOVERY_'+kind.upper()+'_'+secrets.token_hex(5),
                               'txid':'recovery-'+kind+'-'+secrets.token_hex(8),'events':[],'received_events':[]})
    save();sync(case);case['cursor_before_stop']=case['cursor']
    baseline=inspect(name)[0];case['before']=baseline;case['b_before']=inspect(*B_NAMES);save()
    identifier=baseline['id'];case['stop_attempted']=True;save()
    start=time.monotonic();case['test_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    mon=threading.Thread(target=monitor,daemon=True);mon.start()
    print(json.dumps({'runtime':kind,'phase':'stopping','container_id':identifier}),flush=True)
    failure=None
    try:
        command('stop',identifier)
        case['stopped']=inspect(identifier)[0];case['stop_complete_seconds']=round(time.monotonic()-start,3);save()
        if case['stopped']['running']:raise RuntimeError('Container did not remain stopped after stop command')
        for number in range(55 if kind=='worker' else 0):
            current=inspect(identifier)[0]
            if current['running']:
                case['auto_started_during_backlog']=current;save();break
            body=f"隔离恢复验证编号消息 {number:02d}。仅保存上下文，不需要回复。"
            txn=case['txid']+f'-history-{number}'
            case['pending_message']={'tx_id':txn,'body':body};save()
            event=send(case,txn,body,False)
            case['events'].append({'number':number,'event_id':event,'tx_id':txn,'body':body,'runtime_running_before_send':False});save()
        case['before_marker_runtime']=inspect(identifier)[0]
        case['marker_attempted']=True;case['marker_sent_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat();save()
        body=f"{case['user']} 这是隔离恢复验证，只回复 {case['marker']}，不调用工具、不创建资源、不联系其他成员。"
        case['marker_event_id']=send(case,case['txid'],body,True);case['marker_body']=body;save()
        case['after_marker_runtime']=inspect(identifier)[0];save()
        command('start',identifier)
        case['after_start']=inspect(identifier)[0];case['start_complete_seconds']=round(time.monotonic()-start,3);save()
        resume=time.monotonic()
        while time.monotonic()-resume<180:
            for event in sync(case):
                content=event.get('content',{});body=content.get('m.new_content',content).get('body','')
                if event.get('sender')!=case['user']:continue
                observed={'event_id':event['event_id'],'sender':event['sender'],'room':case['room'],
                          'origin_server_ts':event.get('origin_server_ts'),'content':content}
                case['received_events'].append(observed)
                if case['marker'] in body:
                    case['matching_reply']=observed;case['reply_after_start_seconds']=round(time.monotonic()-resume,3);save();break
            if case.get('matching_reply'):break
            save();time.sleep(2)
        case['after']=inspect(identifier)[0]
        case['same_container_id']=case['before']['id']==case['after']['id']
        case['started_at_changed']=case['before']['started_at']!=case['after']['started_at']
        case['all_messages_while_stopped']=not case.get('auto_started_during_backlog') and not case['before_marker_runtime']['running'] and not case['after_marker_runtime']['running']
        case['status']='REPLY_OBSERVED' if case.get('matching_reply') else 'NO_REPLY_WITHIN_180S'
        case['b_after']=inspect(*B_NAMES);save()
    except Exception as exc:
        failure=type(exc).__name__+': '+str(exc);case['error']=failure;case['status']='FAILED_OR_PARTIAL';save()
    finally:
        # Restore only the original, explicitly authorized immutable container ID.
        try:
            current=inspect(identifier)[0]
            if not current['running']:command('start',identifier)
            case['finally_restored']=inspect(identifier)[0]
        except Exception as exc:case['restore_error']=type(exc).__name__
        STOP.set();mon.join(timeout=5);case['monitor_samples']=list(SAMPLES);save()
        logs=subprocess.run(['docker','logs','--since',case['test_started_utc'],identifier],capture_output=True,text=True,encoding='utf-8',timeout=20)
        case['runtime_log_excerpts']=[line for line in (logs.stdout+logs.stderr).splitlines() if '_on_room_event' in line or 'MatrixChannel' in line and any(k in line for k in ['history','sync','skip','initial'])][-90:]
        public={k:v for k,v in case.items() if k not in ['token','cursor','cursor_before_stop']}
        public['saved_cursor_resumed']=bool(case.get('cursor') and case.get('cursor_before_stop'))
        (ROOT/f'evidence/runtime-recovery-live-{kind}.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:public.get(k) for k in ['name','status','same_container_id','started_at_changed','all_messages_while_stopped','reply_after_start_seconds','error','finally_restored']},ensure_ascii=False),flush=True)
    return 1 if failure or not case.get('matching_reply') else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('runtime',choices=['worker','manager']);args=parser.parse_args()
    raise SystemExit(run(args.runtime))
