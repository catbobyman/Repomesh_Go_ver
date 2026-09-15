# F07—F15 房间 / DAG / 假后端验收清单

更新：2026-09-15。本清单随实现维护。范围是 `/demo/workspace` 假数据演示，**不是** B07—B11 产品实现，也不是 AgentTeams 活实例验收。

上游对照源码：`third_party/AgentTeams` commit `517caff`。本环境无 Docker，无法启动 Matrix / Controller；房间与 DAG 按该提交的 `room.meta`、`plan_dag` 与 `GET /api/v1/projects/{id}/workflow` 形状映射，不嵌入 Element。

| ID | 条目 | 状态 | 证据 |
| --- | --- | --- | --- |
| A01 | 独立 `web/fake-backend/`：JSON 假体 + 真实 HTTP 形状说明；页面只 `fetch('/api/...')` | PASS | `web/fake-backend/` 与 README；`vite.config.ts` 挂 `workspaceMockPlugin`；`client.ts` 只走 `/api/...`。Vite `http://127.0.0.1:5173` 上 `GET /api/issues/iss_1/rooms` 与 `plan-graph` 均为 200。 |
| A02 | 浏览器 `roomId` 为 RepoMesh 内部标识；响应不含 Matrix `!…` 或 `matrix:!` 当作可进地址 | PASS | 夹具扫描测试 `fake-backend fixtures never expose Matrix room addresses as browser ids`；现场探测 `contains matrix:! False`。UI 显示 `rm_leader_iss_1_service`。 |
| A03 | 主房间映射上游 `task_room`（Manager 主对话），不是 Admin DM；可 `canEnter` 时进入 RepoMesh 会话，不嵌入 Element | PASS | `GET …/rooms/rm_main_iss_1` → `upstream.roomKind=task_room`、`composer.enabled=true`。会话页为 RepoMesh 气泡，不嵌入 Element。 |
| A04 | Leader 房间映射上游 `team_room`（Leader↔Worker），**不是** AgentTeams 文档里 Manager+Leader 的 worker「Leader Room」；只读 | PASS | `GET …/rooms/rm_leader_iss_1_service` → `roomKind=team_room`、`readOnly=true`、`composer.enabled=false`。全页与 dock 右栏均无输入框。 |
| A05 | `GET /api/issues/{id}/rooms` 给出 `canEnter`/`roomId`；`GET …/rooms/{roomId}` 逐次再核权，旧快照不能继续授权 | PASS | iss_1 列表 `canEnter=true` 且 GET 200；iss_2 列表 `canEnter=false`，`GET …/rm_leader_iss_2_service` → 403 `ROOM_NOT_ENTERABLE`。测试 `room snapshots re-check canEnter…`。 |
| A06 | 会话页采用 dock r2：宽屏常驻悬浮入口；点击 Issue／DAG／Leader 同页右栏；主会话与输入框保留；再点或关闭只收栏 | PASS | 浏览器走查：右栏 Leader／DAG 打开时左侧 composer 仍在；关闭右栏回到会话。约 59s 连续录像。 |
| A07 | `GET /api/issues/{id}/plan-graph` 含上游 native `tasks[]`（`planned\|assigned\|in_progress\|…`）与 Controller `workflow`（`nodes/edges/next`） | PASS | 夹具 `fixtures/plan-graph/iss_1.json`；现场 `upstreamProjects=['tp-service','tp-admin']`，`workflow.next.tp-admin=['ui-01']`。DAG 页画出 native + overlay 节点。 |
| A08 | UI 把 `workflow.next` / `ready_nodes` 标成「候选就绪 · 非派工」；`assigned` 且仍在 `next` 不得显示为已派工 | PASS | `ui-01`：`nativeStatus=assigned`、`inNext=true`、`dispatchState=not_dispatched`。DAG 节点「筛选控件」显示「候选就绪 · 非派工」。 |
| A09 | 跨仓阻塞放在 `businessOverlay`，不写进上游 `status` | PASS | overlay `blockingReasons.ui-01=['cross_repo_predecessor_unmet','attempt_not_reserved']`；`ui-01` native 仍为 `assigned`。图上单独「RepoMesh overlay」组。 |
| A10 | 前端测试覆盖房间再核权、原生 DAG 字段、夹具不含 Matrix 地址 | PASS | `cd web && npm test`：44 pass / 0 fail（含 `mock API lists…` 的 plan-graph 断言、房间再核权、夹具扫描）。 |
| A11 | 类型检查与前端构建通过 | PASS | `cd web && npm run typecheck`；`npm run build` → Vite 产出 `dist/`。native import-extension 仅为 Vite 预告，不是失败。 |
| A12 | AgentTeams 活起动（DeepSeek + Matrix） | BLOCKED | `docker info` → `DOCKER_NO`。对照停留在锁定源码 `517caff`。未提交任何供应商密钥。 |

状态取值：`PENDING` / `PASS` / `FAIL` / `BLOCKED`。未跑过的检查不得标 PASS。
