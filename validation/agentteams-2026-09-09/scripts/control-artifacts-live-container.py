"""Real native attachment/attempt-path validation; no fake transport or model."""
import base64
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

BASE = Path("/tmp/repomesh-artifacts") / CONFIG["run_id"]
PREFIX = CONFIG["shared_prefix"]
PID = "artifact-" + CONFIG["run_id"] + "-project"
OLD = "artifact-" + CONFIG["run_id"] + "-attempt-1"
NEW = "artifact-" + CONFIG["run_id"] + "-attempt-2"
TRACE, DOWNLOADS = [], []
os.environ.update(AGENTTEAMS_AGENT_ROLE="worker", AGENTTEAMS_MATRIX_URL="http://127.0.0.1:6167",
                  AGENTTEAMS_MATRIX_USER_ID=CONFIG["publisher_id"], AGENTTEAMS_WORKER_MATRIX_TOKEN=CONFIG["publisher_token"])
REDACTIONS = [CONFIG["publisher_token"], CONFIG["recipient_token"]] + [v for k, v in os.environ.items()
                if v and len(v) >= 8 and any(s in k.upper() for s in ("TOKEN", "PASSWORD", "SECRET", "API_KEY"))]


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(**values):
    TRACE.append({"at_utc": stamp(), **values})


def clean(text):
    for value in sorted(set(REDACTIONS), key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    return text


def mc(*args):
    result = subprocess.run(["mc", *map(str, args)], capture_output=True, timeout=30)
    record(transport="real-mc", args=list(map(str, args)), returncode=result.returncode,
           stdout_b64=base64.b64encode(result.stdout).decode(), stderr=result.stderr.decode(errors="replace"))
    if result.returncode:
        raise RuntimeError("Real mc failed; raw redacted trace retained")
    return result.stdout


def matrix(method, path, data=None, who="publisher", binary=False):
    token = CONFIG[who + "_token"]
    request = urllib.request.Request("http://127.0.0.1:6167" + path, method=method,
        data=json.dumps(data, ensure_ascii=False).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as exc:
        response = exc
    raw = response.read()
    try:
        value = json.loads(raw) if not binary else None
    except ValueError:
        value = raw.decode(errors="replace")
    record(transport="real-Matrix-HTTP", method=method, path=path, request=data, identity=CONFIG[who + "_id"],
           status=response.code, response=value, response_sha256=sha(raw), response_size=len(raw),
           response_b64=base64.b64encode(raw).decode() if binary else None)
    return response.code, raw if binary else value


def q(value):
    return urllib.parse.quote(value, safe="")


def invoke(tool, action, **arguments):
    args = {"action": action, "workspaceDir": str(BASE), "storage": {"sharedPrefix": PREFIX}, **arguments}
    result = json.loads(server.call_tool(tool, args)["content"][0]["text"])
    record(transport="real-server.call_tool", tool=tool, arguments=args, response=result)
    return result


def task_bytes(tid, name):
    return mc("cat", f"{PREFIX}/tasks/{tid}/{name}")


def snapshot(tid):
    files = {name: task_bytes(tid, name) for name in ("meta.json", "result.md", "output.txt")}
    return {"task_id": tid, "metadata": json.loads(files["meta.json"]),
            "hashes": {name: sha(data) for name, data in files.items()},
            "files_b64": {name: base64.b64encode(data).decode() for name, data in files.items()}}


def write_outputs(tid, revision):
    directory = BASE / "shared/tasks" / tid
    directory.mkdir(parents=True, exist_ok=True)
    contents = {
        "result.md": f"# Isolated result\n\nRun: {CONFIG['run_id']}\nTask: {tid}\nRevision: {revision}\n验证附件完整性。\n".encode(),
        "output.txt": f"Run={CONFIG['run_id']}\nTask={tid}\nRevision={revision}\nOutput=unique-{tid}-{revision}\n输出字节必须一致。\n".encode(),
    }
    for name, data in contents.items():
        (directory / name).write_bytes(data)
    return contents


def download(artifact, who="recipient", phase="before-leave"):
    mxc = artifact["mxcUri"]
    parsed = urllib.parse.urlsplit(mxc)
    assert parsed.scheme == "mxc" and parsed.netloc and parsed.path
    suffix = q(parsed.netloc) + "/" + q(parsed.path.lstrip("/"))
    # Try the authenticated client-media endpoint first. Only fall back for a
    # genuinely unsupported route, preserving that response as evidence.
    path = "/_matrix/client/v1/media/download/" + suffix
    code, raw = matrix("GET", path, who=who, binary=True)
    endpoint = "authenticated-client-media"
    if code in (404, 405):
        path = "/_matrix/media/v3/download/" + suffix
        code, raw = matrix("GET", path, who=who, binary=True)
        endpoint = "legacy-media-v3"
    value = {"phase": phase, "identity": CONFIG[who + "_id"], "source_path": artifact["sourcePath"],
             "event_id": artifact["eventId"], "mxc_uri": mxc, "http_status": code, "endpoint": endpoint,
             "size": len(raw), "sha256": sha(raw), "bytes_b64": base64.b64encode(raw).decode()}
    DOWNLOADS.append(value)
    return value


def submit(tid, revision, parent_event):
    contents = write_outputs(tid, revision)
    response = invoke("taskflow", "submit_task", taskId=tid, summary="Complete small attachment fixture " + revision,
                      status="SUCCESS", deliverables=[f"shared/tasks/{tid}/output.txt"], parentEventId=parent_event)
    assert response["ok"] and response["synced"] and response["task"]["status"] == "submitted", response
    assert response["task"]["project_id"] == PID and response["task"]["task_id"] == tid
    artifacts = response["publishedArtifacts"]
    assert len(artifacts) == 2 and all(item["status"] == "published" for item in artifacts), artifacts
    checked = []
    for artifact in artifacts:
        source = artifact["sourcePath"]
        assert source.startswith(f"shared/tasks/{tid}/") and tid in artifact["filename"]
        expected = contents[Path(source).name]
        code, event = matrix("GET", f"/_matrix/client/v3/rooms/{q(CONFIG['room'])}/event/{q(artifact['eventId'])}", who="recipient")
        assert code == 200 and event["sender"] == CONFIG["publisher_id"]
        content = event["content"]
        assert content["msgtype"] == "m.file" and content["url"] == artifact["mxcUri"]
        assert content["body"] == artifact["filename"] and content["info"]["size"] == len(expected)
        assert content["m.relates_to"]["event_id"] == parent_event
        downloaded = download(artifact)
        assert downloaded["http_status"] == 200 and downloaded["sha256"] == sha(expected)
        stored = task_bytes(tid, Path(source).name)
        assert stored == expected
        checked.append({"artifact": artifact, "task_id": tid, "revision": revision,
                        "local_minio_download_sha256": sha(expected), "all_three_bytes_equal": True,
                        "download": downloaded})
    result = invoke("taskflow", "check_task", taskId=tid, role="leader")
    assert result["ok"] and result["effective"] and not result["validationErrors"]
    return {"submit_response": response, "verified_artifacts": checked, "check_task": result}


def main():
    initial_hash = sha(Path(server.__file__).read_bytes())
    base_meta = {"project_id": PID, "title": "Two task IDs represent fixture Attempts only", "team_id": CONFIG["team"],
                 "source": "matrix", "source_room_id": CONFIG["room"], "status": "active", "plan_type": "dag",
                 "tasks": [{"task_id": tid, "title": tid, "status": "planned", "depends_on": [],
                            "assigned_to": CONFIG["publisher_id"]} for tid in (OLD, NEW)]}
    path = BASE / "shared/projects" / PID / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(base_meta, indent=2) + "\n")
    mc("cp", path, f"{PREFIX}/projects/{PID}/meta.json")
    delegate_events = {}
    for tid in (OLD, NEW):
        assigned = invoke("taskflow", "delegate_task", projectId=PID, taskId=tid, role="leader",
                          assignedTo=CONFIG["publisher_id"], roomId=CONFIG["room"], spec="Small attachment validation only")
        assert assigned["ok"] and assigned["synced"]
        delegate_events[tid] = assigned["task"]["eventId"]
        acknowledged = invoke("taskflow", "ack_task", taskId=tid)
        assert acknowledged["ok"] and acknowledged["synced"]
    old_first = submit(OLD, "old-original", delegate_events[OLD])
    new_result = submit(NEW, "new-current", delegate_events[NEW])
    new_before_late = snapshot(NEW)
    old_before_late = snapshot(OLD)
    old_late = submit(OLD, "old-late-resubmission", delegate_events[OLD])
    new_after_late = snapshot(NEW)
    old_after_late = snapshot(OLD)
    assert new_before_late == new_after_late, "Old task submission must not mutate distinct new task path/metadata"
    assert old_before_late["hashes"]["output.txt"] != old_after_late["hashes"]["output.txt"]
    old_media_reread = download(old_first["verified_artifacts"][1]["artifact"], phase="old-original-after-late")
    assert old_media_reread["sha256"] == old_first["verified_artifacts"][1]["local_minio_download_sha256"]
    remote_project = json.loads(mc("cat", f"{PREFIX}/projects/{PID}/meta.json"))
    assert all(node["status"] == "submitted" for node in remote_project["tasks"])
    # Only recipient Alice leaves this newly created room; every other room
    # and publisher Bob's membership remains untouched.
    code, leave = matrix("POST", f"/_matrix/client/v3/rooms/{q(CONFIG['room'])}/leave", {}, who="recipient")
    assert code == 200
    code, joined = matrix("GET", "/_matrix/client/v3/joined_rooms", who="recipient")
    assert code == 200 and CONFIG["room"] not in joined["joined_rooms"]
    artifact = new_result["verified_artifacts"][1]["artifact"]
    event_code, old_event = matrix("GET", f"/_matrix/client/v3/rooms/{q(CONFIG['room'])}/event/{q(artifact['eventId'])}", who="recipient")
    after_leave = download(artifact, phase="recipient-left-own-case-room")
    permission = {"recipient": CONFIG["recipient_id"], "left_room": CONFIG["room"], "leave_http_status": 200,
                  "room_absent_from_joined_rooms": True, "previous_event_http_status": event_code,
                  "previous_attachment_download": after_leave,
                  "bytes_still_equal_when_200": after_leave["http_status"] == 200 and after_leave["sha256"] == new_result["verified_artifacts"][1]["local_minio_download_sha256"],
                  "boundary": "Existing attachment known while joined; leaving is not a product-level read-right revocation or erasure of prior downloads"}
    result = {"executed_at_utc": stamp(), "run_id": CONFIG["run_id"], "project_id": PID,
              "workspace": str(BASE), "shared_prefix": PREFIX, "room": CONFIG["room"],
              "fixture_mapping": {"logical_task": "fixture-logical-task-" + CONFIG["run_id"],
                                  "attempt_1_upstream_task_id": OLD, "attempt_2_upstream_task_id": NEW,
                                  "persisted_repomesh_mapping": False},
              "source_sha256_before": initial_hash, "source_sha256_after": sha(Path(server.__file__).read_bytes()),
              "old_first_submission": old_first, "new_submission": new_result, "old_late_submission": old_late,
              "new_before_late": new_before_late, "new_after_late": new_after_late,
              "old_before_late": old_before_late, "old_after_late": old_after_late,
              "new_metadata_and_files_unchanged": True, "old_original_media_still_original": True,
              "project_after_late": remote_project, "recipient_leave_observation": permission,
              "downloads": DOWNLOADS, "trace": TRACE,
              "boundary": "Unmodified native MCP, real mc/Matrix media and events, no fake transport, no model, two fixture-encoded task IDs, no RepoMesh Attempt authority"}
    assert result["source_sha256_before"] == result["source_sha256_after"]
    print(clean(json.dumps(result, ensure_ascii=False, indent=2)))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(clean(json.dumps({"error": type(exc).__name__ + ": " + str(exc), "run_id": CONFIG["run_id"],
                               "trace": TRACE, "downloads": DOWNLOADS}, ensure_ascii=False, indent=2)))
        raise SystemExit(1)
