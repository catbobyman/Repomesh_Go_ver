"""One bounded wall-clock observation through the native five-minute auth cache."""
import datetime,json,subprocess,time,urllib.request,urllib.error,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];state=json.loads((ROOT/'private/worker-identity-recreate-state.json').read_text());path=ROOT/'evidence/worker-identity-recreate-live.json';e=json.loads(path.read_text());name=state['name']
first=next(r for r in e['records'] if r['kind']=='controller_http' and r.get('label')=='old_before_delete')
anchor=datetime.datetime.fromisoformat(first['time']);end=anchor+datetime.timedelta(seconds=330)
def append(record):
 e=json.loads(path.read_text());e['records'].append(record);path.write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding='utf8')
def request(label,token,method='GET',suffix='status'):
 now=datetime.datetime.now(datetime.timezone.utc);r=urllib.request.Request('http://127.0.0.1:28090/api/v1/workers/'+name+'/'+suffix,data=b'{}' if method=='POST' else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
 try:p=urllib.request.urlopen(r,timeout=10)
 except urllib.error.HTTPError as x:p=x
 raw=p.read();v=json.loads(raw) if raw else None
 result=dict(kind='cache_window_http',time=now.isoformat(),first_observed_success=anchor.isoformat(),elapsed_seconds=round((now-anchor).total_seconds(),3),label=label,method=method,route=suffix,status=p.code,response={k:v[k] for k in ('name','phase','containerState','message') if k in v} if isinstance(v,dict) else v)
 append(result);print(label,suffix,result['elapsed_seconds'],p.code,flush=True)
while True:
 request('old_snapshot',state['old']['sa_token'])
 now=datetime.datetime.now(datetime.timezone.utc)
 if now>=end:break
 time.sleep(min(30,max(0,(end-now).total_seconds())))
request('old_snapshot_after_window',state['old']['sa_token'],'POST','ready')
request('new_snapshot_after_window',state['new']['sa_token'])
spec=importlib.util.spec_from_file_location('matrix',ROOT/'scripts/matrix-live-validation.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
status,who=m.request('a','GET','/_matrix/client/v3/account/whoami',state['old']['matrix_token']);append(dict(kind='old_matrix_after_cache_window',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=status,user_id=who.get('user_id'),error_code=who.get('errcode')))
v=state['old'];c={k:v[k] for k in ('access_key','secret_key','session_token','bucket')};c.update(method='GET',key=state['object_key'])
p=subprocess.run(['docker','exec','-i','rv-a-controller','python3','/tmp/identity-storage-snapshot.py'],input=json.dumps(c),capture_output=True,text=True,encoding='utf8',timeout=30);assert p.returncode==0
append(dict(kind='old_storage_after_cache_window',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),result=json.loads(p.stdout)))
print('completed TTL+30 window',flush=True)
