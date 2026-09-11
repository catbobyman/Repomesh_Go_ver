"""Real Matrix HTTP experiments; no mocked transport or model calls.

Credentials pass via stdin to docker exec curl --config -, never command args.
Run before, coordinate a controller restart externally, then run after-restart.
Only validation-specific users/rooms are modified. The script never restarts services.
"""
import argparse
import datetime as dt
import hashlib
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "private/matrix-live-state.json"
STATE = {}
RESULTS = []
REQUEST_COUNT = 0


class CheckError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def save_state():
    temporary = PRIVATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(STATE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(PRIVATE)


def q(value):
    return quote(str(value), safe="")


def request(instance, method, path, token=None, data=None, query=None):
    global REQUEST_COUNT
    require(instance in ("a", "b"), "Instance outside dedicated validation scope")
    require(path.startswith("/_matrix/"), "Request outside Matrix API scope")
    url = "http://127.0.0.1:6167" + path
    if query:
        url += "?" + urlencode(query)
    config = ["silent", "show-error", 'max-time = "25"',
              "url = " + json.dumps(url), "request = " + json.dumps(method),
              'header = "Content-Type: application/json"', 'write-out = "\\n%{http_code}"']
    if token:
        config.append("header = " + json.dumps("Authorization: Bearer " + token))
    if data is not None:
        # curl config supports quote/backslash escapes, not JSON \uXXXX escapes.
        # Preserve UTF-8 characters in the outer config string too.
        config.append("data = " + json.dumps(json.dumps(data, ensure_ascii=False), ensure_ascii=False))
    result = subprocess.run(["docker", "exec", "-i", f"rv-{instance}-controller", "curl", "--config", "-"],
                            input="\n".join(config) + "\n", text=True, encoding="utf-8",
                            capture_output=True, timeout=35)
    REQUEST_COUNT += 1
    if result.returncode:
        raise CheckError(f"Transport failed for instance {instance}: docker/curl exit {result.returncode}; raw output suppressed")
    try:
        body, status = result.stdout.rsplit("\n", 1)
        return int(status), json.loads(body)
    except (ValueError, json.JSONDecodeError):
        raise CheckError(f"Invalid HTTP/JSON response from instance {instance}; raw output suppressed") from None


def ok(instance, method, path, token=None, data=None, query=None):
    status, body = request(instance, method, path, token, data, query)
    if not 200 <= status < 300:
        code = body.get("errcode", "unclassified") if isinstance(body, dict) else "unclassified"
        raise CheckError(f"Expected 2xx, got HTTP {status}, errcode {code}, instance {instance}")
    return body


def inspect_start(instance):
    response = subprocess.run(["docker", "inspect", "--format", "{{.State.StartedAt}}", f"rv-{instance}-controller"],
                              capture_output=True, text=True, timeout=15)
    require(response.returncode == 0, f"Cannot inspect dedicated instance {instance}")
    return response.stdout.strip()


def provision(instance):
    entry = STATE.setdefault("instances", {}).setdefault(instance, {"users": {}})
    config = json.loads((ROOT / f"private/rv-{instance}-secrets.json").read_text(encoding="utf-8-sig"))
    require(config.get("instance") == instance, "Secret file instance mismatch")
    versions = ok(instance, "GET", "/_matrix/client/versions")
    for role in ("alice", "bob", "eve"):
        user = entry["users"].setdefault(role, {"localpart": f"mxv_{STATE['run_id']}_{role}",
                                                "password": secrets.token_urlsafe(24)})
        save_state()
        if "token" not in user:
            status, body = request(instance, "POST", "/_matrix/client/v3/register", data={
                "username": user["localpart"], "password": user["password"],
                "auth": {"type": "m.login.registration_token", "token": config["registration_token"]}})
            if status == 401 and body.get("session"):
                status, body = request(instance, "POST", "/_matrix/client/v3/register", data={
                    "username": user["localpart"], "password": user["password"],
                    "auth": {"type": "m.login.registration_token", "token": config["registration_token"],
                             "session": body["session"]}})
            appservice = body.get("errcode") == "M_EXCLUSIVE"
            if appservice:
                user["ordinary_registration_observed"] = {"status": status, "errcode": "M_EXCLUSIVE"}
                status, body = request(instance, "POST", "/_matrix/client/v3/register", config["as_token"], {
                    "type": "m.login.application_service", "username": user["localpart"]})
            if not 200 <= status < 300 and body.get("errcode") != "M_USER_IN_USE":
                raise CheckError(f"Registration failed on {instance}: HTTP {status}, errcode {body.get('errcode', 'UIA')}")
            login_body = {"type": "m.login.application_service" if appservice else "m.login.password",
                          "identifier": {"type": "m.id.user", "user": user["localpart"]},
                          "initial_device_display_name": "RepoMesh isolated validation"}
            if not appservice:
                login_body["password"] = user["password"]
            login = ok(instance, "POST", "/_matrix/client/v3/login", config["as_token"] if appservice else None, login_body)
            user.update(token=login["access_token"], user_id=login["user_id"], device_id=login.get("device_id"))
            user["registration_flow"] = "application_service" if appservice else "password"
            save_state()
        me = ok(instance, "GET", "/_matrix/client/v3/account/whoami", user["token"])
        require(me["user_id"] == user["user_id"], "whoami does not match created validation user")
    if "room" not in entry:
        created = ok(instance, "POST", "/_matrix/client/v3/createRoom", entry["users"]["alice"]["token"], {
            "preset": "private_chat", "name": f"RepoMesh Matrix validation {STATE['run_id']}",
            "room_alias_name": f"mxv_{STATE['run_id']}", "invite": [entry["users"]["bob"]["user_id"]],
            "initial_state": [{"type": "m.room.history_visibility", "state_key": "", "content": {"history_visibility": "joined"}}]})
        entry["room"] = created["room_id"]
        save_state()
    ok(instance, "POST", f"/_matrix/client/v3/join/{q(entry['room'])}", entry["users"]["bob"]["token"], {})
    entry["start_before"] = inspect_start(instance)
    save_state()
    return {"instance": instance, "versions": versions.get("versions"), "users": [u["user_id"] for u in entry["users"].values()],
            "room": entry["room"], "container_started_at": entry["start_before"],
            "registration_flows": [u["registration_flow"] for u in entry["users"].values()]}


def send(instance, transaction, content):
    e = STATE["instances"][instance]
    return ok(instance, "PUT", f"/_matrix/client/v3/rooms/{q(e['room'])}/send/m.room.message/{q(transaction)}",
              e["users"]["alice"]["token"], content)["event_id"]


def timeline(instance):
    e = STATE["instances"][instance]
    events, cursor = [], None
    for _ in range(10):
        query = {"dir": "b", "limit": 100}
        if cursor:
            query["from"] = cursor
        result = ok(instance, "GET", f"/_matrix/client/v3/rooms/{q(e['room'])}/messages", e["users"]["bob"]["token"], query=query)
        events.extend(result.get("chunk", []))
        nxt = result.get("end")
        if not result.get("chunk") or not nxt or nxt == cursor:
            break
        cursor = nxt
    return events


def event_read(instance, event_id):
    e = STATE["instances"][instance]
    return ok(instance, "GET", f"/_matrix/client/v3/rooms/{q(e['room'])}/event/{q(event_id)}", e["users"]["bob"]["token"])


def stable_tx():
    observations = []
    for instance in ("a", "b"):
        txn = f"{STATE['run_id']}-stable"
        content = {"msgtype": "m.text", "body": "validation stable transaction"}
        first = send(instance, txn, content)
        second = send(instance, txn, content)
        require(first == second, f"Repeated transaction returned different event IDs on {instance}")
        matching = [e for e in timeline(instance) if e.get("event_id") == first]
        require(len(matching) == 1, f"Repeated transaction not unique in fetched timeline on {instance}")
        STATE["instances"][instance]["stable_event"] = first
        observations.append({"instance": instance, "same_event_id": True, "timeline_occurrences": len(matching), "event_id": first})
    save_state()
    return observations


def durable_and_sync():
    observations = []
    for instance in ("a", "b"):
        entry = STATE["instances"][instance]
        baseline = ok(instance, "GET", "/_matrix/client/v3/sync", entry["users"]["bob"]["token"], query={"timeout": 0})["next_batch"]
        ids = []
        # Bob is disconnected: no sync polling while Alice writes 55 events.
        for n in range(55):
            ids.append(send(instance, f"{STATE['run_id']}-seq-{n}", {
                "msgtype": "m.text", "body": f"validation sequence {n}", "org.repomesh.validation": {"run": STATE["run_id"], "sequence": n}}))
        reconnect = ok(instance, "GET", "/_matrix/client/v3/sync", entry["users"]["bob"]["token"], query={
            "since": baseline, "timeout": 0,
            "filter": json.dumps({"room": {"rooms": [entry["room"]], "timeline": {"limit": 100}}})})
        joined = reconnect.get("rooms", {}).get("join", {}).get(entry["room"], {}).get("timeline", {})
        received = [e for e in joined.get("events", []) if e.get("event_id") in ids]
        require([e["event_id"] for e in received] == ids, f"Reconnect sync missing/reordering validation events on {instance}")
        durable = [e for e in reversed(timeline(instance)) if e.get("event_id") in ids]
        require([e["event_id"] for e in durable] == ids, f"Durable timeline missing/reordering events on {instance}")
        entry["sequence_event_ids"] = ids
        entry["sync_checkpoint"] = reconnect["next_batch"]
        observations.append({"instance": instance, "sent": 55, "reconnect_sync_count": len(received),
                             "sync_limited": joined.get("limited"), "durable_timeline_count": len(durable), "ordered": True,
                             "event_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
        save_state()
    return observations


def mention_thread():
    observations = []
    for instance in ("a", "b"):
        e = STATE["instances"][instance]
        target = e["users"]["bob"]["user_id"]
        root = e["stable_event"]
        content = {"msgtype": "m.text", "body": f"{target} thread validation", "m.mentions": {"user_ids": [target]},
                   "m.relates_to": {"rel_type": "m.thread", "event_id": root, "is_falling_back": True,
                                    "m.in_reply_to": {"event_id": root}}}
        identifier = send(instance, f"{STATE['run_id']}-thread", content)
        observed = event_read(instance, identifier)["content"]
        require(observed["m.mentions"] == content["m.mentions"] and observed["m.relates_to"] == content["m.relates_to"],
                f"Mention/thread content changed on {instance}")
        e["thread_event"] = identifier
        observations.append({"instance": instance, "event_id": identifier, "mentions_preserved": True, "thread_relation_preserved": True})
    save_state()
    return observations


def isolation():
    observations = []
    for own, other in (("a", "b"), ("b", "a")):
        entry, other_entry = STATE["instances"][own], STATE["instances"][other]
        wrong_token = other_entry["users"]["alice"]["token"]
        for operation, method, path, data in (
            ("cross-token-whoami", "GET", "/_matrix/client/v3/account/whoami", None),
            ("cross-token-read", "GET", f"/_matrix/client/v3/rooms/{q(entry['room'])}/event/{q(entry['stable_event'])}", None),
            ("cross-token-write", "PUT", f"/_matrix/client/v3/rooms/{q(entry['room'])}/send/m.room.message/cross-rejected", {"msgtype": "m.text", "body": "must reject"})):
            status, body = request(own, method, path, wrong_token, data)
            require(status in (401, 403), f"Cross-instance token accepted or unexpected response on {own}: {status}")
            observations.append({"instance": own, "operation": operation, "http_status": status, "errcode": body.get("errcode")})
        for operation, method, path, data in (
            ("nonmember-read", "GET", f"/_matrix/client/v3/rooms/{q(entry['room'])}/event/{q(entry['stable_event'])}", None),
            ("nonmember-write", "PUT", f"/_matrix/client/v3/rooms/{q(entry['room'])}/send/m.room.message/eve-rejected", {"msgtype": "m.text", "body": "must reject"})):
            status, body = request(own, method, path, entry["users"]["eve"]["token"], data)
            require(status in (403, 404), f"Private-room nonmember accepted or unexpected response on {own}: {status}")
            observations.append({"instance": own, "operation": operation, "http_status": status, "errcode": body.get("errcode")})
        visible = timeline(own)
        require(not any(e.get("content", {}).get("body") == "must reject" for e in visible), "Denied write appeared in room history")
        require(entry["room"] != other_entry["room"], "Separate instances reused full room identity")
    return observations


def after_restart():
    observations = []
    for instance in ("a", "b"):
        entry = STATE["instances"][instance]
        current_start = inspect_start(instance)
        require(current_start != entry["start_before"], f"Instance {instance} has not restarted; no recovery claim allowed")
        ids = entry["sequence_event_ids"]
        observed = [e["event_id"] for e in reversed(timeline(instance)) if e.get("event_id") in ids]
        require(observed == ids, f"Timeline did not survive restart on {instance}")
        stable = send(instance, f"{STATE['run_id']}-stable", {"msgtype": "m.text", "body": "validation stable transaction"})
        require(stable == entry["stable_event"], f"Transaction identity did not survive restart on {instance}")
        old = event_read(instance, entry["thread_event"])
        require(old["content"]["m.relates_to"]["rel_type"] == "m.thread", "Thread event not readable after restart")
        synced = ok(instance, "GET", "/_matrix/client/v3/sync", entry["users"]["bob"]["token"], query={"since": entry["sync_checkpoint"], "timeout": 0})
        require(bool(synced.get("next_batch")), "Saved sync cursor unusable after restart")
        observations.append({"instance": instance, "started_before": entry["start_before"], "started_after": current_start,
                             "events_retained": len(observed), "tx_dedup_persistent": True, "saved_sync_cursor_accepted": True,
                             "thread_event_readable": True, "existing_tokens_accepted": True})
    return observations


def run_case(case, fn):
    start = time.perf_counter()
    try:
        observation = fn()
        record = {"id": case, "status": "PASS_REAL_HTTP", "observed": observation}
    except Exception as exc:
        # No traceback or raw HTTP bodies: login/registration responses contain secrets.
        message = str(exc) if isinstance(exc, CheckError) else type(exc).__name__
        record = {"id": case, "status": "FAILED_OR_BLOCKED", "error": message}
    record["elapsed_seconds"] = round(time.perf_counter() - start, 3)
    RESULTS.append(record)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record["status"] == "PASS_REAL_HTTP"


def main():
    global STATE
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("before", "after-restart"))
    args = parser.parse_args()
    require((ROOT / "private").is_dir(), "Dedicated private directory missing; deploy validation instances first")
    STATE = json.loads(PRIVATE.read_text(encoding="utf-8")) if PRIVATE.exists() else {"run_id": secrets.token_hex(5), "instances": {}}
    success = True
    if args.phase == "before":
        for instance in ("a", "b"):
            success = run_case(f"ML-01-{instance}", lambda i=instance: provision(i)) and success
        if success:
            for case, fn in (("ML-02", stable_tx), ("ML-03", durable_and_sync), ("ML-04", mention_thread), ("ML-05", isolation)):
                if not run_case(case, fn):
                    success = False
                    break
    else:
        success = run_case("ML-06", after_restart)
    report = {"executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": args.phase,
              "run_id": STATE["run_id"], "transport": "real curl HTTP via docker exec stdin; no mock", "requests": REQUEST_COUNT,
              "scope": "Matrix delivery/durability/auth only; not QwenPaw processing, model readiness, RepoMesh Issue authorization or outbox",
              "cases": RESULTS}
    path = ROOT / f"evidence/matrix-live-{args.phase}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Matrix validation stopped: " + (str(exc) if isinstance(exc, CheckError) else type(exc).__name__), file=sys.stderr)
        sys.exit(1)
