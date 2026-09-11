"""Dedicated native DAG validation; real call_tool, MinIO and Matrix, no model."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

C = json.load(sys.stdin)
sys.path.insert(0, C['module_path'])
import server

BASE = Path('/tmp/dag-native-live') / C['run_id']
PREFIX = 'agentteams/rv-a-storage/teams/live-harness/shared/dag-native-' + C['run_id']
PID = 'dag-native-' + C['run_id']
T = {key: PID + '-' + key for key in ['root', 'left', 'right', 'join']}
os.environ.update(AGENTTEAMS_AGENT_ROLE='leader', AGENTTEAMS_MATRIX_URL='http://127.0.0.1:6167',
                  AGENTTEAMS_MATRIX_USER_ID=C['user_id'], AGENTTEAMS_WORKER_MATRIX_TOKEN=C['token'])
TRACE, CHECKS, STAGES = [], [], []


def call(tool, action, **kw):
    args = {'action': action, 'workspaceDir': str(BASE), 'storage': {'sharedPrefix': PREFIX}, **kw}
    result = json.loads(server.call_tool(tool, args)['content'][0]['text'])
    TRACE.append({'transport': 'native-server.call_tool', 'tool': tool, 'arguments': args, 'response': result})
    return result


def check(label, passed, **observed):
    CHECKS.append({'name': label, 'passed': bool(passed), **observed})


def remote(kind='projects', ident=PID, filename='meta.json'):
    path = f'{PREFIX}/{kind}/{ident}/{filename}'
    p = subprocess.run(['mc', 'cat', path], capture_output=True, text=True, timeout=30)
    TRACE.append({'transport': 'real-mc', 'args': ['cat', path], 'returncode': p.returncode,
                  'stdout': p.stdout, 'stderr': p.stderr})
    if p.returncode:
        raise RuntimeError('mc read failed; see trace')
    return p.stdout


def stage(label, expected):
    result = call('projectflow', 'ready_nodes', projectId=PID)
    graph = json.loads(remote())
    ids = [t['task_id'] for t in result.get('readyNodes', [])]
    STAGES.append({'stage': label, 'ready_ids': ids, 'project_node_statuses': {t['task_id']: t['status'] for t in graph['tasks']},
                   'remote_project': graph})
    check(label, result.get('ok') and set(ids) == {T[k] for k in expected}, expected_keys=expected, actual_ids=ids)
    return graph


def delegate(key):
    return call('taskflow', 'delegate_task', projectId=PID, taskId=T[key], assignedTo=C['user_id'],
                roomId=C['room'], spec='Dedicated native metadata test; test user only; no model or tools.')


def transition(key, action):
    if action == 'accept_task_result':
        r = call('projectflow', action, projectId=PID, taskId=T[key], accepted=True, resultStatus='SUCCESS',
                 summary='Native test acceptance; no artifact verification claimed', publishArtifacts=False)
    else:
        r = call('taskflow', action, taskId=T[key], role='worker', summary='Synthetic metadata result; no model execution',
                 status='SUCCESS', deliverables=[])
    check(key + '-' + action, r.get('ok'), response_synced=r.get('synced'))
    return r


def timeline():
    path = '/_matrix/client/v3/rooms/' + urllib.parse.quote(C['room'], safe='') + '/messages?dir=b&limit=100'
    req = urllib.request.Request('http://127.0.0.1:6167' + path, headers={'Authorization': 'Bearer ' + C['token']})
    with urllib.request.urlopen(req, timeout=25) as response:
        value = json.load(response)
    TRACE.append({'transport': 'real-Matrix-HTTP', 'method': 'GET', 'path': path, 'response': value})
    return value['chunk']


error = None
try:
    created = call('projectflow', 'create_project', projectId=PID, title=PID, teamId='live-harness',
                   source='matrix', sourceRoomId=C['room'])
    check('native_create_project_remote_persisted', created.get('ok') and json.loads(remote())['project_id'] == PID)
    nodes = [{'taskId': T['root'], 'dependsOn': []},
             {'taskId': T['left'], 'dependsOn': [T['root']]},
             {'taskId': T['right'], 'dependsOn': [T['root']]},
             {'taskId': T['join'], 'dependsOn': [T['left'], T['right']]}]
    planned = call('projectflow', 'plan_dag', projectId=PID, tasks=nodes)
    check('legal_diamond_accepted', planned.get('ok'))
    stage('planned-root-only', ['root'])
    original_meta, original_plan = remote(), remote(filename='plan.md')
    bad = {
        'missing-predecessor': [{'taskId': T['root'], 'dependsOn': [PID + '-absent']}],
        'duplicate-id': [{'taskId': T['root']}, {'taskId': T['root']}],
        'self-cycle': [{'taskId': T['root'], 'dependsOn': [T['root']]}],
        'multi-node-cycle': [{'taskId': T['root'], 'dependsOn': [T['left']]},
                             {'taskId': T['left'], 'dependsOn': [T['right']]},
                             {'taskId': T['right'], 'dependsOn': [T['root']]}],
    }
    for name, invalid_nodes in bad.items():
        response = call('projectflow', 'plan_dag', projectId=PID, tasks=invalid_nodes)
        after_meta, after_plan = remote(), remote(filename='plan.md')
        check('reject-' + name, response.get('ok') is False, error=response.get('error'))
        check('unchanged-after-' + name, original_meta == after_meta and original_plan == after_plan,
              meta_sha256_before=hashlib.sha256(original_meta.encode()).hexdigest(),
              meta_sha256_after=hashlib.sha256(after_meta.encode()).hexdigest(),
              plan_sha256_before=hashlib.sha256(original_plan.encode()).hexdigest(),
              plan_sha256_after=hashlib.sha256(after_plan.encode()).hexdigest())
    first = delegate('root')
    check('root-real-delegate', first.get('ok') and first.get('synced'))
    stage('assigned-root-still-ready-first-query', ['root'])
    stage('assigned-root-still-ready-repeat-query', ['root'])
    retry = delegate('root')
    event = first['task']['eventId']
    msgs = timeline()
    check('assigned-repeat-delegate-reuses-notification', retry.get('ok') and retry['notification'].get('reused')
          and retry['task']['eventId'] == event and sum(e.get('event_id') == event for e in msgs) == 1,
          first_event_id=event, retry_event_id=retry['task']['eventId'],
          first_tx_id=first['notification'].get('txId'), retry_tx_id=retry['notification'].get('txId'),
          timeline_occurrences=sum(e.get('event_id') == event for e in msgs))
    transition('root', 'ack_task'); stage('root-in-progress-no-ready', [])
    transition('root', 'submit_task'); stage('root-submitted-no-ready', [])
    transition('root', 'accept_task_result'); stage('root-completed-parallel-branches-ready', ['left', 'right'])
    for key in ['left', 'right']:
        response = delegate(key)
        check(key + '-real-delegate', response.get('ok') and response.get('synced'))
    stage('both-branches-assigned-both-still-ready', ['left', 'right'])
    transition('left', 'ack_task'); stage('left-in-progress-right-assigned-ready', ['right'])
    transition('right', 'ack_task'); stage('parallel-branches-in-progress-join-blocked', [])
    transition('left', 'submit_task'); stage('left-submitted-join-blocked', [])
    transition('left', 'accept_task_result'); stage('only-left-completed-join-blocked', [])
    transition('right', 'submit_task'); stage('right-submitted-join-blocked', [])
    transition('right', 'accept_task_result'); stage('both-branches-completed-join-ready', ['join'])
    response = delegate('join'); check('join-real-delegate', response.get('ok') and response.get('synced'))
    stage('join-assigned-still-ready', ['join'])
    transition('join', 'ack_task'); stage('join-in-progress-not-ready', [])
    transition('join', 'submit_task'); stage('join-submitted-not-ready', [])
    transition('join', 'accept_task_result'); stage('all-nodes-completed-no-ready', [])
    task_states = {key: json.loads(remote('tasks', tid)) for key, tid in T.items()}
    check('task-records-independent-from-project-node-completion', all(t['status'] == 'submitted' for t in task_states.values()),
          task_record_statuses={key: t['status'] for key, t in task_states.items()})
    msgs = timeline()
    check('four-distinct-delegations-in-test-only-room', len([e for e in msgs if e.get('type') == 'm.room.message']) == 4,
          message_event_ids=[e['event_id'] for e in msgs if e.get('type') == 'm.room.message'])
except Exception as exc:
    error = type(exc).__name__ + ': ' + str(exc)
output = {'executed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'run_id': C['run_id'], 'project_id': PID,
          'workspace': str(BASE), 'storage_prefix': PREFIX, 'room': C['room'], 'matrix_identity': C['user_id'],
          'source_path': server.__file__, 'source_sha256': hashlib.sha256(Path(server.__file__).read_bytes()).hexdigest(),
          'scope': 'Unmodified native TeamHarness in Controller, real MinIO and Matrix to fixture humans; no runtime/model, no Adapter',
          'checks': CHECKS, 'stages': STAGES, 'error': error, 'trace': TRACE}
print(json.dumps(output, ensure_ascii=False, indent=2).replace(C['token'], '[REDACTED]'))
sys.exit(0 if error is None and all(c['passed'] for c in CHECKS) else 1)
