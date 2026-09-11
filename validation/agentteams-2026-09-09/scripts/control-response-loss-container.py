"""Real Matrix response observed by fault hook, then abrupt MCP process exit.

Only _send_delegate_notification is wrapped. The original function performs
real HTTP; no product files, storage functions or server configuration change.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

CONFIG = json.load(sys.stdin)
sys.dont_write_bytecode = True
sys.path.insert(0, CONFIG["source_dir"])
import server

BASE = Path("/tmp/repomesh-response-loss") / CONFIG["run_id"]
PREFIX = CONFIG["shared_prefix"]
TRACE, RESULTS = [], []
os.environ.update(AGENTTEAMS_AGENT_ROLE="worker", AGENTTEAMS_MATRIX_URL="http://127.0.0.1:6167",
                  AGENTTEAMS_MATRIX_USER_ID=CONFIG["user_id"], AGENTTEAMS_WORKER_MATRIX_TOKEN=CONFIG["token"])
REDACTIONS = [CONFIG["token"]] + [v for k, v in os.environ.items()
    if v and len(v) >= 8 and any(s in k.upper() for s in ("TOKEN", "PASSWORD", "SECRET", "API_KEY"))]


def clean(text):
    for value in sorted(set(REDACTIONS), key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    return text


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(**values):
    TRACE.append({"at_utc": stamp(), **values})


def mc(*args):
    process = subprocess.run(["mc", *map(str, args)], capture_output=True, text=True, timeout=30)
    record(transport="real-mc-fixture", arguments=list(map(str, args)), returncode=process.returncode,
           stdout=process.stdout, stderr=process.stderr)
    if process.returncode:
        raise RuntimeError("Real fixture mc call failed; redacted trace retained")
    return process.stdout


def ident(case, kind):
    return "loss-" + CONFIG["run_id"] + "-" + case + "-" + kind


def create_project(case):
    pid, tid = ident(case, "project"), ident(case, "task")
    meta = {"project_id": pid, "title": pid, "team_id": CONFIG["team"], "source": "matrix",
            "source_room_id": CONFIG["room"], "status": "active", "plan_type": "dag",
            "tasks": [{"task_id": tid, "title": tid, "status": "planned", "depends_on": [],
                       "assigned_to": CONFIG["user_id"]}]}
    path = BASE / case / "shared/projects" / pid / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2) + "\n")
    mc("cp", path, f"{PREFIX}/projects/{pid}/meta.json")
    return pid, tid


def local_snapshot(case, pid, tid):
    root = BASE / case
    result = {"directory": str(root), "exists": root.exists(), "project": None, "task": None, "files_sha256": {}}
    for label, key in (("project", f"shared/projects/{pid}/meta.json"), ("task", f"shared/tasks/{tid}/meta.json")):
        path = root / key
        if path.is_file():
            result[label] = json.loads(path.read_text())
    if root.exists():
        result["files_sha256"] = {str(p.relative_to(root)): sha(p.read_bytes()) for p in root.rglob("*") if p.is_file()}
    return result


def remote_snapshot(pid, tid):
    project = mc("cat", f"{PREFIX}/projects/{pid}/meta.json")
    task = mc("cat", f"{PREFIX}/tasks/{tid}/meta.json")
    return {"project": json.loads(project), "task": json.loads(task),
            "project_bytes_sha256": sha(project.encode()), "task_bytes_sha256": sha(task.encode())}


def timeline():
    path = f"/_matrix/client/v3/rooms/{urllib.parse.quote(CONFIG['room'], safe='')}/messages?dir=b&limit=100"
    request = urllib.request.Request("http://127.0.0.1:6167" + path,
                                    headers={"Authorization": "Bearer " + CONFIG["token"]})
    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.load(response)
    record(transport="real-Matrix-timeline", path=path, response=result)
    return result["chunk"]


def sidechannel_path(case, mode):
    return BASE / "observer" / (case + "-" + mode + ".jsonl")


def child_main():
    case, mode = CONFIG["case"], CONFIG["fault_mode"]
    pid, tid = ident(case, "project"), ident(case, "task")
    observer = sidechannel_path(case, mode)
    observer.parent.mkdir(parents=True, exist_ok=True)
    original = server._send_delegate_notification

    def send_wrapper(arguments, **kwargs):
        # This is the ONLY patched function. The native helper makes the real
        # Matrix request and parses its successful event_id before the fault.
        response = original(arguments, **kwargs)
        observed = {"at_utc": stamp(), "mcp_pid": os.getpid(), "mode": mode,
                    "identity": CONFIG["user_id"], "room": kwargs["room_id"], "task_id": kwargs["task_id"],
                    "expected_native_tx_id": "delegate-" + kwargs["task_id"], "real_response": response,
                    "observer_only_not_returned_to_delegate": mode == "hard-exit"}
        with observer.open("a", encoding="utf-8") as handle:
            handle.write(clean(json.dumps(observed, ensure_ascii=False)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if mode == "hard-exit" and response.get("sent") and response.get("eventId"):
            # Ends only this freshly spawned MCP harness PID. No finally or
            # delegate continuation runs, and no service is signaled.
            os._exit(86)
        return response

    server._send_delegate_notification = send_wrapper
    args = {"action": "delegate_task", "workspaceDir": str(BASE / case),
            "storage": {"sharedPrefix": PREFIX}, "projectId": pid, "taskId": tid,
            "assignedTo": CONFIG["user_id"], "roomId": CONFIG["room"], "role": "leader",
            "spec": "Response loss fixture only; no model task or external side effect"}
    response = server.call_tool("taskflow", args)
    server._send_delegate_notification = original
    print(clean(json.dumps({"mcp_pid": os.getpid(), "arguments": args, "native_mcp_response": response,
                            "tool_response": json.loads(response["content"][0]["text"])}, ensure_ascii=False, indent=2)))


def child(case, mode):
    conf = {**CONFIG, "mode": "child", "case": case, "fault_mode": mode}
    process = subprocess.run([sys.executable, __file__], input=json.dumps(conf), capture_output=True,
                             text=True, encoding="utf-8", timeout=90)
    observer = sidechannel_path(case, mode)
    observations = [json.loads(line) for line in observer.read_text().splitlines()] if observer.exists() else []
    result = {"case": case, "mode": mode, "returncode": process.returncode,
              "stdout": process.stdout, "stderr": process.stderr, "observer_sidechannel": observations,
              "observer_path": str(observer)}
    record(operation="MCP-subprocess", **result)
    return result


def experiment(case, discard_local):
    pid, tid = create_project(case)
    before = local_snapshot(case, pid, tid)
    interrupted = child(case, "hard-exit")
    assert interrupted["returncode"] == 86 and not interrupted["stdout"].strip(), interrupted
    assert len(interrupted["observer_sidechannel"]) == 1
    event_id = interrupted["observer_sidechannel"][0]["real_response"]["eventId"]
    lost_pid = interrupted["observer_sidechannel"][0]["mcp_pid"]
    local_after_loss, remote_after_loss = local_snapshot(case, pid, tid), remote_snapshot(pid, tid)
    assert local_after_loss["task"]["status"] == remote_after_loss["task"]["status"] == "prepared"
    assert not local_after_loss["task"].get("eventId") and not remote_after_loss["task"].get("eventId")
    assert local_after_loss["project"]["tasks"][0]["status"] == remote_after_loss["project"]["tasks"][0]["status"] == "planned"
    first_events = [e for e in timeline() if f"**{tid}**" in e.get("content", {}).get("body", "")]
    assert len(first_events) == 1 and first_events[0]["event_id"] == event_id
    archive = None
    if discard_local:
        old, archived = BASE / case, BASE / (case + "-archived-before-retry")
        assert old.resolve().is_relative_to(BASE.resolve()) and archived.resolve().is_relative_to(BASE.resolve())
        assert not archived.exists()
        old.rename(archived)
        old.mkdir()
        archive = {"original": str(old), "archived": str(archived),
                   "archived_files_sha256": {str(p.relative_to(archived)): sha(p.read_bytes()) for p in archived.rglob("*") if p.is_file()}}
        assert archive["archived_files_sha256"] == local_after_loss["files_sha256"]
        record(operation="archive-only-this-fixture-workspace-no-delete", **archive)
    retry_input = local_snapshot(case, pid, tid)
    if discard_local:
        assert not retry_input["files_sha256"] and retry_input["project"] is None and retry_input["task"] is None
    recovered = child(case, "observe-only")
    assert recovered["returncode"] == 0, recovered
    reply = json.loads(recovered["stdout"])
    assert reply["mcp_pid"] != lost_pid
    assert reply["tool_response"]["ok"] and reply["tool_response"]["synced"]
    assert reply["tool_response"]["task"]["eventId"] == event_id
    # The retry really invokes the send helper again. De-duplication is by the
    # Matrix transaction, not the local assigned+eventId shortcut.
    assert len(recovered["observer_sidechannel"]) == 1
    assert recovered["observer_sidechannel"][0]["real_response"]["eventId"] == event_id
    local_after_retry, remote_after_retry = local_snapshot(case, pid, tid), remote_snapshot(pid, tid)
    assert remote_after_retry["task"]["status"] == "assigned"
    assert remote_after_retry["project"]["tasks"][0]["status"] == "assigned"
    events = [e for e in timeline() if f"**{tid}**" in e.get("content", {}).get("body", "")]
    assert len(events) == 1 and events[0]["event_id"] == event_id
    return {"classification": "SUPPORTED_NATIVE_RECOVERY_IN_THIS_FAULT_WINDOW", "project_id": pid, "task_id": tid,
            "before": before, "interrupted": interrupted, "local_after_loss": local_after_loss,
            "remote_after_loss": remote_after_loss, "archive": archive, "retry_input": retry_input,
            "recovered": recovered, "local_after_retry": local_after_retry, "remote_after_retry": remote_after_retry,
            "matrix_event_id": event_id, "matrix_assignment_count_before_retry": len(first_events),
            "matrix_assignment_count_after_retry": len(events), "send_helper_calls": 2,
            "sender_room_task_id_preserved": True, "observer_event_not_injected_into_retry": True,
            "local_workspace_archived_and_replaced": discard_local}


def main():
    if CONFIG.get("mode") == "child":
        child_main()
        return 0
    before_hash = sha(Path(server.__file__).read_bytes())
    for name, discard in (("retained", False), ("empty", True)):
        try:
            result = experiment(name, discard)
            RESULTS.append({"id": "LOSS-01" if not discard else "LOSS-02", "status": "OBSERVATION_CONFIRMED", "observed": result})
        except Exception as exc:
            RESULTS.append({"id": "LOSS-01" if not discard else "LOSS-02", "status": "FAILED_OR_BLOCKED",
                            "error": type(exc).__name__ + ": " + str(exc)})
    result = {"executed_at_utc": stamp(), "run_id": CONFIG["run_id"], "workspace": str(BASE), "shared_prefix": PREFIX,
              "room": CONFIG["room"], "source_sha256_before": before_hash,
              "source_sha256_after": sha(Path(server.__file__).read_bytes()), "results": RESULTS, "trace": TRACE,
              "boundary": "Only native send helper wrapped: real Matrix response -> fsynced observer-only note -> os._exit(86); real mc/native retries; no server/process restart or model; dedicated nested shared prefix is not Controller project API registration"}
    print(clean(json.dumps(result, ensure_ascii=False, indent=2)))
    return 0 if result["source_sha256_before"] == result["source_sha256_after"] and all(x["status"] == "OBSERVATION_CONFIRMED" for x in RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
