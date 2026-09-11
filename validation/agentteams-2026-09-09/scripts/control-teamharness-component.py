#!/usr/bin/env python3
"""Run real TeamHarness functions with explicit local fake external transports.

PASS means an assertion about the observed component behavior was reproduced.
It never means RepoMesh acceptance or a deployed AgentTeams test passed.
No production source is changed; all filesystem fixtures stay in evidence/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.parse
import urllib.request
from unittest import mock

sys.dont_write_bytecode = True
CASES = []


def case(identifier, title, at, disposition, lines):
    def register(fn):
        CASES.append((identifier, title, at, disposition, lines, fn))
        return fn
    return register


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


class JsonResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


class Fixture:
    """Transport-only replacement: mc runs and Matrix HTTP, with explicit logs."""
    remote_prefix = "control-store/teams/control-team/shared/"
    room = "!control-room:validation.invalid"
    worker = "@control-worker:validation.invalid"

    def __init__(self, root, module):
        self.root = root
        self.module = module
        self.workspace = root / "workspace"
        self.remote = root / "fake-object-store"
        self.workspace.mkdir(parents=True)
        self.remote.mkdir(parents=True)
        self.calls = []
        self.transport = []
        self.events = {}
        self.fail_direction = None
        self.before_project_push = None
        self.runtime_role = "worker"

    def project(self, pid, status="active", task_status="planned", task_ids=None):
        value = {
            "project_id": pid, "title": pid, "status": status,
            "plan_type": "dag", "team_id": "control-team", "source": "matrix",
            "source_room_id": self.room,
            "tasks": [{"task_id": tid, "title": tid, "status": task_status,
                       "assigned_to": self.worker, "depends_on": []}
                      for tid in (task_ids or ["T1"])],
        }
        dump(self.local_project(pid), value)
        dump(self.remote_project(pid), value)
        return value

    def task(self, pid, tid="T1", status="assigned"):
        value = {"project_id": pid, "task_id": tid, "status": status,
                 "room_id": self.room, "assigned_to": self.worker,
                 "spec_path": f"shared/tasks/{tid}/spec.md"}
        dump(self.local_task(tid), value)
        dump(self.remote_task(tid), value)
        for base in (self.workspace / "shared", self.remote):
            (base / "tasks" / tid / "spec.md").write_text("Control validation fixture only.\n", encoding="utf-8")
        return value

    def local_project(self, pid):
        return self.workspace / "shared" / "projects" / pid / "meta.json"

    def remote_project(self, pid):
        return self.remote / "projects" / pid / "meta.json"

    def local_task(self, tid):
        return self.workspace / "shared" / "tasks" / tid / "meta.json"

    def remote_task(self, tid):
        return self.remote / "tasks" / tid / "meta.json"

    def invoke(self, tool, action, **values):
        args = {"action": action, "workspaceDir": str(self.workspace),
                "storage": {"sharedPrefix": self.remote_prefix.rstrip("/")}, **values}
        response = self.module.call_tool(tool, args)
        value = json.loads(response["content"][0]["text"])
        self.calls.append({"tool": tool, "arguments": args, "response": value})
        return value

    def delegate(self, pid, tid="T1", **extra):
        return self.invoke("taskflow", "delegate_task", projectId=pid, taskId=tid,
                           assignedTo=self.worker, roomId=self.room,
                           spec=f"Fixture specification for {pid}/{tid}", **extra)

    def filesync_subprocess(self, command, **_kwargs):
        """Emulate only the cp/mirror operations emitted by actual _filesync.

        The local fake is not MinIO and makes no claim about real mc timing,
        atomicity, network, credentials, retries, or cross-system consistency.
        """
        command = [str(value) for value in command]
        if len(command) < 4 or command[0] != "mc" or command[1] not in {"cp", "mirror"}:
            raise AssertionError(f"Unexpected subprocess; not executed: {command}")
        source, destination = command[2:4]
        source_remote = source.startswith(self.remote_prefix)
        destination_remote = destination.startswith(self.remote_prefix)
        if source_remote == destination_remote:
            raise AssertionError("Expected one fake remote path and one fixture local path")
        direction = "pull" if source_remote else "push"
        entry = {"kind": "fake-mc", "direction": direction, "command": command}
        self.transport.append(entry)
        if self.fail_direction in {direction, "all"}:
            entry["injected_failure"] = True
            return subprocess.CompletedProcess(command, 1, "", f"Injected {direction} failure")
        if destination_remote and "/projects/" in destination and self.before_project_push:
            callback = self.before_project_push
            self.before_project_push = None
            callback()
            entry["after_external_write_barrier"] = True
        def resolve(value):
            if value.startswith(self.remote_prefix):
                target = self.remote / value[len(self.remote_prefix):].strip("/")
                assert target.resolve().is_relative_to(self.remote.resolve())
                return target
            target = Path(value)
            assert target.resolve().is_relative_to(self.workspace.resolve()), str(target)
            return target
        src, dst = resolve(source), resolve(destination)
        if not src.exists():
            entry["missing_source"] = str(src)
            return subprocess.CompletedProcess(command, 1, "", "No such fixture source")
        if command[1] == "cp":
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        else:
            excludes = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--exclude"]
            dst.mkdir(parents=True, exist_ok=True)
            for item in src.rglob("*"):
                relative = item.relative_to(src).as_posix()
                if any(fnmatch.fnmatch(relative, pattern) or relative.startswith(pattern.rstrip("/") + "/") for pattern in excludes):
                    continue
                if item.is_file():
                    target = dst / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
        entry["completed"] = True
        return subprocess.CompletedProcess(command, 0, "fixture copy complete", "")

    def matrix_http(self, request, **_kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if not url.startswith("https://matrix.validation.invalid/"):
            raise AssertionError(f"Unexpected network request; not executed: {url}")
        method = request.get_method()
        body = json.loads(request.data.decode()) if request.data else None
        entry = {"kind": "fake-Matrix", "method": method, "url": url, "body": body}
        self.transport.append(entry)
        if url.endswith("/members") and method == "GET":
            return JsonResponse({"chunk": [{"state_key": self.worker, "content": {"membership": "join"}}]})
        if "/send/m.room.message/" in url and method == "PUT":
            # This fake models stable transaction replay; real Matrix behavior
            # remains a separate deployment test. Existing-task reuse happens
            # before this transport and is asserted separately below.
            if url not in self.events:
                self.events[url] = f"$control-event-{len(self.events) + 1}"
            entry["event_id"] = self.events[url]
            return JsonResponse({"event_id": self.events[url]})
        raise AssertionError(f"Unexpected fake Matrix operation: {method} {url}")


@case("CONTROL-01", "Caller role overrides runtime role", ["AT-02"], "GAP_REPRODUCED", [471, 3628, 4100])
def role_override(f):
    f.project("issue-a")
    denied = f.delegate("issue-a")
    assert denied["ok"] is False and "leader role" in denied["error"], denied
    accepted = f.delegate("issue-a", role="leader")
    assert accepted["ok"] is True and accepted["task"]["status"] == "assigned", accepted
    assert len(f.events) == 1
    return {"runtime_role": f.module._runtime_role(), "role_parameter": "leader",
            "without_override_denied": True, "with_override_assigned": True}


@case("CONTROL-02", "Paused ready list is empty but direct delegation assigns", ["AT-02", "AT-03"], "GAP_REPRODUCED", [2974, 4100])
def paused_delegate(f):
    f.project("issue-a", status="paused")
    ready = f.invoke("projectflow", "ready_nodes", projectId="issue-a")
    assert ready["readyNodes"] == [], ready
    result = f.delegate("issue-a", role="leader")
    assert result["ok"] is True and result["task"]["status"] == "assigned", result
    remote = read(f.remote_project("issue-a"))
    assert remote["status"] == "paused" and remote["tasks"][0]["status"] == "assigned", remote
    return {"ready_nodes": [], "project_still_paused": True, "task_assigned": True}


@case("CONTROL-03", "Worker projectflow replaces paused in-progress DAG", ["AT-02", "AT-03"], "GAP_REPRODUCED", [3265, 3397])
def paused_plan(f):
    before = f.project("issue-a", status="paused", task_status="in_progress")
    tools = [tool["name"] for tool in f.module.list_tools()]
    assert "projectflow" in tools
    result = f.invoke("projectflow", "plan_dag", projectId="issue-a", tasks=[{"taskId": "replacement"}])
    after = read(f.remote_project("issue-a"))
    assert result["ok"] is True and [task["task_id"] for task in after["tasks"]] == ["replacement"], result
    assert after["status"] == "paused"
    return {"runtime_role": "worker", "projectflow_visible": True, "before": before, "after": after}


@case("CONTROL-04", "plan_dag reports ok after failed storage push", ["AT-04"], "GAP_REPRODUCED", [3397, 3416, 3823])
def failed_push(f):
    before = f.project("issue-a")
    f.fail_direction = "push"
    result = f.invoke("projectflow", "plan_dag", projectId="issue-a", tasks=[{"taskId": "T2"}])
    local, remote = read(f.local_project("issue-a")), read(f.remote_project("issue-a"))
    assert result["ok"] is True and local["tasks"][0]["task_id"] == "T2", result
    assert remote == before and local != remote
    return {"tool_ok": True, "local_task": "T2", "remote_task": "T1", "remote_unchanged": True}


@case("CONTROL-05", "plan_dag continues after failed authoritative pull", ["AT-04"], "GAP_REPRODUCED", [3239, 3275, 3397])
def failed_pull(f):
    f.project("issue-a")
    remote_before = read(f.remote_project("issue-a"))
    remote_before["status"] = "paused"
    remote_before["external_revision"] = "newer-pause"
    dump(f.remote_project("issue-a"), remote_before)
    f.fail_direction = "pull"
    result = f.invoke("projectflow", "plan_dag", projectId="issue-a", tasks=[{"taskId": "T2"}])
    after = read(f.remote_project("issue-a"))
    assert result["ok"] is True and after["status"] == "active", result
    assert "external_revision" not in after and after["tasks"][0]["task_id"] == "T2"
    return {"remote_before": remote_before, "remote_after": after, "pause_overwritten": True}


@case("CONTROL-06", "Delayed MCP push overwrites an intervening external pause", ["AT-04"], "GAP_REPRODUCED", [2505, 3397, 3823])
def stale_upload(f):
    f.project("issue-a")
    barrier = {}
    def external_pause():
        state = read(f.remote_project("issue-a"))
        state["status"] = "paused"
        state["external_revision"] = "simulated-controller-write-after-pull"
        dump(f.remote_project("issue-a"), state)
        barrier["remote_after_injected_write"] = state
    f.before_project_push = external_pause
    result = f.invoke("projectflow", "plan_dag", projectId="issue-a", tasks=[{"taskId": "T2"}])
    after = read(f.remote_project("issue-a"))
    assert barrier and result["ok"] is True and after["status"] == "active", result
    assert "external_revision" not in after
    return {**barrier, "remote_after_mcp_push": after,
            "external_writer": "direct fixture edit, NOT a running Controller REST call"}


@case("CONTROL-07", "Same-Team distinct Projects reuse the same task metadata", ["AT-05"], "GAP_REPRODUCED", [2807, 3811, 4131])
def task_collision(f):
    f.project("issue-a")
    f.project("issue-b")
    first = f.delegate("issue-a", role="leader")
    second = f.delegate("issue-b", role="leader")
    assert first["ok"] is True and second["ok"] is True
    assert second["task"]["project_id"] == "issue-a", second
    assert second["notification"]["reused"] is True and len(f.events) == 1
    assert read(f.remote_project("issue-b"))["tasks"][0]["status"] == "planned"
    return {"second_requested_project": "issue-b", "second_returned_project": "issue-a",
            "single_task_path": str(f.remote_task("T1")), "notification_reused": True}


@case("CONTROL-08", "Same logical delegation retry reuses assigned event", ["AT-05"], "SUPPORTED_COMPONENT_BEHAVIOR", [4131, 4291])
def delegation_retry(f):
    f.project("issue-a")
    first = f.delegate("issue-a", role="leader")
    second = f.delegate("issue-a", role="leader")
    assert first["ok"] is True and second["ok"] is True
    sends = [entry for entry in f.transport if entry["kind"] == "fake-Matrix" and entry["method"] == "PUT"]
    assert len(sends) == 1 and second["notification"]["reused"] is True
    assert first["task"]["eventId"] == second["task"]["eventId"]
    return {"notification_http_calls": len(sends), "event_id_reused_before_transport": True}


@case("CONTROL-09", "Distinct upstream task IDs preserve separate attempt records", ["AT-05"], "SUPPORTED_COMPONENT_BEHAVIOR", [2807, 4049])
def unique_task_ids(f):
    f.project("issue-a", task_ids=["a-round1-attempt1", "a-round1-attempt2"])
    first = f.delegate("issue-a", "a-round1-attempt1", role="leader")
    second = f.delegate("issue-a", "a-round1-attempt2", role="leader")
    assert first["ok"] is True and second["ok"] is True and len(f.events) == 2
    assert f.remote_task("a-round1-attempt1").exists() and f.remote_task("a-round1-attempt2").exists()
    assert first["task"]["eventId"] != second["task"]["eventId"]
    return {"separate_task_files": True, "separate_notification_ids": True,
            "limitation": "No RepoMesh Attempt, process, worktree, or Worker lease exists in this fixture"}


@case("CONTROL-10", "Cancellation persists terminal metadata and rejects later ack", ["AT-03", "AT-11"], "SEMANTIC_BOUNDARY_CONFIRMED", [4412, 3946])
def cancel_metadata(f):
    f.project("issue-a", task_status="in_progress")
    f.task("issue-a", status="in_progress")
    result = f.invoke("taskflow", "cancel_task", role="leader", taskId="T1", reason="component validation")
    rejected = f.invoke("taskflow", "ack_task", taskId="T1")
    assert result["ok"] is True and result["synced"] is True, result
    assert read(f.remote_task("T1"))["status"] == "cancelled"
    assert read(f.remote_project("issue-a"))["tasks"][0]["status"] == "cancelled"
    assert rejected["ok"] is False and "terminal task" in rejected["error"]
    return {"task_and_project_metadata_cancelled": True, "later_ack_rejected": True,
            "observed_external_operations": [entry["kind"] for entry in f.transport],
            "no_worker_process_present": True,
            "limitation": "This does NOT test actual process termination, container cleanup, or resource release"}


@case("CONTROL-11", "MCP completes a Project with an in-progress task", ["AT-02", "AT-11"], "GAP_REPRODUCED", [3557])
def premature_complete(f):
    f.project("issue-a", task_status="in_progress")
    result = f.invoke("projectflow", "complete_project", projectId="issue-a")
    after = read(f.remote_project("issue-a"))
    assert result["ok"] is True and after["status"] == "completed", result
    assert after["tasks"][0]["status"] == "in_progress"
    return {"project_status": "completed", "task_status": "in_progress", "runtime_role": "worker"}


@case("CONTROL-12", "Result acceptance defaults to completed without result evidence", ["AT-02", "AT-11"], "GAP_REPRODUCED", [3042, 3073])
def evidence_free_accept(f):
    f.project("issue-a")
    assert not f.local_task("T1").exists()
    result = f.invoke("projectflow", "accept_task_result", projectId="issue-a", taskId="T1")
    after = read(f.remote_project("issue-a"))
    assert result["ok"] is True and result["accepted"] is True
    assert after["tasks"][0]["status"] == "completed" and not f.local_task("T1").exists()
    return {"task_was_planned": True, "taskmeta_absent": True, "evidence_files_absent": True,
            "accepted": True, "node_status": "completed"}


@case("CONTROL-13", "submit_task can report ok while remote task sync fails", ["AT-04", "AT-11"], "SEMANTIC_BOUNDARY_CONFIRMED", [4363, 4403])
def submit_sync_failure(f):
    f.project("issue-a", task_status="in_progress")
    f.task("issue-a", status="in_progress")
    f.fail_direction = "push"
    result = f.invoke("taskflow", "submit_task", taskId="T1", status="SUCCESS", summary="fixture", deliverables=[])
    assert result["ok"] is True and result["synced"] is False, result
    assert read(f.local_task("T1"))["status"] == "submitted"
    assert read(f.remote_task("T1"))["status"] == "in_progress"
    return {"tool_ok": True, "explicit_synced_field": False, "local_status": "submitted",
            "remote_status": "in_progress", "correct_consumer_must_check_synced": True}


@case("CONTROL-14", "Taskflow acknowledgement has no shared Worker busy reservation", ["AT-02", "AT-08"], "GAP_REPRODUCED", [4339])
def concurrent_worker_metadata(f):
    f.project("issue-a", task_ids=["A", "B"], task_status="assigned")
    f.task("issue-a", "A")
    f.task("issue-a", "B")
    first = f.invoke("taskflow", "ack_task", taskId="A")
    second = f.invoke("taskflow", "ack_task", taskId="B")
    assert first["ok"] is True and second["ok"] is True
    after = read(f.remote_project("issue-a"))
    assert all(task["status"] == "in_progress" for task in after["tasks"])
    return {"same_runtime_worker": f.worker, "in_progress_task_ids": ["A", "B"],
            "limitation": "Only acknowledgements; no two real Agent/model/command executions were started"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path)
    parser.add_argument("--output-root", type=Path)
    opts = parser.parse_args()
    root = (opts.output_root or Path(__file__).resolve().parents[1]).resolve()
    upstream = (opts.upstream or root / "upstream").resolve()
    source = upstream / "plugins/teamharness/mcp/server.py"
    evidence = root / "evidence"
    reports = root / "reports"
    evidence.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "-c", f"safe.directory={upstream.as_posix()}", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    digest_before = hashlib.sha256(source.read_bytes()).hexdigest()
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location("control_validation_teamharness_server", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runs = evidence / "control-workspaces"
    runs.mkdir(exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="component-", dir=runs))
    results = []
    for identifier, title, at, disposition, lines, fn in CASES:
        fixture = Fixture(run_root / identifier, module)
        # Isolate inherited credentials/configuration. The following token is
        # deliberately fake and the HTTP boundary never opens a connection.
        env = {"AGENTTEAMS_AGENT_ROLE": "worker",
               "AGENTTEAMS_MATRIX_URL": "https://matrix.validation.invalid",
               "AGENTTEAMS_WORKER_MATRIX_TOKEN": "CONTROL_FAKE_NOT_A_CREDENTIAL",
               "AGENTTEAMS_MATRIX_USER_ID": fixture.worker}
        result = {"id": identifier, "title": title, "at": at,
                  "expected_product_disposition": disposition,
                  "source_lines": lines, "fixture_directory": str(fixture.root)}
        try:
            with mock.patch.dict(os.environ, env, clear=True), \
                 mock.patch.object(subprocess, "run", fixture.filesync_subprocess), \
                 mock.patch.object(urllib.request, "urlopen", fixture.matrix_http):
                result["observations"] = fn(fixture)
            result["expectation_check"] = "PASS"
            result["observed_product_disposition"] = disposition
        except Exception as exc:
            result["expectation_check"] = "FAIL"
            result["observed_product_disposition"] = "UNDETERMINED_TEST_FAILED"
            result["error"] = str(exc)
            result["traceback"] = traceback.format_exc()
        result["tool_calls"] = fixture.calls
        result["transport_events"] = fixture.transport
        dump(fixture.root / "trace.json", result)
        results.append(result)
        print(f"{identifier}: {result['expectation_check']} | {result['observed_product_disposition']} | {title}")
    digest_after = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest_before == digest_after, "Upstream source must remain unchanged"
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {"created_at_utc": now, "git_commit": commit,
               "source_path": str(source), "source_sha256": digest_before,
               "source_unchanged": True, "python_version": sys.version,
               "execution_layer": "real upstream Python component functions",
               "entrypoint": "server.call_tool -> unmodified projectflow/taskflow/filesync",
               "replaced_boundaries": ["subprocess.run for mc cp/mirror => local file fake",
                                       "urllib.request.urlopen => deterministic Matrix HTTP fake"],
               "real_external_services_used": [], "deployment_acceptance": "NOT_TESTED",
               "pass_meaning": "Expected observation reproduced, not product acceptance",
               "results": results}
    dump(evidence / "control-component-results.json", payload)
    failed = sum(item["expectation_check"] != "PASS" for item in results)
    base_url = f"https://github.com/agentscope-ai/AgentTeams/blob/{commit}/plugins/teamharness/mcp/server.py"
    lines = ["# TeamHarness 原生工具组件实验", "",
             f"UTC: {now}  ", f"源码: `{commit}`  ", f"Python: `{sys.version.split()[0]}`  ",
             "执行入口：真实 `server.call_tool`，继续调用未改写的 projectflow/taskflow/filesync。", "",
             "**这是已执行的 Python 组件实验。Matrix HTTP 与 mc 文件传输被明确替换为本地 fake；没有部署 Controller、Matrix、MinIO、Agent runtime 或模型。PASS 只表示预期现象成功复现，绝不表示 AT 产品验收通过。**", "",
             f"共 {len(results)} 项组件实验，预期核对 {len(results)-failed} 项 PASS，{failed} 项 FAIL。源码 SHA-256 运行前后相同；没有改写上游生产文件。", "",
             "| 实验 | AT 范围 | 预期核对 | 观察分类 | 观察内容 |", "|---|---|---|---|---|"]
    for result in results:
        lines.append(f"| {result['id']} | {', '.join(result['at'])} | {result['expectation_check']} | {result['observed_product_disposition']} | {result['title']} |")
    lines += ["", "## 可复现方式", "", "在验证根目录运行：", "", "```powershell",
              "python scripts/control-teamharness-component.py", "```", "",
              "每次运行建立独立 evidence/control-workspaces/component-* 文件夹并保留逐例 trace.json、workspace/fake-object-store 任务与 Project 文件。聚合证据为 [control-component-results.json](../evidence/control-component-results.json)。脚本为 [control-teamharness-component.py](../scripts/control-teamharness-component.py)。", "",
              "## 判定边界", "",
              "- GAP_REPRODUCED：在原生工具组件入口复现 RepoMesh 规则尚未被该入口执行的缺口；不是已部署系统漏洞复现。", 
              "- SUPPORTED_COMPONENT_BEHAVIOR：在 fake 传输下组件的重试或唯一ID行为符合预期；真实 Matrix、存储、授权与重启仍未验证。",
              "- SEMANTIC_BOUNDARY_CONFIRMED：确认元数据及回执语义；cancel 未验证进程停止或资源释放，submit 回执显式返回 synced=false，正确适配端可识别，不能称该回执隐瞒同步失败。",
              "- CONTROL-06 以明确标记的 fixture 写入模拟 Controller 在 MCP 拉取之后成功修改共享对象；未执行真实 REST/ETag/MinIO 交错写。",
              "- CONTROL-14 仅证明两个同 Worker 任务都可被原生工具 ack 为 in_progress，不证明实际模型或命令并行。", "",
              "## 仍需部署及 RepoMesh 适配联调", "",
              "AT-02：可信调用身份、Controller/存储/Git/模型权限和网络隔离，原生工具不可绕过实际授权；保留必要心跳和唤醒。",
              "AT-03：真实 REST paused/replan 409、受控恢复窗口、在途收敛、submitted 接收和多目标部分应用、重启恢复。",
              "AT-04：真实 mc/MinIO/Controller 双写、故障和CAS冲突、断网后恢复；本组件 fake 不能替代这些。",
              "AT-05：真实 Matrix transaction 范围、跨团队身份、不同 runtime 工作区同步、持久 Attempt 映射。",
              "AT-08：实际单Worker执行占用、旧执行停止/失去写能力、CPU/内存释放和分支/worktree隔离。",
              "AT-11：真实 artifact、固定组合、作者独立性、证据留存、当前读权及最终业务验收。", "",
              "## 源码定位", ""]
    for result in results:
        citations = ", ".join(f"[L{line}]({base_url}#L{line})" for line in result["source_lines"])
        lines.append(f"- {result['id']}: {citations}")
    (reports / "control-component-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Results: {evidence / 'control-component-results.json'}")
    print(f"Report: {reports / 'control-component-report.md'}")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
