# 原生 DAG 建图、校验与就绪推进：真实服务补测

完成时间 `2026-09-09T17:06:52.925844+00:00`；run `ec283964ba`。本次补齐 AT-03 新细化的**原生 DAG 子项**，没有实现或模拟 RepoMesh Adapter。原生 `create_project`、`plan_dag`、`ready_nodes`、委派／确认／提交／接受路径均通过真实 TeamHarness 与 MinIO 执行；Matrix 只投递给专用测试用户，没有请求模型、启动业务进程或重启服务。

**结果：合法菱形 DAG 的顺序、并行候选和汇合推进符合原生语义；四类非法图均拒绝且远端图保持不变。`assigned` 节点重复查询仍就绪，重复原生委派复用一个事件；相同原生 transaction 的两次真实 HTTP 重放也返回原事件。上述证据不能替代“受控执行不重复启动”或跨仓业务许可验收。**

## 实验边界与证据

- [原始调用与远端读回](../evidence/dag-native-live-ec283964ba.json)：46 项检查全部成立，17 个就绪阶段；外层 trace 共 74 条，包括 40 次原生 `server.call_tool`、32 次独立 `mc cat` 和 2 次 Matrix timeline 读取。46 项含中间断言，不代表 46 个独立业务验收场景；原生工具内部另外会进行真实同步和 Matrix 请求。
- [同 transaction 实际重放](../evidence/dag-native-live-ec283964ba-tx-audit.json)：原事件／content、两个真实 PUT 回执、最终 timeline；检查通过。
- [容器实验脚本](../scripts/dag-native-live-container.py)、[宿主编排](../scripts/dag-native-live-run.py)、[transaction 补核脚本](../scripts/dag-native-live-tx-audit.py)。两个执行命令均退出 0。

运行位置为 `rv-a-controller` 内系统 Python，导入本轮锁定上游提交 `eeaab64391ccaec9118e84977f538aefd40720d6` 的专属副本 `/tmp/dag-native-mcp-ec283964ba/server.py`；运行时文件 SHA-256 为 `741d211b36a4413e598989c43c9a7735926e18e49787e15a9ef9453d825dc98d`。没有改上游源码、替换业务函数、fake transport 或故障注入。

专属 Project 为 `dag-native-ec283964ba`，四个 task ID 分别在此前缀后追加 `root/left/right/join`。工作目录 `/tmp/dag-native-live/ec283964ba`，存储前缀 `agentteams/rv-a-storage/teams/live-harness/shared/dag-native-ec283964ba`。全程由原生工具创建与修改图和 Task 文件，没有通过夹具直接改状态。使用 Controller 已有 `mc` 权限，**不作为真实 Worker 身份授权范围的证据**。

新建私密测试房间 `!Bhq93P9D6dALJ9Wj98:rv-a.matrix.invalid`，只邀请并加入早期 Matrix 实验的测试 Bob。委派身份／接收人均为 `@mxv_21f3caf31d_bob:rv-a.matrix.invalid`；房间中没有模型成员。凭据只从 `private` 读取并通过标准输入传入容器，未出现在报告或 JSON。这里的 `live-harness` 是隔离存储和 Project 元数据夹具，不声称 Controller 实际调度了此 Team。

## 合法建图与非法图拒绝

先经 `create_project` 创建空图，独立 `mc cat` 验证远端 Project 存在，再用 `plan_dag` 建立：

```text
           ┌─ left  ─┐
root ──────┤         ├──── join
           └─ right ─┘
```

`left/right` 各依赖 `root`，`join` 同时依赖 `left/right`。初始只有 `root` 为候选。随后对同一已持久化合法图分别提交四个无效替代图，每次读取远端 `meta.json` 和 `plan.md`，与原始内容比较：

| 输入 | 原生响应 | 远端图结果 |
| --- | --- | --- |
| 缺失前驱：root 依赖不存在的 absent | `ok=false`，`depends on unknown task` | meta 与 plan 内容均未改变 |
| 两个节点使用重复 root ID | `ok=false`，`duplicate task id` | meta 与 plan 内容均未改变 |
| root 依赖自身 | `ok=false`，`task dependency cycle detected` | meta 与 plan 内容均未改变 |
| 三节点环 root → left → right → root | `ok=false`，返回具体环路径 | meta 与 plan 内容均未改变 |

四次拒绝前后的 meta SHA-256 均为 `ceaed0fe0520d5470ed66e1fc289ffd535f6569091bfb8fb5b9f662390af2349`，plan SHA-256 均为 `6fd3fc0bb0054009c389e073ef68ab2ec1d517138819d8616e5e19c767864e09`。完整无效请求、错误和远端文件正文均保留在主 JSON。该结果覆盖这里的四种形状及两个图文件，不扩展为任意输入或所有对象的事务性证明。

## `ready_nodes` 的实际生命周期语义

各阶段都调用原生 `ready_nodes`，再独立读取远端 Project 的节点状态。状态转换使用 `delegate_task` → `ack_task` → `submit_task` → `accept_task_result`；提交的是明确标记的合成元数据结果、无 deliverables，不包含实际工作完成或产物验证。

| 阶段 | 实际 ready 集合 |
| --- | --- |
| 全部 planned | root |
| root assigned；连续两次查询 | 两次均 root |
| root in_progress | 空 |
| root submitted | 空；分支仍未解锁 |
| root completed | left、right 同时就绪 |
| left、right 均 assigned | left、right 仍同时就绪 |
| left in_progress，right assigned | right |
| 两分支均 in_progress | 空；join 被阻挡 |
| left submitted，right in_progress | 空 |
| left completed，right in_progress | 空；只完成一个前驱不解锁 join |
| left completed，right submitted | 空；submitted 不等于完成 |
| 两分支均 completed | join |
| join assigned | join 仍就绪 |
| join in_progress | 空 |
| join submitted | 空 |
| 四个节点均 completed | 空 |

这与上游 `server.py:_ready_nodes` 的条件一致：Project 必须 active；候选节点自身是 planned 或 assigned；每个前驱的 **Project 节点状态**必须 completed。这里的并行是两节点可同时就绪、元数据可同时处于 in_progress；工具调用按顺序执行，**没有验证真实任务同时运行或全局并发配额**。

最后独立读取四个远端 Task `meta.json`，均仍为 `submitted`，而四个 Project 节点已为 `completed`。`accept_task_result` 推进 Project 图节点，不能据此说 Task 记录也变成 completed。Project 自身仍为 `active`；本次没有调用 `complete_project`，不得把“图无 ready 节点”当成 Project 自动终结。

## assigned 重复就绪、重复委派及同 transaction

root 第一次真实委派后处于 assigned，连续两次 `ready_nodes` 都返回 root。第二次相同 `delegate_task` 响应为 `ok=true`、`synced=true`、`notification.reused=true`，返回相同 event ID：

```text
$dBXq3Q1VdqYT4Oa5Adg9i5-TOl-B7oRqieJ4WvPTGPY
```

独立 timeline 中只出现一次该事件；全部四节点委派后，房间总共四个 `m.room.message`。这验证了已记录通知的原生委派复用路径，**该第二次委派并不必然再次发送 Matrix HTTP**。

为单独确认传输幂等，补核脚本按未修改源码 `_send_delegate_notification` 的 `delegate-{task_id}` 规则，使用同一用户 token、原 room、读回的完整原始 content，向 `delegate-dag-native-ec283964ba-root` transaction 连续执行两次真实 Matrix PUT。两次返回上述同一 event ID；最终 timeline 仍为四条消息，原事件出现一次。

主 JSON 的 `first_tx_id/retry_tx_id` 为 null，因为原生工具响应不提供 `txId`，并非“观察到 transaction 为空”。补核 JSON 明确记录 transaction 的源码来源、实际请求路径与两个回执。这里确认的是同一身份、房间和原生 Task transaction 的通知幂等；没有执行重建 Task、修改 task ID、跨房间迁移或实际 Worker 重复启动测试。

## AT-03 覆盖结论

| 新细化范围 | 本次状态 |
| --- | --- |
| 原生建图、合法依赖、重复 ID／缺失依赖／自环／多节点环校验 | 已以真实工具和远端读回验证上述样本 |
| 原生顺序、并行候选、汇合与状态就绪计算 | 已验证 17 个阶段；不是并发业务执行测试 |
| assigned 重复就绪 | 已确认仍返回候选，调用方必须理解此语义 |
| assigned 重复委派通知及同 transaction 去重 | 已验证 native reused 和独立真实 Matrix PUT 幂等 |
| assigned 重复就绪不得重复启动实际工作 | 未完成业务验收；本次没有 Worker 执行启动、去重账本或 lease |
| 经真实受控 Adapter 复用 DAG，原生 ready 不绕过跨仓／业务前驱许可 | 未完成；当前 RepoMesh Adapter 尚无本轮可执行实现，没有伪造一层证明 |
| 停派工、重规划、下一轮、多目标与崩溃一致性 | 沿用既有专项证据及其边界；本报告不重复测试或扩展其通过范围 |

因此可更新的是“AT-03 原生 DAG 子项已有真实服务覆盖”；AT-03 整体仍不能标记 RepoMesh 业务验收通过。
