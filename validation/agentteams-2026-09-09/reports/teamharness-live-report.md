# TeamHarness 原生工具与真实 Matrix／MinIO 联调

执行时间 `2026-09-09T16:37:54.718539Z`；run `c39a1bde1e`；命令退出码 0。**7 项原生行为观察全部复现，包含影响 RepoMesh 接入的明确缺口；不是受控适配验收通过。**

## 环境与真实执行路径

- 从本轮上游提交 `eeaab64391ccaec9118e84977f538aefd40720d6` 复制 `plugins/teamharness/mcp` 到 `rv-a-controller:/tmp/repomesh-live-mcp`，使用容器内 Python 3.10.12 导入真实 `server.call_tool`。容器实际执行的 `server.py` SHA-256 与宿主上游文件一致。
- 不修改、monkeypatch 或 stub 业务函数、subprocess、Matrix HTTP。TeamHarness 自身调用真实 `mc cp/mirror` 与真实 Matrix HTTP；验证夹具另用真实 `mc cp/cat` 创建／读回输入记录、HTTP 分页读回通知。
- 专属工作空间 `/tmp/repomesh-live-harness/c39a1bde1e`；专属对象前缀 `agentteams/rv-a-storage/teams/live-harness/shared/c39a1bde1e/{case}`。没有读写主验证任务的 `shared/projects/live-control-*`。
- 使用已有专用测试 Bob 的独立 Matrix user token，另建专属房间 `!Funjq2MWCDFBx6i5ao:rv-a.matrix.invalid`，没有向真实用户或现有业务房间发送消息。凭据由宿主 private 文件经 stdin 传入，仅存在进程环境／内存，不进入命令参数或报告。
- `AGENTTEAMS_AGENT_ROLE=worker` 为明确运行环境输入。测试工具面的 `role=leader` 是待验证参数；没有修改 Controller 全局权限、实例配置、默认 mc alias，也没有启动真实模型。
- Project／Task 是精确写入真实存储的测试元数据，**不是通过真实 Manager 推理或 Worker CR 自动创建的业务任务**。观察能证明原生工具及其存储／通知副作用，不能替代完整 Agent runtime 执行或 RepoMesh 资源 lease。

运行脚本：[宿主编排](../scripts/teamharness-live-run.py)、[容器实验](../scripts/teamharness-live-container.py)。

```powershell
python -X utf8 validation/agentteams-2026-09-09/scripts/teamharness-live-run.py
```

[原始请求／响应和 trace](../evidence/teamharness-live-results.json)包含 18 次 `server.call_tool` 请求与回执、15 次夹具真实 mc 命令／输出、3 次真实 Matrix timeline 读回和 1 次模拟进程清理。**15 是夹具额外 mc 操作数，不包含原生函数内部全部 mc 子进程数量**；没有以不完整计数声称完整网络追踪。各回执、权威存储读回、Matrix event ID 共同证明副作用实际存在。

## 实验结果

| 用例／关联清单 | 实验与真实结果 | 含义 |
| --- | --- | --- |
| THL-01／AT-02 | runtime role 为 worker 时直接委派被拒绝；相同调用加 `role=leader` 后成功，Task assigned 存入真实 MinIO，真实 Matrix 通知可读 | 原生 taskflow 的角色参数不能独自充当可信身份边界。没有验证外层网关／RepoMesh 是否会禁止这个入口，因此不把它宣称为完整部署越权漏洞。 |
| THL-02／AT-02/03 | paused Project 的 ready_nodes 返回空；直接 delegate_task 仍成功。真实远端 Project 保持 paused，Task 为 assigned，通知 event 在 Matrix timeline 中 | “只先查询 ready_nodes”不足以保证停止派工；受控门禁必须覆盖直接委派路径。 |
| THL-03／AT-02/03 | paused Project 含 in_progress 旧节点，worker runtime 调用 plan_dag 换成新节点 | 工具返回 ok，真实远端 DAG 被替换，Project 仍 paused。与 REST replan 的 active／无在途前置条件并不等价。 |
| THL-04／AT-05 | Project A 委派 `collision-T1`；同 A 重试；Project B 再使用相同 task ID | 同 A 重试复用事件，真实 timeline 只一条，符合单次逻辑操作幂等；但 B 请求也返回 A 的任务／事件且 `reused=true`，B 节点仍 planned。证明同共享范围跨 Project task ID 碰撞已实际发生。 |
| THL-05／AT-08 | 同一 runtime user、两个任务分别委派并 ack | 两次 ack 均 ok/synced，真实远端 Project 的两个节点都为 in_progress。仅元数据确认，没有真实模型并发、执行 lease 或排他进程管理。 |
| THL-06／AT-08/11 | ack 后启动一个外部模拟业务 Python 子进程，每 0.1 秒写 heartbeat，再调用原生 cancel_task | 真实元数据 cancelled，后续 ack 被 terminal 检查拒绝；模拟进程仍活着，写入从 4 行增至 10 行。夹具 finally 已终止自己创建的 PID 4513，退出码 -15。 |
| THL-07／AT-04 | 仅当前 Python 进程设置无效 mc 凭据连接真实 MinIO，再调用 filesync stat 和 plan_dag，随后恢复原环境并读回 | stat 实际失败；plan_dag 仍返回 ok。本地任务变成 `failure-new`，真实远端仍为 `failure-old`，远端元数据没有变化。证实工具成功不等于共享状态已生效。 |

## 故障注入与结论限制

THL-07 没有关闭 MinIO 或改共享 alias：仅在实验进程内临时设置 `MC_HOST_agentteams` 为明确无效凭据，保留真实 endpoint；`finally` 恢复后直接读取原对象。此用例证明真实存储失败与成功回执分离，未单独区分“pull 成功但 push 失败”。需要该精确故障窗口时应另做受控代理或权限阶段切换实验，不把本例扩大解释。

THL-06 的 Python 进程是**明确的外部业务模拟器**，并未被 AgentTeams Worker runtime 启动、管理或登记进程身份。结果说明原生元数据取消不会自动终止任意外部执行，不能直接声称已验证真实 Worker 的停机、进程树清理、容器资源释放或旧 Attempt 写入撤权。完整 AT-08 仍需 RepoMesh 可信执行／lease 和真实 runtime 生命周期证据。

本实验全部正常夹具写入采用真实 `mc cp` 临时文件／原生 `mc mirror`，未用 `mc pipe` 伪造普通对象的 ETag。没有修改 Controller 的 CAS 行为或掩盖主任务观察到的 multipart ETag 差异。

## 对接入设计的结论

原生 MCP 的角色边界、暂停门禁、inflight 重规划约束、跨 Project 身份唯一性、Worker 单占用与存储生效证据都需要 RepoMesh 受控适配或明确上游修复。此次真实服务实验把此前相同内容的组件观察提升为存储与 Matrix 联调证据，**没有使这些业务约束自动达标**。

同一已委派操作重试的任务／通知复用已获得正向真实证据；该保证应保留，并与不同 Project、轮次和 Attempt 的唯一标识一起设计，不能通过“每次随机换 task_id”绕开碰撞而破坏幂等。
