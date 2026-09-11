"""Run unchanged official pytest suite only inside this run's private /tmp tree."""
import datetime as dt
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

C = json.load(sys.stdin)
BASE = Path(C['base'])
CG = Path('/sys/fs/cgroup')


def usage():
    out = {'at_epoch': time.time()}
    if (CG / 'cpuacct/cpuacct.usage').is_file():
        out['cgroup_version'] = 1
        out['cpu.stat'] = {'usage_usec': int((CG / 'cpuacct/cpuacct.usage').read_text()) / 1000}
        for name, path in [('memory.current', 'memory/memory.usage_in_bytes'),
                           ('memory.peak', 'memory/memory.max_usage_in_bytes'),
                           ('memory.failcnt', 'memory/memory.failcnt')]:
            out[name] = int((CG / path).read_text())
        out['memory.stat'] = {k: int(v) for k, v in (line.split() for line in (CG / 'memory/memory.stat').read_text().splitlines())}
        return out
    out['cgroup_version'] = 2
    for name in ['cpu.stat', 'memory.current', 'memory.peak', 'memory.events', 'memory.stat']:
        p = CG / name
        if p.is_file():
            raw = p.read_text()
            out[name] = ({k: int(v) for k, v in (line.split() for line in raw.splitlines())}
                         if ' ' in raw else int(raw))
    return out


def tree_size():
    paths = [p for p in BASE.rglob('*') if p.is_file() and not p.is_symlink()]
    return {'files': len(paths), 'apparent_bytes': sum(p.stat().st_size for p in paths),
            'allocated_bytes': sum(p.stat().st_blocks * 512 for p in paths)}


samples, stop = [], threading.Event()


def sampler():
    while not stop.is_set():
        samples.append(usage())
        stop.wait(.1)


for p in ['home', 'tmp', 'cache']:
    (BASE / p).mkdir(exist_ok=True)
env = {'PATH': '/opt/venv/qwenpaw/bin:/usr/local/bin:/usr/bin:/bin', 'HOME': str(BASE / 'home'),
       'TMPDIR': str(BASE / 'tmp'), 'XDG_CACHE_HOME': str(BASE / 'cache'),
       'PYTHONPATH': str(BASE / 'deps'), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
       'PYTHONPYCACHEPREFIX': str(BASE / 'pycache'), 'LANG': 'C.UTF-8',
       'TEAMHARNESS_SHARED_DIR': str(BASE / 'unbound-shared')}
cmd = ['/opt/venv/qwenpaw/bin/python', '-m', 'pytest', '-q',
       '--basetemp=' + str(BASE / 'pytest-tmp'), '-o', 'cache_dir=' + str(BASE / 'pytest-cache'),
       '--junitxml=' + str(BASE / 'junit.xml'), *C['tests']]
before = {'tree': tree_size(), 'cgroup': usage()}
while time.time() < C['start_at']:
    time.sleep(min(.1, C['start_at'] - time.time()))
monitor = threading.Thread(target=sampler)
monitor.start()
p = None
timed_out = False
start = time.time()
try:
    with (BASE / 'stdout.txt').open('w') as stdout, (BASE / 'stderr.txt').open('w') as stderr:
        p = subprocess.Popen(cmd, cwd=BASE / 'repo', env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = p.wait(timeout=120)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(p.pid, signal.SIGTERM)
            try:
                code = p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                code = p.wait(timeout=3)
finally:
    finish = time.time()
    stop.set()
    monitor.join(timeout=2)
    if p is not None and p.poll() is None:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait(timeout=3)
after = {'tree': tree_size(), 'cgroup': usage()}
r = resource.getrusage(resource.RUSAGE_CHILDREN)
junit = None
if (BASE / 'junit.xml').exists():
    doc = ET.parse(BASE / 'junit.xml').getroot()
    suites = [doc] if doc.tag == 'testsuite' else list(doc.iter('testsuite'))
    junit = {'tests': sum(int(s.get('tests', 0)) for s in suites),
             'failures': sum(int(s.get('failures', 0)) for s in suites),
             'errors': sum(int(s.get('errors', 0)) for s in suites),
             'skipped': sum(int(s.get('skipped', 0)) for s in suites),
             'cases': [{'name': t.get('name'), 'classname': t.get('classname'), 'time': t.get('time'),
                        'failure': t.find('failure') is not None, 'error': t.find('error') is not None,
                        'skipped': t.find('skipped') is not None} for t in doc.iter('testcase')]}
out = {'instance': C['instance'], 'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
       'base': str(BASE), 'command': cmd, 'clean_environment_keys': sorted(env),
       'test_started_epoch': start, 'test_finished_epoch': finish, 'elapsed_seconds': finish-start,
       'exit_code': code, 'timed_out': timed_out, 'pid': p.pid, 'own_test_process_exited': p.poll() is not None,
       'child_user_cpu_seconds': r.ru_utime, 'child_system_cpu_seconds': r.ru_stime,
       'child_max_rss_kib': r.ru_maxrss, 'before': before, 'after': after, 'samples': samples, 'junit': junit,
       'stdout': (BASE / 'stdout.txt').read_text(), 'stderr': (BASE / 'stderr.txt').read_text()}
(BASE / 'result.json').write_text(json.dumps(out, indent=2))
print(json.dumps(out))
