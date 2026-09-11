"""Exactly two real short model requests: ordinary reply and m.thread; no resend."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('matrix_live', ROOT / 'scripts/matrix-live-validation.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
prior = json.loads((ROOT / 'private/twin-model-live-state.json').read_text(encoding='utf-8'))
ref = prior['cases']['a-worker']
token = prior['instances']['a']['team_token']
sender = prior['instances']['a']['team_user_id']
private = ROOT / 'private/runtime-reply-thread-live-state.json'
if private.exists():
    raise SystemExit('State already exists: do not resend either request')
state = {'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'room': ref['room'],
         'sender': sender, 'worker': ref['target_user'], 'reference_event_id': ref['event_id'], 'cases': []}


def save():
    private.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def read_event(eid):
    return m.ok('a', 'GET', '/_matrix/client/v3/rooms/' + m.q(state['room']) + '/event/' + m.q(eid), token)


def sync():
    query = {'timeout': 0, 'filter': json.dumps({'room': {'rooms': [state['room']], 'timeline': {'limit': 100}}})}
    if state.get('cursor'):
        query['since'] = state['cursor']
    got = m.ok('a', 'GET', '/_matrix/client/v3/sync', token, query=query)
    state['cursor'] = got['next_batch']; save()
    return got.get('rooms', {}).get('join', {}).get(state['room'], {}).get('timeline', {}).get('events', [])


state['reference_event'] = read_event(state['reference_event_id'])
sync()
for kind in ['reply', 'thread']:
    marker = 'RV_RT_' + kind.upper() + '_' + secrets.token_hex(5)
    body = marker + ' 是本次隔离校验标记。请只回复这个标记，不调用工具、不创建资源、不委派或联系其他成员。'
    relation = {'m.in_reply_to': {'event_id': state['reference_event_id']}}
    if kind == 'thread':
        relation.update(rel_type='m.thread', event_id=state['reference_event_id'], is_falling_back=True)
    content = {'msgtype': 'm.text', 'body': body, 'm.mentions': {'user_ids': [state['worker']]}, 'm.relates_to': relation}
    case = {'kind': kind, 'marker': marker, 'tx_id': 'runtime-' + kind + '-' + secrets.token_hex(8),
            'intended_content': content, 'since_before': state['cursor'], 'attempted': True,
            'sent_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'bot_events': []}
    state['cases'].append(case); save()
    started = time.monotonic()
    try:
        sent = m.ok('a', 'PUT', '/_matrix/client/v3/rooms/' + m.q(state['room']) + '/send/m.room.message/' + m.q(case['tx_id']), token, content)
        case['send_response'] = sent; save()
        case['readback'] = read_event(sent['event_id'])
        case['content_exact'] = case['readback']['content'] == content
        save()
        if not case['content_exact']:
            raise RuntimeError('Exact inbound content mismatch')
        matched_at = None
        while time.monotonic() - started < 180:
            for event in sync():
                if event.get('sender') == sender or event.get('type') != 'm.room.message':
                    continue
                case['bot_events'].append(event)
                c = event.get('content', {})
                text = c.get('m.new_content', c).get('body', '')
                if event.get('sender') == state['worker'] and marker in text:
                    if matched_at is None:
                        matched_at = time.monotonic()
                        case['first_marker_reply_seconds'] = round(matched_at-started, 3)
                    case['last_marker_reply'] = event
            save()
            if matched_at is not None and time.monotonic()-matched_at >= 4:
                case['status'] = 'ACTUAL_TARGET_MODEL_MARKER_REPLY'
                break
            time.sleep(1)
        else:
            case['status'] = 'NO_MATCHING_REPLY_WITHIN_180_SECONDS'
        case['observed_seconds'] = round(time.monotonic()-started, 3)
    except Exception as exc:
        case['status'] = 'FAILED_OR_UNKNOWN_SEND'
        case['error_type'] = type(exc).__name__
    save()
    print(json.dumps({'kind': kind, 'status': case['status'], 'marker': marker,
                      'reply_seconds': case.get('first_marker_reply_seconds')}), flush=True)

# Read only safe configuration fields, deployed source and matching DB rows.
code = '''import os,pathlib,sqlite3,json,hashlib,sys
c=json.load(sys.stdin)
home=pathlib.Path(os.environ['HOME'])/'.qwenpaw'
agent=home/'workspaces/default/agent.json'
channels=json.loads(agent.read_text()).get('channels',{})
source=home/'plugins/agentteams-matrix-channel/agentteams_matrix/channel.py'
lines=source.read_text().splitlines()
con=sqlite3.connect('file:'+str(home/'workspaces/default/history.db')+'?mode=ro',uri=True)
con.row_factory=sqlite3.Row
rows=[]
for marker in c['markers']:
 rows += [dict(r) for r in con.execute('SELECT seq,session_id,agent_id,kind,role,name,content,created_at FROM conversation_history WHERE content LIKE ? ORDER BY seq',('%'+marker+'%',))]
out={'builtin_enabled':channels.get('matrix',{}).get('enabled'),'custom_enabled':channels.get('agentteams_matrix',{}).get('enabled'),
 'source_path':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_excerpts':[], 'matching_history_rows':rows}
for a,b in [(2680,2713),(2764,2809),(3120,3155),(3358,3370),(3603,3630)]:
 out['source_excerpts'] += [{'line':i,'text':lines[i-1]} for i in range(a,b+1)]
print(json.dumps(out))
'''
payload = json.dumps({'markers': [c['marker'] for c in state['cases']]})
# Source passed as -c; only harmless markers go through stdin.
audit = subprocess.run(['docker', 'exec', '-i', 'rv-a-worker-live-twin-worker', 'python', '-c', code],
                       input=payload, capture_output=True, text=True, encoding='utf-8', timeout=25)
state['readonly_audit'] = json.loads(audit.stdout) if audit.returncode == 0 else {'error': 'read-only audit failed'}
logs = subprocess.run(['docker', 'logs', '--since', state['started_utc'], 'rv-a-worker-live-twin-worker'],
                      capture_output=True, text=True, encoding='utf-8', timeout=20)
all_lines = (logs.stdout + logs.stderr).splitlines()
state['handler_and_session_logs'] = [line for line in all_lines if any(c['marker'] in line for c in state['cases'])
                                   or ('session_id' in line and state['room'] in line)]
state['completed_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
save()
out = ROOT / 'evidence/runtime-reply-thread-live.json'
out.write_text(json.dumps(state, ensure_ascii=False, indent=2).replace(token, '[REDACTED]'), encoding='utf-8')
print(json.dumps({'evidence': str(out), 'handler_logs': len(state['handler_and_session_logs']),
                  'matching_db_rows': len(state['readonly_audit'].get('matching_history_rows', []))}))
