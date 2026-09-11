# AT-01—12 执行状态

2026-09-09，原生实验记录已收拢，完整业务验收仍未完成。本文区分已执行实验、已复现的不满足项和缺少 RepoMesh 实现而无法联调的范围，不是验收通过报告。

## 已完成的组件证据

- [TeamHarness](control-component-report.md)：14 个实际组件实验；10 项原生约束缺口、2 项正常对照、2 项语义边界。Matrix 与 mc 传输是显式 fake。
- [Controller](controller-components.md)：42 个上游顶层测试与10个子测试，以及7个自定义顶层探针与8个状态子测试均执行。调用真实 Handler／Backend，依赖为测试存储或后端替身。
- [Matrix](matrix-component-report.md)：10 个组件实验，加39个上游测试。通道函数真实，runtime、nio、队列及网络传输为显式 fake。

“测试退出成功”表示实际观察符合断言，包括成功复现不符合 RepoMesh 业务要求的行为，不能作为产品验收通过。

## 已完成的真实服务证据

- [最新源码部署](deployment-run.md)：四个官方 Dockerfile 镜像已构建，两套独立 Controller／Matrix／MinIO／Gateway 正常启动；a、b Manager 已启用。
- [Controller／MinIO](controller-live-report.md)：实际认证隔离、CR 读回、暂停与重规划、陈旧覆盖，以及 multipart ETag 与普通文件上传的对照。
- [Matrix](matrix-live-report.md)：两实例各 55 条历史事件、事务重试去重、跨实例凭据拒绝、非成员权限、基础设施重启后的持久性。
- [TeamHarness](teamharness-live-report.md)：真实 MCP 函数与真实 MinIO／Matrix；role 覆盖、paused 派工、跨 Project 同任务 ID、同步失败成功回执等已复现。外部 heartbeat 仍不是实际 Worker 执行证明。
- [Manager](manager-model-live.md)：修正传输转义后中文全文逐字读回、真实模型唯一 marker 往返；实际是内置 Matrix handler，自定义通道测试不能直接推广到 Manager。
- [Worker](worker-runtime-live.md)：实际启动、Gateway 模型配置、Ready、cgroup 与有界 CPU 负载。CPU／内存限制未落实已经确认。
- [实际 Worker 权限](worker-auth-live.md)、[模型工具写文件](worker-model-file-live.md)与[旧 Ready 报告](worker-ready-restart-live.md)：分别记录实际自身凭据、获准 Manager 身份的模型工具闭环，以及停止窗口仍接受 Ready 的边界。
- [双实例运行](twin-runtime-live.md)与[六个模型请求](twin-model-live.md)：同名 Team／成员、真实请求归属、同一 Git 来源的独立 clone 已验证；Worker 发布端口和资源限制另有缺口。
- [MCP／REST 交错及恢复](controller-mcp-race-live.md)：真实 MCP 上传覆盖 REST 暂停；通知已发送后的部分回写恢复可能留下 Project／Task 不一致；真实多目标更新仅部分成功。
- [runtime 恢复](runtime-recovery-live.md)：同 ID 停止／启动后目标 marker 回复，但 Worker 55 条离线编号仅尾部 9 条出现回调；Matrix 完整保存与 runtime 完整处理不能混同。
- [产物与取消](worker-side-effects-live.md)：实际 Worker 容器中的独立夹具进程取消后继续写；缺失附件可被接受，取消后接受使两种元数据终态不一致。夹具进程不是模型发起任务。
- 后续[同一原生 Task 的模型取消](model-task-cancel-live.md)补齐更强证据：真实 delegate 事件驱动模型工具启动 PID，同 Task 取消并独立读回后 PID 仍写 5→8 行，finally 清理。两阶段实验不拼接冒称同一次执行。
- [不同 task_id 的附件正向对照](artifacts-attempts-live.md)：6 个实际附件事件，本地／MinIO／mxc 三处字节哈希一致；旧任务迟到重提未改新任务。收件人离开房间仍可读已知历史附件，不能以 leave 代替业务读权撤销。
- [资源实测](capacity-live.md)：启动、双团队与恢复采样、镜像／磁盘及原生 token 计数；不外推最大承载量。
- [原生 DAG 补测](dag-native-live.md)：合法菱形图的 17 个就绪阶段、四类非法图拒绝且远端不变；assigned 仍可重复就绪，通知复用不能证明实际工作只启动一次。
- [通知结果未知后恢复](mcp-response-loss-live.md)：真实 Matrix 接受通知后、delegate 获得返回值前硬退出；保留目录和空目录两种重试均恢复 assigned、各只一个事件。这一成功窗口不覆盖已有的双对象上传失败反例。
- [删除同名重建的身份](worker-identity-recreate-live.md)：CR／SA／容器标识均更换；旧 SA 在认证缓存窗口仍被接受，随后 status／ready 均转 401；旧 Matrix whoami 仍 200，旧 MinIO 凭据拒绝。
- [checkpoint 版本契约](checkpoint-capability-live.md)：当前 QwenPaw 2.0.1 下代理返回 200 且标为 JSON，正文实际为前端 HTML，不能当作可用恢复接口。
- [实际 Worker 上的官方回归负载](native-regression-load.md)：两边各76项通过，耗时2.120／2.070秒，健康样本各23次全200；保留官方fake边界与前两次准备／采样错误，不作业务重验证调度验收。
- [显式 MCP 配置](mcp-config-contract-live.md)：保存、读回、desired投影、原生DriverCard与工具列表均确认；实际安装客户端调用echo成功，最后清除专用配置和helper。原探针误查mcporter路径已纠正，不能算产品缺陷。
- [不同Team同名Project](project-team-disambiguation-live.md)：两实例无Team读写409，明确Team才能命中正确对象；八次pause/resume逐次只改目标。管理身份、直接元数据夹具和首次multipart ETag失败均单列。
- [实际runtime普通回复与thread](runtime-reply-thread-live.md)：两类输入均到已部署handler并获真实模型回复，但出站未保留入站父消息／thread关系，两者共用房间session。
- [原生采集查询耗时](observation-latency-live.md)：三轮Controller请求4.199—27.020ms，固定11容器stats取回2.058—2.770s；不证明业务状态到页面可见延迟。

本轮可运行的原生对照、失败与恢复实验已记录在下表；业务适配尚无实现的项目保留明确缺口，不因原生测试脚本退出成功而关闭。

## 逐项覆盖

| 编号 | 当前证据 | 尚未完成 |
|---|---|---|
| AT-01 | 提交／四镜像／两 Manager、两 Team 与真实 Leader／Worker 已核对；六请求响应、模型工具实际写文件；支持、忽略及通道选择差异明确 | RepoMesh 版本化 Adapter 和配置生效核验未实现；管理员用户名投影问题尚未修复 |
| AT-02 | 真实 Worker 自身 REST 写入拒绝，但实际 shared 写权限＋工具 role 覆盖可改状态；合法身份可触发真实模型文件写入 | 无许可／旧计划／预算／占用／撤权等统一受控入口未实现，不能验收业务门禁 |
| AT-03 | 真存储验证暂停、在途／submitted／completed、新 DAG 限制；两个目标仅部分更新已读回；MCP 可越过 REST 状态前置条件 | 多目标整体生效、全程停派工、Plan Version 与轮次业务协议未实现 |
| AT-04 | 实际 MCP 拉取→REST pause→原同步上传造成陈旧覆盖；双对象回写失败后重试成功仍状态不一致；真实存储失效与 multipart ETag 对照 | 权威状态、所有写方统一并发约束与业务生效恢复未实现 |
| AT-05 | 真实跨Project同task_id错误复用；同tx_id通知幂等；不同task_id旧迟到不覆盖新产物；双实例同名Project显式Team读写与目标hash隔离已测 | 测试编码不等于持久业务Issue／轮次／Attempt映射；业务代次和迟到结果采纳尚无实现 |
| AT-06 | Manager builtin与Leader／Worker custom分别实证；六请求sender／实例marker正常；Matrix入站thread关系保留，实际Worker回复未保留父消息／thread，仍按房间session | 同会话多Issue可信目标、歧义、各仓权限、迟到归属适配未实现；模型回复不证明这些业务能力 |
| AT-07 | 实际模型处理与 Ready 分开；同 ID 停启及删除同名重建均已测；重建后旧 SA 在缓存窗口可 status200／ready204，之后两接口401，新 SA 同期200 | 首消息／页面双触发、持久待办、业务幂等恢复与运行代次约束未实现；缓存到期不等于 JWT 自然过期测试 |
| AT-08 | 真实双 ack；同一原生 Task 实际驱动模型工具启动 PID，取消持久化后仍写 5→8 行，最终精确回收；模型执行时 Task 仍 assigned；同 Worker 重启旧 token 仍有效 | 业务旧 Attempt 撤权、停止确认和全局最后槽位原子争用未实现；原生取消不满足进程停止要求 |
| AT-09 | 同名 Team／成员并发及共享 Git 来源独立副本、跨凭据拒绝、a 停止不重启 b 已验证；cgroup 未限额，Worker 宿主端口对全部接口发布 | 强制 CPU／内存与统一受限主机策略不满足要求；不承诺恶意租户／VM 级隔离 |
| AT-10 | 两实例 Matrix 原消息持久性与 tx_id 已确认；Worker 停机存 55 条，恢复 sync 默认 10 且 limited=true，只尾部 9 条编号回调，无补拉 | 原生完整 backlog 恢复未通过；RepoMesh 持久 outbox／业务操作去重与未知前序核查未实现 |
| AT-11 | 缺失／失败仍可 SUCCESS／accept；取消后两对象终态不一致；完整6附件三处字节核验、旧首次媒体引用及退房后的历史读取均已实测 | 独立业务验收、动态读权与产物版本固定未实现；不能把历史媒体可读误作当前权限已撤销 |
| AT-12 | 已采启动／双团队／runtime恢复／无新模型任务四阶段61组；另有双Worker各76项官方回归的并行耗时、资源、目录增长及健康记录 | 无全局调度实现，不能验证额度争用、公平性及业务重验证吞吐；有限样本不宣称最大承载量 |

## 环境进度

[Docker启动故障已修复](docker-startup-repair.md)，隔离容器 smoke 通过。[旧环境清理](environment-cleanup.md)已完成独占容器和活动工作目录处理，共享旧卷待用户确认。最新源码四镜像已构建完成；前置构建问题、离线包检查、真实启动与重试证据均保留。

当前仓库是文档设计工程，不能把其他旧 RepoMesh 项目的运行结果等同现行 ADR 已实现。要求 RepoMesh 实现的事务、许可、派工和业务身份约束仍是明确的实现／联调缺口。

原清单细分要求、原生证据与未完成条件另见[完成度审计](completion-audit.md)，其中包含后来细化的 DAG 与跨仓启动要求。它保留所有业务验收范围，没有以测试脚本结束替代验收完成。

当前下一步的验收依赖是 RepoMesh 受控适配和业务实现，而非重复上述已复现的原生失败。若实现、配置或上游版本改变，按受影响条目重测；当前保留原始失败、成功对照、证据审阅及[接手摘要](findings-and-handoff.md)，不宣称 AT-01—12 全部完成验收。旧跨项目共享卷清理也仍等待原有确认问题的答复。
