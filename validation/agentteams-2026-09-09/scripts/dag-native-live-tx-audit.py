"""Focused same-transaction replay of the already sent test-only native notification."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
run_id = sys.argv[1]
config = json.loads((ROOT / ('private/dag-native-live-' + run_id + '.json')).read_text())
evidence = json.loads((ROOT / ('evidence/dag-native-live-' + run_id + '.json')).read_text(encoding='utf-8'))
original = next(x['response'] for x in evidence['trace'] if x.get('arguments', {}).get('action') == 'delegate_task')
event_id = original['task']['eventId']
spec = importlib.util.spec_from_file_location('matrix_live', ROOT / 'scripts/matrix-live-validation.py')
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)
path = '/_matrix/client/v3/rooms/' + matrix.q(config['room'])
event = matrix.ok('a', 'GET', path + '/event/' + matrix.q(event_id), config['token'])
tx_id = 'delegate-' + original['task']['task_id']
send_path = path + '/send/m.room.message/' + matrix.q(tx_id)
replies = [matrix.ok('a', 'PUT', send_path, config['token'], event['content']) for _ in range(2)]
timeline = matrix.ok('a', 'GET', path + '/messages?dir=b&limit=100', config['token'])
messages = [e for e in timeline['chunk'] if e.get('type') == 'm.room.message']
passed = all(r.get('event_id') == event_id for r in replies) and sum(e.get('event_id') == event_id for e in messages) == 1 and len(messages) == 4
result = {'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'run_id': run_id,
          'scope': 'Two real Matrix PUTs using unchanged original notification content and original native delegate task transaction; no new delegate/start/model',
          'tx_id_source': 'server.py:_send_delegate_notification txn=delegate-{task_id}; native delegate response omits txId',
          'transaction_id': tx_id, 'method': 'PUT', 'path': send_path, 'request_content': event['content'],
          'original_event': event, 'put_responses': replies, 'timeline': timeline,
          'message_count_after': len(messages), 'original_event_occurrences_after': sum(e.get('event_id') == event_id for e in messages),
          'passed': passed}
(ROOT / ('evidence/dag-native-live-' + run_id + '-tx-audit.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': passed, 'transaction_id': tx_id, 'put_responses': replies, 'message_count_after': len(messages)}))
sys.exit(0 if passed else 1)
