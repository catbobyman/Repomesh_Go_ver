"""Runs inside the dedicated rv-a-controller with unmodified copied TeamHarness.
All call_tool, mc and Matrix operations are real. No monkeypatches or mocks.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request

CONFIG = json.load(sys.stdin)
sys.path.insert(0, "/tmp/repomesh-live-mcp")
import server

BASE = Path("/tmp/repomesh-live-harness") / CONFIG["run_id"]
PREFIX = "agentteams/rv-a-storage/teams/live-harness/shared/" + CONFIG["run_id"]
BASE.mkdir(parents=True, exist_ok=True)
os.environ.update(AGENTTEAMS_AGENT_ROLE="worker", AGENTTEAMS_MATRIX_URL="http://127.0.0.1:6167",
                  AGENTTEAMS_MATRIX_USER_ID=CONFIG["user_id"], AGENTTEAMS_WORKER_MATRIX_TOKEN=CONFIG["token"])
TRACE, RESULTS = [], []


def mc(*args):
    result = subprocess.run(["mc", *map(str, args)], capture_output=True, text=True, timeout=35)
    TRACE.append({"transport": "real-mc", "args": list(map(str, args)), "returncode": result.returncode,
                  "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError("mc operation failed; inspect redacted trace")
    return result.stdout


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def workspace(case):
    return BASE / case


def project(case, pid, tids, status="active", task_status="planned"):
    value = {"project_id": pid, "title": pid, "team_id": "live-harness", "source": "matrix",
             "source_room_id": CONFIG["room"], "plan_type": "dag", "status": status,
             "tasks": [{"task_id": tid, "title": tid, "status": task_status,
                        "assigned_to": CONFIG["user_id"], "depends_on": []} for tid in tids]}
    path = workspace(case) / "shared/projects" / pid / "meta.json"
    dump(path, value)
    mc("cp", path, f"{PREFIX}/{case}/projects/{pid}/meta.json")
    return value


def remote(case, kind, ident):
    return json.loads(mc("cat", f"{PREFIX}/{case}/{kind}/{ident}/meta.json"))


def invoke(case, tool, action, **kwargs):
    args = {"action": action, "workspaceDir": str(workspace(case)),
            "storage": {"sharedPrefix": f"{PREFIX}/{case}"}, **kwargs}
    result = json.loads(server.call_tool(tool, args)["content"][0]["text"])
    TRACE.append({"transport": "real-server.call_tool", "tool": tool, "arguments": args, "response": result})
    return result


def delegate(case, pid, tid, **kwargs):
    return invoke(case, "taskflow", "delegate_task", projectId=pid, taskId=tid,
                  assignedTo=CONFIG["user_id"], roomId=CONFIG["room"], spec="Isolated validation only", **kwargs)


def matrix_timeline():
    path = "/_matrix/client/v3/rooms/" + urllib.parse.quote(CONFIG["room"], safe="") + "/messages?dir=b&limit=100"
    req = urllib.request.Request("http://127.0.0.1:6167" + path,
                                 headers={"Authorization": "Bearer " + CONFIG["token"]})
    with urllib.request.urlopen(req, timeout=20) as response:
        value = json.load(response)
    TRACE.append({"transport": "real-Matrix-HTTP", "method": "GET", "path": path, "response": value})
    return value["chunk"]


def role_override():
    case, tid = "role", "role-task"
    project(case, "role-project", [tid])
    denied = delegate(case, "role-project", tid)
    accepted = delegate(case, "role-project", tid, role="leader")
    assert not denied["ok"] and "leader role" in denied["error"]
    assert accepted["ok"] and accepted["synced"] and remote(case, "tasks", tid)["status"] == "assigned"
    event = accepted["task"]["eventId"]
    assert any(e["event_id"] == event for e in matrix_timeline())
    return {"runtime_role": server._runtime_role(), "without_role_denied": True,
            "with_role_leader_assigned_and_persisted": True, "real_matrix_event": event}


def paused():
    case, tid = "paused", "paused-task"
    project(case, "paused-project", [tid], status="paused")
    ready = invoke(case, "projectflow", "ready_nodes", projectId="paused-project")
    result = delegate(case, "paused-project", tid, role="leader")
    after = remote(case, "projects", "paused-project")
    assert ready["readyNodes"] == [] and result["ok"] and result["synced"]
    assert after["status"] == "paused" and after["tasks"][0]["status"] == "assigned"
    assert any(e["event_id"] == result["task"]["eventId"] for e in matrix_timeline())
    return {"ready_nodes": [], "project_status": after["status"], "task_status": after["tasks"][0]["status"],
            "real_matrix_event": result["task"]["eventId"]}


def inflight_replan():
    case = "inflight"
    before = project(case, "inflight-project", ["inflight-old"], status="paused", task_status="in_progress")
    result = invoke(case, "projectflow", "plan_dag", projectId="inflight-project", tasks=[{"taskId": "inflight-new"}])
    after = remote(case, "projects", "inflight-project")
    assert result["ok"] and after["status"] == "paused"
    assert [t["task_id"] for t in after["tasks"]] == ["inflight-new"]
    return {"runtime_role": server._runtime_role(), "before": before, "after": after}


def collision_retry():
    case, tid = "collision", "collision-T1"
    project(case, "collision-a", [tid])
    project(case, "collision-b", [tid])
    first = delegate(case, "collision-a", tid, role="leader")
    retry = delegate(case, "collision-a", tid, role="leader")
    second = delegate(case, "collision-b", tid, role="leader")
    assert first["ok"] and retry["ok"] and second["ok"]
    assert retry["notification"]["reused"] and second["notification"]["reused"]
    assert second["task"]["project_id"] == "collision-a"
    assert remote(case, "projects", "collision-b")["tasks"][0]["status"] == "planned"
    event = first["task"]["eventId"]
    assert retry["task"]["eventId"] == second["task"]["eventId"] == event
    count = sum(e["event_id"] == event for e in matrix_timeline())
    assert count == 1
    return {"same_project_retry_reused": True, "different_project_returned_original": True,
            "requested_project": "collision-b", "returned_project": "collision-a", "second_project_still_planned": True,
            "event_id": event, "real_timeline_event_occurrences": count}


def double_ack():
    case, tids = "double-ack", ["double-A", "double-B"]
    project(case, "double-project", tids)
    for tid in tids:
        assert delegate(case, "double-project", tid, role="leader")["ok"]
    responses = [invoke(case, "taskflow", "ack_task", taskId=tid) for tid in tids]
    assert all(r["ok"] and r["synced"] for r in responses)
    after = remote(case, "projects", "double-project")
    assert all(t["status"] == "in_progress" for t in after["tasks"])
    return {"same_runtime_user": CONFIG["user_id"], "in_progress": tids,
            "scope": "Real metadata ack; no model/runtime concurrent execution or RepoMesh lease exists"}


def cancellation():
    case, tid = "cancel", "cancel-task"
    project(case, "cancel-project", [tid])
    assert delegate(case, "cancel-project", tid, role="leader")["ok"]
    assert invoke(case, "taskflow", "ack_task", taskId=tid)["ok"]
    output = workspace(case) / "external-simulator-heartbeat.txt"
    child_code = "import pathlib,time,sys; p=pathlib.Path(sys.argv[1]);\nfor n in range(100):\n p.open('a').write(str(n)+'\\n'); time.sleep(0.1)"
    child = subprocess.Popen([sys.executable, "-c", child_code, str(output)])
    try:
        time.sleep(0.4)
        before = output.read_text().splitlines()
        result = invoke(case, "taskflow", "cancel_task", taskId=tid, role="leader", reason="isolated live cancellation validation")
        time.sleep(0.4)
        after = output.read_text().splitlines()
        assert result["ok"] and result["synced"]
        assert remote(case, "tasks", tid)["status"] == "cancelled"
        assert child.poll() is None and len(after) > len(before)
        refused = invoke(case, "taskflow", "ack_task", taskId=tid)
        assert not refused["ok"] and "terminal task" in refused["error"]
        return {"metadata_cancelled": True, "later_ack_denied": True, "external_process_pid": child.pid,
                "heartbeat_lines_before": len(before), "heartbeat_lines_after": len(after), "external_process_alive_after_cancel": True,
                "scope": "Explicit externally spawned simulated business process, NOT a real AgentTeams-launched Worker process"}
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)
        TRACE.append({"operation": "cleanup-only-own-external-simulator", "pid": child.pid, "exit_code": child.returncode})


def storage_failure():
    case = "storage-failure"
    before = project(case, "failure-project", ["failure-old"])
    old = os.environ.get("MC_HOST_agentteams")
    endpoint = urllib.parse.urlsplit(os.environ.get("AGENTTEAMS_FS_ENDPOINT", "http://127.0.0.1:9000"))
    # Process-local invalid credentials against real MinIO; never edit global mc alias.
    os.environ["MC_HOST_agentteams"] = f"{endpoint.scheme}://validation-invalid:validation-invalid@{endpoint.hostname}:{endpoint.port or 9000}"
    try:
        failed_stat = invoke(case, "filesync", "stat", path="shared/projects/failure-project/meta.json")
        result = invoke(case, "projectflow", "plan_dag", projectId="failure-project", tasks=[{"taskId": "failure-new"}])
    finally:
        if old is None:
            os.environ.pop("MC_HOST_agentteams", None)
        else:
            os.environ["MC_HOST_agentteams"] = old
    after = remote(case, "projects", "failure-project")
    local = json.loads((workspace(case) / "shared/projects/failure-project/meta.json").read_text())
    assert not failed_stat["ok"] and result["ok"]
    assert after == before and local["tasks"][0]["task_id"] == "failure-new"
    return {"fault": "only this process's mc alias credentials invalid for real MinIO", "real_filesync_stat_failed": True,
            "plan_tool_ok": True, "remote_unchanged": True, "remote_task": after["tasks"][0]["task_id"],
            "local_task": local["tasks"][0]["task_id"]}


for number, name, fn in [(1,"role_override",role_override), (2,"paused_delegation",paused),
                         (3,"paused_inflight_plan_dag",inflight_replan), (4,"task_collision_and_retry",collision_retry),
                         (5,"same_worker_double_ack",double_ack), (6,"cancel_external_process",cancellation),
                         (7,"real_storage_failure",storage_failure)]:
    started = time.perf_counter()
    try:
        value = fn()
        result = {"id": f"THL-{number:02}", "name": name, "status": "OBSERVATION_CONFIRMED_REAL_SERVICES", "observed": value}
    except Exception as exc:
        result = {"id": f"THL-{number:02}", "name": name, "status": "FAILED_OR_BLOCKED", "error": type(exc).__name__ + ": " + str(exc)}
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    RESULTS.append(result)
result = {"executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "run_id": CONFIG["run_id"],
          "upstream_source_sha256": hashlib.sha256(Path(server.__file__).read_bytes()).hexdigest(),
          "python": sys.version, "workspace": str(BASE), "storage_prefix": PREFIX,
          "boundary": "Unmodified native call_tool, real mc MinIO, real Matrix HTTP, no model or RepoMesh controlled adapter",
          "results": RESULTS, "trace": TRACE}
serialized = json.dumps(result, ensure_ascii=False, indent=2)
serialized = serialized.replace(CONFIG["token"], "[REDACTED]")
print(serialized)
sys.exit(0 if all(r["status"] == "OBSERVATION_CONFIRMED_REAL_SERVICES" for r in RESULTS) else 1)
