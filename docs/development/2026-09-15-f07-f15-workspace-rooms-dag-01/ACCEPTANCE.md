# F07—F15 房间 / DAG / 假后端验收清单

更新：2026-09-15。本清单随实现维护。范围是 `/demo/workspace` 假数据演示，**不是** B07—B11 产品实现，也不是 AgentTeams 活实例验收。

上游对照源码：`third_party/AgentTeams` commit `517caff`。本环境无 Docker，无法启动 Matrix / Controller；房间与 DAG 按该提交的 `room.meta`、`plan_dag` 与 `GET /api/v1/projects/{id}/workflow` 形状映射，不嵌入 Element。

| ID | 条目 | 状态 | 证据 |
| --- | --- | --- | --- |
| A01 | 独立 `web/fake-backend/`：JSON 假体 + 真实 HTTP 形状说明；页面只 `fetch('/api/...')` | PENDING | 目录、README、Network |
| A02 | 浏览器 `roomId` 为 RepoMesh 内部标识；响应不含 Matrix `!…` 或 `matrix:!` 当作可进地址 | PENDING | 夹具 JSON、解析测试 |
| A03 | 主房间映射上游 `task_room`（Manager 主对话），不是 Admin DM；可 `canEnter` 时进入 RepoMesh 会话，不嵌入 Element | PENDING | 房间快照 `upstream.roomKind`、UI |
| A04 | Leader 房间映射上游 `team_room`（Leader↔Worker），**不是** AgentTeams 文档里 Manager+Leader 的 worker「Leader Room」；只读 | PENDING | 快照 `roomKind`/`readOnly`、无 composer |
| A05 | `GET /api/issues/{id}/rooms` 给出 `canEnter`/`roomId`；`GET …/rooms/{roomId}` 逐次再核权，旧快照不能继续授权 | PENDING | 可进 200、不可进 403 `ROOM_NOT_ENTERABLE` |
| A06 | 会话页采用 dock r2：宽屏常驻悬浮入口；点击 Issue／DAG／Leader 同页右栏；主会话与输入框保留；再点或关闭只收栏 | PENDING | 浏览器走查 |
| A07 | `GET /api/issues/{id}/plan-graph` 含上游 native `tasks[]`（`planned\|assigned\|in_progress\|…`）与 Controller `workflow`（`nodes/edges/next`） | PENDING | 夹具、解析测试、DAG 页 |
| A08 | UI 把 `workflow.next` / `ready_nodes` 标成「候选就绪 · 非派工」；`assigned` 且仍在 `next` 不得显示为已派工 | PENDING | DAG 节点说明、夹具 `dispatchState` |
| A09 | 跨仓阻塞放在 `businessOverlay`，不写进上游 `status` | PENDING | 夹具 overlay、节点详情 |
| A10 | 前端测试覆盖房间再核权、原生 DAG 字段、夹具不含 Matrix 地址 | PENDING | `npm --prefix web test` |
| A11 | 类型检查与前端构建通过 | PENDING | `typecheck` / `build` |
| A12 | AgentTeams 活起动（DeepSeek + Matrix） | BLOCKED | 本机 `docker` 不可用；不提交任何供应商密钥 |

状态取值：`PENDING` / `PASS` / `FAIL` / `BLOCKED`。未跑过的检查不得标 PASS。
