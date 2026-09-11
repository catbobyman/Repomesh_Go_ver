"""Prepare upstream Makefile prerequisites in an isolated build context."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
source = root / 'upstream'
target = root / 'runtime' / 'build-source'
if target.exists():
    raise SystemExit('Build context already exists; refusing to overwrite it.')
shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
shutil.copytree(target / 'manager' / 'agent', target / 'agentteams-controller' / 'agent')
commit = subprocess.check_output(['git', '-c', f'safe.directory={source.as_posix()}', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
manifest = {'commit': commit, 'context': str(target), 'makefile_prerequisite': 'manager/agent copied to agentteams-controller/agent', 'files': {}}
for name in ['agentteams-controller/Dockerfile', 'agentteams-controller/Dockerfile.embedded', 'manager/Dockerfile.qwenpaw', 'qwenpaw/Dockerfile']:
    manifest['files'][name] = hashlib.sha256((target / name).read_bytes()).hexdigest()
(root / 'evidence' / 'build-context.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps({'commit': commit, 'context': str(target)}))
