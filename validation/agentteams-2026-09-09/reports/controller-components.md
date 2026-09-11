# Controller 组件验证（AT-01／03／04／05／07／09／11）

日期：2026-09-09。上游提交：`eeaab64391ccaec9118e84977f538aefd40720d6`。

## 范围与方法

本报告运行上游真实 Go Handler、存储写入逻辑和 Docker payload 构造代码。Project 存储与 Kubernetes client 使用上游内存替身；生命周期的进程后端使用可注入失败的替身。测试 HTTP 请求进入实际 Handler，但不经过完整服务网络、认证中间件或模型执行。Docker payload 实验不调用 Docker daemon。

自定义探针通过 Go `-overlay` 注入到同包，文件仅位于本验证目录 `scripts/controller-*_test.go`，没有修改上游源码。已有上游测试复用其实际断言，额外的探针记录关键响应及状态序列。所有“PASS”表示预期行为得到复现，包括不符合 RepoMesh 接入要求的行为；不表示 AT 整项验收通过。

运行环境与原始证据：

- [Go 版本](../evidence/controller-go-version.txt)
- [上游相关测试日志](../evidence/controller-upstream-tests.log)及[退出码](../evidence/controller-upstream-tests.exitcode)
- [自定义探针日志](../evidence/controller-probes.log)及[退出码](../evidence/controller-probes.exitcode)
- [可复跑脚本](../scripts/controller-run.ps1)、[Server 探针](../scripts/controller-server_test.go)、[Backend 探针](../scripts/controller-backend_test.go)

## 实验与结果

运行结束：两次 `go test` 均退出 **0**。上游选定测试 **42 个顶层测试、10 个子测试**通过；自定义探针 **7 个顶层测试、8 个状态子测试**通过。Go 为 `go1.26.4 windows/amd64`，module 声明 Go 1.25.0。依赖首次下载和编译成功。

| 实验 | 真实执行结果 | 接入判定 |
|---|---|---|
| AT-03：对同一持久状态依次 pause、replan、resume、replan | HTTP 序列 **200 → 409 → 200 → 200**；409 内容为 `replan requires an active project`；最终存储为 active、新任务 planned | 确认原生 pause 后不能直接应用新计划。resume 只是组件正向对照，未证明恢复窗口安全 |
| AT-03：8 种状态组合 | active+dag+planned、active+空plan_type、active+已completed任务均200；paused、completed Project、loop、in_progress／submitted在途任务均409 | 需要保留业务派工门禁，再选择受控衔接方案；下一轮不能先把 Project 完结 |
| AT-01：创建 Worker 请求含 remoteSkills、model、runtime、resources，再直接读回 CR | 201成功；model、qwenpaw runtime、CPU=1／memory=512Mi已存；**RemoteSkills 数量为0** | 创建成功不能作为所有配置已生效的证据；该字段创建路径存在确定缺口 |
| AT-07：Ready后重建 Handler但保留同一Worker CR | 原先Ready；新Handler的EnsureReady返回Running；随后含`attempt=old-attempt`的Ready请求又使其Ready | 确认Ready仅内存状态且该Handler不校验Attempt代次。测试不经过认证中间件，不能推导旧凭据一定可用 |
| AT-07：注入backend.Start失败后EnsureReady | Start执行1次且失败；HTTP **200、phase=Running**，日志注明reconciler将重试 | Running是状态/期望证据，不能等价于容器已启动，更不能等价于模型可处理 |
| AT-09：Docker CreateRequest显式请求CPU和内存，再运行buildCreatePayload | 实际JSON为`{"Image":"validation:local","HostConfig":{"NetworkMode":"validation-net"}}`；无Memory、NanoCpus、CpuQuota、PidsLimit等字段 | 原生payload路径未落实资源限额；仍需测真实容器，不能排除宿主外部限制 |
| AT-11：实际运行状态归一化函数 | in_progress、submitted都变成in-progress；blocked、cancelled都变成blocked | 展示状态不保留业务验收所需区别，需读取原始状态及独立证据 |
| AT-04：复用上游ETag注入竞态测试 | Pause在读取后遇到新版本返回409；失败Project写不提前更改Task | REST单路径具备条件写冲突行为，不能推广到MCP覆盖上传 |
| AT-04／11：取消时注入Task写失败 | 第一次500：Project节点已cancelled，Task仍in_progress；重试200并使两处收敛 | 不是多对象原子写。恢复流程必须识别部分成功并重试；不是进程已停止证据 |
| AT-05：同名Project跨Team | 无Team的管理员查询409；明确`team=alpha-team`返回200；仅alpha权限调用者仅见自身Project | 该REST读取路径具有消歧保护；映射仍须携带Team和实例身份 |
| AT-11：上游历史快照失败注入 | 快照写失败测试仍允许当前Project写入成功；历史GC测试通过 | 历史记录是best-effort且有限留存，不足以充当RepoMesh完整审计日志 |

上游原测试命令（从`upstream/agentteams-controller`执行）：

```powershell
go test -p 2 ./internal/server ./internal/backend -run 'Test(PauseProject|ResumeProject|ReplanProject|CancelTask|CompleteProject|GetProjectWorkflow_(AmbiguousProjectID|TaskLifecycleStatusNormalization)|WriteProjectMeta|Lifecycle|CreateWorkerPreservesResources|DockerCreate)' -count=1 -v
```

自定义实验通过`./scripts/controller-run.ps1`复跑。此脚本只运行探针并重新生成路径overlay和本次探针日志；原上游回归日志保留。

## 全范围边界

| 验证项 | 本组件实验覆盖 | 仍需部署／业务实验 |
|---|---|---|
| AT-01 配置 | 创建后字段在 CR 中的读回，模型／runtime／资源保存，RemoteSkills 行为 | 配置投影、runtime 实际加载、镜像和包版本、模型调用 |
| AT-03 重规划 | pause→replan→resume 序列，计划类型及任务状态前置条件 | 真 Agent 派工收敛、resume 窗口门禁、迟到产物、跨目标部分应用 |
| AT-04 一致写 | REST ETag 冲突、取消多对象写失败及重试、历史 best-effort | MCP／REST 与真实对象存储交错写、网络断开恢复、所有写入方一致性 |
| AT-05 身份 | 同名 Project 的 Team 消歧、跨 Team 读取约束 | instance/team/project/task/attempt 全链路身份和重试映射 |
| AT-07 就绪 | 内存 Ready 重建丢失，旧回报按名字接受，启动失败回执 | 真实 Controller 重启、双入口竞态、Matrix／模型就绪和旧身份凭据失效 |
| AT-09 资源 | 有显式 CPU／内存请求的 Docker payload 中无对应限额 | 实际容器 cgroup、主机外部限制、双实例网络卷凭据隔离、限额负载 |
| AT-11 证据 | workflow 展示状态压缩、取消部分成功与重试、历史保存失败容忍 | 独立验收产物与来源、迟到结果隔离、GitHub 交付及当前权限 |

本组件工作不运行 RepoMesh DB 事务／SSE、不验证模型效果，也不能证明旧 Attempt 已终止或不再能写文件。完整 AT 结果应合并其他 Agent 的部署与 TeamHarness 实验证据。
