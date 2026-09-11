"""Execute unmodified upstream Matrix channel functions with explicit transport/runtime fakes.

No Matrix server, model, QwenPaw queue, auth policy or persistent session store is exercised.
Uses the upstream test loader, which stubs nio and QwenPaw imports. Assertions document
native observations, including limitations; PASS is not a RepoMesh business gate pass.
"""
import asyncio
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream"
SOURCE = UP / "plugins/agentteams-matrix-channel/agentteams_matrix/channel.py"
LOADER = UP / "qwenpaw/tests/test_matrix_overlay.py"
spec = importlib.util.spec_from_file_location("matrix_upstream_fixture", LOADER)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
m = fixture._load_overlay_module()


def fake_base_init(self, **kwargs):
    self._enqueue = None
    self._process = kwargs["process"]


m.BaseChannel.__init__ = fake_base_init
BOT = "@bot:fixture.test"
ROOM = "!conversation-a:fixture.test"
observations = []


def channel():
    processed = []
    async def fake_process(*args, **kwargs):
        processed.append((args, kwargs))
    c = m.AgentTeamsMatrixChannel(process=fake_process, matrix_user_id=BOT)
    c._user_id = BOT
    c.trace, c.queue, c.sent, c.processed = [], [], [], processed
    async def fake_dm(*args):
        return False
    async def receipt(room, event):
        c.trace.append(["receipt", event])
    async def typing(room, active):
        c.trace.append(["typing", active])
    async def prepare(room):
        return None
    async def send(room, typ, content, **kwargs):
        c.sent.append({"room": room, "content": content, **kwargs})
        return NS(event_id=f"$out{len(c.sent)}")
    def enqueue(payload):
        c.trace.append(["enqueue", payload["meta"]["event_id"]])
        c.queue.append(payload)
    c._is_dm_room, c._send_read_receipt, c._send_typing = fake_dm, receipt, typing
    c._prepare_room_send = prepare
    c._client = NS(rooms={}, room_send=send)
    c._enqueue = enqueue
    c.build_agent_request_from_user_content = lambda **kw: NS(**kw)
    return c


def room(room_id=ROOM):
    return NS(room_id=room_id, users={}, user_name=lambda uid: uid.split(":")[0][1:])


def event(body, event_id="$e", sender="@alice:fixture.test", mention=False, thread=False, **content):
    content = {"msgtype": "m.text", "body": body, **content}
    if mention:
        content["m.mentions"] = {"user_ids": [BOT]}
    if thread:
        content["m.relates_to"] = {"rel_type": "m.thread", "event_id": "$root"}
    return NS(body=body, event_id=event_id, sender=sender, server_timestamp=1000,
              source={"content": content})


async def sessions():
    c = channel()
    for who, issue in [("alice", "issue-a"), ("bob", "issue-b")]:
        await c._on_room_event(room(), event(f"Operate {issue}", sender=f"@{who}:fixture.test",
                                             mention=True, issue_id=issue))
    reqs = [c.build_agent_request_from_native(p) for p in c.queue]
    assert reqs[0].session_id == reqs[1].session_id == f"matrix:{ROOM}"
    assert reqs[0].sender_id == reqs[1].sender_id == ROOM
    assert [r.channel_meta["sender_id"] for r in reqs] == ["@alice:fixture.test", "@bob:fixture.test"]
    assert all("issue_id" not in r.channel_meta for r in reqs)
    await c._on_room_event(room("!other:fixture.test"), event("Other room", mention=True))
    other = c.build_agent_request_from_native(c.queue[-1])
    assert other.session_id != reqs[0].session_id
    assert c.get_debounce_key(c.queue[0]) == c.get_debounce_key(c.queue[1])
    assert c.get_debounce_key(c.queue[-1]) != c.get_debounce_key(c.queue[0])
    return {"sessions": [r.session_id for r in reqs] + [other.session_id],
            "user_key": ROOM, "actual_sender_retained": True, "source_issue_id_projected": False,
            "scope": "Captured arguments to fake BaseChannel request builder; not real persisted session behavior"}


async def history_limit():
    c = channel()
    for i in range(55):
        await c._on_room_event(room(), event(f"history-{i}", event_id=f"$h{i}"))
    assert not c.queue and not c.trace
    entries = c._room_histories[ROOM]
    assert len(entries) == 50 and entries[0].body == "history-5" and entries[-1].body == "history-54"
    await c._on_room_event(room(), event("issue-b: current request", mention=True))
    text = c.queue[0]["content_parts"][0].text
    assert "history-5 [" in text and "history-0 [" not in text
    assert "[Current message - respond to this]" in text and ROOM not in c._room_histories
    return {"input": 55, "retained": 50, "first": "history-5", "last": "history-54",
            "queue_after_trigger": len(c.queue), "history_cleared_after_enqueue": True,
            "cross_issue_context": "room history prepended to issue-b trigger without issue partition"}


async def restart():
    c = channel()
    await c._on_room_event(room(), event("pending before restart"))
    assert len(c._room_histories[ROOM]) == 1
    replacement = channel()
    assert replacement._room_histories == {}
    await replacement._on_room_event(room(), event("now respond", mention=True))
    assert "pending before restart" not in replacement.queue[0]["content_parts"][0].text
    return {"old_buffer": 1, "new_instance_buffer": 0,
            "scope": "Constructed fresh channel; Matrix replay/session restoration not simulated"}


async def threads():
    c = channel()
    await c._on_room_event(room(), event("room context", event_id="$context"))
    await c._on_room_event(room(), event("unmentioned thread", thread=True))
    assert len(c._room_histories[ROOM]) == 1 and not c.queue
    await c._on_room_event(room(), event("mentioned thread", event_id="$thread", mention=True, thread=True))
    assert len(c.queue) == 1 and "room context" not in c.queue[0]["content_parts"][0].text
    assert len(c._room_histories[ROOM]) == 1
    await c._on_room_event(room(), event("ordinary reply", event_id="$reply", mention=True,
                                       **{"m.relates_to": {"m.in_reply_to": {"event_id": "$context"}}}))
    assert "room context" in c.queue[-1]["content_parts"][0].text
    return {"unmentioned_thread": "dropped, not buffered", "mentioned_thread": "queued without room history",
            "ordinary_reply": "queued with room history", "thread_payload_root": c.queue[0]["meta"]["thread_root_event_id"]}


async def readiness():
    c = channel()
    await c._on_room_event(room(), event("Readiness check: reply with the exact text READY", mention=True))
    assert len(c.sent) == 1 and c.sent[0]["content"]["body"] == "READY"
    assert not c.queue and not c.processed and not c.trace
    return {"reply": "READY", "enqueued": 0, "model_process_calls": 0, "read_receipts": 0}


async def receipt_before_process():
    c = channel()
    await c._on_room_event(room(), event("execute", mention=True))
    assert c.trace == [["receipt", "$e"], ["typing", True], ["enqueue", "$e"]]
    assert not c.processed
    return {"trace": c.trace, "process_calls": 0, "scope": "queue consumer intentionally not running"}


async def replay():
    c = channel()
    e = event("same event replayed", event_id="$same", mention=True)
    await c._on_room_event(room(), e)
    await c._on_room_event(room(), e)
    assert [p["meta"]["event_id"] for p in c.queue] == ["$same", "$same"]
    return {"same_event_callbacks": 2, "enqueues": 2,
            "scope": "No callback-level duplicate suppression; real nio sync replay behavior not claimed"}


async def enqueue_failure():
    c = channel()
    await c._on_room_event(room(), event("buffered"))
    def unavailable(payload):
        raise RuntimeError("injected queue failure")
    c._enqueue = unavailable
    try:
        await c._on_room_event(room(), event("trigger", mention=True))
    except RuntimeError as exc:
        assert str(exc) == "injected queue failure"
    else:
        raise AssertionError("queue failure unexpectedly swallowed")
    assert len(c._room_histories[ROOM]) == 1 and c.trace[0] == ["receipt", "$e"]
    return {"queue_failure_propagated": True, "buffer_retained": 1, "receipt_already_sent": True}


async def queue_order():
    c = channel()
    for i in range(3):
        await c._on_room_event(room(), event(str(i), event_id=f"$seq{i}", mention=True))
    sequential = [p["meta"]["event_id"] for p in c.queue]
    assert sequential == ["$seq0", "$seq1", "$seq2"]
    c = channel()
    first_waiting, release = asyncio.Event(), asyncio.Event()
    async def delayed_receipt(r, e):
        if e == "$first":
            first_waiting.set()
            await release.wait()
        c.trace.append(["receipt", e])
    c._send_read_receipt = delayed_receipt
    first = asyncio.create_task(c._on_room_event(room(), event("first", "$first", mention=True)))
    await first_waiting.wait()
    await c._on_room_event(room(), event("second", "$second", mention=True))
    release.set()
    await first
    concurrent = [p["meta"]["event_id"] for p in c.queue]
    assert concurrent == ["$second", "$first"]
    return {"sequential_callbacks": sequential, "concurrent_callbacks_delayed_first_receipt": concurrent,
            "scope": "Channel callback injection only; does not demonstrate actual nio callback concurrency or QwenPaw queue scheduling"}


async def lost_response_retry():
    c = channel()
    transactions = []
    async def lossy_send(r, typ, content, **kwargs):
        transactions.append(kwargs["tx_id"])
        if len(transactions) == 1:
            raise TimeoutError("injected loss after server acceptance")
        return NS(event_id="$accepted")
    c._client.room_send = lossy_send
    result = await c._room_send_with_retry(ROOM, "m.room.message", {"body": "one operation"}, base_delay=0)
    assert result.event_id == "$accepted" and len(transactions) == 2 and transactions[0] == transactions[1]
    await c._room_send_with_retry(ROOM, "m.room.message", {"body": "one operation"}, base_delay=0)
    assert transactions[2] != transactions[0]
    return {"tx_ids": transactions, "same_invocation_retry_id_stable": True,
            "new_invocation_new_id": True, "server_deduplication": "not tested; transport fake records IDs only"}


CASES = [("MX-01", "AT-06", sessions), ("MX-02", "AT-10", history_limit),
         ("MX-03", "AT-07/10", restart), ("MX-04", "AT-06/10", threads),
         ("MX-05", "AT-07", readiness), ("MX-06", "AT-07/10", receipt_before_process),
         ("MX-07", "AT-10", replay), ("MX-08", "AT-10", enqueue_failure),
         ("MX-09", "AT-10", queue_order), ("MX-10", "AT-10", lost_response_retry)]


async def main():
    for case_id, gate, fn in CASES:
        start = time.perf_counter()
        record = {"id": case_id, "gate": gate, "name": fn.__name__}
        try:
            record.update(status="OBSERVATION_CONFIRMED", observed=await fn())
        except Exception:
            record.update(status="HARNESS_OR_EXPECTATION_FAILURE", error=traceback.format_exc())
        record["elapsed_seconds"] = round(time.perf_counter() - start, 6)
        observations.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    commit = subprocess.check_output(["git", "-c", f"safe.directory={UP.as_posix()}", "-C", str(UP), "rev-parse", "HEAD"], text=True).strip()
    report = {"executed_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "upstream_commit": commit, "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              "loader_sha256": hashlib.sha256(LOADER.read_bytes()).hexdigest(),
              "boundary": "Unmodified channel functions; upstream loader stubs QwenPaw/nio; fake transport, request builder and queue; no model or live server",
              "cases": observations}
    (ROOT / "evidence/matrix-component-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 1 if any(r["status"] != "OBSERVATION_CONFIRMED" for r in observations) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
