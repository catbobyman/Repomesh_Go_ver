"""Stop only the previous run's recorded container IDs; retain all data and images."""
import datetime,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
old=ROOT.parent/'agentteams-2026-09-09'
record=json.loads((old/'evidence/supplement-runtime-snapshot.json').read_text(encoding='utf-8'))
expected=[r for r in record['containers'] if r['name'].startswith(('rv-a-','rv-b-'))]
assert len(expected)==11, 'Unexpected previous-run inventory'
def inspect(name):
    p=subprocess.run(['docker','inspect',name],capture_output=True,text=True,encoding='utf-8',timeout=30)
    if p.returncode:raise RuntimeError('Recorded container missing: '+name)
    return json.loads(p.stdout)[0]
for row in expected:
    c=inspect(row['name'])
    assert c['Id']==row['id'] and c['Image']==row['image'], 'Recorded identity changed: '+row['name']
out={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Stop recorded 09-09 validation containers only; no remove, volume deletion, network removal, or unrelated resources','records':[]}
path=ROOT/'evidence/prior-runtime-retirement.json'
try:
    for row in sorted(expected,key=lambda r:(not r['name'].endswith('-controller'),r['name'])):
        c=inspect(row['id'])
        entry={'name':row['name'],'id':row['id'],'was_running':c['State']['Running']}
        if entry['was_running']:
            p=subprocess.run(['docker','stop','--time','20',row['id']],capture_output=True,text=True,timeout=45)
            entry['stop_exit']=p.returncode
            if p.returncode:raise RuntimeError('Stop failed: '+row['name'])
        entry['running_after']=inspect(row['id'])['State']['Running']
        assert not entry['running_after']
        out['records'].append(entry)
finally:
    path.write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'recorded':len(expected),'stopped_or_already_stopped':len(out['records'])}))
