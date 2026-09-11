# 同机双实例：六个真实模型请求与实际通道核查

2026-09-09。本轮仅发送 **6 条模型请求**：a/b Manager 并发各一条，再在 a/b 同名 Team 的真实房间中分别 mention Leader／Worker，共四条。全部请求中文内容按实际 event ID 逐字读回一致，全部收到正确目标的唯一 marker；其中 b Worker 额外解释一句，因此**目标响应为 6/6，通过严格“仅 marker”格式为 5/6**。

## 真实证据与执行边界

[执行脚本](../scripts/twin-model-live.py)、[只读复核脚本](../scripts/twin-model-readonly-audit.py)；[Manager 并发证据](../evidence/twin-model-live-managers.json)、[Team 并发证据](../evidence/twin-model-live-team.json)、[通道／串线／格式核查](../evidence/twin-model-live-readonly-audit.json)。凭据保存在新的 private state，没有覆盖之前 Matrix 或 Manager 测试状态。

Manager 使用各实例 bootstrap admin；Team 使用主任务新建的对应 `live-twin-human` Human 身份。最初 Team.admin 引用了仅有 Matrix 身份、没有 Human CR 的 bootstrap admin，导致 Team Failed、无 teamRoomID。主任务补齐 Human CR 并更新 Team 关联后才开始 Team 测试。没有绕过房间成员限制、改 allowlist 或重启容器。

每条请求都有唯一 tx_id，发送前保存，未知结果不重发。请求要求只回复 marker，不调用工具、不建资源、不委派、不联系其他成员。报告不以短回复推断所有后台工具调用绝对为零。

## 实际回复

| 对象 | 唯一 marker | 观察延迟 | 精确仅 marker |
| --- | --- | --- | --- |
| a Manager | `RV_TWIN_A_MANAGER_fdf1388d` | 4.266 s | 是 |
| b Manager | `RV_TWIN_B_MANAGER_fcbe3714` | 4.312 s | 是 |
| a Leader | `RV_TWIN_A_LEADER_2ec45857` | 3.312 s | 是 |
| a Worker | `RV_TWIN_A_WORKER_38990409` | 5.578 s | 是 |
| b Leader | `RV_TWIN_B_LEADER_eb06d768` | 5.485 s | 是 |
| b Worker | `RV_TWIN_B_WORKER_586da857` | 5.578 s | 否，marker 后增加中文确认段落 |

观察延迟包括 HTTP 和轮询，不是模型精确首 token 时间。Team 通道通过 `m.replace` 编辑处理占位事件；检查最终文本使用真实 `m.new_content.body`，没有把外层 `* ...` 编辑提示误当模型内容。

房间如下，完整 sender／请求 event／回复 event／server timestamp 均在 JSON 中：

- a Manager：`!cstiVyQcRNbIj1a5r3:rv-a.matrix.invalid`，sender `@manager:rv-a.matrix.invalid`。
- b Manager：`!ZO58QGGf9Ejgh89GCE:rv-b.matrix.invalid`，sender `@manager:rv-b.matrix.invalid`。
- a Team：`!Ff6iZ4IGTwHpkhX922:rv-a.matrix.invalid`，sender 分别 `@live-twin-leader:rv-a.matrix.invalid`／`@live-twin-worker:rv-a.matrix.invalid`。
- b Team：`!pgSItIpN055Z7RrhYv:rv-b.matrix.invalid`，同成员短名但 domain 为 `rv-b.matrix.invalid`。

每个房间再只读扫描最近 100 条 timeline，按六个唯一 marker 匹配：**未发现来自另一实例的 marker，也未发现错误目标 sender 回复某一 marker**。这一结论限于本轮消息与扫描窗口，不等同一般性跨 Issue 授权证明。

## Worker／Leader 实际通道与 session

四个真实成员容器的 `workspaces/default/agent.json` 都为 `matrix.enabled=false`、`agentteams_matrix.enabled=true`，日志 `_on_room_event` 来源也在各自 AgentTeams 自定义插件中。已分别核查，未沿用 Manager 的配置结论。

这与 Manager 的 builtin `matrix` 路径不同。自定义插件源码的 session 构造为 `matrix:{room_id}`，request 用户键为 room_id；报告保存了容器实际源码及行号。**session 标识来源于运行代码映射，未读取私人 session 文件或独立查询持久 session 数据库**。实际 room／sender／event 来源于真实 Matrix 事件，两种证据层级不混用。

## 健康与资源

Team 四请求并发期间，从 `16:48:20.278859Z` 到 `16:48:26.065753Z` 采集 a/b Controller `/healthz` **24 个样本，全部 200**。

Manager 并发阶段健康夹具误用 `/health`，18 个样本均为 HTTPError；后续诊断确认 `/health=404`、正确 `/healthz=200`。原始失败样本保留，没有改写成成功。这是夹具路由错误，**Manager 并发期间的有效 healthz 连续样本缺失**；不能声称那一段服务故障，也不以事后 200 补作历史健康证据。未为修复采样而额外发送模型请求。

Docker 瞬时资源样本在两阶段前后采集，完整 CPU、内存、PID 在 JSON。Team 回复后样本：

| 容器角色 | a 内存 | b 内存 |
| --- | --- | --- |
| embedded Controller（含基础服务） | 1.903 GiB | 1.771 GiB |
| Manager | 437.2 MiB | 422.2 MiB |
| Leader | 472.7 MiB | 476.6 MiB |
| Worker | 464.8 MiB | 470.2 MiB |

这些是低负载瞬时值，不是峰值、容量上限、配额强制或每个逻辑组件的独占消耗。样本显示共同宿主可见内存上限 15.27 GiB，不构成每个 Worker 的业务预算限制证明。

## 对验收的贡献

本轮为 AT-01 实际配置加载、AT-06 房间／目标归属、AT-09 同机双实例真实运行、AT-12 最小实测响应和资源提供证据。没有验证 RepoMesh 多 Issue 歧义、权限变更、持久 outbox、最大吞吐或公平调度，也没有将 b Worker 多余文本隐藏为严格指令通过。
