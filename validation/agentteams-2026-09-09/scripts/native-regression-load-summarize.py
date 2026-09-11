"""Read final metrics and verify runtime identity and test-process exit; no new tests."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUN = sys.argv[1]
summary = json.loads((ROOT / 'evidence' / ('native-regression-load-' + RUN + '-summary.json')).read_text())
result = {'run_id': RUN, 'metrics': {}, 'health': {}}
intervals = []
for key in ['a', 'b']:
    d = json.loads((ROOT / 'evidence' / ('native-regression-load-' + RUN + '-' + key + '.json')).read_text())
    samples = d['samples']
    first, last = samples[0], d['after']['cgroup']
    cpu = (last['cpu.stat']['usage_usec'] - first['cpu.stat']['usage_usec']) / 1e6
    delta = last['at_epoch'] - first['at_epoch']
    changes = {k: d['after']['tree'][k] - d['before']['tree'][k] for k in d['before']['tree']}
    ins = json.loads(subprocess.check_output(['docker', 'inspect', 'rv-' + key + '-worker-live-twin-worker'], text=True))[0]
    scan = '''import os,json,pathlib
base = %r
out = []
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid(): continue
 try: cmd=(p/'cmdline').read_bytes().decode(errors='replace')
 except OSError: continue
 if base in cmd: out.append({'pid':int(p.name),'matches_own_test_path':True})
print(json.dumps(out))
''' % d['base']
    proc = subprocess.run(['docker', 'exec', '-i', 'rv-' + key + '-worker-live-twin-worker', 'python', '-'],
                          input=scan, capture_output=True, text=True, check=True)
    metrics = {'elapsed_seconds': d['elapsed_seconds'], 'cgroup_cpu_seconds_in_sample_window': cpu,
               'cgroup_cpu_sample_window_seconds': delta, 'cgroup_cpu_average_percent_one_core': cpu / delta * 100,
               'cgroup_cpu_max_interval_percent_one_core': max((b['cpu.stat']['usage_usec']-a['cpu.stat']['usage_usec'])/1e6/(b['at_epoch']-a['at_epoch'])*100 for a,b in zip(samples,samples[1:])),
               'container_memory_before_bytes': first['memory.current'],
               'container_memory_sampled_peak_bytes': max(s['memory.current'] for s in samples),
               'container_memory_after_bytes': last['memory.current'],
               'container_memory_failcnt_delta': last['memory.failcnt']-first['memory.failcnt'],
               'sample_count': len(samples), 'directory_growth': changes,
               'child_cpu_seconds': d['child_user_cpu_seconds'] + d['child_system_cpu_seconds'],
               'child_max_rss_kib': d['child_max_rss_kib'],
               'runtime_id_unchanged': ins['Id'] == summary['before_containers'][key]['id'],
               'runtime_started_at_unchanged': ins['State']['StartedAt'] == summary['before_containers'][key]['started_at'],
               'runtime_running': ins['State']['Running'], 'own_test_processes_remaining': json.loads(proc.stdout)}
    result['metrics'][key] = metrics
    intervals.append((d['test_started_epoch'], d['test_finished_epoch']))
    h = [x for x in summary['health_samples'] if x['instance'] == key]
    result['health'][key] = {'samples': len(h), 'all_200': all(x.get('status') == 200 for x in h),
                             'max_latency_seconds': max(x['latency_seconds'] for x in h),
                             'samples_during_test_interval': sum(d['test_started_epoch'] <= x['at_epoch'] <= d['test_finished_epoch'] for x in h)}
result['overlap_seconds'] = min(x[1] for x in intervals)-max(x[0] for x in intervals)
path = ROOT / 'evidence' / ('native-regression-load-' + RUN + '-metrics.json')
path.write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
