"""Check this run's Markdown local links, JSON syntax, and accidental known-secret copies."""
import json,re
from pathlib import Path
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
secrets=set()
secret_name=re.compile(r'password|(?:^|_)token$|api[_-]?key|gateway_key|(?:^|_)secret$',re.I)
def gather(obj,key=''):
    if isinstance(obj,dict):
        for k,v in obj.items():gather(v,k)
    elif isinstance(obj,list):
        for v in obj:gather(v,key)
    elif isinstance(obj,str):
        if secret_name.search(key) and len(obj)>=16:secrets.add(obj)
        if '=' in obj:
            k,v=obj.split('=',1)
            if secret_name.search(k) and len(v)>=16:secrets.add(v)
for path in (ROOT/'private').glob('*'):
    if path.suffix=='.json':
        try:gather(json.loads(path.read_text(encoding='utf-8-sig')))
        except (ValueError,OSError):pass
    elif path.suffix=='.env':
        for line in path.read_text(encoding='utf-8-sig').splitlines():gather(line)
out={'markdown_files':0,'json_files':0,'broken_links':[],'invalid_json':[],'known_secret_files':[]}
for folder in ('scripts','reports','evidence'):
    for path in (ROOT/folder).rglob('*'):
        if not path.is_file() or path.suffix.lower() not in ('.md','.json','.py','.go','.ps1','.patch'):continue
        raw=path.read_text(encoding='utf-8-sig',errors='replace')
        if any(secret in raw for secret in secrets):out['known_secret_files'].append(str(path.relative_to(ROOT)))
        if path.suffix=='.json':
            out['json_files']+=1
            try:json.loads(raw)
            except ValueError:out['invalid_json'].append(str(path.relative_to(ROOT)))
        if path.suffix=='.md':
            out['markdown_files']+=1
            for target in re.findall(r'\]\(([^)]+)\)',raw):
                target=target.strip('<>').split('#',1)[0]
                if not target or re.match(r'[a-zA-Z]+://',target) or target.startswith('mailto:'):continue
                resolved=path.parent/unquote(target)
                if not resolved.exists():out['broken_links'].append({'file':str(path.relative_to(ROOT)),'target':target})
out['passed']=not any(out[k] for k in ('broken_links','invalid_json','known_secret_files'))
(ROOT/'evidence/artifact-check.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if out['passed'] else 1)
