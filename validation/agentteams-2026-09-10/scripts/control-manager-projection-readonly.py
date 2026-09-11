"""Read only c Manager CR and native generated config; emit safe fields only."""
import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('contract', ROOT / 'scripts/control-manager-config-live.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
parser = argparse.ArgumentParser()
parser.add_argument('--manager', default='cfg-clear-2b043b42f8')
args = parser.parse_args()
assert args.manager == 'default' or (args.manager.startswith('cfg-clear-') and args.manager.replace('-', '').isalnum())
CODE = r'''
import hashlib,json,os,pathlib,subprocess,sys
c=json.load(sys.stdin)
prefix=os.getenv('AGENTTEAMS_STORAGE_PREFIX','agentteams/rv-c-storage').rstrip('/')
out={'safe_environment':{k:os.getenv(k) for k in ['AGENTTEAMS_MANAGER_ENABLED','AGENTTEAMS_AI_GATEWAY_URL','AGENTTEAMS_MANAGER_MODEL','AGENTTEAMS_DEFAULT_MODEL','AGENTTEAMS_MANAGER_IMAGE']},'objects':[]}
for relative in ['agents/'+c['name']+'/openclaw.json','agents/'+c['name']+'/runtime/runtime.yaml','agents/manager/openclaw.json']:
 p=subprocess.run(['mc','cat',prefix+'/'+relative],capture_output=True,text=True,timeout=20)
 row={'key':prefix+'/'+relative,'exit_code':p.returncode}
 if p.returncode:
  message=(p.stdout+p.stderr).lower()
  row['error_summary']={'not_found':any(x in message for x in ['does not exist','not found','nosuchkey']),'access_denied':'access denied' in message,'alias_not_configured':'alias' in message and 'not' in message}
 elif relative.endswith('.json'):
  d=json.loads(p.stdout);row['sha256']=hashlib.sha256(p.stdout.encode()).hexdigest()
  row['default_model']=d.get('agents',{}).get('defaults',{}).get('model')
  row['providers']={k:{field:v.get(field) for field in ['baseUrl','api','models'] if field in v} for k,v in d.get('models',{}).get('providers',{}).items()}
  for v in row['providers'].values():
   if isinstance(v.get('models'),list):v['models']=[{k:m.get(k) for k in ['id','name']} for m in v['models'] if isinstance(m,dict)]
 else:row['bytes']=len(p.stdout.encode())
 out['objects'].append(row)
print(json.dumps(out))
'''
cfg = {'name': args.manager, 'namespace': 'default', 'provider_marker': 'fixture-provider-'}
cr = json.loads(contract.docker('exec', '-i', 'rv-c-controller', 'python3', '-c', contract.KUBE_READ, data=json.dumps(cfg)))
generated = json.loads(contract.docker('exec', '-i', 'rv-c-controller', 'python3', '-c', CODE, data=json.dumps(cfg)))
out = {'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'manager': args.manager, 'cr': cr, **generated,
       'boundary': 'Read-only native storage/config and CR; no model, state change, fake projection or server modification'}
stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
path = ROOT / 'evidence' / ('control-manager-projection-state-' + stamp + '.json')
path.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, indent=2))
print('evidence=' + str(path))
