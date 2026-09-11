"""Read only the named Worker and run one bounded 2.5s single-thread CPU probe."""
import ast,datetime,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'evidence/worker-runtime-live.json'
records=json.loads(out.read_text(encoding='utf8'))
def run(code):
    p=subprocess.run(['docker','exec','rv-a-worker-live-runtime-worker-a','/opt/venv/qwenpaw/bin/python','-c',code],capture_output=True,text=True,encoding='utf8',timeout=20)
    assert p.returncode==0,p.stderr
    return json.loads(p.stdout)
def append(kind,result,**extra):
    records.append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),result=result,**extra))
    out.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
tree=ast.parse((ROOT/'scripts/worker-runtime-live.py').read_text(encoding='utf8'))
probe=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='probe' for x in n.targets))
append('post_ready_probe',run(probe),cgroup_note='Read cgroup v1 or v2 controls actually present')
append('bounded_single_core_probe',run('import time,json; w=time.perf_counter(); c=time.process_time(); n=0\nwhile time.perf_counter()-w<2.5:n+=1\nprint(json.dumps(dict(wall_seconds=time.perf_counter()-w,process_cpu_seconds=time.process_time()-c,iterations=n)))'),duration_bound_seconds=2.5)
append('qwenpaw_model_file',run('import json,pathlib; p=pathlib.Path("/root/agentteams-fs/agents/live-runtime-worker-a/.qwenpaw/workspaces/default/agent.json");d=json.loads(p.read_text());print(json.dumps(dict(path=str(p),active_model=d.get("active_model"),name=d.get("name"),id=d.get("id"))))'))
