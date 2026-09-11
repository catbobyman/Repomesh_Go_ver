"""Audit the six existing model cases and four running channel configurations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('matrix_live',ROOT/'scripts/matrix-live-validation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state=json.loads((ROOT/'private/twin-model-live-state.json').read_text(encoding='utf-8'))
report={'channel_audits':[],'room_audits':[],'response_format':[]}
for instance in ['a','b']:
    for role in ['leader','worker']:
        name=f'rv-{instance}-worker-live-twin-{role}'
        code=r'''
import json,pathlib,os,hashlib
home=pathlib.Path(os.environ['HOME'])
p=home/'.qwenpaw/workspaces/default/agent.json'
ch=json.loads(p.read_text()).get('channels',{})
v={'path':str(p),'builtin_matrix_enabled':ch.get('matrix',{}).get('enabled'),
   'custom_agentteams_matrix_enabled':ch.get('agentteams_matrix',{}).get('enabled')}
plugin=home/'.qwenpaw/plugins/agentteams-matrix-channel/agentteams_matrix/channel.py'
v['custom_channel_source_exists']=plugin.exists()
if plugin.exists():
 v['custom_channel_sha256']=hashlib.sha256(plugin.read_bytes()).hexdigest()
 lines=plugin.read_text().splitlines()
 v['session_source']=[{'line':i+1,'text':line} for i,line in enumerate(lines) if 'session_id = f"matrix:' in line or 'sender_id=room_id' in line]
print(json.dumps(v))
'''
        got=subprocess.run(['docker','exec','-i',name,'/opt/venv/qwenpaw/bin/python','-'],input=code,capture_output=True,text=True,encoding='utf-8',timeout=20)
        if got.returncode:
            report['channel_audits'].append({'container':name,'error':'read-only query failed'})
            continue
        config=json.loads(got.stdout)
        logs=subprocess.run(['docker','logs','--since','2026-09-09T16:45:00Z',name],capture_output=True,text=True,encoding='utf-8',timeout=20)
        relevant=[]
        for line in (logs.stdout+logs.stderr).splitlines():
            if '_on_room_event' in line or ('session_id' in line and 'matrix:' in line): relevant.append(line)
        report['channel_audits'].append({'container':name,'config':config,'handler_log_lines':relevant[-15:]})
    for role in ['manager','leader']:
        c=state['cases'][instance+'-'+role]
        token=state['instances'][instance]['token' if role=='manager' else 'team_token']
        events=m.ok(instance,'GET','/_matrix/client/v3/rooms/'+m.q(c['room'])+'/messages',token,query={'dir':'b','limit':100})['chunk']
        matching=[];wrong_instance=[];wrong_sender=[]
        for event in events:
            content=event.get('content',{});text=content.get('m.new_content',content).get('body','')
            if event.get('sender') in [state['instances'][instance]['user_id'],state['instances'][instance].get('team_user_id')]:continue
            markers=[(cid,case) for cid,case in state['cases'].items() if case['marker'] in text]
            if not markers:continue
            matching.append({'event_id':event['event_id'],'sender':event.get('sender'),'content':content,'matched_cases':[cid for cid,_ in markers]})
            for cid,case in markers:
                if case['instance']!=instance:wrong_instance.append(cid)
                elif event.get('sender')!=case['target_user']:wrong_sender.append({'case':cid,'actual_sender':event.get('sender')})
        report['room_audits'].append({'instance':instance,'room':c['room'],'events_scanned':len(events),'matching_replies':matching,
             'foreign_instance_markers':wrong_instance,'wrong_sender_markers':wrong_sender})
for cid,c in state['cases'].items():
    content=c['reply']['content'];body=content.get('m.new_content',content).get('body','')
    report['response_format'].append({'case':cid,'only_exact_marker':body.strip()==c['marker'],'actual_final_body':body})
health=[]
for instance,port in [('a',28090),('b',38090)]:
    for path in ['/health','/healthz']:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=3) as response:status=response.status
        except urllib.error.HTTPError as error:status=error.code
        health.append({'instance':instance,'path':path,'status':status})
report['health_fixture_diagnosis_after_experiment']=health
(ROOT/'evidence/twin-model-live-readonly-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'channels':[{'container':c['container'],'builtin':c.get('config',{}).get('builtin_matrix_enabled'),
                               'custom':c.get('config',{}).get('custom_agentteams_matrix_enabled'),'handler_lines':len(c.get('handler_log_lines',[]))} for c in report['channel_audits']],
 'room_cross_instance_findings':[r['foreign_instance_markers'] for r in report['room_audits']],
 'room_wrong_sender_findings':[r['wrong_sender_markers'] for r in report['room_audits']],
 'strict_format':[{'case':r['case'],'exact':r['only_exact_marker']} for r in report['response_format']],
 'health_fixture_diagnosis':health},ensure_ascii=False))
