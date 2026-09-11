"""Read active Envoy AI proxy path-related fields only, excluding secrets and headers."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
code=r'''
import urllib.request,urllib.parse,json,datetime,re
with urllib.request.urlopen('http://127.0.0.1:15000/config_dump',timeout=5) as r: data=json.load(r)
out={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'path_fields':[],'ai_proxy_config_shapes':[]}
safe={'prefix_rewrite','regex_rewrite','path_rewrite_policy','host_rewrite_literal','baseUrl','base_url','apiPrefix','api_prefix','openaiCustomUrl','openaiCustomModelMapping','apiVersion','api_version','type','providerType','provider_type'}
blocked=re.compile(r'token|secret|credential|password|api.?key|authorization|header',re.I)
def clean(value):
 if not isinstance(value,str): return value
 if value.startswith(('http://','https://')):
  u=urllib.parse.urlsplit(value);return urllib.parse.urlunsplit((u.scheme,u.hostname+(':'+str(u.port) if u.port else ''),u.path,'',''))
 return value
def walk(v,path='root'):
 if isinstance(v,dict):
  for k,x in v.items():
   if blocked.search(k): continue
   p=path+'.'+k
   if k in safe and isinstance(x,(str,int,bool)):
    out['path_fields'].append({'json_path':p,'value':clean(x)})
   if isinstance(x,str) and 'ai-proxy' in x and len(x)<300:
    out['ai_proxy_config_shapes'].append({'json_path':p,'value':clean(x)})
   if isinstance(x,str) and x.lstrip().startswith('{'):
    try: parsed=json.loads(x)
    except ValueError: parsed=None
    if parsed is not None:
     out['ai_proxy_config_shapes'].append({'json_path':p,'json_top_level_keys':list(parsed) if isinstance(parsed,dict) else []})
     walk(parsed,p+'[json]')
   else: walk(x,p)
 elif isinstance(v,list):
  for i,x in enumerate(v): walk(x,path+'['+str(i)+']')
walk(data)
print(json.dumps(out))
'''
p=subprocess.run(['docker','exec','-i','rv-c-controller','python3','-'],input=code,capture_output=True,text=True,encoding='utf-8',timeout=15)
if p.returncode: raise SystemExit('Readonly plugin inspection failed; no raw output disclosed')
out=json.loads(p.stdout)
(ROOT/'evidence/provider-url-plugin-fields.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
