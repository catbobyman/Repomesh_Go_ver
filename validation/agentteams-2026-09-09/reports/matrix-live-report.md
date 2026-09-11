# 真实 Matrix 服务验证：投递、持久化与身份隔离

2026-09-09；测试 run `21f3caf31d`。测试使用本轮从上游锁定提交构建的两个 embedded 实例 `rv-a-controller`、`rv-b-controller`。各自 Matrix domain 为 `rv-a.matrix.invalid`、`rv-b.matrix.invalid`。镜像及部署事实见本轮部署 inventory；本报告只声明实测 Matrix 范围。

## 执行方法

[执行脚本](../scripts/matrix-live-validation.py)通过 `docker exec -i <container> curl --config -` 向容器内 `http://127.0.0.1:6167` 发送**真实 HTTP**；不使用 mock、模型或 QwenPaw。配置／凭据经标准输入传递，不放入命令行参数或输出。用户 token 和恢复游标仅保存到已受 ACL 保护的 `private/matrix-live-state.json`，报告仅保留测试用户／房间／事件 ID 和脱敏结果。

每个实例创建同短名称的 Alice、Bob、Eve 三名专用用户；Alice 创建私密房间并邀请 Bob，Eve 不入房。私密房间显式使用 `history_visibility=joined`。正常测试请求均使用各用户的独立 access token。AppService token 只用于注册／登录获得用户 token。

```powershell
python -X utf8 validation/agentteams-2026-09-09/scripts/matrix-live-validation.py before
# 由主验证任务协调实例重启，并确认服务恢复后：
python -X utf8 validation/agentteams-2026-09-09/scripts/matrix-live-validation.py after-restart
```

脚本本身不停止或重启任何服务。以上第二阶段在获得实际恢复证据后才记录通过。

## 首次注册失败与处理

首轮 a/b 均在普通 registration-token 注册时返回 **HTTP 400 `M_EXCLUSIVE`**。原始记录保留在 [attempt-01](../evidence/matrix-live-attempt-01-registration.json)，没有覆盖失败证据。

查上游 `agentteams-controller/internal/matrix/appservice.go` 与 `client.go` 确认：默认 AgentTeams AppService 独占本地域全部用户命名空间；应按原生 `EnsureAppServiceUser`／`LoginAppServiceUser` 使用 `m.login.application_service`。随后修改验证夹具走这一实际路径。没有修改服务权限、解除 namespace exclusivity 或使用管理员身份绕过后续房间权限验证。

## 重启前结果

完成时间 `2026-09-09T16:32:08.509282Z`，**174 次真实 HTTP 请求**，命令退出码 0。[结构化证据](../evidence/matrix-live-before.json)。

| 用例 | 实验 | a/b 实测结果 |
| --- | --- | --- |
| ML-01-a/b | 创建／登录三用户、whoami、创建私密房间并让 Bob 加入 | 两实例均成功，Matrix v3 API 可用。全用户名域不同，完整 room ID 不同。 |
| ML-02 | 同一 sender、room、tx_id 连续发送相同内容两次 | 两次回执的 event ID 相同；分页读取 timeline，该 event 只出现一次。证明服务器幂等，不是 fake transport 猜测。 |
| ML-03 | Bob 获取 sync 游标后停止 sync；Alice 顺序发送 55 条；Bob 以旧 since 游标重连 | 每实例 sync 返回完整 55 条且顺序等于发送顺序；分页 timeline 同样完整保留 55 条。两实例合计 110 条。 |
| ML-04 | 发送带真实 `m.mentions.user_ids` 与 `m.thread` relation 的消息，再按 event ID 读取 | 两实例 content 中 mention 和 thread relation 均原样保留。 |
| ML-05 | 用 b 用户 token 请求 a，反向亦然；分别测试 whoami、读事件、发消息 | 6 个跨实例请求全部 **401 `M_UNKNOWN_TOKEN`**。 |
| ML-05 | 每实例 Eve 读取／写入未加入的私密房间 | 4 个非成员请求全部 **403 `M_FORBIDDEN`**；再次读取 timeline，没有拒绝请求的消息副作用。 |

## 重启恢复

状态：**ML-06 已通过真实重启恢复检查，命令退出码 0**。主验证任务顺序重启两个实例后，本脚本核验容器 `StartedAt` 确已改变，再实际使用旧凭据及游标请求 Matrix。没有自行重启、重新注册或重新登录来掩盖恢复问题。[恢复结构化证据](../evidence/matrix-live-after-restart.json)。

| 检查 | 实例 a | 实例 b |
| --- | --- | --- |
| 重启前 StartedAt | `2026-09-09T16:29:38.960244211Z` | `2026-09-09T16:29:48.740314925Z` |
| 重启后 StartedAt | `2026-09-09T16:34:10.714931276Z` | `2026-09-09T16:34:24.797200338Z` |
| 55 条历史事件逐 ID／顺序核对 | 完整保留 | 完整保留 |
| 重用重启前 tx_id | 返回原 event ID | 返回原 event ID |
| 旧 token | 仍可读写所属房间 | 仍可读写所属房间 |
| 旧 thread 事件 | 可读，relation 保留 | 可读，relation 保留 |
| 旧 sync cursor | `/sync` 接受并返回 next_batch | `/sync` 接受并返回 next_batch |

恢复核查耗时 3.485 秒是服务可达后的检查用时，**不是容器恢复时间**。容器启动及其他实例可用性的时间证据由主任务记录在基础设施重启报告。本用例覆盖服务器停止／启动并复用持久卷，不包含丢失卷、磁盘损坏或强制断电。

## 结论的边界

- 这里证明 Matrix 服务器可以保存超过通道 50 条内存缓冲上限的消息。**不证明 QwenPaw 或 RepoMesh 已把这些消息全部处理**。组件报告中的 50 条上限仍然存在，两者并不矛盾。
- Bob 的“断线”指关闭轮询后重新请求 `/sync?since=...`，不是拔网络、丢包或在 TCP 响应途中切断连接。ML-02 是实际重新请求同 tx_id，不宣称注入了真实网络丢响应。
- 顺序结论限于单 sender 顺序发送的 55 条事件；没有覆盖并行多 sender、模型队列调度或跨房间业务全序。
- 双实例 token 隔离和私密房间成员权限通过，不证明同房间内 Issue／仓库权限。所有参与者一旦同房，细粒度业务授权仍是 RepoMesh 的职责。
- 此报告为 AT-07／AT-09／AT-10 的真实基础服务证据。AT-06 的歧义、目标绑定和模型行为、AT-07 的双触发业务幂等、AT-10 的 RepoMesh 持久 outbox 与业务重放仍需单独验证。
