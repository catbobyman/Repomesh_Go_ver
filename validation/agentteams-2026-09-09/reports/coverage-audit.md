# AT-01—12 覆盖审计与剩余实验

审计日期：2026-09-09。本文件只审计已落盘证据并提出实验，**没有执行新实验、操作服务或修改其他文件**。上游基线为 `eeaab64391ccaec9118e84977f538aefd40720d6`。执行仍在继续，后续新增证据应补入主状态记录；本审计不将尚未读取的运行结果判为失败或通过。

## 结论

现有隔离部署仍能完成几组有价值的原生验证，优先是：**真实 Worker 身份与工具可达面、runtime 实际启动的进程在取消／停机后的行为、派工通知成功但状态回写未知时的恢复、不同 Attempt 的迟到产物、真实附件完整性与读取权限。** 这些无需写入真实 GitHub，也不必等待 RepoMesh 业务后端才能调查。

但 AT-02 的业务许可与执行门禁、AT-03 的多目标整体生效、AT-05 的持久业务身份、AT-08 的统一资源预留、AT-11 的独立验收，都需要 RepoMesh 实现后才能验收。当前没有该实现：见 [HANDOFF](../../../docs/current/HANDOFF.md) 的“原型与实现完成度”，以及 [架构 §6／§8](../../../docs/current/architecture-design-v1.md)。不能把新建一个测试字典、测试数据库表或测试锁的成功叫作 RepoMesh 已经具备这些能力。

已有原生缺口复现是“查明不满足要求”，不是“AT 通过”。特别是原生 Docker 限额已经从 payload、实际 HostConfig、真实 cgroup 与有界 CPU 负载四层确认不符合请求，没有必要再以 OOM 或更长压力测试重复证明同一缺口。

## 本审计采信的证据

- [TeamHarness 组件](control-component-report.md)：14 项，外部传输为明确 fake。
- [TeamHarness 真实服务](teamharness-live-report.md)：THL-01—07；真实 MCP、mc/MinIO 与 Matrix，但运行于 Controller 内的独立夹具，使用专用 Bob 用户 token，**不是实际 Worker runtime 工具执行**。THL-06 的写入进程由夹具额外启动，不归 Worker runtime 管理。
- [Controller 组件](controller-components.md)与[真实服务](controller-live-report.md)：REST 状态衔接、存储覆盖、真实 token 隔离、资源创建及两实例持久化恢复。LIVE-C04 的覆盖使用管理员存储能力，不能外推 Worker 拥有同样能力。
- [Matrix 组件](matrix-component-report.md)与[真实服务](matrix-live-report.md)：服务器 55 条消息、权限、tx_id、旧 token／游标恢复；组件通道行为与真实模型消费分开。
- [实际 Worker](worker-runtime-live.md)：真实 Running→Ready、模型配置与插件文件投影、实际 cgroup 限额缺口；尚无 Worker 模型任务／执行工具过程。
- [Manager 模型](manager-model-live.md)及[中文纠正证据](../evidence/manager-model-live-corrected.json)：正确中文逐字读回、目标 Manager 精确 marker 响应已取得证据。当前 Manager 实际使用 builtin `matrix`；AgentTeams 自定义通道注册为 `agentteams_matrix`，只注册但未被 Manager 配置启用。组件自定义通道结论不能直接套到 Manager。
- [容量采样](../evidence/capacity-startup.json)：16:41:13—16:43:13 UTC 共 15 次采样，观测 a Controller／Manager／Worker 与 b Controller。它明确是当前部署采样，不是最大容量基准，也不是两实例都有 Manager／Worker 的并发负载测量。

[validation-status.md](validation-status.md) 的逐项表仍含早期“真实服务／当前源码镜像／模型／容量尚未运行”等描述；上述更晚的专项报告和原始证据已覆盖其中部分内容。本审计使用具体实验结果，不把旧总表的未完成项机械复制为当前缺口，也不修改该表。

## 逐项覆盖与责任边界

| 项目 | 当前最强证据 | 现有上游／隔离部署仍可补的实验 | 必须等 RepoMesh 实现的验收 |
| --- | --- | --- | --- |
| AT-01 | Controller／Manager／Worker 当前源码镜像，持久配置与运行文件读回；Manager 中文模型回包；Manager 实际通道选择偏差已定位 | 读取实际 Worker 工具注册与调用 trace；完成 Worker 模型→工具→产物闭环；真实 Team／Leader 创建、成员／房间／凭据投影。既定 Manager 通道配置应如实测量，若切换需作为单独配置变更重测 | Adapter 对支持／忽略字段的处理、运行契约版本及配置生效核验 |
| AT-02 | THL-01 role 参数覆盖、THL-02 暂停后真实通知、THL-03 原生改图；真实 Controller 管理 token 跨实例被拒 | 下文 N1：真实 Worker／Leader 自有凭据与已安装工具面；N2：用真实工具执行观察本地文件／Git 副作用；N6：旧运行身份能力 | 无许可、旧 Plan Version、无占用、撤权、预算耗尽时所有入口统一拒绝；身份可信绑定；执行端再次核验 |
| AT-03 | 真实 pause→replan→resume→replan 为 200/409/200/200；组件有 8 种状态；paused/inflight 原生 MCP 可改图 | N2：在真实工作期间 pause/cancel；N3：将 submitted、completed、下一有限 DAG 以及两 Project 部分应用变成真实存储事实 | 选定 pause/replan 接法的全程门禁，多目标生效状态、崩溃恢复与既有 Plan Version 的轮次规则 |
| AT-04 | 真实普通覆盖写可覆盖暂停；THL-07 真存储失败而 plan_dag ok；REST 条件写及部分取消为组件证据 | N4：真正 MCP 拉取→暂停→上传交错；精确区分 pull 成功／push 失败，以及通知已落盘／assigned 回写失败 | 唯一权威事实、统一并发控制、计划生效核验和恢复算法 |
| AT-05 | THL-04 同次重试一条真实通知，但跨 Project 相同 task_id 返回旧任务；跨 Team 消歧为组件证据 | N5：独立 task_id 的下一轮／新尝试、旧结果晚到、不同 sender/room 范围；真实 REST 同名 Project 跨 Team；N4 崩溃重试 | 持久 `instance/team/project/Issue/Task/round/Attempt` 映射、旧结果归属及业务幂等 |
| AT-06 | 自定义通道房间 session／字段投影组件；Manager builtin 中文模型冒烟 | 以实际生效 handler 做同房两事项和双房请求的可追溯本地文件实验，读取 session／工具 trace；确认 Worker 与 Manager 的实际 handler 差异 | 主会话多 Issue 的可信目标、正文与导航来源规则、当前仓库权限、歧义澄清业务协议 |
| AT-07 | 双 Controller／Matrix 持久化恢复，真实 Worker Ready、Manager 模型响应；旧 Ready 代次仅组件 | N6：真实 runtime 停启／重建、旧自有 SA token 的 Ready 回报和权限；真实运行进程／队列恢复 | 首消息／建项双入口的持久创建、同事务待办、未知外部结果核查、只复用一套正确实例 |
| AT-08 | THL-05 同 Worker 两任务 in_progress；THL-06 取消不终止外部模拟器；真实资源未限额 | N2／N6：真实工具进程取消、sleep、网络失联后的写能力，真实队列最大并行度、恢复后重复执行；独立 clone 的隔离对照 | Attempt＋Worker＋团队／项目／全局最后槽位原子预留；准备期间撤权／取消；代次失效和资源释放分开；替补启动门禁 |
| AT-09 | 真实双实例 token／Project／Matrix 房间隔离；交替重启互不影响；真实 Worker cgroup 未符合 0.5CPU／512Mi | N1／N6 的真实 Worker 跨实例／跨 Team 存储请求；两个实际 Manager／同短名称 Team／Worker；同一本地 bare repo 的独立 clone 写入隔离 | 受限主机执行模块、Agent 无任意 socket／挂载通道、强制资源约束及统一生命周期管理 |
| AT-10 | Matrix 真实 tx_id 幂等、55 条历史与旧游标恢复；组件回调重复、缓存等 | N4 精确丢响应；实际生效 runtime 的未读消息、进程重启、重复消费和多 sender／房间队列调度；不能把服务器有消息当模型已处理 | 持久 outbox／待办、服务端业务顺序、结果未知先核查、业务幂等消费 |
| AT-11 | 组件完成／接受语义、状态压缩、取消分步写；THL-07 真存储失败；目前无完整实际产物验证 | N5／N7：真实 result/deliverables、缺失附件、篡改、读取权限变化、迟到提交、Project complete 与底层文件差异 | 不可覆盖证据归档、来源／组合／版本适用性、作者独立性、当前读权、业务接受／交付条件 |
| AT-12 | 120 秒 15 次资源采样；Controller 恢复约 12.8／13.3 秒，单 Worker Ready 约 13.5 秒 | 同负载下 API 延迟、实际 Manager／Leader／Worker 分项成本、磁盘与 provider 用量；本地有界负载阶梯，每级带明确退出条件 | RepoMesh 全局额度争用吞吐／调度成本；容量上限不能由原生容器数直接外推 |

## 优先剩余原生实验

以下是建议，尚未运行。测试中的“通过条件”指这一条实验的可核查判定，不等价于整项 AT／RepoMesh 验收通过。所有故障都限定到新建的验证身份、对象前缀、文件、进程和测试请求；不变更共用 MinIO／Matrix 的全局凭据或其他项目权限。

### N1：使用真实 Worker 身份调查实际入口（AT-01／02／09，优先）

**缺口：** THL-01—07 已有真实存储与通知，但凭据和运行入口仍由 Controller 内夹具提供；[该报告第 5—15 行](teamharness-live-report.md)已明确边界。真实 Worker 报告只确认插件 manifest 进入工作区，未证明对应工具成功注册并被 runtime 调用。

**最小夹具：** 单独创建一个验证 Team／Leader／Worker，或为现有专用 Worker 建专属测试范围。按实际生效 runtime 读取工具注册结果，要求执行一次只写自己验证目录 nonce 文件的工具，记录消息 event、工具名／参数／结果、PID、文件 SHA-256。随后用该 Worker 自己的 Controller SA token、Matrix token、存储临时凭据分别做自有、另一测试 Team、另一实例的最小读写；不得用管理员凭据替代否定用例。原生 MCP 的 `role=leader` 输入也要在实际工具面重试，保持真实身份不变。

**判定：** 正常路径要有真实文件或对象／事件读回；拒绝路径要同时证明 HTTP／工具拒绝及对象／timeline 无新增 nonce。若工具未注册、sandbox ASK 阻止执行，记录实际边界，不能关闭保护后仍称原配置通过。Manager 广泛权限是原生角色契约，不能因它成功管理资源就判为 Issue 级越权漏洞；RepoMesh 细粒度许可尚不存在。

### N2：取消与暂停作用到真实工具进程的哪一层（AT-02／03／08，优先）

**缺口：** THL-06 的外部 Python heartbeat 只证明元数据取消不杀任意外部进程，尚不能回答 Worker runtime 管理的工具子进程／进程树是否停止。源码 `taskflow.cancel_task` 只更新并同步元数据，而 `LifecycleHandler.Sleep` 会尝试 `backend.Stop`，两者应分开实验，不能混成一个“取消”。见 `upstream/plugins/teamharness/mcp/server.py:4412` 与 `upstream/agentteams-controller/internal/server/lifecycle_handler.go:73`。

**最小夹具：** 由真实 Worker 工具启动一个最长 20 秒、每 200ms 追加 nonce/时间/任务 ID 的进程，仅写新建任务子目录；可带一个子进程以观察进程树。记录实际启动 trace 后，先调用原生 task cancel，另一次独立运行测试 Project pause，第三次通过该 Worker 的原生 sleep／停止接口。分别记录 metadata、PID／进程树、Docker running 状态、输出增长及结束时间。不改正在验证的其他 Worker，也不把 docker exec 额外启动的 heartbeat 冒称 runtime 工具启动。

**判定：** 原生 pause/cancel 后若继续写，记录明确缺口；sleep 只有实际 PID 消失、写入停止和容器状态一致才可计为本用例停止。若停止回执成功但仍运行也须如实记录。并发两次实际工具请求可测该 runtime 的排队／并发事实，但即便恰好串行也不能证明 ADR-0017 的全局槽位原子性。启动工具时拒绝或等待 ASK 也是可用性／执行策略结果，不以额外外部进程补成成功。

### N3：真实存储上的在途重规划、下一轮及部分应用（AT-03）

**缺口：** 真实 REST 只测过一个顺序衔接；8 种状态前置条件为组件实验。业务多目标整体生效没有实现，原生仍可调查两个独立 Project 各自的事实。

**最小夹具：** 两个专属 Project 分别安排 planned、真实 ack 后 in_progress、真实 submit 后 submitted、节点 completed、Project completed。针对各状态调用真实 replan，并独立读取原始 Project／Task 与 workflow 摘要。对仍 active 且本轮节点均终态的 Project，用新 task_id 写下一有限 DAG；另对 Project completed 做拒绝对照。两目标实验只让 A 更新成功，B 因 submitted 返回冲突，再终止负责顺序调用的**测试协调进程**，重建夹具后重新读取两边。

**判定：** 成功／409、版本与节点状态必须和真实对象一致；A 已更新、B 未更新的事实必须保留。该实验只能证明原生多次写入可能部分完成，不能证明 RepoMesh 自动回滚或恢复。不得将 `resume→replan` 对照默认为已采纳方案；没有可信门禁时，恢复 active 的派工窗口仍未解决。轮次 ID 与业务 Plan Version 的关系继续由 RepoMesh 定义。

### N4：精确故障窗口与跨进程幂等（AT-04／05／10，优先）

**缺口：** LIVE-C04 是管理员普通覆盖；THL-07 同时让拉取／上传能力失败；THL-04 只有无故障同进程重试。尚无“通知已被 Matrix 接受，但客户端未收到回执／assigned 元数据未上传”的真实恢复证据。原生发送后才持久标记 assigned，并分别同步：`server.py:4250-4338`。

**最小夹具：** 只给专属 MCP 进程配置请求级故障代理，或 PATH 中的 mc 调度包装器；包装器正常路径仍调用原始真实 mc，只延迟指定对象的上传，不伪造成功响应。先等待真实拉取完成，再 REST pause，放行真实上传。另在专用 Matrix send 已获服务端 event 后丢弃该次响应，或在通知成功后的 Task 上传阶段拒绝指定对象写入，然后终止 MCP 夹具。用原持久工作目录、同一身份和同一逻辑 task_id 重启重试；再用丢失本地工作目录的单独用例比较。拒绝／延迟只命中特定测试 key/tx_id，避免改 Controller 全局 endpoint 或停 MinIO。

**判定：** 分别核对 Matrix timeline event 数、远端与本地 prepared/assigned、Project 节点、重试回执；陈旧覆盖要通过对象字节／ETag 证明。记录精确失败阶段，不能把恢复连接后普通重试外推成所有崩溃窗口幂等。包装器／代理是显式故障调度夹具，正常存储与通知仍是真实服务；不能声称整条测试完全没有故障注入层。

### N5：新尝试、迟到结果与身份范围（AT-05／08／11，优先）

**缺口：** 相同 task_id 跨 Project 碰撞已定性，不必重复换名称再证明。仍需验证新的唯一标识保留旧结果，以及真实身份／房间变化时的通知范围。

**最小夹具：** 在同一测试 Team 下建 A/B 两 Project，为 A 第 1／2 轮与同轮新 Attempt 使用明确不同的 task_id，分别生成内容不同的 result 与 marker 文件；先同一次逻辑操作重试，再以独立 task_id 开替代尝试，最后让旧身份提交旧结果。另用两个测试 Team 同名 project_id 经真实 REST 读取／更新，验证无 Team 参数冲突、显式 Team 正确归属。通知重试依次改变 sender 或 room 的用例单独标识，不能预设它们与原 sender/room 共享事务去重范围。

**判定：** 每个任务目录、对象、event、提交者、内容哈希和业务夹具 ID 全部能对应；新旧产物不能覆盖。原生若允许被计划移除但本地仍 in_progress 的旧任务提交，要如实保存其归属与影响；不能先假定 terminal 检查覆盖所有晚到路径。`_taskflow` 会先拉 Project（`server.py:4082-4099`），所以不得为了复现而描述成“提交完全不拉权威计划”；需针对拉取之后交错、旧节点已移除、TaskMeta／Project 不一致分别安排真实条件。实际 RepoMesh 映射表和“不解除当前依赖”的判定仍未实现。

### N6：旧执行的凭据、恢复与写能力（AT-07／08／09）

**缺口：** 旧 Ready 在组件内按名字接受，不证明真实旧 token 在身份重建后仍有效；基础设施重启也不等于 Worker 进程／队列恢复。Ready Handler 不读取 Attempt，但鉴权由中间件负责，见 `lifecycle_handler.go:162-172`，必须实际经过它。

**最小夹具：** 为单独验证 Worker 将自己原先已合法获得的 SA token、Matrix token 和存储凭据仅留在 private。分别测试其原生 sleep→wake、停止→重建／同名重建后的旧身份请求：自有 Ready、另一 Worker Ready、自有测试对象写入、另一 Team／实例对象读写；采集真实 HTTP 与对象结果。若要测网络失联，只暂时隔离该验证 Worker；20 秒文件 writer 有自身期限，观察本地写入、上传失败、重连后旧文件上传与新执行的关系。其他实例作为可用性对照，重启／断网仍需主任务协调。

**判定：** 分开记录控制面 Ready 回报、模型消费、实际进程停止、存储写能力及凭据过期／失效。旧凭据仍能完成原生允许的自有操作是代次隔离的适配需求，不自动等价为上游身份认证漏洞。凭据失效不等价为 PID／CPU 已释放；容器停止也不自动证明已经发出的远端请求被撤销。RepoMesh 未实现前不能宣称“允许替补”的业务安全条件通过。

### N7：实际附件、状态与可复核性（AT-11，优先）

**缺口：** 当前多数完成／接受语义为组件；还没有用真实附件对比 status、对象存储与 Matrix 附件。上游 `_task_result_from_meta` 核验 result_status／summary／路径格式，未在那里核验内容存在或哈希；`check_task.effective` 用 submitted 加这些校验结果计算。见 `server.py:3770-3806,4443-4460`。这只能提出需要实验的边界，不能提前宣布所有缺失文件都被接受，因为 artifact 发布有自己的错误结果。

**最小夹具：** 真实工具提交三组小文件：完整 `result.md`＋UTF-8 deliverable；声明 deliverable 路径但文件缺失；文件存在但 Matrix 上传或存储同步阶段只对本任务失败。读取 submit 回执中的 `publishedArtifacts`／`synced`、check_task、Project 原始／摘要状态、MinIO 对象字节、Matrix event／下载内容。再提交后修改或删除**本用例文件**，检查现有引用是否仍能复核；最后让测试收件人退出 joined-only 私密房间，比较旧 artifact 引用的后续读取结果。已经下载／读入上下文的数据不能声称被撤回。

**判定：** 完整用例须内容哈希、文件版本和任务身份一致；缺失／失败用例分别记录各层是否成功及差异。即使上游 complete／accept 返回成功，也只说明原生状态写入，不能转换成业务已验收。判断是否可归档、验证者独立性、固定组合和当前读权由 RepoMesh 完成；可以调查上游不会提供哪些证据，不能用上游 completed 替代这些实现。

## 不写真实 GitHub 的夹具安排

1. 在本轮独立 workspace 下新建小型 bare Git 仓库，确认 remote 是该验证路径或 `file://` 本地路径；只含两三个文本文件。每个业务夹具 Attempt 独立 clone／分支／构建目录，Git 对象／ref／工作树 SHA-256 和提交 hash 可作为真实 Git 副作用证据。没有 GitHub token、推送到远端服务、PR、合并或外部消息。先核实该实际 Worker runtime 可用 Git，再决定工具路径，不预设镜像已安装它。
2. 若要观察“调用 PR 接口前后”的行为，可在本轮网络里放只记录 nonce／请求哈希的本地 HTTP 接收器，提供明确标记的假响应。它只能证明测试执行路径／重试次数，不能证明 GitHub 权限、PR 幂等、真实合并或 webhook 契约。不要把假 PR 响应写进正式交付证据。
3. 文件／对象／消息只使用 `coverage-<run>-<case>` 专属前缀与测试房间；普通对象上传沿用文件＋真实 `mc cp`，避免 LIVE-C06 中 `mc pipe` 的 multipart ETag 差异混进普通故障用例。凭据留 private，公开证据只记身份、操作范围、event/object/version/hash 和状态。
4. 用真实 runtime 工具启动的有界 writer 可测执行副作用；由夹具外部启动的 writer、fake model endpoint、故障代理都要标明自身边界。安全夹具可以替代业务内容，不能替代可信授权／Attempt 占用实现，也不能把“夹具自己正确”当产品通过。

## 建议执行顺序与停止条件

优先 N1 确认实际 Worker 工具和身份，再做 N2、N4、N5、N7；之后协调 N6 的生命周期扰动，补 N3 的真实状态组合。AT-06／10 的 runtime 场景以实际 handler 为基线；AT-12 只在已有可用的工作闭环上增加有界采样。

任何实验如果依赖尚不存在的 RepoMesh 事务、可信许可或运行代次，就标为“等待实现联调”；仍可继续原生契约调查。已经证明的原生不满足项保留为缺口，不为了得到绿灯而改变角色、替换凭据、关闭保护、改用外部进程或把失败用例改成只检查 2xx。
