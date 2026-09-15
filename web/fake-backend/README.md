# 工作区演示假后端

本目录是 F07—F15 `/demo/workspace` 的假 HTTP 体。浏览器只打 `/api/...`；Vite 中间件用同一形状应答。**不是** Go 产品路由，也不冻结 `docs/current/api-design.md` 的 `/api/v1`。

上游对照：AgentTeams `517caff` 的 Matrix `room.meta` 与 TeamHarness `plan_dag` / Controller `GET /api/v1/projects/{id}/workflow`。浏览器 JSON 用 RepoMesh 内部 `roomId`，**不**把 Matrix `!room:server` 或 `matrix:!…` 当作可进地址。

## 入口

- 夹具：`fixtures/`
- 加载：`load.ts`
- 路由目录：`fixtures/catalog.json`
- 请求处理：`../src/workspace/mock/server.ts`（读写内存 + 本目录静态 GET）
- Vite 插件：`plugin.ts`

## 本轮新增的只读形状（演示扩展）

| 方法 | 路径 | 夹具 | 上游对应 |
| --- | --- | --- | --- |
| GET | `/api/issues/{issueId}/rooms` | `fixtures/rooms/{issueId}.json` | 创建契约 §7 观察；`roomId` 内部化 |
| GET | `/api/issues/{issueId}/rooms/{roomId}` | `fixtures/rooms/snapshots/{roomId}.json` | 再核权后的房间正文；`roomKind` 来自 `room.meta` |
| GET | `/api/issues/{issueId}/plan-graph` | `fixtures/plan-graph/{issueId}.json` | native `tasks` + 压缩 `workflow` + RepoMesh overlay |

可变资源（创建 Issue、发消息）仍由内存 store 生成，形状与已采用浏览器契约一致。

## 房间映射（不要按显示名对）

| RepoMesh UI | 夹具 `upstream.roomKind` | AgentTeams 事实 |
| --- | --- | --- |
| 主房间 | `task_room` | Issue 工作面；不是 Manager Admin DM（`direct_room`） |
| Leader 只读房间 | `team_room` | Leader + Worker 协作；**不是**文档里 Manager 所在的 leader `worker_room` |

`session_id = matrix:{room_id}` 只存在于上游；本演示不在浏览器字段里给出带 `!` 的 Matrix id。
