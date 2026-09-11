"""Read stopped a credential via Docker tar stream, secrets memory only."""
import subprocess,tarfile,io,json,datetime,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':[],'credential_source':'Existing stopped rv-a-controller /var/run/agentteams/cli-token read using docker cp tar stream entirely in memory; no container start','project':'upgrade-smoke-387e374202','task':'upgrade-task-387e374202'}
out=ROOT/'evidence/controller-upgrade-smoke-387e374202-cross-instance.json'
assert not out.exists()
def run(*args):
 p=subprocess.run(['docker',*args],capture_output=True,timeout=25)
 if p.returncode:raise RuntimeError('Docker read failed '+str(args[:2]))
 return p.stdout
def ident(c):
 d=json.loads(run('inspect',c))[0];return {'name':c,'id':d['Id'],'image':d['Image'],'started_at':d['State']['StartedAt'],'running':d['State']['Running']}
def read_token(c):
 archive=run('cp',c+':/var/run/agentteams/cli-token','-')
 with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
  members=[m for m in tf.getmembers() if m.isfile()];assert len(members)==1
  return tf.extractfile(members[0]).read().decode().strip()
tokens=[]
try:
 R['before']=[ident(c) for c in ['rv-a-controller','rv-c-controller']]
 for c in ['rv-a-controller','rv-c-controller']:
  token=read_token(c);assert token;tokens.append(token)
  path='/api/v1/projects/'+R['project']+'/tasks/'+R['task']
  req=urllib.request.Request('http://127.0.0.1:48090'+path,headers={'Authorization':'Bearer '+token})
  try:r=urllib.request.urlopen(req,timeout=20)
  except urllib.error.HTTPError as e:r=e
  R['records'].append({'identity_source':c,'method':'GET','path':path,'status':r.code,'response':json.loads(r.read())})
 R['after']=[ident(c) for c in ['rv-a-controller','rv-c-controller']]
 R['exit_code']=0 if [r['status'] for r in R['records']]==[401,200] and R['before']==R['after'] else 1
except Exception as e:R['error']=str(e);R['exit_code']=1
text=json.dumps(R,ensure_ascii=False,indent=2)
for token in tokens:text=text.replace(token,'[REDACTED]')
out.write_text(text,encoding='utf8');print(json.dumps({'evidence':str(out),'exit_code':R['exit_code'],'statuses':[r['status'] for r in R['records']],'error':R.get('error')}))
raise SystemExit(R['exit_code'])
