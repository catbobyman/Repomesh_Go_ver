"""Exactly-once test submission and bounded polling of real Manager responses."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("matrix_live", ROOT / "scripts/matrix-live-validation.py")
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)
private = ROOT / "private/manager-model-live-state.json"
evidence = ROOT / "evidence/manager-model-live-results.json"
state = json.loads(private.read_text(encoding="utf-8")) if private.exists() else {}
results = []


def save():
    private.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def persist():
    evidence.write_text(json.dumps({"updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "manager": state.get("manager"), "sender": state.get("user_id"), "room": state.get("room"),
        "request_started_utc": state.get("started_at"), "results": results,
        "scope": "Native readiness is separated from real Manager model response; no config edits or restarts"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(value):
    results.append(value)
    persist()
    print(json.dumps(value, ensure_ascii=False), flush=True)


def sync():
    query = {"timeout": 0, "filter": json.dumps({"room": {"rooms": [state["room"]], "timeline": {"limit": 100}}})}
    if state.get("cursor"):
        query["since"] = state["cursor"]
    body = matrix.ok("a", "GET", "/_matrix/client/v3/sync", state["token"], query=query)
    state["cursor"] = body["next_batch"]
    save()
    return body.get("rooms", {}).get("join", {}).get(state["room"], {}).get("timeline", {}).get("events", [])


def send_once(kind, body):
    item = state.setdefault(kind, {"tx_id": "manager-validation-" + kind + "-" + secrets.token_hex(8)})
    if item.get("attempted"):
        if not item.get("event_id"):
            raise RuntimeError("Previous send outcome unknown; no automatic repeat")
        return item
    sync()
    item.update(attempted=True, sent_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), body=body)
    save()
    response = matrix.ok("a", "PUT", "/_matrix/client/v3/rooms/" + matrix.q(state["room"]) +
        "/send/m.room.message/" + matrix.q(item["tx_id"]), state["token"], {
            "msgtype": "m.text", "body": body, "m.mentions": {"user_ids": [state["manager"]["matrixUserID"]]}})
    item["event_id"] = response["event_id"]
    save()
    record({"kind": kind + "-sent", **item})
    return item


def poll(kind, expected, seconds):
    start = time.monotonic()
    seen = set()
    while time.monotonic() - start < seconds:
        for event in sync():
            if event.get("sender") != state["manager"]["matrixUserID"] or event.get("event_id") in seen:
                continue
            seen.add(event["event_id"])
            content = event.get("content", {})
            actual = content.get("m.new_content", content).get("body", "")
            match = actual.strip() == expected if kind == "probe" else expected in actual
            value = {"kind": kind + "-bot-event", "sender": event["sender"], "room": state["room"],
                     "event_id": event["event_id"], "origin_server_ts": event.get("origin_server_ts"),
                     "event_type": event.get("type"), "content": content, "expected_match": match,
                     "elapsed_seconds": round(time.monotonic() - start, 3)}
            record(value)
            if match:
                state[kind]["matched_reply"] = value
                save()
                return True
        time.sleep(2)
    record({"kind": kind + "-timeout", "timeout_seconds": seconds, "seen_bot_events": len(seen)})
    return False


def main():
    if "token" not in state:
        env = {}
        for line in (ROOT / "private/rv-a-controller.env").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
        secret = json.loads((ROOT / "private/rv-a-secrets.json").read_text(encoding="utf-8"))
        login = matrix.ok("a", "POST", "/_matrix/client/v3/login", data={"type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": env["AGENTTEAMS_ADMIN_USER"]}, "password": secret["admin_password"]})
        state.update(token=login["access_token"], user_id=login["user_id"], started_at=dt.datetime.now(dt.timezone.utc).isoformat())
        save()
    inventory = subprocess.run(["docker", "exec", "rv-a-controller", "agt", "get", "managers", "-o", "json"],
                              capture_output=True, text=True, timeout=20)
    if inventory.returncode:
        raise RuntimeError("Manager inventory failed")
    manager = json.loads(inventory.stdout)["managers"][0]
    state.update(manager=manager, room=manager["roomID"])
    save()
    record({"kind": "inventory", "manager": manager, "authenticated_sender": state["user_id"]})
    send_once("probe", "@manager:rv-a.matrix.invalid Readiness check: reply with the exact text READY. Isolated validation probe.")
    probe = bool(state["probe"].get("matched_reply")) or poll("probe", "READY", 45)
    record({"kind": "probe-conclusion", "channel_ready_response": probe, "model_execution_proven": False})
    marker = state.setdefault("marker", "RV_MODEL_A_20260909_" + secrets.token_hex(4))
    save()
    send_once("model", "这是隔离验证，只回复 " + marker + "，不调用工具或创建资源。")
    model = bool(state["model"].get("matched_reply")) or poll("model", marker, 180)
    record({"kind": "model-conclusion", "expected_unique_marker": marker, "matching_manager_response": model,
            "send_event_id": state["model"]["event_id"], "submission_attempts": 1})
    return 0 if probe and model else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        record({"kind": "harness-error", "error_type": type(exc).__name__, "message": str(exc) if isinstance(exc, RuntimeError) else "details suppressed"})
        raise SystemExit(1)
