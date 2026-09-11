"""Three rounds of read-only Controller/Docker query wall-time observation."""
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('live', ROOT / 'scripts/controller-live-validation.py')
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)  # Reads own Controller tokens into memory only.
STAMP = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
PATH = ROOT / 'evidence' / ('control-observation-latency-' + STAMP + '.json')


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def duration(start_ns):
    return round((time.perf_counter_ns() - start_ns) / 1_000_000, 6)


def controller(instance):
    port = 28090 if instance == 'a' else 38090
    path = '/api/v1/workers'
    request = urllib.request.Request('http://127.0.0.1:' + str(port) + path,
                                    headers={'Authorization': 'Bearer ' + live.TOKENS[instance]}, method='GET')
    started = utc()
    start_ns = time.perf_counter_ns()
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read()
        elapsed_ms = duration(start_ns)
        ended = utc()
        status = response.status
        date_header = response.headers.get('Date')
    parsed = json.loads(raw)
    items = parsed if isinstance(parsed, list) else parsed.get('workers', parsed.get('items'))
    if not isinstance(items, list):
        raise RuntimeError('Unexpected Worker list response shape; no fabricated count')
    fields = ('name', 'phase', 'state', 'runtime', 'containerState', 'containerManaged')
    return {'kind': 'controller-workers', 'instance': instance, 'method': 'GET', 'path': path,
            'started_at_utc': started, 'completed_at_utc': ended, 'elapsed_ms': elapsed_ms,
            'completion_definition': 'urllib response body fully read into the host Python process; excludes JSON decode',
            'status': status, 'http_date_header': date_header,
            'body_bytes': len(raw), 'body_sha256': digest(raw), 'worker_count': len(items),
            'safe_summary': [{k: item.get(k) for k in fields if k in item} for item in items]}


def docker_stats(containers):
    command = ['docker', 'stats', '--no-stream', '--format', '{{json .}}', *containers]
    started = utc()
    start_ns = time.perf_counter_ns()
    process = subprocess.run(command, capture_output=True, timeout=20)
    elapsed_ms = duration(start_ns)
    ended = utc()
    if process.returncode:
        raise RuntimeError('Read-only docker stats failed; details suppressed')
    rows = [json.loads(line) for line in process.stdout.decode('utf-8').splitlines()]
    fields = ('Name', 'ID', 'CPUPerc', 'MemUsage', 'MemPerc', 'PIDs', 'NetIO', 'BlockIO')
    return {'kind': 'docker-stats', 'started_at_utc': started, 'completed_at_utc': ended,
            'elapsed_ms': elapsed_ms, 'exit_code': process.returncode, 'container_count': len(rows),
            'completion_definition': 'docker stats child process exited and full stdout captured; excludes JSON decode',
            'stdout_bytes': len(process.stdout), 'stdout_sha256': digest(process.stdout),
            'safe_summary': [{k: row.get(k) for k in fields if k in row} for row in rows]}


inventory = subprocess.run(['docker', 'ps', '--format', '{{json .}}'], capture_output=True, text=True,
                           encoding='utf-8', timeout=15, check=True)
containers = sorted(item['Names'] for line in inventory.stdout.splitlines()
                    if (item := json.loads(line))['Names'].startswith(('rv-a-', 'rv-b-')))
assert 'rv-a-controller' in containers and 'rv-b-controller' in containers
output = {'started_at_utc': utc(), 'round_limit': 3, 'fixed_container_selection': containers,
          'boundary': 'Read-only native query and host collection wall time; no resource transition, model request, product collector, state-to-database or browser visibility measurement',
          'preparation_excluded': ['own Controller tokens read from the two existing containers', 'one Docker running-container inventory'],
          'clock': 'UTC wall timestamps for trace correlation; elapsed uses perf_counter_ns monotonic timer',
          'records': []}
for round_id in range(1, 4):
    for result in (controller('a'), controller('b'), docker_stats(containers)):
        output['records'].append({'round': round_id, **result})
    PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
output['completed_at_utc'] = utc()
output['summary'] = []
for label, kind, instance in [('Controller a workers', 'controller-workers', 'a'),
                              ('Controller b workers', 'controller-workers', 'b'),
                              ('Docker stats all selected', 'docker-stats', None)]:
    values = [r['elapsed_ms'] for r in output['records'] if r['kind'] == kind and r.get('instance') == instance]
    output['summary'].append({'query': label, 'count': len(values), 'elapsed_ms': values,
                              'min_ms': min(values), 'median_ms': statistics.median(values), 'max_ms': max(values)})
assert all(r.get('status', 200) == 200 and r.get('exit_code', 0) == 0 for r in output['records'])
PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'evidence': str(PATH), 'containers': len(containers), 'summary': output['summary']}, indent=2))
