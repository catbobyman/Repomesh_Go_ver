# 按原清单复核完成度

2026-09-09。本审计以当前 `docs/current/agentteams-validation-plan.md` §3—6 为要求，**没有把“原生实验脚本结束”重定义为“所有 AT 验收完成”**。在真实模型任务取消、消息恢复及产物实验之外，本次已补测 DAG 子项、通知响应未知、同名重建身份、显式 MCP 配置、checkpoint端点与固定官方回归负载。以下逐项记录证据与未完成条件。

本轮[环境核查](../evidence/completion-audit-environment.json)重新查询官方 main，与 checkout 同为 `eeaab64391ccaec9118e84977f538aefd40720d6`。扫描验证目录以外工作树没有 `go.mod` 或 `.go` 文件，与 [HANDOFF](../../../docs/current/HANDOFF.md)“没有 RepoMesh Go 产品实现”一致。该事实只说明当前仓库中没有可验收的业务实现，不能拿另一旧项目运行结果补证。

表内“有证据”均限定到所写范围；“不满足”是反例已经成立；“缺实现”不是通过，也不表示删去原要求。当前未完成项继续保留在目标内。

## 环境和交付要求

| 要求 | 当前证据 | 判断 |
|---|---|---|
| 新建验证目录与独立源码 | 本目录、scripts/evidence/reports；[来源与构建](deployment-run.md) | 有证据 |
| 使用 GitHub 最新 AgentTeams | 官方 main 再查询与本地 HEAD 一致；四镜像及源码指纹 | 有证据，固定至本次查询时刻 |
| 先清空之前的环境 | 13 个独占旧容器已清理，工作目录封存；旧 shared 卷仍被另一个项目 API 挂载 | **未完成全部清理**；原有连带清理问题待答复，[清理记录](environment-cleanup.md) |
| 报告记录过程、结果和限制 | 专项报告包含错误尝试、具体输入、状态、副作用、版本、恢复及原始证据链接 | 已有明确记录；业务层未运行项也须保留 |
| 屏蔽密钥／令牌 | private 忽略 Git，已知凭据误落扫描和 JSON／链接检查 | 检查通过限于扫描范围，[artifact-check.json](../evidence/artifact-check.json)；不是所有未知秘密的绝对证明 |

## AT-01：版本与配置

| 原要求子项 | 证据与剩余范围 | 判断 |
|---|---|---|
| Controller／TeamHarness／runtime／镜像／Matrix／存储版本 | 构建及实际版本、四镜像 ID、包清单与真实调用 | 有证据 |
| Manager／Worker／Team 配置及实际加载 | 两套同名 Team、四成员、Manager 模型和实际 handler；成员 Ready 与 Team 汇总计数不混用 | 有限定证据，[双实例](twin-runtime-live.md) |
| 选用 mcpServers 写入→读回→实际使用 | REST200、desired投影、DriverCard生成、原生API列出validation_echo；同Worker安装的HttpStatefulClient调用回显nonce且helper只记录1次 | 有限定正向证据，[配置契约](mcp-config-contract-live.md)；独立客户端调用不是模型策略执行；最初查mcporter路径错误保留 |
| 忽略／不支持字段明确列出 | remoteSkills 创建忽略；资源字段存储但不限额；Matrix 通道选择不同 | 已明确缺口 |
| 若依赖 checkpoint，必须核对真实版本和端点 | QwenPaw 2.0.1，代理 200 返回 HTML，实际路由不提供 checkpoint JSON | **当前组合不满足**，[实测](checkpoint-capability-live.md)；没有 snapshot/restore 验收 |

## AT-02—05：控制、一致性和身份

| 原要求子项 | 最强证据或缺口 | 判断 |
|---|---|---|
| 无许可、旧计划、无占用、撤权、预算耗尽均拒绝执行 | 当前无 RepoMesh 许可、Plan Version、资源占用或预算实现 | **缺实现，五种条件均未验收** |
| 原生 MCP／REST／文件等可达面遵守同一门禁 | 自身 REST403，但实际 Worker shared 写和 role 参数可改变真实 Task | **原生不满足**，[权限](worker-auth-live.md) |
| 合法身份完整实际执行 | Manager 身份驱动真实 Worker 模型工具写出字节一致文件 | 有限定正向证据；没有替人类管理员权限失败过关，[模型文件](worker-model-file-live.md) |
| 可信适配绑定身份 | 实验知道真实 token 身份，但没有 RepoMesh 可信业务上下文适配 | **缺实现** |
| 原生 DAG 建图、缺失依赖／重复 ID／环拒绝、顺序／并行／汇合候选 | 本轮追加真实 MinIO 下的 DAG 用例；候选和元数据与真实并发执行分开 | 原生子项有证据，[DAG](dag-native-live.md) |
| assigned 重复就绪不得重复启动 | 原生 assigned 仍候选；通知 tx_id 去重不证明执行只启动一次 | **业务启动门禁未验收** |
| 上游 ready 不绕过跨仓及业务前驱 | 无 RepoMesh 跨仓前驱适配；不造测试锁冒充 | **缺实现** |
| paused replan、in_progress、submitted、空闲、completed、下一 DAG | 真存储及 REST/MCP 状态矩阵，正常与拒绝均已读回 | 原生契约有证据，[交错及状态](controller-mcp-race-live.md) |
| 受控接法、多目标全部读回才生效、更新中崩溃、轮次不伪造版本 | 多目标部分应用已有原生反例；没有业务生效事务／运行版本 | **缺实现，未验收整体收敛** |
| MCP 拉旧状态→REST暂停→延迟上传不得覆盖 | 精确 barrier 后实际 MCP 上传覆盖暂停 | **不满足** |
| 存储不可用时计划／结果不得假生效 | 实际存储鉴权失败与未同步回执已记录；不能冒称已覆盖所有网络中断／超时 | 有负向证据，业务生效核验缺实现 |
| 通知已接受但调用结果未知、进程中断后重试 | 本轮追加 helper 收到真实响应后硬退出，再新进程恢复；保留／空工作目录分别测试 | 有限定正向证据；不代表网络所有窗口或业务 exactly-once，[响应丢失](mcp-response-loss-live.md) |
| 同 Team 多 Issue、下一轮、重试、新 Attempt、迟到结果 | 同 task_id 跨 Project 碰撞；不同测试 task_id 的旧迟到不覆盖新产物 | 原生反例和对照已测；**持久业务映射未实现** |
| 不同 Team 同名 Project 要显式 Team，绑定 instance/team/project_id | a/b真实HTTP均确认无Team读写409、显式Team正确、错误Team／缺Project404；八次定向pause/resume逐次仅目标hash改变 | 有管理身份和元数据夹具范围内的服务证据，[消歧实测](project-team-disambiguation-live.md)；不替代业务映射或scoped caller授权 |

## AT-06—10：会话、启动、执行与消息

| 原要求子项 | 最强证据或缺口 | 判断 |
|---|---|---|
| 一会话交错两 Issue／两仓，歧义澄清，A 页面明确 B | 当前只有页面内存原型，无可信目标路由／业务权限服务 | **缺实现；marker 未代替此项** |
| 迟到结果、不同权限用户、重启后目标归属 | 原生房间权限、sender、thread、实际模型回复与 Task 产物有证据 | 业务 Issue 归属与权限变化未验收 |
| 不同房间、角色执行文件 | Manager builtin、Worker/Leader custom 分开；实际 Worker 文件操作有证据 | 不推广为多 Issue 存储／工具权限隔离 |
| 首消息与页面建项并发、重复待办、部分建房、响应未知只复用一套 | RepoMesh 创建事务与持久待办不存在 | **缺实现** |
| 资源存在、进程存活、房间可达、实际处理分别证明 | 独立版本／inspect／Matrix／模型轨迹 | 各层有证据 |
| Controller／runtime 重启、旧 Ready 迟到 | 同 ID 停启和删除同名重建均已测；旧 SA 在缓存窗口 status200／ready204，之后两接口401；旧 Matrix whoami200、旧存储403 | 有限定证据，[身份重建](worker-identity-recreate-live.md)；缓存到期不等于 JWT 自然过期，不能跨凭据类型推广 |
| 两任务争 Worker、团队／项目／全局最后槽位 | 原生双 ack；当前无资源预留事务 | **原生无单活跃保证；原子争用缺实现** |
| 准备期撤权／取消、启动前再核验 | 无 RepoMesh 启动门禁 | **缺实现** |
| 旧进程仍工作时取消、停止、断网、替补不得冲突 | 同一原生 Task 的实际模型进程取消后仍写；精确清理 PID | **取消不满足**；断网＋新旧 Attempt 替补全场景未验收，[模型取消](model-task-cancel-live.md) |
| 授权失效不等于释放 CPU／内存；新旧副本／分支／目录分离 | 旧身份行为和 PID 分开；共享 Git 来源的两容器副本独立 | 业务 Attempt 工作目录政策与释放准入缺实现 |
| 同机同名团队／成员、同测试仓库、交叉凭据、停止恢复边界 | 双实例真实请求、独立 clone、a 重启时 b 保持 | 有限定证据 |
| 实际端口、挂载、网络、cgroup；CPU／内存不能越上限 | CPU 请求未落实、实际无限 cgroup、短负载反证；端口不限 localhost | **不满足**，无需用 OOM 重复证明未限额 |
| 超缓冲消息、mention／非mention、thread、重放、runtime 恢复 | Matrix 保存55条；实际 Worker 只尾9条编号回调，sync limited 未补拉；tx重试已有正向 | **完整恢复不满足**，[恢复](runtime-recovery-live.md) |
| 普通reply／thread实际runtime处理与回复关系 | 两类入站关系持久化，已部署handler和真实model_turn有证据；出站在主时间线新建占位再m.replace，两者共用房间session | 已实际处理，但原父消息／thread关系未保留，[运行时回复](runtime-reply-thread-live.md)；不证明Issue／thread隔离 |
| 已保存消息不依赖内存、未知前序核查、业务重放不重复 | Matrix持久事实有证据；RepoMesh outbox和消费幂等不存在 | **业务层缺实现** |
| 不把已读当模型处理 | 组件顺序、真实请求／回复分层记录 | 证据分级落实；不等于全部投递完成 |

## AT-11—12：产物与成本

| 原要求子项 | 最强证据或缺口 | 判断 |
|---|---|---|
| submitted／Task completed／Project completed 真实语义 | 状态矩阵、DAG推进、原生accept两对象不一致 | 已调查，不把原生状态当业务验收 |
| 缺附件、上传失败、重复／迟到、当前读权 | 失败附件仍可accept；6真实附件三处字节核验；旧迟到不改新任务；退房后历史媒体仍200 | 原生语义有证据；**动态业务读权与固定证据版本缺实现** |
| 事实保留来源和版本，completed不自动转换交付 | 真实 sender/task/event/hash 已记录；没有业务转换代码 | 记录符合分级，业务转换仍不可验收 |
| 空闲、启动、Manager／Leader／Worker、存储、模型成本 | 四阶段61组样本、真实响应／恢复、磁盘和原生token计数 | 有限定测量，非最大容量 |
| 重验证负载 | 两实际 Worker 各76项官方回归通过，墙钟2.120／2.070秒；CPU／内存／目录增长和各23次healthz记录齐全，官方mock范围单列 | 有固定组件回归成本证据，[回归负载](native-regression-load.md)；业务重验证调度仍未验收 |
| 采集延迟 | 三轮Controller查询4.199—27.020ms、11容器Docker stats取回2.058—2.770s，保存开始／结束和单调时钟计时 | 有原生查询／本机采集开销证据，[采集计时](observation-latency-live.md)；业务状态产生→入库→页面可见无实现，未验收 |
| 跨项目额度争用吞吐／延迟、控制面仍响应 | 并发／恢复healthz有证据；没有额度调度实现 | **全局争用未验收** |
| 未测不宣称固定项目／Worker承载数 | 报告明确拒绝从少量样本外推 | 表述约束落实 |

## 保持的完成边界

### 原清单 §4 的业务验收边界

§4说明这些范围不能由AgentTeams单独证明，不表示它们已通过，也不表示本轮原生夹具可以代替产品实现：

| 范围 | 当前可执行依据 | 未完成条件 |
|---|---|---|
| 创建事务与幂等 | 当前只有创建契约文档；没有相应业务数据库和服务 | Issue／ChangeSet／会话／待办同事务及201／200／410语义未联调 |
| 浏览器REST／SSE | 页面原型不能证明业务订阅实现 | 游标恢复、快照重查、断连及失权缓存清理未联调 |
| 跨仓Graph／Loop／预算 | 原生DAG有实测；RepoMesh业务放行与累计计量无实现 | 跨仓前驱、轮次／预算上限和实际派工需真实受控适配 |
| GitHub授权与交付 | 本轮只读Git来源及容器本地提交有证据 | GitHub App权限交集、工作分支限制、PR和固定组合交付未联调；未向外发布测试PR |
| 业务验证者独立性 | 本轮部分报告由非作者复核，范围有记录 | 尚无产品作者／验证者身份和固定组合证据管理，不能用研究Agent分工代替 |

最近一次[前提复核](../evidence/remaining-preconditions-check.json)仍未发现验证目录以外的Go源码或go.mod；旧共享卷的实际消费者仍运行并挂载该卷。该快照只核实阻塞前提，没有重跑已完成实验或操作另一个项目。

首轮暂缓的 Skill 工程、其他 coding runtime、人工审批与多机高可用没有被悄悄加入本轮；同样没有删掉一会话多 Issue、跨仓许可、业务原子槽位等难项。缺少业务实现不是原生 AgentTeams 的测试失败，也不是可以假装完成的理由。

本页所列原生补测已形成记录。当前仍需要明确原有旧共享卷是否连带清理，以及是否将“验证”扩展为实现最小 RepoMesh 受控适配。相关问题已发出；不以未回复推定授权或缩小验收范围。现有失败已有反例，不需要反复运行同一测试才承认不满足；缺实现的业务子项仍保留未验收状态。

在原生服务／模型实验、随后DAG／身份／配置补测、以及本轮跨Team消歧／reply-thread／采集计时期间，这两项前提持续未满足。现有可独立执行的清单补测已结束，三个执行Agent均已完成；继续完成原清单中的业务门禁、事务、身份映射与调度验收需要真实实现或明确允许进入实现阶段，清除旧共享卷需要解决另一项目的实际占用。总目标保持未完成并记录为受阻，不以本报告齐全宣称产品验收通过。
