# AgentTeams 活房间／DAG 映射（测试隔离）

本目录是一次**真实 AgentTeams 实例**的房间与 DAG 映射实验。它不进入 `web/`、`internal/` 或 `web/fake-backend/`。浏览器演示 `/demo/workspace` 仍然只用假后端。

对照源码：`third_party/AgentTeams` commit `517caff`。运行时用官方安装脚本拉起的 **v1.2.3** embedded 镜像（Tuwunel + Element + Controller）。

## 映射（读 `room.meta.roomKind`，不要只看房间标题）

| AgentTeams 事实 | RepoMesh 对应 | 不要当成 |
| --- | --- | --- |
| Manager Admin DM，`direct_room` + `managerName` | Manager 主对话（人 ↔ Manager） | Issue 本身 |
| `task_room`（`TASK：{projectId}`） | 事项工作面 | Admin DM |
| `team_room`（`Team: {name}`） | Leader 协作房间（Leader ↔ Worker） | AT 文档里的 Leader `worker_room` |
| Leader 的 `worker_room` | AT 文档「Leader Room」（Manager ↔ Leader） | RepoMesh Leader 协作房间 |
| `Leader DM`（`direct_room`） | Leader ↔ Team Admin 私聊 | 主房间或协作房间 |
| 普通 `worker_room` | Worker 个人房间 | 团队房间 |

DAG：`GET /api/v1/projects/{id}/workflow` 的 `nodes` / `edges` / `next`。`next` 是候选就绪，不是派工。没有 Project 时页面标明「尚无 workflow」。

## 本机秘密

密钥、管理员口令只放在 `$HOME/.config/agentteams-live/`，不要提交。安装日志 `/tmp/agentteams-install.log` 也不要提交。

## 入口

1. 安装并启动 AgentTeams（见仓库外安装记录）。Element：http://127.0.0.1:18088/#/login
2. 采集并打开映射页：

```bash
cd tests/agentteams-live-rooms
python3 mapping.py --capture runtime/snapshot.json
python3 serve.py
```

映射页：http://127.0.0.1:18089/
