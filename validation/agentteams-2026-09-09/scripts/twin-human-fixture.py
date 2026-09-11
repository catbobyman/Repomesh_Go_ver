"""Provision dedicated Human CRs required by Team.admin; do not reuse bootstrap admin identities."""
import importlib.util,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('live',ROOT/'scripts/controller-live-validation.py')
live=importlib.util.module_from_spec(s);s.loader.exec_module(live)
out=[]
for i in 'ab':
    code,h=live.api(i,'GET','/api/v1/humans/live-twin-human')
    if code==404:
        code,h=live.api(i,'POST','/api/v1/humans',{'name':'live-twin-human','displayName':'Isolated twin team human',
            'permissionLevel':2,'accessibleTeams':['live-twin-team']})
    assert code in (200,201)
    for n in range(40):
        code,h=live.api(i,'GET','/api/v1/humans/live-twin-human')
        if h.get('phase')=='Ready' or (h.get('phase')=='Active' and h.get('matrixUserID')):break
        if h.get('matrixUserID') and h.get('initialPassword'):break
        time.sleep(2)
    (ROOT/f'private/twin-human-{i}.json').write_text(json.dumps(h,ensure_ascii=False,indent=2),encoding='utf-8')
    assert h.get('matrixUserID'), 'Human provisioning failed; private response saved'
    code,t=live.api(i,'PUT','/api/v1/teams/live-twin-team',{'admin':{'name':'live-twin-human','matrixUserId':h['matrixUserID']}})
    out.append({'instance':i,'human':{k:v for k,v in h.items() if k!='initialPassword'},'team_update_status':code,'team':t})
    (ROOT/'evidence/twin-human-fixture.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    assert code==200
(ROOT/'evidence/twin-human-fixture.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'humans_created':len(out),'secrets_saved_privately':True}))
