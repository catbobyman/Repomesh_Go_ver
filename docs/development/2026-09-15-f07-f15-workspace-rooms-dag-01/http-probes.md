# 现场 HTTP 探测（Vite 假后端）

时间：2026-09-15T17:00:24Z。原点：`http://127.0.0.1:5173`。完整原始输出在本机 artifacts `workspace_rooms_dag_http_probes.log`。

| 请求 | 状态 | 要点 |
| --- | --- | --- |
| `GET /api/issues/iss_1/rooms` | 200 | `rm_main_iss_1`、`rm_leader_iss_1_service`、`rm_leader_iss_1_admin` 的 `canEnter=true` |
| `GET /api/issues/iss_1/rooms/rm_main_iss_1` | 200 | `upstream.roomKind=task_room`，`readOnly=false` |
| `GET /api/issues/iss_1/rooms/rm_leader_iss_1_service` | 200 | `upstream.roomKind=team_room`，`readOnly=true`，`composer.enabled=false` |
| `GET /api/issues/iss_2/rooms` | 200 | 列表 `canEnter=false`，仍给出内部 `roomId` |
| `GET /api/issues/iss_2/rooms/rm_leader_iss_2_service` | 403 | `error.code=ROOM_NOT_ENTERABLE` |
| `GET /api/issues/iss_3/rooms` | 200 | `roomId=null`，无可进入口 |
| `GET /api/issues/iss_1/plan-graph` | 200 | `workflow.next=['ui-01']`；`ui-01` 为 `assigned` + `inNext` + `not_dispatched`；overlay `cross_repo_predecessor_unmet`；响应不含 `matrix:!` |

iss_2 的 403 体：

```json
{
  "error": {
    "code": "ROOM_NOT_ENTERABLE",
    "message": "当前不能进入该房间。列表上的旧 canEnter 不能继续授权。",
    "fieldErrors": [],
    "requestId": "req_demo"
  }
}
```
