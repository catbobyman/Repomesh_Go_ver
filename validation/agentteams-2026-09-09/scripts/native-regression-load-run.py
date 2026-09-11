"""Copy existing pure Python pytest dependencies, then concurrently run official regression."""
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUN = secrets.token_hex(5)
STAGE = ROOT / 'runtime' / ('native-regression-' + RUN)
STAGE.mkdir()
DEPS = STAGE / 'deps'
DEPS.mkdir()
versions = {}
for name in ['pytest', '_pytest', 'pluggy', 'iniconfig', 'packaging', 'pygments']:
    src = Path(importlib.util.find_spec(name).origin).parent
    shutil.copytree(src, DEPS / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if name != '_pytest':
        dist = importlib.metadata.distribution(name)
        versions[name] = dist.version
        shutil.copytree(dist._path, DEPS / dist._path.name)
# pytest also distributes a top-level py.py compatibility shim outside its packages.
shutil.copyfile(importlib.util.find_spec('py').origin, DEPS / 'py.py')
assert not list(DEPS.rglob('*.pyd')) and not list(DEPS.rglob('*.so')), 'Nonportable native dependency found'
for part in ['plugins/teamharness', 'plugins/tests/teamharness']:
    shutil.copytree(ROOT / 'upstream' / part, STAGE / 'repo' / part,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copyfile(ROOT / 'scripts/native-regression-load-container.py', STAGE / 'runner.py')
hashes = {str(p.relative_to(STAGE)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in (STAGE / 'repo').rglob('*') if p.is_file()}
archive = STAGE.with_suffix('.tar')
with tarfile.open(archive, 'w') as tf:
    for part in ['deps', 'repo', 'runner.py']:
        tf.add(STAGE / part, arcname=part)
containers = {i: 'rv-' + i + '-worker-live-twin-worker' for i in ['a', 'b']}
base = '/tmp/native-regression-' + RUN
initial = {}
for key, container in containers.items():
    ins = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    initial[key] = {'id': ins['Id'], 'started_at': ins['State']['StartedAt'], 'image': ins['Image']}
    subprocess.run(['docker', 'exec', container, 'mkdir', '-p', base], check=True, capture_output=True)
    subprocess.run(['docker', 'cp', str(archive), container + ':' + base + '/input.tar'], check=True, capture_output=True)
    subprocess.run(['docker', 'exec', container, 'tar', '-xf', base + '/input.tar', '-C', base], check=True, capture_output=True)
tests = ['plugins/tests/teamharness/' + p for p in [
    'test_mcp_workspace.py', 'test_pull_project.py', 'test_trace.py', 'test_trace_integration.py',
    'adapters/qwenpaw/test_adapter.py']]
health, done = [], threading.Event()


def health_sample(instance):
    url = 'http://127.0.0.1:' + ('28090' if instance == 'a' else '38090') + '/healthz'
    while not done.is_set():
        now = time.time()
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                row = {'instance': instance, 'at_epoch': now, 'url': url, 'status': response.status,
                       'latency_seconds': time.time()-now}
        except Exception as exc:
            row = {'instance': instance, 'at_epoch': now, 'url': url, 'error_type': type(exc).__name__,
                   'latency_seconds': time.time()-now}
        health.append(row)
        done.wait(.2)


start_at = time.time() + 2


def run(instance):
    config = {'instance': instance, 'base': base, 'tests': tests, 'start_at': start_at}
    p = subprocess.run(['docker', 'exec', '-i', containers[instance], 'python', base + '/runner.py'],
                       input=json.dumps(config), capture_output=True, text=True, encoding='utf-8', timeout=135)
    path = ROOT / 'evidence' / ('native-regression-load-' + RUN + '-' + instance + '.json')
    try:
        result = json.loads(p.stdout)
    except ValueError:
        path.with_suffix('.error.txt').write_text(p.stdout + p.stderr, encoding='utf-8')
        return {'instance': instance, 'error': 'No JSON from runner', 'docker_exec_code': p.returncode}
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    for file in ['junit.xml', 'stdout.txt', 'stderr.txt']:
        copied = subprocess.run(['docker', 'cp', containers[instance] + ':' + base + '/' + file,
                        str(ROOT / 'evidence' / ('native-regression-load-' + RUN + '-' + instance + '-' + file))],
                       capture_output=True, text=True)
        if copied.returncode:
            result.setdefault('evidence_copy_errors', []).append({'file': file, 'stderr': copied.stderr})
    return result


monitors = [threading.Thread(target=health_sample, args=(i,)) for i in containers]
for m in monitors:
    m.start()
try:
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, containers))
finally:
    done.set()
    for m in monitors:
        m.join(timeout=3)
summary = {'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'run_id': RUN,
           'scope': 'Actual official upstream pytest workload inside two existing Workers; official fixtures/mock transports retained; no model or real business writes',
           'dependencies_source': 'Copied existing host pure Python packages to isolated /tmp PYTHONPATH; no download or production venv install',
           'versions': versions, 'source_hashes': hashes, 'before_containers': initial, 'health_samples': health,
           'results': [{k:v for k,v in r.items() if k not in ['samples', 'stdout', 'stderr']} for r in results]}
path = ROOT / 'evidence' / ('native-regression-load-' + RUN + '-summary.json')
path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps({'run_id': RUN, 'summary': str(path), 'health_samples': len(health),
                  'results': [{'instance': r['instance'], 'exit_code': r.get('exit_code'),
                               'elapsed_seconds': r.get('elapsed_seconds'), 'junit': {k:v for k,v in (r.get('junit') or {}).items() if k != 'cases'},
                               'error': r.get('error')} for r in results]}))
