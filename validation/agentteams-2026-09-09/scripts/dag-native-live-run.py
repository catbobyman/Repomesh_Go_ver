"""One dedicated real-service DAG run; persists private config before calling tools."""
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('matrix_live', ROOT / 'scripts/matrix-live-validation.py')
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)
a = json.loads((ROOT / 'private/matrix-live-state.json').read_text())['instances']['a']
run_id = secrets.token_hex(5)
room = matrix.ok('a', 'POST', '/_matrix/client/v3/createRoom', a['users']['alice']['token'], {
    'preset': 'private_chat', 'name': 'DAG native validation ' + run_id,
    'invite': [a['users']['bob']['user_id']]})['room_id']
matrix.ok('a', 'POST', '/_matrix/client/v3/join/' + matrix.q(room), a['users']['bob']['token'], {})
config = {'run_id': run_id, 'room': room, 'token': a['users']['bob']['token'], 'user_id': a['users']['bob']['user_id'],
          'module_path': '/tmp/dag-native-mcp-' + run_id}
(ROOT / ('private/dag-native-live-' + run_id + '.json')).write_text(json.dumps(config, indent=2))
for source, target in [(ROOT / 'upstream/plugins/teamharness/mcp', config['module_path']),
                       (ROOT / 'scripts/dag-native-live-container.py', '/tmp/dag-native-live-' + run_id + '.py')]:
    p = subprocess.run(['docker', 'cp', str(source), 'rv-a-controller:' + target], capture_output=True, text=True)
    if p.returncode:
        raise SystemExit('Dedicated source copy failed; no experiment launched')
p = subprocess.run(['docker', 'exec', '-i', 'rv-a-controller', 'python3', '/tmp/dag-native-live-' + run_id + '.py'],
                   input=json.dumps(config), capture_output=True, text=True, encoding='utf-8', timeout=300)
output = p.stdout.replace(config['token'], '[REDACTED]')
path = ROOT / ('evidence/dag-native-live-' + run_id + '.json')
try:
    result = json.loads(output)
except ValueError:
    path.with_suffix('.error.txt').write_text((p.stderr + output).replace(config['token'], '[REDACTED]'), encoding='utf-8')
    raise SystemExit('Run did not return JSON; redacted error preserved')
path.write_text(output, encoding='utf-8')
print(json.dumps({'evidence': str(path), 'exit_code': p.returncode, 'checks': len(result['checks']),
                  'failed': [c for c in result['checks'] if not c['passed']], 'error': result['error'],
                  'stages': len(result['stages']), 'trace_entries': len(result['trace'])}, ensure_ascii=False))
sys.exit(p.returncode)
