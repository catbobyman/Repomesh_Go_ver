"""Run inside rv-c-controller, stdout contains allowlisted evidence only.

Raw mc admin trace JSON, including headers, stays in process memory.
Only a nonce Project/Task/probe fixture is written via mc cp. No model call.
"""
import datetime, hashlib, json, os, secrets, signal, subprocess, tempfile
import threading, time, urllib.request, urllib.error
from pathlib import Path

run = secrets.token_hex(6)
pid, tid = 'trace-project-' + run, 'trace-task-' + run
bucket = 'rv-c-storage'
project_path = bucket + '/shared/projects/' + pid + '/meta.json'
task_path = bucket + '/shared/tasks/' + tid + '/meta.json'
probe_path = bucket + '/shared/projects/' + pid + '/trace-probe.json'
allowed = {project_path, task_path, probe_path}
result = {'run_id': run, 'project_id': pid, 'task_id': tid, 'container': 'rv-c-controller',
          'trace_events': [], 'cases': [], 'checks': [], 'trace_schema_paths': [],
          'boundary': 'Real Controller HTTP and real MinIO admin trace, direct nonce metadata fixtures. No mock, model, service change, or inference about other requests.'}
lock = threading.Lock()
started = time.monotonic()
listener = None
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def check(name, value): result['checks'].append({'name': name, 'passed': bool(value)})
def mc(*args):
    p = subprocess.run(['mc', *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
    if p.returncode: raise RuntimeError('mc operation failed: ' + args[0] + ', exit=' + str(p.returncode))
    return p.stdout
def schema(obj, prefix='', depth=0):
    if not isinstance(obj, dict) or depth > 4: return []
    return [prefix + k for k in obj if k.lower() not in ('headers','header')] + sum(
        [schema(v, prefix+k+'.', depth+1) for k,v in obj.items() if isinstance(v,dict) and k.lower() not in ('headers','header')], [])
def parse(obj):
    # Support mc releases that wrap a server trace record in 'trace'.
    trace = obj.get('trace', obj)
    req = trace.get('request', {})
    resp = trace.get('response', {})
    # Current mc also flattens s3 traces into these public fields.
    method = req.get('method', trace.get('method'))
    if method is None:
        method = {'s3.GetObject':'GET','s3.HeadObject':'HEAD','s3.PutObject':'PUT','s3.DeleteObject':'DELETE',
                  'GetObject':'GET','HeadObject':'HEAD','PutObject':'PUT','DeleteObject':'DELETE'}.get(trace.get('api'))
    path = req.get('path', trace.get('path', ''))
    if isinstance(path,str): path = path.split('?',1)[0].lstrip('/')
    if path not in allowed: return None
    return {'method': method, 'path': path, 'status': resp.get('statusCode', resp.get('status', trace.get('statusCode'))),
            'time': trace.get('time'), 'received_at': utc(), 'received_monotonic': round(time.monotonic()-started,6)}
def read_trace():
    for raw in listener.stdout:
        try: obj = json.loads(raw)
        except Exception: continue
        if not isinstance(obj,dict): continue
        with lock:
            if not result['trace_schema_paths']: result['trace_schema_paths'] = sorted(schema(obj))
            event = parse(obj)
            if event: result['trace_events'].append(event)
def events():
    with lock: return list(result['trace_events'])
def wait_probe(index, timeout=4):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if any(e['method']=='GET' and e['path']==probe_path for e in events()[index:]): return True
        if listener.poll() is not None: return False
        time.sleep(.05)
    return False
def get_api(query):
    path='/api/v1/projects/'+pid+'/workflow?'+query
    req=urllib.request.Request('http://127.0.0.1:8090'+path,headers={'Authorization':'Bearer '+token})
    try: r=urllib.request.urlopen(req,timeout=12)
    except urllib.error.HTTPError as e: r=e
    raw=r.read()
    try: body=json.loads(raw)
    except ValueError: body=raw.decode('utf8')
    return {'method':'GET','path':path,'status':r.code,'content_type':r.headers.get('Content-Type'),'body':body}
try:
    result['started_at']=utc()
    result['trace_method_provenance']='Use explicit request.method if present; mc flattened api s3.GetObject maps to HTTP GET, s3.HeadObject to HEAD. Unrecognized operations remain null; raw api/headers are not emitted.'
    token=Path('/var/run/agentteams/cli-token').read_text().strip()
    assert token
    fixtures={project_path: {'project_id':pid,'title':'Storage trace fixture '+run,'status':'active','plan_type':'dag','tasks':[{'task_id':tid,'title':'Trace task','status':'planned','depends_on':[]}],'source_room_id':''},
              task_path: {'task_id':tid,'project_id':pid,'status':'in_progress','summary':'TaskMeta-only marker '+run,'history':[]},
              probe_path:{'probe':run}}
    with tempfile.TemporaryDirectory(prefix='mermaid-storage-'+run+'-') as tmp:
        for i,(path,value) in enumerate(fixtures.items()):
            p=Path(tmp)/str(i);p.write_text(json.dumps(value),encoding='utf8');mc('cp',str(p),'agentteams/'+path)
    before={path: hashlib.sha256(mc('cat','agentteams/'+path)).hexdigest() for path in fixtures}
    result['fixtures']=[{'path':p,'sha256':h,'content':fixtures[p]} for p,h in before.items()]
    # --all emits S3 plus internal operations; never persist raw lines/headers.
    listener=subprocess.Popen(['mc','admin','trace','--json','--all','agentteams'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
    result['listener']={'pid':listener.pid,'command':['mc','admin','trace','--json','--all','agentteams'],'timeout_seconds':70,'ready_probe_path':probe_path}
    thread=threading.Thread(target=read_trace,daemon=True);thread.start()
    ready=False
    for _ in range(4):
        index=len(events());mc('cat','agentteams/'+probe_path)
        if wait_probe(index): ready=True;break
    check('listener-positive-probe-observed-before-cases',ready)
    if not ready: raise RuntimeError('Trace readiness not established; no measured API cases issued')
    for name,query,wants_task in [('json-positive-before','includeTasks=true',True),('mermaid-true','format=mermaid&includeTasks=true',False),('mermaid-false','format=mermaid&includeTasks=false',False),('json-positive-after','includeTasks=true',True)]:
        if time.monotonic()-started > 60: raise TimeoutError('Bounded trace execution exceeded 60 seconds')
        time.sleep(.3)
        i=len(events());begin=utc();begin_mono=round(time.monotonic()-started,6)
        http=get_api(query)
        time.sleep(1.25)  # Defined response-completion observation grace window.
        end=utc();end_mono=round(time.monotonic()-started,6);selected=events()[i:]
        # Marker outside the measured window confirms the stream is still active.
        probe_index=len(events());mc('cat','agentteams/'+probe_path);alive=wait_probe(probe_index)
        project_get=[e for e in selected if e['method']=='GET' and e['path']==project_path]
        task_get=[e for e in selected if e['method']=='GET' and e['path']==task_path]
        result['cases'].append({'name':name,'window_start':begin,'window_end':end,'window_start_monotonic':begin_mono,'window_end_monotonic':end_mono,'grace_after_http_seconds':1.25,'http':http,'observed_events':selected,'project_get_count':len(project_get),'task_get_count':len(task_get),'post_window_probe_seen':alive})
        check(name+'/http200',http['status']==200)
        check(name+'/project-get-observed',bool(project_get))
        check(name+'/task-get-expectation',bool(task_get)==wants_task)
        check(name+'/trace-active-after-window',alive)
        if wants_task: check(name+'/raw-task-detail-marker-returned',run in json.dumps(http['body'].get('tasks_detail',[])))
    result['completed']=True
    after={path:hashlib.sha256(mc('cat','agentteams/'+path)).hexdigest() for path in fixtures}
    check('fixture-content-unchanged',before==after)
except Exception as e:
    result['error']={'type':type(e).__name__,'message':str(e) if isinstance(e,(RuntimeError,TimeoutError)) else 'See bounded check outcomes; no raw transport error emitted'}
finally:
    if listener is not None:
        if listener.poll() is None:
            os.killpg(listener.pid,signal.SIGTERM)
            try:listener.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(listener.pid,signal.SIGKILL);listener.wait(timeout=3)
        result['listener']['exit_code']=listener.returncode
        result['listener']['terminated']=listener.poll() is not None
        thread.join(timeout=1)
    result['ended_at']=utc();result['elapsed_seconds']=round(time.monotonic()-started,3)
    result['exit_code']=0 if result.get('completed') and all(x['passed'] for x in result['checks']) else 1
    print(json.dumps(result,ensure_ascii=False))
raise SystemExit(result['exit_code'])
