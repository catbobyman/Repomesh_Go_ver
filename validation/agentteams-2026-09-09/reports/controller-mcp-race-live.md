# Controller／MCP 精确交错、派工回写恢复与真实重规划状态

2026-09-09，最终 run `32447df06f`，完成于 `16:52:22 UTC`，命令退出 **0**。四项观察均复现；其中两项是原生接入缺口，一项是有限条件下的正确恢复，一项是状态契约／部分应用事实。**这不是 RepoMesh 验收通过。**

结论：原生 MCP 在成功拉取之后，仍能以原同步上传覆盖已持久化的 REST 暂停。通知已被 Matrix 接受后，单独丢失 Task 的 assigned 回写可由新进程重试恢复；但若 Project 与 Task 的回写都失败，重试会返回 `ok=true, synced=true, reused=true`，只修复 Task，**Project 节点仍为 planned**。两种重试均未产生第二条通知。

## 方法、独立范围与证据

- 上游 `eeaab64391ccaec9118e84977f538aefd40720d6` 的完整 `plugins/teamharness/mcp` 复制到 run 专属 `/tmp/repomesh-race-mcp-32447df06f`，容器内 Python 3.10.12 调用真实 `server.call_tool`。
- workspace：`/tmp/repomesh-control-race/32447df06f`；共享前缀：`agentteams/rv-a-storage/teams/coverage-race-32447df06f/shared`；Project／Task 均为 `cov-32447df06f-*`，不覆盖此前对象。
- 新专属 Matrix 房间 `!jTrBA6L1EQS55sSru7:rv-a.matrix.invalid`。沿用专用测试 Alice 建房、Bob 加入；通知使用 Bob 的真实 user token，不使用模型或真实用户业务房间。Controller pause/replan 使用本实例管理员 CLI token，mc 使用本容器实际存储配置；**不是实际 Worker 自有权限实验**。
- 为使 Controller 的 Team 前缀枚举能找到对象，通过真实 API 创建 `coverage-race-32447df06f` Team，引用专属 `coverage-race-leader-32447df06f` Worker。Worker 明确 `Stopped`、`containerManaged=false`。[后续只读检查](../evidence/control-race-live-32447df06f-fixture-state.json)确认仍是 Stopped，预期 Worker 容器不存在。没有启动 Agent runtime、模型任务或重启任何容器。
- 上游源文件未修改；实际运行 `server.py` 的前后 SHA-256 与宿主上游均为 `741d211b36a4413e598989c43c9a7735926e18e49787e15a9ef9453d825dc98d`。

执行脚本：[宿主编排](../scripts/control-race-live-run.py)、[容器实验](../scripts/control-race-live-container.py)。从项目根目录运行：

```powershell
python -X utf8 validation/agentteams-2026-09-09/scripts/control-race-live-run.py
```

每次运行生成新 run／房间／资源与文件，不覆写旧证据。最终[完整原输出](../evidence/control-race-live-32447df06f.stdout.json)、[stderr](../evidence/control-race-live-32447df06f.stderr.log)、[退出码](../evidence/control-race-live-32447df06f.exitcode)、[简表](../evidence/control-race-live-32447df06f.summary.json)均保留。原输出包括 44 条外层夹具操作记录，并内嵌 5 次独立 MCP 子进程的完整 stdout／stderr；5 份子进程输出另展开保存在 `evidence/control-race-live-32447df06f-children/`。这些计数不冒充所有原生网络／mc 调用的全量计数。凭据只在 private、stdin、进程环境／内存中使用，输出脱敏。

## 显式故障注入，哪些仍是真实执行

本实验在**独立 Python 夹具进程**中临时包装 `server._filesync`，不改上游磁盘文件，也不改 Controller／MinIO／Matrix 配置。包装器正常路径调用原 `_filesync`；所有对象读写、Matrix send 和 REST 请求仍进入真实服务。

| 注入点 | 实际做法 | 不应扩大解释 |
| --- | --- | --- |
| 成功拉取与后续上传之间 | 原 `_filesync(pull)` 完成并读到本地 active 后，包装器同步执行真实 REST pause，读回远端 paused，再返回原调用继续执行原 MCP 业务及上传 | 是确定安排的真实交错，不是随机并发压力或所有写入方的完整测试 |
| 通知后指定上传失败 | 只在本地 Task 已 assigned 且已有 eventId 时，先从真实 timeline 核对该事件，再为本次原 `_filesync(push)` 临时设置进程内 `MC_HOST_agentteams` 的无效凭据，调用真实 mc／MinIO，finally 恢复 | 是实际存储认证失败，不是网络断线／服务器崩溃；没有修改共用 mc alias 或撤销其他进程凭据 |
| 再运行恢复 | 首次 MCP 子进程正常返回失败并退出；另起全新 Python 进程，使用原 workspace／身份／task_id 重试 | 已证明跨进程且保留本地工作目录的恢复；未注入 kill、丢失本地卷或 Matrix 响应途中断开 |

真实 mc 在认证失败时输出 `The Access Key Id you provided does not exist in our records`；本镜像 mc 的该次返回码为 0，但原 `_filesync` 将其判为 `ok=false`。原输出保留二者，不把“进程退出 0”误称存储成功。

## RACE-01：MCP 原同步上传覆盖真实 REST 暂停（AT-03／04）

真实顺序为：

1. `plan_dag` 的原 MCP 拉取成功，本地 Project 为 active。
2. barrier 内真实 REST `pause?team=coverage-race-32447df06f` 返回 200；MinIO 独立读回为 paused。
3. 放行原 MCP 业务。`plan_dag` 生成新 DAG，由原 `_sync_project → _filesync → mc` 上传。
4. 工具返回 `ok=true`；MinIO 最终状态是 **active**，任务已替换成 `cov-32447df06f-pause-race-new-task`。

这次直接运行了 MCP 的真实拉取与同步路径，补足 LIVE-C04 仅由夹具管理员普通上传的边界。确定存在“拉取后新干预被后续无条件写覆盖”的窗口；仍不能据此证明 Worker 的原生凭据拥有本夹具全部存储权限。

源码对应：`server.py:3275` 在 projectflow 开始时拉取；`server.py:3397-3416` 本地改图并同步；`server.py:3823-3839` 走文件上传；Controller `project_handler.go:2073-2118` 读取写上下文并带条件版本，`PauseProject` 的条件写保护不能延伸到另一普通上传方。

## RACE-02／03：通知成功之后的回写失败与恢复（AT-04／05／10／11）

两种用例的通知都先进入真实 Matrix，随后才注入失败。首次原生 delegate 回执完全相同：`ok=false`、`synced=false`、`retryable=true`，错误为 `task assigned but shared-storage sync failed; retry to complete`。

| 用例 | 首次通知后失败范围 | 失败后远端 Project／Task | 新进程重试回执 | 重试后远端 Project／Task | 通知 |
| --- | --- | --- | --- | --- | --- |
| RACE-02 | 仅 Task assigned 上传失败，Project assigned 已真实上传 | assigned／prepared | ok=true、synced=true、notification.reused=true | **assigned／assigned** | 原 event，timeline 仅 1 条 |
| RACE-03 | Project assigned 上传和随后 Task assigned 上传均失败 | planned／prepared | ok=true、synced=true、notification.reused=true | **planned／assigned** | 原 event，timeline 仅 1 条 |

RACE-02 的初次／重试 PID 为 10749／10952，事件 `$HdblSWKbGdelJfrWFUg2hm0bu4MeWtwKW7tF1G5JDbQ`。RACE-03 为 11114／11233，事件 `$hfrN3fUjdvI5vzwwO2K_n0FKUtOnpycNrkWIP76kdog`。重试事件 ID 与首次相同；以唯一 task_id 的通知正文筛选 timeline 也只有一条，不只是重复读同一 event 的计数。

**RACE-02 是有条件的正向恢复证据**：本地 assigned＋eventId 被保留，Project 已先同步，重试只需补 Task。**RACE-03 是新增部分恢复缺口**：重试成功不是 Project 与 Task 已一致的保证。

源码与实际结果对应：首次 delegate 的 `_update_project_task` 写本地 Project 并调用 `_sync_project`，没有检查其返回布尔值（`server.py:3952-3971`）；随后 Task 同步失败被显式返回。重试先拉取远端 planned Project（`server.py:4082-4099`），本地 Task 仍有 assigned/eventId，于是进入复用分支；该分支只 `_sync_task`（`server.py:4131-4178`），未重补 Project 节点，所以 Task 恢复为 assigned 后 Project 仍 planned。报告只是核实原生机制，没有实施上游修复或 RepoMesh 收敛算法。

## STATE-01：真实 submitted／completed 与多目标部分应用（AT-03／11）

这些状态通过真实 MCP 委派、ack、submit、accept 和真实 REST 产生并由 MinIO 读回；没有构造虚假 HTTP 成功。

| 实验 | HTTP／存储结果 |
| --- | --- |
| 已实际 ack 为 in_progress 时 REST replan | 409 |
| 实际 submit 为 submitted 时 REST replan | 409 |
| submitted 时 REST complete Project | 409 |
| accept 后节点 completed、Project 仍 active，再 REST replan 下一有限 DAG | 200，新 task_id planned 持久化 |
| A 已更新下一 DAG，B 实际 submitted 后 replan | B 为 409；独立读回保留 A 新节点 planned、B 旧节点 submitted |
| 所有节点已终态，REST complete Project，再 replan | complete 200，随后 replan 409 |

本用例的 submit 使用空 deliverables 和夹具 summary；第二轮节点的完成由原生 `accept_task_result` 直接标记，未要求实际 TaskMeta／产物。它验证状态契约和元数据语义，**不证明 Worker 执行、独立产物验收或下一轮获准**。A/B 是两个独立上游 Project；没有 RepoMesh 事务、整体 Plan Version、回滚或测试协调器崩溃恢复，不能把保存了部分事实称为业务整体生效。

## 首次失败保留

首轮 `c1a9f95d77` 的[原输出](../evidence/control-race-live-c1a9f95d77.stdout.json)、[退出码 1](../evidence/control-race-live-c1a9f95d77.exitcode)保留。该轮只建专属 Team 存储目录、未建 Team CR，原 MCP 能读写该显式前缀，但 Controller REST 返回 404。源码 `project_handler.go:245-265` 只枚举实际 Team CR 对应前缀及 global shared 前缀，解释了差异。首轮 RACE-02／03 已复现；RACE-01／STATE-01 未完成。

修正仅补齐第二轮的合法测试 Team／Stopped unmanaged Worker 引用，使用全新 run／对象／房间后重跑；未修改上游查找逻辑、服务配置或旧证据。最终四项均取得实际结果。

## 剩余边界

本次补足精确 MCP／REST 交错、通知成功后的两类上传故障与保留 workspace 的新进程重试。未测试真实 Worker runtime 工具、Worker 自有凭据、Matrix 已处理请求但响应丢失、进程强杀／本地盘丢失、RepoMesh 持久映射或多目标收敛。通知幂等在本用例成立，不代表状态已一致；`synced=true` 应理解为本分支执行的同步结果，不可直接作为完整业务生效证明。
