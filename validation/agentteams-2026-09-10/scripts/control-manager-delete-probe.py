"""UID-guarded removal of only the never-running CFG fixture; preserve CR privately."""
import datetime,json,pathlib,subprocess,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
NAME='cfg-clear-2b043b42f8'
UID='170c88f2-8028-427c-acda-b191a573e181'
CODE=r'''
import json,pathlib,ssl,urllib.request,urllib.error,sys
c=json.load(sys.stdin)
assert c['name']=='cfg-clear-2b043b42f8' and c['uid']=='170c88f2-8028-427c-acda-b191a573e181'
token=pathlib.Path('/data/agentteams-controller/admin-token').read_text().strip()
ctx=ssl.create_default_context(cafile='/data/agentteams-controller/pki/ca.crt')
url='https://127.0.0.1:6443/apis/agentteams.io/v1beta1/namespaces/default/managers/'+c['name']
def request(method,data=None):
 r=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:response=urllib.request.urlopen(r,context=ctx,timeout=20)
 except urllib.error.HTTPError as e:response=e
 with response:return response.code,json.load(response)
code,before=request('GET');assert code==200
assert before['metadata']['uid']==c['uid'] and before['spec']['state']=='Stopped'
assert not before.get('status',{}).get('phase') and not before.get('status',{}).get('containerID')
if c['action']=='read':print(json.dumps({'before':before}));sys.exit(0)
assert c['action']=='delete'
code,result=request('DELETE',{'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':c['uid'],'resourceVersion':before['metadata']['resourceVersion']}})
assert code in (200,202)
after_code,after=request('GET')
print(json.dumps({'before':before,'delete_http':code,'delete_result':result,'after_http':after_code,'after':after}))
'''
def run(action):
 p=subprocess.run(['docker','exec','-i','rv-c-controller','python3','-c',CODE],input=json.dumps({'name':NAME,'uid':UID,'action':action}),capture_output=True,text=True,encoding='utf-8',timeout=35)
 if p.returncode:raise RuntimeError('UID guarded probe operation failed; raw output suppressed')
 return json.loads(p.stdout)
ins=json.loads(subprocess.run(['docker','inspect','rv-c-controller'],capture_output=True,text=True,check=True).stdout)[0]
assert ins['Config']['Labels']['repomesh.validation.run']=='agentteams-2026-09-10'
env=dict(v.split('=',1) for v in ins['Config']['Env']);assert env['AGENTTEAMS_MANAGER_ENABLED']=='false'
names=subprocess.run(['docker','ps','-a','--format','{{.Names}}'],capture_output=True,text=True,check=True).stdout.splitlines()
assert 'rv-c-manager-'+NAME not in names
snapshot=run('read')
(ROOT/'private/control-manager-probe-before-delete.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
result=run('delete')
(ROOT/'private/control-manager-probe-delete-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert result['after_http']==404
safe={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'name':NAME,'uid':UID,'before_spec':snapshot['before']['spec'],'before_metadata':{k:snapshot['before']['metadata'].get(k) for k in ['name','namespace','uid','generation','resourceVersion']},'before_status':snapshot['before'].get('status'), 'full_snapshot_private':'private/control-manager-probe-before-delete.json','snapshot_sha256':hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest(),'delete_http':result['delete_http'],'after_http':result['after_http'],'container_absent':True}
(ROOT/'evidence/control-manager-probe-delete.json').write_text(json.dumps(safe,indent=2),encoding='utf-8')
print(json.dumps(safe,indent=2))
