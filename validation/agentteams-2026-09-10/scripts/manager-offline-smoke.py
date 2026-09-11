"""Bounded offline checks of the newly built Manager; no persistent mounts or model."""
import datetime as dt
import json
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANAGER = 'repomesh-validation/manager-qwenpaw:517caff9'
CONTROLLER = 'repomesh-validation/controller:517caff9'
RUN_ID = 'agentteams-2026-09-10'
code = r'''
import hashlib,importlib.metadata,json,pathlib,subprocess,time
packages=['qwenpaw','agentscope','mcp','fastmcp','copaw-worker','loongsuite-site-bootstrap','loongsuite-distro',
          'loongsuite-otel-util-genai','loongsuite-instrumentation-qwenpaw','loongsuite-instrumentation-agentscope',
          'opentelemetry-api','opentelemetry-sdk','opentelemetry-exporter-otlp','pydantic','httpx']
out={'packages':{},'checks':[],'agt_sha256':hashlib.sha256(pathlib.Path('/usr/local/bin/agt').read_bytes()).hexdigest()}
for name in packages:
 try: out['packages'][name]=importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError: out['packages'][name]=None
for command in [['/usr/local/bin/qwenpaw','--help'],['/usr/local/bin/agt','--help'],['/opt/venv/qwenpaw/bin/python','-m','pip','check']]:
 start=time.monotonic()
 try:
  p=subprocess.run(command,capture_output=True,text=True,timeout=30)
  out['checks'].append({'command':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'seconds':time.monotonic()-start})
 except subprocess.TimeoutExpired:
  out['checks'].append({'command':command,'timeout_seconds':30})
print(json.dumps(out))
'''
name = 'rv-c-manager-offline-' + secrets.token_hex(4)
cmd = ['docker','run','--rm','--network','none','--name',name,'--label','repomesh.validation.run='+RUN_ID,
       '--label','repomesh.validation.instance=c','--entrypoint','/opt/venv/qwenpaw/bin/python',MANAGER,'-c',code]
p = subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',timeout=110)
report = {'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'container_name':name,'network':'none','auto_remove':True,
          'persistent_mounts':False,'manager_image':MANAGER,'docker_exit_code':p.returncode}
try:
 report['result']=json.loads(p.stdout)
except ValueError:
 report['harness_error']={'stdout':p.stdout,'stderr':p.stderr}
hash_run = subprocess.run(['docker','run','--rm','--network','none','--label','repomesh.validation.run='+RUN_ID,
                          '--entrypoint','/bin/sh',CONTROLLER,'-c','sha256sum /usr/local/bin/agt'],
                         capture_output=True,text=True,encoding='utf-8',timeout=20)
report['controller_agt']={'image':CONTROLLER,'exit_code':hash_run.returncode,'stdout':hash_run.stdout,'stderr':hash_run.stderr}
if hash_run.returncode == 0:
 report['agt_matches_controller']=report.get('result',{}).get('agt_sha256')==hash_run.stdout.split()[0]
report['images']={}
for image in [MANAGER,CONTROLLER,'repomesh-validation/embedded:517caff9']:
 raw=json.loads(subprocess.check_output(['docker','image','inspect',image],text=True))[0]
 report['images'][image]={'id':raw['Id'],'created':raw['Created']}
remaining=subprocess.run(['docker','container','inspect',name],capture_output=True,text=True)
report['temporary_manager_container_removed']=remaining.returncode!=0
path=ROOT/'evidence/manager-offline-smoke.json'
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'evidence':str(path),'docker_exit_code':p.returncode,'agt_matches_controller':report.get('agt_matches_controller'),
                  'checks':[{'command':x['command'],'exit_code':x.get('exit_code'),'timeout_seconds':x.get('timeout_seconds')} for x in report.get('result',{}).get('checks',[])],
                  'packages':report.get('result',{}).get('packages',{}),'temporary_container_removed':report['temporary_manager_container_removed']}))
