"""Read only allowlisted config fields and installed source; no secrets emitted."""
import json
from pathlib import Path
import subprocess
import hashlib

ROOT = Path(__file__).resolve().parents[1]
code = r'''
import hashlib,importlib.metadata,json,pathlib
root=pathlib.Path('/root/manager-workspace/.qwenpaw')
site=pathlib.Path('/opt/venv/qwenpaw/lib/python3.11/site-packages')
result={'qwenpaw_version':importlib.metadata.version('qwenpaw'),'configs':[],'sources':[]}
for rel in ['config.json','workspaces/default/agent.json']:
 d=json.loads((root/rel).read_text()); ch=d.get('channels',{})
 result['configs'].append({'path':str(root/rel),'channel_keys':list(ch),'matrix':{'present':'matrix' in ch,'enabled':ch.get('matrix',{}).get('enabled')},'agentteams_matrix':{'present':'agentteams_matrix' in ch,'enabled':ch.get('agentteams_matrix',{}).get('enabled')}})
for path,ranges in [(site/'copaw_worker/bridge.py',[(420,450),(528,553)]),
 (pathlib.Path('/opt/agentteams/scripts/init/start-qwenpaw-manager.sh'),[(79,83),(298,316)]),
 (site/'qwenpaw/app/channels/registry.py',[(18,36),(122,134)]),
 (site/'qwenpaw/app/channels/manager.py',[(131,161)]),
 (root/'plugins/agentteams-matrix-channel/plugin.py',[(1,12)]),
 (root/'plugins/agentteams-matrix-channel/agentteams_matrix/channel.py',[(81,86),(345,348)])]:
 data=path.read_bytes(); lines=data.decode().splitlines()
 result['sources'].append({'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),
  'excerpts':[{'line':i,'text':lines[i-1]} for start,end in ranges for i in range(start,min(end,len(lines))+1)]})
result['manifest']=json.loads((root/'plugins/agentteams-matrix-channel/plugin.json').read_text())
print(json.dumps(result,ensure_ascii=False))
'''
response = subprocess.run(["docker", "exec", "-i", "rv-a-manager", "/opt/venv/qwenpaw/bin/python", "-"],
                          input=code, capture_output=True, text=True, encoding="utf-8", timeout=30)
if response.returncode:
    raise SystemExit("Readonly source query failed; output suppressed")
result = json.loads(response.stdout)
logs = subprocess.run(["docker", "logs", "rv-a-manager"], capture_output=True, text=True, encoding="utf-8", timeout=30)
result["plugin_log_lines"] = [line for line in (logs.stdout + logs.stderr).splitlines()
    if "registered channel" in line or "Loaded plugin: agentteams-matrix-channel" in line or "Installed plugin: agentteams-matrix-channel" in line]
for entry in result["sources"]:
    local = None
    if entry["path"].endswith("copaw_worker/bridge.py"):
        local = ROOT / "upstream/copaw/src/copaw_worker/bridge.py"
    elif entry["path"].endswith("start-qwenpaw-manager.sh"):
        local = ROOT / "upstream/manager/scripts/init/start-qwenpaw-manager.sh"
    if local:
        entry["matches_locked_upstream_sha256"] = hashlib.sha256(local.read_bytes()).hexdigest() == entry["sha256"]
(ROOT / "evidence/manager-model-live-channel-selection.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"qwenpaw_version":result["qwenpaw_version"],"configs":result["configs"],"plugin_log_lines":result["plugin_log_lines"],
                  "upstream_hash_checks":[{"path":v['path'],"matches":v['matches_locked_upstream_sha256']} for v in result['sources'] if 'matches_locked_upstream_sha256' in v]},ensure_ascii=False))
