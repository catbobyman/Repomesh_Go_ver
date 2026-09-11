"""Delete/recreate only a new dedicated Worker; replay unchanged old snapshots."""
import base64,datetime,importlib.util,json,secrets,subprocess,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];private=ROOT/'private/worker-identity-recreate-state.json';out=ROOT/'evidence/worker-identity-recreate-live.json'
assert not private.exists(),'Existing identity experiment state found; refuse automatic duplicate deletion/recreation'
S={'nonce':secrets.token_hex(4),'records':[]};S['name']='coverage-identity-recreate-'+S['nonce'];name=S['name'];container='rv-a-worker-'+name
def save():
 private.write_text(json.dumps(S,ensure_ascii=False,indent=2),encoding='utf8');out.write_text(json.dumps({'name':name,'nonce':S['nonce'],'records':S['records']},ensure_ascii=False,indent=2),encoding='utf8')
def record(kind,**kw):S['records'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save();print(kind,flush=True)
def docker(*args,data=None,check=True):
 p=subprocess.run(['docker',*args],input=data,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=35)
 if check and p.returncode:raise RuntimeError('docker '+str(args[:2])+' failed')
 return p
admin=docker('exec','rv-a-controller','cat','/var/run/agentteams/cli-token').stdout.strip()
kube=docker('exec','rv-a-controller','cat','/data/agentteams-controller/admin-token').stdout.strip()
spec=importlib.util.spec_from_file_location('matrix',ROOT/'scripts/matrix-live-validation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def api(method,path,token=None,body=None,label='admin'):
 req=urllib.request.Request('http://127.0.0.1:28090'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+(token or admin),'Content-Type':'application/json'},method=method)
 try:r=urllib.request.urlopen(req,timeout=20)
 except urllib.error.HTTPError as e:r=e
 b=r.read();v=json.loads(b) if b else None
 safe={k:v[k] for k in ('name','phase','state','containerState','message') if k in v} if isinstance(v,dict) else v
 record('controller_http',label=label,method=method,path=path,status=r.code,response=safe);return r.code,v
def raw(resource,key):
 conf='\n'.join(['silent','show-error','cacert = "/data/agentteams-controller/pki/ca.crt"',f'header = "Authorization: Bearer {kube}"',f'url = "https://127.0.0.1:6443/'+('api/v1/namespaces/default/serviceaccounts/' if resource=='sa' else 'apis/agentteams.io/v1beta1/namespaces/default/workers/')+key+'"'])
 return json.loads(docker('exec','-i','rv-a-controller','curl','--config','-',data=conf).stdout)
def inspect():
 p=docker('inspect',container,check=False)
 if p.returncode:return None
 d=json.loads(p.stdout)[0];return {'id':d['Id'],'running':d['State']['Running'],'started_at':d['State']['StartedAt'],'image':d['Image']}
def create():
 code,v=api('POST','/api/v1/workers',body=dict(name=name,runtime='qwenpaw',model='deepseek-chat',image='repomesh-validation/qwenpaw-worker:eeaab643',state='Running',containerManaged=True));assert code==201,(code,v)
 for _ in range(60):
  c=inspect()
  if c and c['running']:
   code,v=api('GET','/api/v1/workers/'+name+'/status')
   if code==200 and v.get('phase')=='Ready':return
  time.sleep(3)
 raise RuntimeError('Worker did not report Ready within 180s')
def snapshot(label):
 code='''import os,pathlib,json
print(json.dumps({'sa_token':pathlib.Path(os.environ['AGENTTEAMS_AUTH_TOKEN_FILE']).read_text().strip(),'matrix_token':os.environ['AGENTTEAMS_WORKER_MATRIX_TOKEN'],'access_key':os.environ['AGENTTEAMS_FS_ACCESS_KEY'],'secret_key':os.environ['AGENTTEAMS_FS_SECRET_KEY'],'session_token':os.getenv('AGENTTEAMS_FS_SESSION_TOKEN',''),'bucket':os.environ['AGENTTEAMS_FS_BUCKET']}))'''
 v=json.loads(docker('exec',container,'/opt/venv/qwenpaw/bin/python','-c',code).stdout);S[label]=v;save()
 claims=json.loads(base64.urlsafe_b64decode(v['sa_token'].split('.')[1]+'==='));saname=claims['kubernetes.io']['serviceaccount']['name'];cr=raw('worker',name);sa=raw('sa',saname)
 identity=dict(worker_uid=cr.get('metadata',{}).get('uid'),sa_name=saname,sa_uid=sa.get('metadata',{}).get('uid'),token_sa_uid=claims['kubernetes.io']['serviceaccount']['uid'],token_exp=claims.get('exp'),container=inspect(),storage_snapshot_source='Actual Worker projected environment; replay uses standalone S3 SigV4 without credential refresh')
 S[label+'_identity']=identity;record(label+'_identity',**identity);return v
def storage(v,method,key,value=None):
 c={k:v[k] for k in ('access_key','secret_key','session_token','bucket')};c.update(method=method,key=key,value=value)
 return json.loads(docker('exec','-i','rv-a-controller','python3','/tmp/identity-storage-snapshot.py',data=json.dumps(c)).stdout)
def probes(label,v,key):
 a,_=api('GET','/api/v1/workers/'+name+'/status',token=v['sa_token'],label=label)
 b,_=api('POST','/api/v1/workers/'+name+'/ready',token=v['sa_token'],body={},label=label)
 c,who=m.request('a','GET','/_matrix/client/v3/account/whoami',v['matrix_token']);record('matrix_snapshot',label=label,status=c,user_id=who.get('user_id'),error_code=who.get('errcode'))
 g=storage(v,'GET',key);record('storage_snapshot',label=label,result=g)
 p=storage(v,'PUT',key,{'fixture':S['nonce'],'writer':label});record('storage_snapshot',label=label,result=p)
 return dict(sa_status=a,sa_ready=b,matrix=c,storage_read=g['http_status'],storage_write=p['http_status'])
save();docker('cp',str(ROOT/'scripts/identity-storage-snapshot.py'),'rv-a-controller:/tmp/identity-storage-snapshot.py')
try:
 create();old=snapshot('old');key=f'agents/{name}/validation-identity-{S["nonce"]}/probe.json';S['object_key']=key;save()
 initial=storage(old,'PUT',key,{'fixture':S['nonce'],'writer':'initial'});record('storage_initial_baseline',result=initial);assert initial['http_status']==200,initial
 baseline=probes('old_before_delete',old,key);record('baseline',results=baseline);assert all(v in (200,204) for v in baseline.values()),baseline
 code,_=api('DELETE','/api/v1/workers/'+name);assert code==204
 for _ in range(40):
  code,_=api('GET','/api/v1/workers/'+name);c=inspect()
  if code==404 and c is None:break
  time.sleep(3)
 else:raise RuntimeError('Deletion not complete within 120s; recreation not attempted')
 record('deletion_verified',worker_cr=raw('worker',name).get('code'),serviceaccount=raw('sa',S['old_identity']['sa_name']).get('code'),container_absent=inspect() is None)
 record('old_after_delete',results=probes('old_after_delete',old,key))
 create();new=snapshot('new');record('identity_comparison',worker_uid_changed=S['old_identity']['worker_uid']!=S['new_identity']['worker_uid'],sa_uid_changed=S['old_identity']['sa_uid']!=S['new_identity']['sa_uid'],container_id_changed=S['old_identity']['container']['id']!=S['new_identity']['container']['id'],sa_token_same=old['sa_token']==new['sa_token'],matrix_token_same=old['matrix_token']==new['matrix_token'],storage_access_key_same=old['access_key']==new['access_key'],storage_secret_same=old['secret_key']==new['secret_key'])
 record('old_after_recreate',results=probes('old_after_recreate',old,key))
 record('new_after_recreate',results=probes('new_after_recreate',new,key))
finally:
 record('finally_state',container=inspect(),scope='Only new dedicated Worker was deleted/recreated; no model messages sent; no credential rotation or global cleanup')
