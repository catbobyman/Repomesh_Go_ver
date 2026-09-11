"""Run unmodified affected official Go packages; preserve raw stdout/stderr."""
import datetime,json,subprocess,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence';OUT.mkdir(exist_ok=True)
stdout=OUT/'controller-official-tests.jsonl';stderr=OUT/'controller-official-tests.stderr.log';summary=OUT/'controller-official-tests-summary.json'
assert not stdout.exists() and not summary.exists(),'Refuse to overwrite earlier run evidence'
cmd=['go','test','-p','2','-count=1','-json','./internal/server','./internal/workflow','./cmd/agt']
S={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':cmd,'cwd':str(ROOT/'upstream/agentteams-controller'),'go_executable':shutil.which('go'),'scope':'Unmodified official Go package tests; no Docker/service operations','stdout':stdout.name,'stderr':stderr.name}
summary.write_text(json.dumps(S,indent=2),encoding='utf8');start=time.time()
try:
 p=subprocess.run(['go','version'],capture_output=True,text=True,timeout=30);S['go_version']=p.stdout.strip();S['go_version_exit_code']=p.returncode
 with stdout.open('wb') as o,stderr.open('wb') as e:
  p=subprocess.run(cmd,cwd=S['cwd'],stdout=o,stderr=e,timeout=1800)
 S['exit_code']=p.returncode
except Exception as exc:S['error']=str(exc);S['exit_code']=None
S['elapsed_seconds']=round(time.time()-start,3);S['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
events=[]
if stdout.exists():
 for line in stdout.read_text(encoding='utf8',errors='replace').splitlines():
  try:events.append(json.loads(line))
  except ValueError:pass
S['packages']=[{'package':e['Package'],'action':e['Action'],'elapsed_seconds':e.get('Elapsed')} for e in events if e.get('Action') in ('pass','fail','skip') and not e.get('Test')]
S['test_events']={kind:sum(e.get('Action')==kind and bool(e.get('Test')) for e in events) for kind in ('pass','fail','skip')}
S['top_level_test_events']={kind:sum(e.get('Action')==kind and bool(e.get('Test')) and '/' not in e['Test'] for e in events) for kind in ('pass','fail','skip')}
S['failed_tests']=[{'package':e.get('Package'),'test':e['Test']} for e in events if e.get('Action')=='fail' and e.get('Test')]
summary.write_text(json.dumps(S,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(S,ensure_ascii=False,indent=2))
raise SystemExit(S['exit_code'] if S['exit_code'] is not None else 1)
