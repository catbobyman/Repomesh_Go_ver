"""Run SA scope fixture and two existing-resource CLI probes; no new resources."""
import datetime,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUN='d33b63db78'
source=json.loads((ROOT/'evidence'/('controller-delta-live-'+RUN+'.json')).read_text())
out=ROOT/'evidence'/('controller-delta-scope-'+RUN+'.json');assert not out.exists()
refs=next(r['resources'] for r in source['records'] if r['kind']=='finally_fixture_inventory')
keys=[r['key'] for r in source['records'] if r['kind']=='direct_minio_fixture_mc_cp']
local=ROOT/'scripts/controller-delta-scope-container.py';remote='/tmp/controller-delta-scope-'+RUN+'.py'
subprocess.run(['docker','cp',str(local),'rv-c-controller:'+remote],check=True,capture_output=True)
p=subprocess.run(['docker','exec','-i','rv-c-controller','python3',remote],input=json.dumps(dict(refs=refs,keys=keys,project_id=source['project_id'],task_id=source['task_ids']['raw'])),capture_output=True,text=True,encoding='utf8',timeout=240)
out.write_text(p.stdout,encoding='utf8');(ROOT/'evidence'/('controller-delta-scope-'+RUN+'.stderr.log')).write_text(p.stderr,encoding='utf8')
result=json.loads(p.stdout);result['process_exit_code']=p.returncode;out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
cli={'run_id':RUN,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'credential_source':'agt default configuration inside rv-c-controller; token not passed on CLI','records':[]}
for label,command in [('reserved-end',['agt','get','projects',source['project_id']+'-reserved-end','--mermaid']),('ambiguous-with-team',['agt','get','projects',source['project_id'],'--team',source['teams'][0]])]:
 q=subprocess.run(['docker','exec','rv-c-controller',*command],capture_output=True,timeout=35)
 rec=dict(label=label,command=command,exit_code=q.returncode,stdout=q.stdout.decode('utf8',errors='replace'),stderr=q.stderr.decode('utf8',errors='replace'))
 if label=='reserved-end':
  original=(ROOT/'evidence'/('controller-delta-live-'+RUN+'-reserved-end.mmd')).read_bytes()
  rec.update(exact_bytes_equal=q.stdout==original,equal_except_trailing_newlines=q.stdout.rstrip(b'\n')==original.rstrip(b'\n'),api_sha256=hashlib.sha256(original).hexdigest(),cli_sha256=hashlib.sha256(q.stdout).hexdigest())
 cli['records'].append(rec)
(ROOT/'evidence'/('controller-delta-cli-'+RUN+'.json')).write_text(json.dumps(cli,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(scope_exit=p.returncode,scope_checks=len(result['checks']),scope_failures=[c['name'] for c in result['checks'] if not c['passed']],cli=[{'label':r['label'],'exit_code':r['exit_code']} for r in cli['records']]),ensure_ascii=False))
raise SystemExit(p.returncode)
