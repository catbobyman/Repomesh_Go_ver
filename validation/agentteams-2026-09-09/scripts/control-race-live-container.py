"""Real Controller/MCP/MinIO/Matrix with explicit process-local transport faults.

The source files are unmodified. Only this harness replaces server._filesync
with a wrapper that calls the real function, adding a scheduling barrier or
invalid credentials for narrowly selected upload calls. No service restart.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CONFIG = json.load(sys.stdin)
sys.dont_write_bytecode = True
sys.path.insert(0, CONFIG["source_dir"])
import server

BASE = Path("/tmp/repomesh-control-race") / CONFIG["run_id"]
TEAM = "coverage-race-" + CONFIG["run_id"]
PREFIX = "agentteams/rv-a-storage/teams/" + TEAM + "/shared"
TRACE, RESULTS = [], []
os.environ.update(AGENTTEAMS_AGENT_ROLE="worker", AGENTTEAMS_MATRIX_URL="http://127.0.0.1:6167",
                  AGENTTEAMS_MATRIX_USER_ID=CONFIG["user_id"], AGENTTEAMS_WORKER_MATRIX_TOKEN=CONFIG["token"])
ADMIN_TOKEN = Path("/var/run/agentteams/cli-token").read_text().strip()
REDACTIONS = [CONFIG["token"], ADMIN_TOKEN] + [v for k, v in os.environ.items()
                if v and len(v) >= 8 and any(x in k.upper() for x in ("PASSWORD", "TOKEN", "SECRET", "API_KEY"))]


def clean(text):
    for value in sorted(set(REDACTIONS), key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    return text


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def record(**value):
    TRACE.append({"at_utc": stamp(), **value})


def mc(*args):
    result = subprocess.run(["mc", *map(str, args)], capture_output=True, text=True, timeout=35)
    record(transport="real-mc-fixture", args=list(map(str, args)), returncode=result.returncode,
           stdout=result.stdout, stderr=result.stderr)
    if result.returncode:
        raise RuntimeError("Real mc fixture request failed; see redacted trace")
    return result.stdout


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def workspace(case):
    return BASE / case


def ident(case, kind):
    return "cov-" + CONFIG["run_id"] + "-" + case + "-" + kind


def project(case, pid, tid, status="planned"):
    value = {"project_id": pid, "title": pid, "team_id": TEAM, "source": "matrix",
             "source_room_id": CONFIG["room"], "plan_type": "dag", "status": "active",
             "tasks": [{"task_id": tid, "title": tid, "status": status,
                        "assigned_to": CONFIG["user_id"], "depends_on": []}]}
    path = workspace(case) / "shared/projects" / pid / "meta.json"
    dump(path, value)
    mc("cp", path, f"{PREFIX}/projects/{pid}/meta.json")
    return value


def remote(kind, name):
    return json.loads(mc("cat", f"{PREFIX}/{kind}/{name}/meta.json"))


def http(method, path, body=None, matrix=False):
    base = "http://127.0.0.1:6167" if matrix else "http://127.0.0.1:8090"
    req = urllib.request.Request(base + path, method=method,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + (CONFIG["token"] if matrix else ADMIN_TOKEN),
                 "Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=25)
    except urllib.error.HTTPError as exc:
        response = exc
    raw = response.read().decode()
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw
    record(transport="real-Matrix-HTTP" if matrix else "real-Controller-HTTP", method=method,
           path=path, request=body, status=response.code, response=value)
    return response.code, value


def api(pid, action, body=None):
    return http("POST", "/api/v1/projects/" + urllib.parse.quote(pid, safe="") + "/" + action
                + "?team=" + urllib.parse.quote(TEAM, safe=""), {} if body is None else body)


def timeline():
    code, value = http("GET", "/_matrix/client/v3/rooms/" + urllib.parse.quote(CONFIG["room"], safe="")
                       + "/messages?dir=b&limit=100", matrix=True)
    assert code == 200
    return value["chunk"]


def invoke(case, tool, action, **kwargs):
    arguments = {"action": action, "workspaceDir": str(workspace(case)),
                 "storage": {"sharedPrefix": PREFIX}, **kwargs}
    result = json.loads(server.call_tool(tool, arguments)["content"][0]["text"])
    record(transport="real-server.call_tool", tool=tool, arguments=arguments, response=result)
    return result


def delegate_args(pid, tid):
    return dict(projectId=pid, taskId=tid, assignedTo=CONFIG["user_id"], roomId=CONFIG["room"],
                spec="Isolated race validation only; no model or repository actions", role="leader")


def native_transport_wrapper(mode, case, pid, tid):
    original = server._filesync
    state = {"barrier_fired": False, "faulted_paths": [], "source_function": "server._filesync"}

    def wrapped(arguments):
        action, path = arguments.get("action"), arguments.get("path", "")
        fault = False
        task_file = workspace(case) / "shared/tasks" / tid / "meta.json"
        task = json.loads(task_file.read_text()) if task_file.is_file() else {}
        if mode in ("task-upload-fault", "project-and-task-upload-fault") and action == "push":
            targets = {f"shared/tasks/{tid}"}
            if mode == "project-and-task-upload-fault":
                targets.add(f"shared/projects/{pid}")
            fault = path in targets and task.get("status") == "assigned" and bool(task.get("eventId"))
        record(transport="instrumented-filesync-enter", mode=mode, action=action, path=path,
               local_task_status=task.get("status"), injecting_invalid_credentials=bool(fault))
        if fault:
            # Verify the notification is really readable before denying its
            # assigned-state write. No synthetic Matrix response is used.
            event_id = task["eventId"]
            count = sum(event.get("event_id") == event_id for event in timeline())
            assert count == 1, "Assignment event must exist before the upload fault"
            old = os.environ.get("MC_HOST_agentteams")
            endpoint = urllib.parse.urlsplit(os.environ.get("AGENTTEAMS_FS_ENDPOINT", "http://127.0.0.1:9000"))
            os.environ["MC_HOST_agentteams"] = f"{endpoint.scheme}://coverage-invalid:coverage-invalid@{endpoint.hostname}:{endpoint.port or 9000}"
            try:
                result = original(arguments)
            finally:
                if old is None:
                    os.environ.pop("MC_HOST_agentteams", None)
                else:
                    os.environ["MC_HOST_agentteams"] = old
            state["faulted_paths"].append(path)
            record(transport="real-MinIO-auth-fault", action=action, path=path,
                   matrix_event_verified=event_id, response=result)
            assert not result.get("ok"), "Injected credentials must produce an actual transport failure"
        else:
            result = original(arguments)
        record(transport="instrumented-filesync-return", action=action, path=path, response=result)
        if mode == "pause-after-pull" and not state["barrier_fired"] and action == "pull" and path == f"shared/projects/{pid}/meta.json":
            assert result.get("ok"), "Barrier requires a successful native pull"
            local = json.loads((workspace(case) / "shared/projects" / pid / "meta.json").read_text())
            assert local["status"] == "active"
            code, value = api(pid, "pause", {"reason": "MCP pull/upload barrier validation"})
            paused = remote("projects", pid)
            assert code == 200 and paused["status"] == "paused", (code, value)
            state.update(barrier_fired=True, pulled_before_pause=local, rest_pause_response=value, remote_paused=paused)
            record(operation="barrier-released-after-real-REST-pause", project_id=pid,
                   local_status=local["status"], remote_status=paused["status"])
        return result

    server._filesync = wrapped
    return original, state


def child_operation():
    case, pid, tid = CONFIG["case"], CONFIG["project_id"], CONFIG["task_id"]
    mode = CONFIG.get("fault_mode", "none")
    original, state = native_transport_wrapper(mode, case, pid, tid)
    try:
        if mode == "pause-after-pull":
            response = invoke(case, "projectflow", "plan_dag", projectId=pid,
                              tasks=[{"taskId": ident(case, "new-task"), "title": "MCP new plan"}])
        else:
            response = invoke(case, "taskflow", "delegate_task", **delegate_args(pid, tid))
    finally:
        server._filesync = original
    return {"pid": os.getpid(), "fault_mode": mode, "fault_state": state, "tool_response": response,
            "local_project": json.loads((workspace(case) / "shared/projects" / pid / "meta.json").read_text()),
            "local_task": json.loads((workspace(case) / "shared/tasks" / tid / "meta.json").read_text())
                          if (workspace(case) / "shared/tasks" / tid / "meta.json").is_file() else None}


def child(case, pid, tid, mode):
    conf = {**CONFIG, "mode": "child", "case": case, "project_id": pid, "task_id": tid, "fault_mode": mode}
    started = stamp()
    process = subprocess.run([sys.executable, __file__], input=json.dumps(conf), capture_output=True,
                             text=True, encoding="utf-8", timeout=100)
    # Preserve every child stdout/stderr as distinct, redacted on-container
    # files and in the host result, including a failed child.
    stem = BASE / (case + "-" + mode + "-" + str(time.time_ns()))
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".stdout.json").write_text(clean(process.stdout))
    stem.with_suffix(".stderr.log").write_text(clean(process.stderr))
    record(operation="fresh-MCP-process", started_at_utc=started, mode=mode, case=case,
           returncode=process.returncode, stdout=process.stdout, stderr=process.stderr,
           raw_prefix=str(stem))
    if process.returncode:
        raise RuntimeError("MCP child exited nonzero; raw output retained")
    return json.loads(process.stdout)["result"]


def race():
    case = "pause-race"
    pid, tid = ident(case, "project"), ident(case, "old-task")
    before = project(case, pid, tid)
    outcome = child(case, pid, tid, "pause-after-pull")
    after = remote("projects", pid)
    assert outcome["fault_state"]["barrier_fired"] and outcome["tool_response"]["ok"]
    assert after["status"] == "active" and after["tasks"][0]["task_id"] == ident(case, "new-task")
    return {"classification": "NATIVE_GAP_REPRODUCED", "before": before, "child": outcome, "after": after,
            "conclusion": "Native MCP pull succeeds, REST pause persists, original MCP upload overwrites pause"}


def assignment_failure(both=False):
    case = "both-fail" if both else "task-fail"
    pid, tid = ident(case, "project"), ident(case, "task")
    project(case, pid, tid)
    first = child(case, pid, tid, "project-and-task-upload-fault" if both else "task-upload-fault")
    failed_project, failed_task = remote("projects", pid), remote("tasks", tid)
    reply = first["tool_response"]
    assert reply["ok"] is False and reply["synced"] is False and reply["retryable"] is True
    assert failed_task["status"] == "prepared" and first["local_task"]["status"] == "assigned"
    event = first["local_task"]["eventId"]
    retried = child(case, pid, tid, "none")
    after_project, after_task = remote("projects", pid), remote("tasks", tid)
    repeated = retried["tool_response"]
    assert repeated["ok"] and repeated["synced"] and repeated["notification"]["reused"]
    assert first["pid"] != retried["pid"] and repeated["task"]["eventId"] == event
    assert after_task["status"] == "assigned"
    events = timeline()
    assignment_events = [e for e in events if f"**{tid}**" in e.get("content", {}).get("body", "")]
    assert len(assignment_events) == 1 and assignment_events[0]["event_id"] == event
    expected = "planned" if both else "assigned"
    assert after_project["tasks"][0]["status"] == expected
    return {"classification": "NATIVE_GAP_REPRODUCED" if both else "SUPPORTED_RECOVERY_WITH_RETAINED_WORKSPACE",
            "first": first, "remote_after_failure": {"project": failed_project, "task": failed_task},
            "retry_fresh_process": retried, "remote_after_retry": {"project": after_project, "task": after_task},
            "matrix_event_id": event, "matrix_assignment_count": len(assignment_events),
            "conclusion": "Retry restores Task and reuses notification; Project remains planned" if both
                else "Retry restores assigned Task without another Matrix event; Project already persisted assigned"}


def states():
    case = "states"
    pid, tid = ident(case, "project"), ident(case, "task")
    project(case, pid, tid)
    assert invoke(case, "taskflow", "delegate_task", **delegate_args(pid, tid))["ok"]
    assert invoke(case, "taskflow", "ack_task", taskId=tid)["ok"]
    in_progress_code, _ = api(pid, "replan", {"tasks": [{"taskId": ident(case, "blocked-new")}]})
    submitted = invoke(case, "taskflow", "submit_task", taskId=tid, summary="Fixture result without a business artifact", status="SUCCESS", deliverables=[])
    assert submitted["ok"] and submitted["synced"]
    submitted_state = remote("projects", pid)
    submitted_code, _ = api(pid, "replan", {"tasks": [{"taskId": ident(case, "blocked-new")}]})
    complete_submitted_code, _ = api(pid, "complete")
    accepted = invoke(case, "projectflow", "accept_task_result", projectId=pid, taskId=tid, accepted=True, resultStatus="SUCCESS")
    assert accepted["ok"]
    completed_node = remote("projects", pid)
    next_code, _ = api(pid, "replan", {"tasks": [{"taskId": ident(case, "round2-task"), "title": "Next finite DAG"}]})
    next_round = remote("projects", pid)
    assert [in_progress_code, submitted_code, complete_submitted_code, next_code] == [409, 409, 409, 200]
    assert completed_node["status"] == "active" and completed_node["tasks"][0]["status"] == "completed"
    # A second Project has actual submit state and is intentionally left there
    # while A accepts its next DAG: this is independent native state, no RM tx.
    case_b = "partial-b"
    pb, tb = ident(case_b, "project"), ident(case_b, "task")
    project(case_b, pb, tb)
    assert invoke(case_b, "taskflow", "delegate_task", **delegate_args(pb, tb))["ok"]
    assert invoke(case_b, "taskflow", "ack_task", taskId=tb)["ok"]
    assert invoke(case_b, "taskflow", "submit_task", taskId=tb, summary="Second target still submitted", status="SUCCESS", deliverables=[])["ok"]
    b_code, _ = api(pb, "replan", {"tasks": [{"taskId": ident(case_b, "new")}]})
    persisted_pair = {"a": remote("projects", pid), "b": remote("projects", pb)}
    assert b_code == 409 and persisted_pair["b"]["tasks"][0]["status"] == "submitted"
    # Reuse the real completed-node fixture by accepting round2 (native accept
    # has no Task-result existence check), then close Project via REST.
    native_accept = invoke(case, "projectflow", "accept_task_result", projectId=pid, taskId=ident(case, "round2-task"), accepted=True, resultStatus="SUCCESS")
    assert native_accept["ok"]
    complete_code, _ = api(pid, "complete")
    closed_code, _ = api(pid, "replan", {"tasks": [{"taskId": ident(case, "after-close")}]})
    assert [complete_code, closed_code] == [200, 409]
    return {"classification": "NATIVE_CONTRACT_AND_PARTIAL_APPLICATION_CONFIRMED", "http_codes": {
                "in_progress_replan": in_progress_code, "submitted_replan": submitted_code,
                "submitted_complete": complete_submitted_code, "completed_node_next_dag": next_code,
                "second_target_submitted_replan": b_code, "terminal_project_complete": complete_code,
                "completed_project_replan": closed_code},
            "submitted_state": submitted_state, "completed_node_state": completed_node,
            "next_round": next_round, "partial_target_readback": persisted_pair,
            "closed_project": remote("projects", pid),
            "boundary": "No model/workload/artifact acceptance or RepoMesh multi-target transaction; round2 accepted by native metadata tool only"}


def prepare_team_prefix():
    # Controller scans prefixes belonging to actual Team CRs. A bare MinIO
    # directory is intentionally insufficient. Use a stopped unmanaged Worker
    # reference so this registration cannot launch an Agent runtime.
    name = "coverage-race-leader-" + CONFIG["run_id"]
    code, worker = http("POST", "/api/v1/workers", {"name": name, "runtime": "qwenpaw",
        "model": "deepseek-chat", "state": "Stopped", "containerManaged": False})
    assert code == 201 and worker.get("state") == "Stopped" and worker.get("containerManaged") is False, (code, worker)
    name = worker["name"]
    code, team = http("POST", "/api/v1/teams", {"name": TEAM, "teamName": TEAM,
        "description": "Dedicated native race fixture; stopped unmanaged leader; no model tasks",
        "workerMembers": [{"name": name, "role": "team_leader"}]})
    assert code == 201 and team["name"] == TEAM, (code, team)
    return {"worker": worker, "team": team, "boundary": "Real resource registration only; Worker explicitly stopped and unmanaged"}


def main():
    before_hash = hashlib.sha256(Path(server.__file__).read_bytes()).hexdigest()
    if CONFIG.get("mode") == "child":
        result = child_operation()
        output = {"result": result, "trace": TRACE, "source_sha256": before_hash}
        print(clean(json.dumps(output, ensure_ascii=False, indent=2)))
        return 0
    resource_fixture = prepare_team_prefix()
    for case, fn in (("RACE-01", race), ("RACE-02", assignment_failure),
                     ("RACE-03", lambda: assignment_failure(True)), ("STATE-01", states)):
        try:
            observed = fn()
            RESULTS.append({"id": case, "status": "OBSERVATION_CONFIRMED", "observed": observed})
        except Exception as exc:
            RESULTS.append({"id": case, "status": "FAILED_OR_BLOCKED", "error": type(exc).__name__ + ": " + str(exc)})
    after_hash = hashlib.sha256(Path(server.__file__).read_bytes()).hexdigest()
    output = {"executed_at_utc": stamp(), "run_id": CONFIG["run_id"], "source_sha256_before": before_hash,
              "source_sha256_after": after_hash, "workspace": str(BASE), "shared_prefix": PREFIX,
              "matrix_room": CONFIG["room"], "resource_fixture": resource_fixture,
              "python": sys.version, "results": RESULTS, "trace": TRACE,
              "boundary": "Unmodified disk source; real services with explicit process-local filesync barrier/auth-fault wrapper; fresh Python retry processes; no runtime/model or RepoMesh transaction"}
    print(clean(json.dumps(output, ensure_ascii=False, indent=2)))
    return 0 if before_hash == after_hash and all(r["status"] == "OBSERVATION_CONFIRMED" for r in RESULTS) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(clean(json.dumps({"error": type(exc).__name__ + ": " + str(exc), "trace": TRACE}, ensure_ascii=False)))
        raise SystemExit(1)
