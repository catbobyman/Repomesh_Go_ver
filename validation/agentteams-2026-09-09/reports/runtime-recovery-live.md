# 真实 runtime 停止／启动、离线投递与恢复缺口

2026-09-09。**a Worker 和 a Manager 都在复用原不可变容器 ID 启动后回复了停机期间保存的唯一 marker；但 Worker 的 55 条离线编号消息未全部进入原生通道回调。** Matrix 持久保存与 runtime 完整消费必须分开验收。

## 执行与约束

[执行脚本](../scripts/runtime-recovery-live.py)仅对已授权的 `rv-a-worker-live-twin-worker` 和 `rv-a-manager` 逐个 `docker stop --time 5 <immutable-id>`／`docker start <same-id>`。没有停止 Controller、其他成员或实例 b，没有修改配置、权限、allowlist 或自动重试模型请求。脚本 finally 核对并恢复原 ID 为 Running。

停止前记录 ID、StartedAt、旧 Matrix sync cursor、身份和房间。所有消息 tx_id 发送前持久保存；发送后按事件 ID 逐字读回。每个 runtime 仅一条模型 marker 请求，没有未知发送重试。

Worker 停机期间保存 55 条编号 00—54 的普通消息，明确不 mention 任何 bot；随后保存一条仅 mention 目标 Worker 的新 marker。事先只读确认同房 Leader 对全局与该 teamRoom 都配置 `requireMention=true`。Leader 实际日志记录未 mention 缓存，恢复窗口的 timeline 没有 Leader 发出的模型回应。

Manager DM 中普通消息可能直接触发模型，所以该用例**只保存一条 marker，不发送 55 条普通消息**。这是两个不同覆盖范围，不把 Manager 用例写成大缓冲恢复。

## 容器与实际回应

| 核查 | Worker | Manager |
| --- | --- | --- |
| 不可变 ID | `1b8bdff6e607536dc2e6e9a5e01c8134a993486c59bdb4ee2a4946814668eb3c` | `90648a5b386310775ef6eb9d37496bf7141022f77f0b19d4dc9bcd0a7efd317d` |
| 停止窗口 | 55 条编号＋1 条 marker 全部确认在停止时接受 | 1 条 marker 确认在停止时接受 |
| 容器重建 | 无，前后 ID 一致 | 无，前后 ID 一致 |
| StartedAt | 确实变化，新值 `16:51:55.480603979Z` | 确实变化，新值 `16:52:29.220442071Z` |
| start 完成后观察到回复 | **14.578 s** | **31.937 s** |
| marker | `RV_RECOVERY_WORKER_d64b8902c9` | `RV_RECOVERY_MANAGER_8a105f7b6b` |
| 最终状态 | 原 ID Running | 原 ID Running |

以上响应时间包括 runtime 初始化、模型响应和轮询观察，不是模型首 token 延迟。两条最终文本都精确等于 marker（Worker 通过 `m.replace` 的 `m.new_content.body` 读取）。容器 StartedAt 与 stopped/running 快照、请求事件、回复事件、sender／room／时间均保存在 [Worker 原始证据](../evidence/runtime-recovery-live-worker.json)和 [Manager 原始证据](../evidence/runtime-recovery-live-manager.json)。

## 关键发现：55 条保存成功，不等于 55 条恢复处理

[补充只读审计](../evidence/runtime-recovery-live-worker-sync-audit.json)得到三组互相印证的事实：

1. 55 条编号消息全部逐事件读回成功，最后 marker 也在 Worker 停止期间接受。没有 Controller 自动拉起打断停止窗口的证据。
2. Worker 恢复日志明确 `restored token, performing full-state sync`。完整时间窗口日志中的编号消息 `_on_room_event` 仅为 **46—54，共 9 条**；00—45 未观察到相应回调。最后 marker 随后被模型正确响应。
3. 用同一测试 Human 的停机前旧 cursor 只读请求真实 `/sync`：不指定 timeline limit 返回 **10 条、`limited=true`**；显式 `timeline.limit=100` 返回 **59 条事件**，其中包含全部 55 条编号消息。这个额外读取没有把消息重新注入 runtime，也没有发送第二条模型请求。

原生自定义通道 `channel.py:1629—1644` 恢复时调用 `sync(since=next_batch, full_state=True)`，没有指定 timeline limit；正常循环 `1660—1672` 同样直接更新 next_batch。当前源码没有对 `timeline.limited` 做分页补齐。这与实测只看见末 9 条编号＋最后 marker 相符。

**结论：本次“已保存离线消息完整恢复到 runtime”的要求未通过。** 不是 Matrix 丢失持久消息，也不能靠最后 marker 成功掩盖。9 条回调是运行日志证据，默认 10 条及 limited 是真实服务器读回，缺少 backfill 是固定源码事实；三者层级分别标明，不声称额外读取 Human cursor 就是直接抓取 Worker 网络包。

即使将默认 sync 数量提高，50 条内存 history 本身仍不能代替业务消息持久队列。本次早期截断发生在 sync timeline 交付层，先于此前确认的 history_limit=50。完整 AT-10 应定义有限 timeline 的分页／补齐、消费游标、已处理确认与幂等，再运行同样故障窗口。

## 控制面及另一实例未受影响

- Worker 用例：a/b `/healthz` 共 **208 样本，全部 200**；b Controller／Manager／Leader／Worker 共 26 轮 ID/StartedAt 快照，均与启动前一致。
- Manager 用例：a/b `/healthz` 共 **138 样本，全部 200**；b 四容器共 18 轮快照，ID/StartedAt 均未变化。
- 合计 **346 个 healthz 样本、44 轮 b 容器快照**；没有把历史错误路由 `/health` 的采样混入。

这些事实证明本轮停止／启动 a 的两个 runtime 时，另一实例容器没有被重启、a/b 控制面仍响应。它们不证明实例间 CPU／内存强制隔离或最大压力下的可用性。

## 验收状态

- **已通过实际观察：** 同一容器 stop/start、身份和房间复用、停机期间 Matrix 接受、旧 token/cursor 后续可用、最后一条目标请求恢复后由真实模型回应、finally 恢复、另一实例生命周期不受影响。
- **已复现缺口：** Worker 大于默认 timeline 的离线 backlog 未完整送达原生消息回调。
- **未在本例证明：** 每条编号消息都被模型处理、RepoMesh 持久 outbox、真实业务副作用幂等、丢卷／磁盘损坏恢复、全机故障、硬配额或 Worker lease 撤权。本用例不改动上游来制造通过结果。
