"""Read only safe Higress route path/rewrite fields; credentials remain in container."""
import datetime as dt
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
code = r'''
import http.cookiejar,json,os,urllib.request,urllib.error
base='http://127.0.0.1:8001'
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
body=json.dumps({'username':os.environ['AGENTTEAMS_ADMIN_USER'],'password':os.environ['AGENTTEAMS_ADMIN_PASSWORD']}).encode()
with opener.open(urllib.request.Request(base+'/session/login',data=body,headers={'Content-Type':'application/json'}),timeout=5) as r:
 login_status=r.status
def get(path):
 with opener.open(base+path,timeout=5) as r: return r.status,json.load(r)
out={'login_status':login_status,'routes':[],'envoy_routes':[]}
status,data=get('/v1/ai/routes')
out['route_list_status']=status
allow={'name','pathPredicate','path','pathPrefix','rewrite','pathRewrite','rewriteConfig','regexRewrite','prefixRewrite','prefix_rewrite','regex_rewrite','matchType','matchValue','caseSensitive','replacement','pattern','uri','uriRegex','match','route','prefix','safe_regex','regex'}
def pathfields(obj):
 if isinstance(obj,list): return [pathfields(x) for x in obj]
 if isinstance(obj,dict): return {k:pathfields(v) for k,v in obj.items() if k in allow or 'rewrite' in k.lower()}
 if isinstance(obj,(str,int,bool)) or obj is None: return obj
 return None
for entry in data.get('data',[]):
 name=entry.get('name')
 if not name: continue
 sc,detail=get('/v1/ai/routes/'+urllib.parse.quote(name,safe=''))
 value=detail.get('data',detail)
 out['routes'].append({'name':name,'status':sc,'provider_names':[u.get('provider') for u in value.get('upstreams',[])],
                       'top_level_keys':list(value),'safe_path_rewrite_fields':pathfields(value)})
# Envoy live routing gives stronger rewrite evidence than route name alone.
try:
 with urllib.request.urlopen('http://127.0.0.1:15000/config_dump',timeout=5) as r:
  out['envoy_config_dump_status']=r.status; dump=json.load(r)
 def walk(value):
  if isinstance(value,dict):
   if 'match' in value and 'route' in value:
    match=value['match']; route=value['route']
    if isinstance(match,dict) and isinstance(route,dict):
     out['envoy_routes'].append({'match':pathfields(match),'route':pathfields(route)})
   for v in value.values(): walk(v)
  elif isinstance(value,list):
   for v in value: walk(v)
 walk(dump)
except Exception as e:
 out['envoy_config_dump_error_type']=type(e).__name__
print(json.dumps(out))
'''
p = subprocess.run(['docker','exec','-i','rv-c-controller','python3','-'],input=code,
                   capture_output=True,text=True,encoding='utf-8',timeout=30)
if p.returncode:
    raise SystemExit('Readonly route query failed; output suppressed to protect auth material')
result={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Console session login plus GET-only route/admin reads; no model/data-plane inference call or config changes',
        'result':json.loads(p.stdout)}
path=ROOT/'evidence/provider-url-readonly.json'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
