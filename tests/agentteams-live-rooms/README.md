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

## Docker 出网（Higress → LLM）

Cloud 嵌套 Docker 上，`iptables-legacy` 的 FORWARD 默认 **DROP**，而 Docker 把 `agentteams-net` 的放行写在 `iptables-nft` 里。结果是：宿主机能访问 `api.deepseek.com`，`agentteams-controller` / Manager 容器 SYN 出不去，Higress `/v1/chat/completions` 变成 503/超时，Manager 收得到 Matrix 消息但回不了 LLM。

安装后如果容器 `curl https://api.deepseek.com/v1/models` 超时，先跑：

```bash
bash tests/agentteams-live-rooms/fix-docker-egress.sh
```

桥名不是默认 `br-8b0a57af09b5` 时设 `AGENTTEAMS_DOCKER_BRIDGE`。规则只覆盖 `172.18.0.0/16`，不提交、也不改产品网络栈。

## 本机这次跑通的事实

Embedded 安装：`agentteams-controller` + `agentteams-manager`（`openai-compat` → Higress → DeepSeek `deepseek-chat`，实际 completions 返回 `deepseek-flash`）。Element http://127.0.0.1:18088 ，Matrix 网关 http://127.0.0.1:18080 。

修好 Docker FORWARD 之后，Admin 在 `Manager: default` 里发中文探活，`@manager` 用 LLM 回复了自我介绍、安装欢迎语，以及对「收到请只回复：DeepSeek 通道已通。」的原句确认。密钥只在本机 `~/.config/agentteams-live/` 与安装 env，不进 Git。

已创建 `live-demo` 团队（leader=`live-lead`，worker=`live-dev`）。Admin 加入的房间包括：

- `Manager: default` → `direct_room` → Manager 主对话
- `Team: live-demo` → `team_room` → RepoMesh Leader 协作
- `Leader DM: live-lead` → `direct_room` → Leader↔Admin
- `Worker: live-lead` → `worker_room` + Controller `team_leader` → AT 文档 Leader Room
- `Worker: live-dev` → `worker_room` → Worker 个人房间

Project `live-dag-1` 经 `agt project create` / `replan` 写入 DAG：`n2` 在 `workflow.next`（候选就绪，不是派工）。Worker 曾因 MinIO 不可达退出；修好桥接 FORWARD 并重启 `live-lead` / `live-dev` 后容器保持 Up。

映射页：http://127.0.0.1:18089/

1. 安装并启动 AgentTeams（见仓库外安装记录）。Element：http://127.0.0.1:18088/#/login
2. 采集并打开映射页：

```bash
cd tests/agentteams-live-rooms
python3 mapping.py --capture runtime/snapshot.json
python3 serve.py
```

映射页：http://127.0.0.1:18089/
