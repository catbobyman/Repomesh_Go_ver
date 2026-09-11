# MCP 收不到通知结果时的真实进程中断与重试

执行时间：2026-09-09 17:06:28 UTC。Run ID：`fecb288f32`。对应 AT-04 / AT-05 / AT-10 的一个原生故障窗口。

结论：真实 Matrix 已接受任务通知，但原生 delegate 尚未收到发送函数返回时，将该 MCP 实验子进程硬退出；随后使用相同 sender、access token、room、task_id 和原请求重试，两个用例都恢复到 Project 节点与 Task 为 `assigned`，每个任务最终只有一个 Matrix 通知事件。保留工作目录和封存后创建空工作目录均实测成功。这是明确条件下的原生恢复证据，不是 RepoMesh 身份映射、事务或业务副作用恰好执行一次的证明。

## 环境与注入边界

- 源码：AgentTeams `eeaab64391ccaec9118e84977f538aefd40720d6`，实际调用 `plugins/teamharness/mcp/server.py` 的 `call_tool("taskflow", ...)`。
- 服务：已有 `rv-a-controller` 内的真实 Matrix、真实 MinIO 与 `mc`，未修改任何服务配置或上游生产文件，未重启服务，未调用模型。
- 专属房间：`!b6KUFbOv7fZSuEq8uc:rv-a.matrix.invalid`；本轮验证账户 Alice 创建，Bob 加入、发送，只有这些验证账户参与。
- 专属共享前缀：`agentteams/rv-a-storage/teams/coverage-race-32447df06f/shared/response-loss-fecb288f32`。这是本次 MCP 显式提供的独立 `sharedPrefix`，不是另一个已注册的 Controller Project API 路由；本轮未调用 Project REST API。
- 工作目录：容器内 `/tmp/repomesh-response-loss/fecb288f32`。源码副本位于 `/tmp/repomesh-response-loss-mcp-fecb288f32`。
- `server.py` 运行前后及宿主源码 SHA-256 均为 `741d211b36a4413e598989c43c9a7735926e18e49787e15a9ef9453d825dc98d`；执行后 upstream `git status --short` 为空。

本实验只在新建的 MCP 子进程中包装 `_send_delegate_notification`：先调用原函数完成真实 Matrix HTTP 请求并解析成功 `eventId`，再把观测记录写入独立旁路文件，`flush`、`fsync` 后执行 `os._exit(86)`。原生 delegate 没有获得该返回值，也没有执行后续 assigned 提交；调用方收到的是进程退出和空 stdout，没有正常的 MCP 成功或失败响应。旁路用于研究者确认服务端已经接受，未把 eventId 注入重试参数或任务元数据。

因此，注入位置是“HTTP 成功回复已经抵达发送 helper，返回值尚未交给 delegate”的进程中断，不是实际网络丢包，也不是 Matrix 服务宕机。只结束了两个本实验新建的子进程；没有向 Controller、Matrix、MinIO、Manager 或 Worker 进程发送终止信号。

## 两个实测结果

| 项目 | LOSS-01：保留目录 | LOSS-02：封存目录后从空目录重试 |
|---|---|---|
| Project | `loss-fecb288f32-retained-project` | `loss-fecb288f32-empty-project` |
| Task | `loss-fecb288f32-retained-task` | `loss-fecb288f32-empty-task` |
| 中断子进程 PID / exit | `18256 / 86` | `18487 / 86` |
| 中断子进程 stdout | 0 字节，无 MCP 返回 | 0 字节，无 MCP 返回 |
| 中断后本地与远端 Project 节点 | `planned` | `planned` |
| 中断后本地与远端 Task | `prepared`，没有 `eventId` | `prepared`，没有 `eventId` |
| 中断后真实 Matrix 通知数 | 1 | 1 |
| 重试输入的本地目录 | 保留 Project meta、Task meta、spec 三个文件 | 空目录、0 文件；原三文件已封存且哈希一致 |
| 重试子进程 PID / exit | `18333 / 0` | `18566 / 0` |
| 真实发送 helper 总调用数 | 2 | 2 |
| 重试返回 | `ok:true, synced:true, notification.sent:true` | `ok:true, synced:true, notification.sent:true` |
| 重试返回 eventId | 与第一次真实 Matrix 成功响应相同 | 与第一次真实 Matrix 成功响应相同 |
| 重试后本地与远端 Project 节点 / Task | `assigned / assigned` | `assigned / assigned` |
| 重试后真实 Matrix 通知数 | 1 | 1 |

两个实际事件分别为：

- LOSS-01：`$yjjPcKyoYETKFvEiudsnMV9yRJpSMjfVAVKzOnTjYEY`。
- LOSS-02：`$CamEfqmLWATMulGy3WjsPl0lnZxsXM1VOFfBajIYCiU`。

重试进程仍使用只观察的发送包装器，调用原函数后正常返回；两次旁路记录与真实房间 timeline 确认发送 helper 实际再次执行，Matrix 返回原事件，而不是凭本地 `assigned + eventId` 跳过发送。两个重试的 `notification.reused` 字段均不存在。

LOSS-02 原目录封存在 `/tmp/repomesh-response-loss/fecb288f32/empty-archived-before-retry`，其三个文件的 SHA-256 与中断后的快照完全一致。封存前验证原路径和目标路径都位于本次实验根目录内；使用目录重命名保留证据，没有删除。相同原路径创建空目录后，快照确认没有 Project、Task 或其他文件，再启动新的 MCP 进程。

## 与原生实现的对应关系

原生发送使用 `PUT .../send/m.room.message/delegate-{task_id}`，实际稳定 transaction ID 构造见 [server.py:4049](../upstream/plugins/teamharness/mcp/server.py#L4049)。成功响应被解析为 `eventId` 后返回，见 [server.py:4061](../upstream/plugins/teamharness/mcp/server.py#L4061)。本次退出点恰在此返回值即将交回 delegate 之前。

delegate 先写 `prepared` 任务和 spec 并上传真实共享存储，见 [server.py:4201](../upstream/plugins/teamharness/mcp/server.py#L4201)；之后才调用通知，见 [server.py:4258](../upstream/plugins/teamharness/mcp/server.py#L4258)。通知成功后才写入 `assigned + eventId`，更新 Project 节点并再次同步 Task，见 [server.py:4293](../upstream/plugins/teamharness/mcp/server.py#L4293)。这解释了中断时两个存储面均为 `planned / prepared`。

每次 taskflow 调用首先拉取远端 Project，见 [server.py:4093](../upstream/plugins/teamharness/mcp/server.py#L4093)。空目录用例依赖这个远端 Project、实验调用方保存并重放的原始 delegate 参数，以及相同 Matrix transaction ID；不能描述成上游仅凭远端存储就会自动发现并恢复原命令。此路径不会先把所有远端 Task 状态完整拉回再自动判断整个业务恢复流程。

两次重试都没有进入本地 `assigned + eventId` 的复用分支，见 [server.py:4136](../upstream/plugins/teamharness/mcp/server.py#L4136)，而是重新发送，再执行后续完整状态回写。

这与 [上一轮 RACE-03 的真实上传失败结果](controller-mcp-race-live.md)不矛盾：上一轮 native 已经在本地写好 `assigned + eventId`，随后 Project/Task 远端上传失败；其重试进入复用分支，只补 Task 同步，留下远端 Project 节点 `planned`。本轮硬退出更早，本地仍是 `prepared`，因此走完整分支并更新 Project。不能用本轮成功覆盖上一轮已确认的恢复缺口。

## 证据与复现

- [原始总输出](../evidence/control-response-loss-fecb288f32.stdout.json)：完整 MCP 子进程 stdout/stderr、旁路发送响应、前后本地与远端元数据、真实 Matrix timeline、目录封存与文件哈希。
- [结果摘要](../evidence/control-response-loss-fecb288f32.summary.json)：两个观察均为 `OBSERVATION_CONFIRMED / SUPPORTED_NATIVE_RECOVERY_IN_THIS_FAULT_WINDOW`，外层执行 exit 0。
- [子进程原始证据目录](../evidence/control-response-loss-fecb288f32-children/)：每次调用独立的 `.stdout.txt`、`.stderr.log`、`.exitcode`、`.observer.json`；两份 hard-exit stdout 为 0 字节、退出码为 86，两份 observe-only 为正常原生 MCP 返回、退出码为 0。
- [容器实验脚本](../scripts/control-response-loss-container.py)与[宿主编排脚本](../scripts/control-response-loss-run.py)。凭据仅从已有 private 配置读取，证据输出脱敏。

在同一套授权隔离服务和验证账户仍有效时，从仓库根目录执行下列命令会创建新 run ID、新房间和新共享子前缀；无需改动上游源码或重启服务：

```powershell
python -X utf8 validation/agentteams-2026-09-09/scripts/control-response-loss-run.py
```

## 对 AT-04 / AT-05 / AT-10 的证明范围

本次补齐了短时间内、相同发送身份与 token、相同房间和 task_id、重放原请求时的“通知已接受，调用方没有 MCP 结果，进程丢失”的真实恢复证据；也确认在该条件下保留工作目录并非必要条件。

仍不能据此宣称跨 token 轮换、换 sender、换房间、长时间后 transaction 去重保留期限、Task 身份碰撞、消费者重复执行、正在执行的模型或工具副作用、服务自身重启后的恢复全部成立。没有 Worker/模型消费本次通知，更没有外部 GitHub 写入。本轮 task_id 是实验指定的原生 ID，不是 RepoMesh 持久 Attempt 映射。RepoMesh 的命令持久化、Outbox、Attempt fencing、失败恢复调度和业务动作去重仍需其实现后单独联调。
