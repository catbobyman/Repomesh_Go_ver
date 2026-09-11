from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'scripts/worker-auth-container.py'
p=subprocess.run(['docker','cp',str(src),'rv-a-worker-live-runtime-worker-a:/tmp/worker-auth-container.py'],capture_output=True,text=True);assert p.returncode==0
p=subprocess.run(['docker','exec','rv-a-worker-live-runtime-worker-a','/opt/venv/qwenpaw/bin/python','/tmp/worker-auth-container.py'],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=240)
if p.returncode:
 (ROOT/'evidence/worker-auth-live-error.log').write_text(p.stderr,encoding='utf8');raise SystemExit(p.returncode)
result=json.loads(p.stdout);(ROOT/'evidence/worker-auth-live.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
for r in result['records']:
 print(json.dumps({k:v for k,v in r.items() if k in ('kind','path','status','key','returncode','role_argument','runtime_role')},ensure_ascii=False))
