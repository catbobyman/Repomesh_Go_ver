#!/usr/bin/env python3
"""Live AgentTeams room + DAG mapper. Isolated test helper; not product code."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

GATEWAY = os.environ.get("AGENTTEAMS_GATEWAY", "http://127.0.0.1:18080")
ELEMENT = os.environ.get("AGENTTEAMS_ELEMENT", "http://127.0.0.1:18088")
CONTAINER = os.environ.get("AGENTTEAMS_CONTROLLER", "agentteams-controller")
SECRETS = Path.home() / ".config/agentteams-live"


def _read_admin_password() -> str:
    for candidate in (SECRETS / "admin-password", Path.home() / "agentteams-manager.env"):
        if not candidate.exists():
            continue
        text = candidate.read_text()
        if candidate.name == "admin-password":
            return text.strip()
        for line in text.splitlines():
            if line.startswith("AGENTTEAMS_ADMIN_PASSWORD="):
                return line.split("=", 1)[1]
    raise SystemExit("admin password not found under ~/.config/agentteams-live or ~/agentteams-manager.env")


def _http_json(url: str, *, method: str = "GET", token: str | None = None, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode())
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{method} {url} -> {err.code} {detail}") from err


def matrix_login(user: str, password: str) -> str:
    payload = _http_json(
        f"{GATEWAY}/_matrix/client/v3/login",
        method="POST",
        body={"type": "m.login.password", "identifier": {"type": "m.id.user", "user": user}, "password": password},
    )
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Matrix login returned no access_token")
    return token


def _docker() -> list[str]:
    probe = subprocess.run(["docker", "info"], check=False, capture_output=True, text=True)
    if probe.returncode == 0:
        return ["docker"]
    return ["sudo", "-n", "docker"]


def docker_agt(*args: str) -> Any:
    cmd = [*_docker(), "exec", CONTAINER, "agt", *args]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {proc.stderr[-400:] or proc.stdout[-400:]}")
    text = proc.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def docker_curl_json(path: str) -> Any:
    script = (
        "TOKEN=$(cat /var/run/agentteams/cli-token 2>/dev/null || true); "
        "if [ -z \"$TOKEN\" ]; then TOKEN=$(printenv AGENTTEAMS_AUTH_TOKEN); fi; "
        f"curl -sf -H \"Authorization: Bearer $TOKEN\" http://127.0.0.1:8090{path}"
    )
    proc = subprocess.run([*_docker(), "exec", CONTAINER, "bash", "-lc", script], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": (proc.stderr or proc.stdout)[-400:]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"raw": proc.stdout[:1000]}


def encode_room(room_id: str) -> str:
    return urllib.parse.quote(room_id, safe="")


def map_room(*, room_id: str, name: str, kind: str | None, meta: dict[str, Any]) -> dict[str, str]:
    name = name or ""
    kind = kind or ""
    if kind == "task_room" or name.startswith("TASK：") or name.startswith("TASK:"):
        return {
            "repomeshRole": "issue_work_surface",
            "labelZh": "RepoMesh 事项工作面",
            "notes": "TeamHarness task_room；绑定 projectId。不是 Admin DM。",
        }
    if kind == "team_room":
        return {
            "repomeshRole": "leader_collaboration",
            "labelZh": "RepoMesh Leader 协作房间（Leader↔Worker）",
            "notes": "CONTEXT.md 的 Leader 房间。不是 AT 文档里 Leader 的 worker_room。",
        }
    if kind == "direct_room" and meta.get("managerName"):
        return {
            "repomeshRole": "manager_admin_dm",
            "labelZh": "Manager 主对话（Admin↔Manager）",
            "notes": "Controller ProvisionManager；roomKind=direct_room。",
        }
    if kind == "direct_room" and (meta.get("leaderWorker") or name.startswith("Leader DM")):
        return {
            "repomeshRole": "leader_admin_dm",
            "labelZh": "Leader DM（Leader↔Team Admin）",
            "notes": "Manager 默认不在此房；不要映射成协作房间。",
        }
    leader = meta.get("leaderWorker") if isinstance(meta.get("leaderWorker"), dict) else {}
    if kind == "worker_room" and meta.get("workerName") and leader.get("workerName") == meta.get("workerName"):
        return {
            "repomeshRole": "at_docs_leader_room",
            "labelZh": "AgentTeams 文档「Leader Room」（leader worker_room）",
            "notes": "Manager↔Leader 通道。不要当成 RepoMesh Leader↔Worker 协作房。",
        }
    if kind == "worker_room":
        return {
            "repomeshRole": "worker_personal",
            "labelZh": "Worker 个人房间",
            "notes": "单 Worker 房间。",
        }
    return {
        "repomeshRole": "unclassified",
        "labelZh": "未分类房间",
        "notes": "缺少 room.meta 或名称无法对照。",
    }


def apply_controller_roles(rooms: list[dict[str, Any]], controller: dict[str, Any]) -> None:
    workers_raw = controller.get("workers")
    workers = workers_raw.get("workers") if isinstance(workers_raw, dict) else workers_raw
    leader_rooms = {
        worker.get("roomID")
        for worker in (workers or [])
        if isinstance(worker, dict) and worker.get("role") == "team_leader" and worker.get("roomID")
    }
    for room in rooms:
        if room.get("roomId") in leader_rooms and room.get("roomKind") == "worker_room":
            room["mapping"] = {
                "repomeshRole": "at_docs_leader_room",
                "labelZh": "AgentTeams 文档「Leader Room」（leader worker_room）",
                "notes": "Controller role=team_leader。room.meta 可能只有 workerName；这是 Manager↔Leader 通道，不是 team_room。",
            }


def collect_rooms(token: str) -> list[dict[str, Any]]:
    joined = _http_json(f"{GATEWAY}/_matrix/client/v3/joined_rooms", token=token) or {}
    rooms: list[dict[str, Any]] = []
    for room_id in joined.get("joined_rooms") or []:
        name = ""
        try:
            name_ev = _http_json(f"{GATEWAY}/_matrix/client/v3/rooms/{encode_room(room_id)}/state/m.room.name", token=token)
            name = (name_ev or {}).get("name") or ""
        except RuntimeError:
            name = ""
        meta: dict[str, Any] = {}
        try:
            meta = _http_json(f"{GATEWAY}/_matrix/client/v3/rooms/{encode_room(room_id)}/state/room.meta/", token=token) or {}
        except RuntimeError:
            meta = {}
        kind = meta.get("roomKind") if isinstance(meta, dict) else None
        messages: list[dict[str, Any]] = []
        try:
            page = _http_json(
                f"{GATEWAY}/_matrix/client/v3/rooms/{encode_room(room_id)}/messages?dir=b&limit=8",
                token=token,
            )
            for event in page.get("chunk") or []:
                if event.get("type") != "m.room.message":
                    continue
                content = event.get("content") or {}
                messages.append(
                    {
                        "sender": event.get("sender"),
                        "body": (content.get("body") or "")[:400],
                        "ts": event.get("origin_server_ts"),
                    }
                )
        except RuntimeError:
            messages = []
        mapping = map_room(room_id=room_id, name=name, kind=kind, meta=meta if isinstance(meta, dict) else {})
        rooms.append(
            {
                "roomId": room_id,
                "name": name,
                "roomKind": kind,
                "lifecycle": meta.get("lifecycle") if isinstance(meta, dict) else None,
                "createdBy": meta.get("createdBy") if isinstance(meta, dict) else None,
                "meta": {
                    key: meta.get(key)
                    for key in ("managerName", "teamName", "workerName", "leaderWorker", "manager", "admin")
                    if isinstance(meta, dict) and key in meta
                },
                "messages": messages,
                "elementUrl": f"{ELEMENT}/#/room/{urllib.parse.quote(room_id, safe='')}",
                "mapping": mapping,
            }
        )
    rooms.sort(key=lambda item: (item.get("roomKind") or "zzz", item.get("name") or item["roomId"]))
    return rooms


def collect_controller() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, args in (
        ("managers", ("get", "managers", "-o", "json")),
        ("workers", ("get", "workers", "-o", "json")),
        ("teams", ("get", "teams", "-o", "json")),
        ("projects", ("get", "projects", "-o", "json")),
    ):
        try:
            out[key] = docker_agt(*args)
        except RuntimeError as err:
            out[key] = {"error": str(err)[-400:]}
    return out


def collect_workflows(projects: Any) -> list[dict[str, Any]]:
    items: list[Any] = []
    if isinstance(projects, dict):
        items = projects.get("projects") or projects.get("items") or []
        if not items and projects.get("project_id"):
            items = [projects]
    elif isinstance(projects, list):
        items = projects
    graphs: list[dict[str, Any]] = []
    for project in items:
        if not isinstance(project, dict):
            continue
        project_id = project.get("project_id") or project.get("projectId") or project.get("id")
        if not project_id:
            continue
        team = project.get("team_id") or project.get("teamId") or ""
        path = f"/api/v1/projects/{urllib.parse.quote(str(project_id), safe='')}/workflow"
        if team:
            path += f"?team={urllib.parse.quote(str(team), safe='')}&includeTasks=true"
        else:
            path += "?includeTasks=true"
        payload = docker_curl_json(path)
        graphs.append({"projectId": project_id, "teamId": team or None, "workflow": payload})
    return graphs


def capture() -> dict[str, Any]:
    password = _read_admin_password()
    token = matrix_login("admin", password)
    rooms = collect_rooms(token)
    controller = collect_controller()
    apply_controller_roles(rooms, controller)
    workflows = collect_workflows(controller.get("projects"))
    return {
        "source": "live-agentteams",
        "gateway": GATEWAY,
        "element": ELEMENT,
        "rooms": rooms,
        "controller": controller,
        "workflows": workflows,
        "legend": [
            "Manager Admin DM (direct_room + managerName) → Manager 主对话",
            "task_room → RepoMesh 事项工作面",
            "team_room → RepoMesh Leader 协作（Leader↔Worker）",
            "leader worker_room → AT 文档 Leader Room（Manager↔Leader）",
            "workflow.next → 候选就绪，不是派工",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture live AgentTeams rooms and DAG into an isolated snapshot.")
    parser.add_argument("--capture", default="", help="Write snapshot JSON to this path")
    args = parser.parse_args()
    snapshot = capture()
    text = json.dumps(snapshot, ensure_ascii=False, indent=2)
    if args.capture:
        path = Path(args.capture)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")
        print(f"wrote {path} rooms={len(snapshot['rooms'])} workflows={len(snapshot['workflows'])}")
    else:
        print(text)


if __name__ == "__main__":
    main()
