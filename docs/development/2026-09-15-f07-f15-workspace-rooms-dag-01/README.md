# 2026-09-15：工作区可进房间、原生 DAG 与假后端目录

按用户授权，把 F07–F15 演示接到 AgentTeams `517caff` 的房间／DAG 语义：独立 `web/fake-backend/` JSON、可进 Manager／Leader 房间、dock r2 同页右栏、native + Controller workflow 图。验收清单见 [ACCEPTANCE.md](ACCEPTANCE.md)。

## 做了什么

- `web/fake-backend/fixtures/` 提供真实 HTTP 形状的假体；`GET /rooms/{roomId}` 再核权。
- 主房间 `task_room`、Leader `team_room`；浏览器 `roomId` 内部化，不嵌入 Element。
- `plan-graph` 含 native `planned|assigned|in_progress|…`、压缩 `workflow`、`next`≠派工、overlay 跨仓阻塞。
- 会话页 dock r2：悬浮入口打开同页右栏，主会话与输入框保留。

## 不是什么

- 不是 B07—B11 产品实现，无 Go 路由、无真实 Matrix。
- AgentTeams 活起动本环境无 Docker，标 BLOCKED；未写入任何供应商密钥。
