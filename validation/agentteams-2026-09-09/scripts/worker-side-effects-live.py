"""Bounded real Worker filesystem side effects across a native fixture cancellation."""
from pathlib import Path
import json,subprocess,secrets,time,datetime
ROOT=Path(__file__).resolve().parents[1];E=[]
C=json.loads((ROOT/'private/teamharness-live-state.json').read_text());C['id']=secrets.token_hex(5)
W='rv-a-worker-live-runtime-worker-a';F='/tmp/repomesh-worker-side-effects/'+C['id'];child=None
def docker(*args,data=None):
 p=subprocess.run(['docker',*args],input=data,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=90)
 if p.returncode:raise RuntimeError(f'docker {args[:2]} failed; '+p.stderr[:200])
 return p.stdout
def record(kind,**kw):
 E.append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw))
 text=json.dumps(E,ensure_ascii=False,indent=2).replace(C['token'],'[REDACTED]')
 (ROOT/'evidence/worker-side-effects-live.json').write_text(text,encoding='utf8')
def call(action):
 payload={**C,'action':action}
 text=docker('exec','-i','rv-a-controller','python3','/tmp/worker-side-effects-container.py',data=json.dumps(payload))
 result=json.loads(text);record(action,**result);return result['result']
docker('cp',str(ROOT/'upstream/plugins/teamharness/mcp'),'rv-a-controller:/tmp/repomesh-sidefx-mcp')
docker('cp',str(ROOT/'scripts/worker-side-effects-container.py'),'rv-a-controller:/tmp/worker-side-effects-container.py')
setup=call('setup');record('boundary',worker=W,fixture=F,note='Native fixture task is assigned to fixture Matrix user; heartbeat is harness-spawned in real Worker, not a model-launched task or execution-lease integration.')
code='import pathlib,time,os,sys; p=pathlib.Path(sys.argv[1]);p.mkdir(parents=True,exist_ok=True);(p/"pid").write_text(str(os.getpid()))\nfor n in range(600):\n (p/"heartbeat.txt").open("a").write(str(n)+"\\n");time.sleep(0.1)'
try:
 child=subprocess.Popen(['docker','exec',W,'/opt/venv/qwenpaw/bin/python','-c',code,F],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 def heartbeat():return json.loads(docker('exec',W,'/opt/venv/qwenpaw/bin/python','-c','import pathlib,json; p=pathlib.Path("'+F+'");print(json.dumps(dict(pid=int((p/"pid").read_text()),lines=len((p/"heartbeat.txt").read_text().splitlines()))))'))
 time.sleep(.6);before=heartbeat();cancel=call('cancel');assert cancel['cancel']['ok'] and cancel['cancel']['synced']
 at_cancel=heartbeat();time.sleep(.7);after=heartbeat()
 assert after['lines']>at_cancel['lines'] and child.poll() is None
 record('post_cancel_real_worker_write',before=before,at_cancel=at_cancel,after=after,process_alive=True)
finally:
 if child is not None:
  cleanup='import pathlib,os,signal,time,json; p=pathlib.Path("'+F+'");pid=int((p/"pid").read_text());cmd=pathlib.Path("/proc")/str(pid)/"cmdline";match=cmd.exists() and str(p).encode() in cmd.read_bytes();assert match,"PID identity mismatch";os.kill(pid,signal.SIGTERM);print(json.dumps(dict(pid=pid,signal="SIGTERM",identity_checked=True)))'
  stopped=json.loads(docker('exec',W,'/opt/venv/qwenpaw/bin/python','-c',cleanup));child.wait(timeout=10);record('cleanup',**stopped,docker_exec_exitcode=child.returncode)
late=call('late');artifacts=call('artifacts')
record('complete',fixture_id=C['id'],process_cleaned=True)
print(json.dumps(dict(fixture_id=C['id'],heartbeat_continued=True,late_submit_ok=late['submit'].get('ok'),late_accept_ok=late['accept'].get('ok'),missing_submit_ok=artifacts['missing'].get('ok'),upload_submit_ok=artifacts['upload'].get('ok'))))
