# 核心验证报告的只读证据审阅

审阅日期：2026-09-09。范围：worker-auth、worker-side-effects、controller-mcp-race、runtime-recovery、twin-model、twin-runtime 六份专项报告及对应原始 JSON，补看旧 Ready token 和模型文件闭环证据以避免沿用早期覆盖缺口。本次不重跑实验、不请求模型、不读取凭据、不修改其他报告或服务，只新增本文件。

这是执行后的单独只读复核；其中 runtime-recovery、twin-model 的实验和报告由同一审阅 Agent 先前完成，**不能将本文件称为全部作者独立或外部审计**。主任务正在更新的总状态与资源汇总不作为本次差异判定对象。

## 总体判断

六份核心报告的主要运行结论均能在原始结果中找到支持，且总体没有把原生 AgentTeams 行为、人工夹具和 RepoMesh 业务实现混成整体通过。**本轮可确认的是原生能力及缺口调查已有真实服务、真实身份、部分模型与故障恢复证据；不能确认 AT-01—12 的 RepoMesh 业务验收全部通过。**

需要保留的精度问题如下。这里的“需要限定”不等于新发现了产品缺陷，也不要求为完善表述而重跑模型。

## 应保留的限定与表述风险

| 编号 | 证据差异／范围 | 审阅结论 |
| --- | --- | --- |
| ER-01 | `worker-auth-live.json` 最终 `final_after_pull_remote_task` 独立读取的是 Task；Project cancelled 出现在 `actual_packaged_native_tool_after_pull.result.project` | `worker-auth-live.md` 中“远端 Task 读回 cancelled，Project 节点也 cancelled”宜明确后半句来自工具返回。不能在总摘要扩写为“两个对象都已独立远端读回”。实际角色覆盖和 Task 持久副作用仍充分成立。 |
| ER-02 | twin Manager 并发阶段 18 个采样请求用了 `/health`，后验实际路由诊断为 404；只有 Team 四请求阶段的 `/healthz` 24 样本是有效并发健康证据 | 报告已如实披露。不得将 Manager 阶段写成“全部健康 200”，也不得把该夹具错误写成 Controller 并发故障。后验 `/healthz=200` 不能补作过去的连续样本。 |
| ER-03 | twin 六个目标都返回自身 marker，但 b Worker 最终 `m.new_content.body` 附加解释段 | 6/6 是目标回应，严格“只 marker”为 5/6。报告已正确区分；原始脚本 `PASS_REAL_MODEL_REPLY` 只检查 marker 包含关系，汇总必须保留严格格式差异。 |
| ER-04 | `twin-runtime-results.json.latest.*.members` 的四个 `/status` 为 Ready，但同一 snapshot 的 `team.readyWorkers` 仍为 0 | “四成员已分别观察到 Ready”成立；“Team 汇总计数也全部收敛”未被该快照证明。可能是采样／协调滞后，本审阅不把它新判为产品错误。 |
| ER-05 | runtime 恢复时 Matrix 55 条编号都可读，Worker 日志仅见 46—54 九条，默认 `/sync` limited=true | 报告正确判“最后 marker 恢复回应通过，但完整 backlog 恢复未通过”。不能改写为“55 条恢复处理全部成功”，也不能改写为“Matrix 永久丢失 46 条”。 |
| ER-06 | twin Worker HostConfig 的发布端口 `HostIp=""`；没有本轮防火墙外侧连通性实验 | 可以确认发布配置未限定 localhost，不能进一步宣称任意外部网络都实际能连入。现报告讨论的是发布配置差异，没有将其扩大成外部攻击实证。 |

## 逐报告核心结论核对

### 1. 实际 Worker 身份与权限

[报告](worker-auth-live.md)、[原始记录](../evidence/worker-auth-live.json)。共 23 条记录，身份是实际 Worker 投影 ServiceAccount，运行角色为 standalone。

- 自身 Worker 与 status GET 为 200；其他 Worker GET、Worker list、Project pause／replan 为 403；自身 Ready 为 204，均与报告相符。
- 新建 global shared Project／Task 两个路径实际写入，独立读回 matches=true；外部 agents 与外部 Team 的两个新探针路径被 Insufficient permissions 拒绝。报告已经限制在实测新路径，不能外推为所有对象开放或所有存储访问被禁止。
- 不传 role 的取消失败；初次传 leader 因未拉取而 task not found；正常 filesync 拉取后再传 leader，Task cancelled/synced=true 且远端 Task 读回 cancelled。没有用初次 task not found 当成授权有效，也没有假称模型实际发起这个请求。
- Project 最终独立远端读回的精度问题见 ER-01，不影响实际 Task 角色覆盖副作用成立。

本报告当时只描述 token shape，没有声称旧 token 重启实验通过。更晚的 [worker-ready-restart-live.json](../evidence/worker-ready-restart-live.json)已经额外确认：同一容器停机时旧 token 可 POST Ready=204，status 仍如实显示 stopped；start 后同 token 可 Ready=204，状态显示 Ready。**这不是停机状态被伪装成 Ready 的证据，也不是容器重建／token 过期／轮换测试**。总汇总应引用较晚实验，不把早期“本轮未测”机械变成当前缺项。

### 2. 取消、真实文件副作用与结果语义

[报告](worker-side-effects-live.md)、[原始记录](../evidence/worker-side-effects-live.json)。真实 Worker 中夹具子进程 heartbeat 为 7 → 15 → 25 行，取消之后仍在增长；finally 验证 PID 身份后终止，最终记录原 PID 不存在且 Worker running，与报告一致。

- Task cancel 后 ack／submit 均被 terminal 检查拒绝；随后 projectflow accept 返回 ok，远端 Project 节点 completed、Task 仍 cancelled，确有跨对象状态不一致。
- 缺失文件和真实 Matrix 401 两例的 submit 均 ok/synced=true，Task submitted/result_status=SUCCESS，`publishedArtifacts` 均明确 failed，符合报告。
- 这个 heartbeat 由脚本 docker exec 创建，Task 委派对象仍是测试 Matrix 用户；**并非模型工具启动并与原生 Task 绑定的进程**。不能将其称为“真实模型任务取消失败”的完整复现。
- 后来的模型→工具→文件闭环报告虽已证明 Manager 身份能驱动实际 Worker 创建、自己修正 BOM 的 nonce 文件，但那个模型文件实验与本取消实验是两个不同请求。不能拼成一个未运行的“模型进程取消”实验。

### 3. Controller／MCP 精确交错及部分恢复

[报告](controller-mcp-race-live.md)、[最终原输出](../evidence/control-race-live-32447df06f.stdout.json)。4 项结果、44 条外层 trace，与文中计数相符。

- RACE-01 保留原拉取 active、真实 REST pause 响应、独立 remote paused、放行后原 MCP 上传、最终 remote active 的连续记录，支持覆盖窗口存在。
- RACE-02 失败后 Project assigned／Task prepared，新进程重试后 assigned／assigned；RACE-03 失败后 planned／prepared，重试后 planned／assigned。两者 tool retry 为 ok/synced/reused=true、各实际通知只有 1 条。报告没有把“无重复通知”混成“两对象必然一致”。
- STATE-01 的 HTTP 顺序为 409／409／409／200／409／200／409，分别对应在途、submitted、complete 与下一 DAG 条件，原始读回支持部分目标应用事实。
- 报告明确夹具在内存包装 `_filesync` 以安排真实 REST barrier 和单次凭据故障。上游文件哈希不变不等于“执行过程中从未包装函数”；该差异已经透明说明。真实服务执行结论成立，不能把它包装成无故障注入的随机并发压力或 actual Worker 自有权限实验。
- 重试保留 workspace，首进程正常返回错误后退出，不是 kill／丢盘／网络已提交但响应丢失。报告保留了这些限制。

### 4. runtime 停启与离线 backlog

[报告](runtime-recovery-live.md)、[Worker](../evidence/runtime-recovery-live-worker.json)、[Manager](../evidence/runtime-recovery-live-manager.json)、[sync 补充证据](../evidence/runtime-recovery-live-worker-sync-audit.json)。

- 两 runtime 都是原 ID stop/start，StartedAt 变化、最终 Running；marker 确实在停止窗口被接受。Worker 14.578 秒、Manager 31.937 秒为 start 后观察延迟，未冒充模型延迟。
- Worker 55 条非 mention 加一 marker、Manager 仅一 marker，覆盖范围在报告中不同，没有用 Manager 结果填补 55 条验证。
- 208＋138=346 个 a/b healthz 样本均为 200；26＋18=44 轮 b 四容器快照保持 ID/StartedAt，不受操作影响的结论符合采样范围。
- 实际 Worker 日志显示恢复旧 token；只有九个编号回调。Human 旧 cursor 的默认 sync 10 条／limited=true 与 limit100 取回59条为独立服务器对照，**不是 Worker 请求的抓包**。报告已经明确此层级，不能从公开 Boolean `saved_cursor_resumed` 单独推导每条消费已完成。
- 停启复用容器层，未覆盖删除／重建或 Worker 本地目录丢失。与 twin-runtime 报告“工作目录没有持久挂载”没有矛盾。

### 5. 六个模型请求与目标隔离

[报告](twin-model-live.md)、[Manager](../evidence/twin-model-live-managers.json)、[Team](../evidence/twin-model-live-team.json)、[只读审计](../evidence/twin-model-live-readonly-audit.json)。

- 所有请求中文读回一致，实际 sender、room、event 与各 target 一致；四个房间最近100条窗口无另一实例 marker 或错误 sender 的 marker 回应。
- Worker／Leader 四个实际配置都是 builtin matrix=false、自定义 agentteams_matrix=true，日志来源一致；Manager builtin 路径由独立配置审计确认。两套报告范围不同并非互相矛盾。
- session 仅有运行源码映射 `matrix:{room_id}`，没有读取实际持久 session 私有数据库。报告没有把这层源码映射写成独立 session 存储隔离实测。
- 模型可回应不是工具白名单、无后台工具调用或 RepoMesh Issue 权限验收，报告已经限制。格式和 Manager health 采样限制见 ER-02／03。

### 6. 双实例同名资源与 Git 文件隔离

[报告](twin-runtime-live.md)、[运行 JSON](../evidence/twin-runtime-results.json)、[同源仓库](../evidence/shared-repo-isolation.json)。

- 四个成员分别 Ready、Team Active 与房间 ID 完整；160.688 秒包含 Human 依赖失败及修正，不能充当干净启动时间。Team 聚合计数见 ER-04。
- 各容器网络分别为 rv-a-net／rv-b-net，唯一挂载为专属 auth 卷，Memory/NanoCpus/CpuQuota 均为 0，端口 HostIp 未限定localhost，与文中一致。
- 两 Worker clone 同一 URL、初始 commit 相同；仅 a 改动后 a commit 变化，b 与 origin 未变、b 无 only-a.txt；helper cleanup 已记载。
- Git 是脚本操作和本地只读来源，没有 GitHub 写入、模型 Git 工具、RepoMesh Attempt 分支策略或对抗式跨网络访问。双网络 helper 是实验目的下共享代码来源，不可描述成已经证明全网络不可达。

## 尚不能由本轮证据确认的范围

以下不是要求立即重跑，而是总验收必须保持未通过／未实现边界：

1. **RepoMesh 业务适配尚无验收对象：** 无许可、旧计划、无 Worker lease、撤权、预算耗尽时的统一执行拒绝；可信身份绑定与启动端复核；不能拿原生 REST403 或一个测试锁代替。
2. **业务一致性与恢复：** 多 Project 整体计划生效、部分成功后的自动收敛、持久 Issue／round／Attempt 映射、未知结果恢复和业务幂等。原生已经复现窗口或不一致，尚未部署解决方案。
3. **全局资源与旧执行：** 团队／项目／全局最后槽位原子争抢、真实模型工具进程的取消／撤权、代次失效、资源回收与替补启动。独立 heartbeat＋另一条模型文件请求不能合成该完整证明。
4. **消息业务消费：** 原生 Worker 55 条 backlog 完整交付已有负向证据；RepoMesh outbox、消费游标、limited backfill 与重复业务动作保护未实现。Matrix 持久化通过不等于这些约束通过。
5. **产物与授权：** 已确认失败附件状态和原生 accepted 语义；但不可变证据、独立验证者、当前读权变化、不同 Attempt 晚到／篡改、真正 GitHub 交付还未具备全面验收证据。
6. **容量与隔离：** 有真实瞬时资源、有限 CPU反证、部分并发和恢复采样；没有完整负载阶梯、最大容量、硬内存压力、公平调度、磁盘峰值或所有外部网络可达性测试。已有原生限额未落实，不需 OOM 再重复证明同一点。

## 审阅意见

可采信核心报告中限定范围的成功与缺口结论；汇总中须保留 ER-01—06 的精度。**“实验执行完并查明缺口”“原生有限能力通过”“RepoMesh 整体设计已验证”是三种不同状态。** 当前证据支持前两类的具体条目，不支持第三类的总体声明。

## 主任务在审阅后的处理

主任务已按 ER-01 将 worker-auth 的 Project 状态明确限定为工具返回，独立远端读回只指 Task；按 ER-04 为 twin-runtime 增补 Team 汇总 readyWorkers=0 的快照限制。上述原始审阅意见保留用于追溯。

审阅后另完成[完整附件与不同 task_id 对照](artifacts-attempts-live.md)，以及[同一原生 Task 的真实模型进程取消](model-task-cancel-live.md)。这是后续新增证据，并非本审阅 Agent 已经独立复核了这两个新实验；前述“尚未覆盖”的描述应结合新增报告读取，不应把两阶段证据混为一次审计。
