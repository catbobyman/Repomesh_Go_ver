"""Bounded observation of only this run's actual validation containers."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import time

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=120);p.add_argument('--label',default='startup')
args=p.parse_args()
if not 5<=args.seconds<=300:raise SystemExit('duration must be 5..300 seconds')
if not args.label.replace('-','').isalnum():raise SystemExit('label must be alphanumeric/hyphens')
def cmd(*a):return subprocess.check_output(['docker',*a],text=True,encoding='utf-8',errors='replace',timeout=30)
host=json.loads(cmd('info','--format','{{json .}}'))
out={'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'host':{k:host.get(k) for k in ['ServerVersion','NCPU','MemTotal','KernelVersion','OperatingSystem','Architecture','CgroupVersion','Driver']},
     'scope':'Observed deployment only; samples are not a maximum-capacity benchmark','samples':[]}
begin=time.monotonic()
while time.monotonic()-begin<args.seconds:
    raw=cmd('ps','--format','{{json .}}').splitlines()
    selected=[]
    for line in raw:
        c=json.loads(line)
        if c['Names'].startswith(('rv-a-','rv-b-')):selected.append(c['ID'])
    sample={'at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-begin,2),'containers':[]}
    if selected:
        sample['containers']=[json.loads(s) for s in cmd('stats','--no-stream','--format','{{json .}}',*selected).splitlines()]
    out['samples'].append(sample)
    (root/'evidence'/f'capacity-{args.label}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    time.sleep(5)
out['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
(root/'evidence'/f'capacity-{args.label}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'samples':len(out['samples']),'seconds':round(time.monotonic()-begin,2),'file':f'capacity-{args.label}.json'}))
