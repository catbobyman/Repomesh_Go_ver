"""Actual Controller-generated SA TokenRequest identity; token stays in memory."""
import base64,datetime,hashlib,json,pathlib,ssl,subprocess,sys,urllib.request,urllib.error,urllib.parse
C=json.load(sys.stdin);R={'records':[],'checks':[],'boundary':'Actual existing Worker SA TokenRequest; Team CR membership promotes these identities to team-leader. No projected runtime token and no ordinary-worker-role claim.'}
admin=pathlib.Path('/data/agentteams-controller/admin-token').read_text().strip();secret=[admin]
ctx=ssl.create_default_context(cafile='/data/agentteams-controller/pki/ca.crt')
def rec(kind,**kw):R['records'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw))
def check(name,c):R['checks'].append(dict(name=name,passed=bool(c)))
def http(base,path,token,body=None):
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST' if body is not None else 'GET')
 try:r=urllib.request.urlopen(req,context=ctx if base.startswith('https:') else None,timeout=20)
 except urllib.error.HTTPError as x:r=x
 raw=r.read()
 try:v=json.loads(raw)
 except ValueError:v=raw.decode()
 return r.code,v
def kube(path,body=None):return http('https://127.0.0.1:6443',path,admin,body)
def hashes():
 out={}
 for key in C['keys']:
  p=subprocess.run(['mc','cat',key],capture_output=True,timeout=20);assert p.returncode==0
  out[key]=hashlib.sha256(p.stdout).hexdigest()
 return out
try:
 before=hashes();rec('minio_hashes_before',objects=before)
 for ref in C['refs']:
  name=ref['worker'];team=ref['team'];sa='rv-c-worker-'+name
  code,s=kube('/api/v1/namespaces/default/serviceaccounts/'+sa);assert code==200,'Controller did not generate stopped Worker SA'
  code,w=kube('/apis/agentteams.io/v1beta1/namespaces/default/workers/'+name);assert code==200
  code,t=kube('/apis/agentteams.io/v1beta1/namespaces/default/teams/'+team);assert code==200
  role=next(m['role'] for m in t['spec']['workerMembers'] if m['name']==name)
  assert s['metadata']['labels']['agentteams.io/worker']==name and role=='team_leader'
  code,issued=kube('/api/v1/namespaces/default/serviceaccounts/'+sa+'/token',{'apiVersion':'authentication.k8s.io/v1','kind':'TokenRequest','spec':{'audiences':['agentteams-controller'],'expirationSeconds':600}})
  assert code==201,'TokenRequest failed';token=issued['status']['token'];secret.append(token)
  claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'==='))
  uid=claims['kubernetes.io']['serviceaccount']['uid']
  check(name+'/token-uid-matches-real-sa',uid==s['metadata']['uid'])
  rec('actual_sa_tokenrequest_identity',worker=name,worker_uid=w['metadata']['uid'],worker_state=w['spec'].get('state'),container_managed=w['spec'].get('containerManaged'),team=team,team_uid=t['metadata']['uid'],membership_role=role,sa_name=sa,sa_uid=s['metadata']['uid'],sa_labels=s['metadata']['labels'],claim_sa_uid=uid,subject=claims.get('sub'),audience=claims.get('aud'),expiration=issued['status'].get('expirationTimestamp'),token_source='Kubernetes TokenRequest against Controller-generated existing SA; token never persisted')
  review_code,review=kube('/apis/authentication.k8s.io/v1/tokenreviews',{'apiVersion':'authentication.k8s.io/v1','kind':'TokenReview','spec':{'token':token,'audiences':['agentteams-controller']}})
  st=review.get('status',{});rec('safe_tokenreview_status',worker=name,http_status=review_code,authenticated=st.get('authenticated'),username=st.get('user',{}).get('username'),error=st.get('error'))
  check(name+'/tokenreview-authenticated',st.get('authenticated') is True)
  own=urllib.parse.urlencode({'team':team});other=urllib.parse.urlencode({'team':next(x['team'] for x in C['refs'] if x['team']!=team)})
  for action in ['tasks/'+C['task_id'],'workflow','workflow?format=mermaid']:
   base='/api/v1/projects/'+C['project_id']+'/'+action
   sep='&' if '?' in base else '?'
   for label,suffix,expected in [('own',sep+own,200),('other',sep+other,404),('unqualified','',200)]:
    code,v=http('http://127.0.0.1:8090',base+suffix,token)
    rec('scoped_controller_http',worker=name,team=team,scope=label,path=base+suffix,status=code,response=v)
    check(name+'/'+action+'/'+label,code==expected)
    if label in ('own','unqualified') and isinstance(v,dict):
     if action.startswith('tasks/'):check(name+'/'+action+'/'+label+'/correct-meta',v.get('summary')=='owned-by:'+team)
     else:check(name+'/'+action+'/'+label+'/correct-team',v.get('team_id')==team)
 after=hashes();rec('minio_hashes_after',objects=after);check('all-fixture-hashes-unchanged',before==after)
except Exception as exc:R['error']=str(exc)
R['exit_code']=0 if not R.get('error') and all(c['passed'] for c in R['checks']) else 1
text=json.dumps(R,ensure_ascii=False,indent=2)
for value in secret:text=text.replace(value,'[REDACTED]')
print(text);raise SystemExit(R['exit_code'])
