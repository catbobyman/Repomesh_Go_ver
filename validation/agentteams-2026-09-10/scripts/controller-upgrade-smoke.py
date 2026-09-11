"""Bounded c-only metadata lifecycle/CAS upgrade smoke, no model work."""
import datetime,hashlib,json,secrets,subprocess,urllib.request,urllib.error,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
run=secrets.token_hex(5); project='upgrade-smoke-'+run; task='upgrade-task-'+run
key='shared/projects/'+project+'/meta.json'; tk='shared/tasks/'+task+'/meta.json'
out=ROOT/'evidence'/('controller-upgrade-smoke-'+run+'.json')
R={'run_id':run,'project_id':project,'task_id':task,'scope':'Admin HTTP plus directly seeded global metadata, not business task creation or Worker authorization','records':[],'checks':[]}
tokens=[];start=time.monotonic()
def save():
 s=json.dumps(R,ensure_ascii=False,indent=2)
 for t in tokens:s=s.replace(t,'[REDACTED]')
 out.write_text(s,encoding='utf8')
def rec(kind,**kw):R['records'].append(dict(kind=kind,time=datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw));save()
def check(name,ok):R['checks'].append({'name':name,'passed':bool(ok)});save();assert ok,name
def docker(*args,data=None):
 assert time.monotonic()-start<180,'execution bound'
 p=subprocess.run(['docker',*args],input=data,capture_output=True,timeout=30)
 if p.returncode:raise RuntimeError('Docker subprocess failed: '+str(args[:3]))
 return p.stdout
def ident(container):
 d=json.loads(docker('inspect',container))[0]
 return dict(container=container,id=d['Id'],image=d['Image'],started_at=d['State']['StartedAt'],running=d['State']['Running'])
def api(method,action,body=None,token=None):
 path='/api/v1/projects/'+project+'/'+action
 req=urllib.request.Request('http://127.0.0.1:48090'+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers={'Authorization':'Bearer '+(tokens[0] if token is None else token),'Content-Type':'application/json'})
 try:r=urllib.request.urlopen(req,timeout=20)
 except urllib.error.HTTPError as e:r=e
 val=json.loads(r.read());rec('controller_http',method=method,path=path,request=body,identity='c admin' if token is None else 'actual a admin replay to c',status=r.code,response=val)
 return r.code,val
def put(k,value):
 data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode();local='/tmp/'+project+'/'+k
 docker('exec','-i','rv-c-controller','python3','-c','import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(sys.stdin.buffer.read())',local,data=data)
 docker('exec','rv-c-controller','mc','cp',local,'agentteams/rv-c-storage/'+k)
 rec('single_part_fixture_mc_cp',key=k,content=value,sha256=hashlib.sha256(data).hexdigest())
def read(label,k=key):
 data=docker('exec','rv-c-controller','mc','cat','agentteams/rv-c-storage/'+k)
 stat=json.loads(docker('exec','rv-c-controller','mc','stat','--json','agentteams/rv-c-storage/'+k))
 rec('independent_mc_readback',label=label,key=k,sha256=hashlib.sha256(data).hexdigest(),md5=hashlib.md5(data).hexdigest(),etag=stat.get('etag'),content=json.loads(data))
 return data,json.loads(data),stat.get('etag')
CAS=r'''
import sys,json,pathlib,urllib.request,urllib.error,urllib.parse,datetime,hashlib,hmac
spec=json.load(sys.stdin);cfg=json.loads((pathlib.Path.home()/'.mc/config.json').read_text())['aliases']['agentteams']
endpoint=urllib.parse.urlsplit(cfg['url']);uri='/rv-c-storage/'+spec['key'];region='us-east-1'
def request(body,etag):
 now=datetime.datetime.now(datetime.timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%SZ');day=stamp[:8];payload=hashlib.sha256(body).hexdigest()
 headers={'host':endpoint.netloc,'if-match':'"'+etag.strip('"')+'"','x-amz-content-sha256':payload,'x-amz-date':stamp}
 names=';'.join(sorted(headers));canonical='PUT\n'+uri+'\n\n'+''.join(k+':'+headers[k]+'\n' for k in sorted(headers))+'\n'+names+'\n'+payload
 scope=day+'/'+region+'/s3/aws4_request';string='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
 def sign(k,v):return hmac.new(k,v.encode(),hashlib.sha256).digest()
 signing=sign(sign(sign(sign(('AWS4'+cfg['secretKey']).encode(),day),region),'s3'),'aws4_request')
 headers['Authorization']='AWS4-HMAC-SHA256 Credential='+cfg['accessKey']+'/'+scope+', SignedHeaders='+names+', Signature='+hmac.new(signing,string.encode(),hashlib.sha256).hexdigest()
 req=urllib.request.Request(cfg['url'].rstrip('/')+uri,data=body,headers=headers,method='PUT')
 try:r=urllib.request.urlopen(req,timeout=20)
 except urllib.error.HTTPError as e:r=e
 response=r.read().decode();return {'status':r.code,'response_etag':r.headers.get('ETag'),'error_code':'PreconditionFailed' if '<Code>PreconditionFailed</Code>' in response else None}
fresh=json.dumps(spec['fresh'],ensure_ascii=False).encode();stale=json.dumps(spec['stale'],ensure_ascii=False).encode()
print(json.dumps({'key':spec['key'],'condition_etag':spec['etag'],'fresh_sha256':hashlib.sha256(fresh).hexdigest(),'stale_sha256':hashlib.sha256(stale).hexdigest(),'fresh':request(fresh,spec['etag']),'stale':request(stale,spec['etag'])}))
'''
try:
 before=ident('rv-c-controller');rec('controller_before',**before)
 tokens.append(docker('exec','rv-c-controller','cat','/var/run/agentteams/cli-token').decode().strip())
 check('unique-project-absent',api('GET','workflow')[0]==404)
 put(key,dict(project_id=project,title='Upgrade smoke '+run,status='active',plan_type='dag',tasks=[dict(task_id=task,title='Only fixture task',status='planned',depends_on=[])],source_room_id=''))
 put(tk,dict(project_id=project,task_id=task,status='planned',summary='metadata fixture only'))
 raw,meta,etag=read('initial');check('initial-single-part-etag-is-content-md5',etag==hashlib.md5(raw).hexdigest())
 check('pause200',api('POST','pause',{'reason':'upgrade fixture '+run})[0]==200)
 paused,meta,_=read('after-pause');check('pause-persisted',meta['status']=='paused' and paused!=raw)
 plan={'tasks':[dict(taskId=task,title='Replanned fixture',status='planned',dependsOn=[])]}
 check('paused-replan409',api('POST','replan',plan)[0]==409)
 rejected,_,_=read('after-rejected-replan');check('rejected-replan-no-write',rejected==paused)
 check('resume200',api('POST','resume',{})[0]==200)
 _,meta,_=read('after-resume');check('resume-persisted',meta['status']=='active')
 check('active-replan200',api('POST','replan',plan)[0]==200)
 _,meta,_=read('after-active-replan');check('replan-persisted',meta['tasks'][0]['title']=='Replanned fixture')
 check('cancel200',api('POST','tasks/'+task+'/cancel',{'reason':'upgrade cancel '+run})[0]==200)
 cancelled,meta,etag=read('after-cancel-project');_,taskmeta,_=read('after-cancel-task',tk)
 check('cancel-two-objects-persisted',meta['tasks'][0]['status']=='cancelled' and taskmeta['status']=='cancelled' and taskmeta['cancel_reason']=='upgrade cancel '+run)
 check('inspection-cancelled200',api('GET','tasks/'+task)[1].get('status')=='cancelled')
 fresh=dict(meta,title='CAS fresh '+run);stale=dict(meta,title='CAS stale must not win '+run)
 cas=json.loads(docker('exec','-i','rv-c-controller','python3','-c',CAS,data=json.dumps(dict(key=key,etag=etag,fresh=fresh,stale=stale)).encode()))
 rec('real_s3_conditional_put',**cas);check('fresh-if-match200',cas['fresh']['status']==200);check('stale-if-match412',cas['stale']['status']==412 and cas['stale']['error_code']=='PreconditionFailed')
 final,meta,_=read('after-fresh-and-stale-CAS');check('fresh-wins-stale-no-overwrite',meta['title']=='CAS fresh '+run and hashlib.sha256(final).hexdigest()==cas['fresh_sha256'])
 rec('wrong-instance-source',**ident('rv-a-controller'))
 old=docker('exec','rv-a-controller','cat','/var/run/agentteams/cli-token').decode().strip();tokens.append(old)
 check('a-token-c-task-inspection401',api('GET','tasks/'+task,token=old)[0]==401)
 check('c-token-c-task-inspection200',api('GET','tasks/'+task)[0]==200)
 R['completed']=True
except Exception as exc:R['error']=str(exc)
finally:
 try:
  after=ident('rv-c-controller');rec('controller_after',**after);check('controller-unchanged-running',before==after and after['running'])
  rec('retained_fixture_inventory',project_key=key,task_key=tk,history_prefix='shared/projects/'+project+'/history/',no_new_cr=True,no_runtime_created=True)
 except Exception as exc:R['finally_error']=str(exc)
 R['exit_code']=0 if R.get('completed') and not R.get('finally_error') else 1;R['elapsed_seconds']=round(time.monotonic()-start,3);save()
 print(json.dumps({'evidence':str(out),'exit_code':R['exit_code'],'checks':len(R['checks']),'error':R.get('error')}))
raise SystemExit(R['exit_code'])
