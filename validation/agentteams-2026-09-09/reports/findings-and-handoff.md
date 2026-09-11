# 验证发现与接手边界

2026-09-09。基线：GitHub main `eeaab64391ccaec9118e84977f538aefd40720d6`，已从干净副本构建四个镜像并运行两套独立实例。**上游能完成真实协作与模型工具工作，但现有原生行为不足以直接满足 RepoMesh 的受控执行、恢复与验收要求。** 缺口复现不是产品通过；逐项覆盖以[执行状态](validation-status.md)为准。

## 已实际跑通

- 两个 Manager、两个同名 Team，各有真实 Leader／Worker；六个目标请求均收到正确 sender 的 marker，严格仅 marker 格式为 5/6。
- 获准 Manager 身份触发真实 Worker 模型→文件工具→shell 自检；最终文件字节和 SHA-256 独立核对一致。配置的人类管理员却被拒绝，其白名单投影问题单列。
- 两实际 Worker 从同一个只读 Git URL 克隆，a 的本地提交和文件变化没有改动 b 或 origin。
- Matrix 实际存储、权限、事务去重和基础设施重启持久性均有正向证据；runtime 同 ID 重启能回复停机期间保存的目标 marker。
- 恢复过程中 a/b healthz 346 个样本全 200，b 的四容器 ID／StartedAt 保持。这里不代表完整消息 backlog 已恢复。

## 必须带入实现设计的发现

| 优先范围 | 实际观察 | 接手时不能假定什么 |
|---|---|---|
| 业务执行边界 | Worker 自身 REST 更新 Project 得到 403；同一身份却可写 global shared，已安装工具传 `role=leader` 能实际取消 Task | REST 鉴权或提示词不能覆盖存储／原生工具路径；不能把模型填写的 role 当可信身份。见[权限实验](worker-auth-live.md)。 |
| 图更新与并发 | paused REST replan=409；实际 MCP 拉取后，REST 已暂停，原 MCP 后续上传仍覆盖为 active／新 DAG | resume→replan 需要真实门禁；单一 REST ETag 不约束全部写方。见[交错实验](controller-mcp-race-live.md)。 |
| 未知结果恢复 | 通知发送后 Project／Task 回写同时失败，下一进程重试返回 ok／synced／reused，但 Project 仍 planned、Task assigned | 幂等通知不等于跨对象一致；需要逐对象权威读回与恢复协议。 |
| 身份与代次 | 跨 Project 同 task_id 返回旧 Task；旧 Worker token 在容器已停止时仍可提交 Ready=204，同 ID 重启不换 token | 重试、下一轮、新 Attempt 不能混用短任务编号；Ready 报告不证明当前执行代次活着。见[工具实验](teamharness-live-report.md)、[旧 Ready](worker-ready-restart-live.md)。 |
| 取消与产物 | 同一真实 delegate Task 驱动模型工具启动进程，取消持久化后仍写 5→8 行；取消后 accept 可使 Project completed／Task cancelled；缺失附件仍可被接受 | 取消状态不证明旧写能力失效，SUCCESS／synced／completed 不证明产物完整或业务已验收。见[模型任务取消](model-task-cancel-live.md)与[产物](worker-side-effects-live.md)。 |
| 离线消息恢复 | 55 条编号消息完整保存于 Matrix；Worker 恢复默认 sync 返回 10 且 limited=true，只观察尾部 9 条编号回调；显式 limit100 能取回全部55 | 最后 marker 有回复不代表前面消息全部恢复。当前通道未 backfill，业务持久投递不能依赖它补齐。见[恢复报告](runtime-recovery-live.md)。 |
| 资源与端口 | 请求 0.5CPU／512Mi，实际 Docker/cgroup 无限额；CPU 探针证实不限额；Worker 自动发布端口 HostIp 为空 | 配置字段保存不等于资源强制；Controller／Manager 的 localhost 绑定不能推广到所有子 Worker。见[Worker](worker-runtime-live.md)、[同机部署](twin-runtime-live.md)。 |
| 运行配置 | Manager 实际启用 builtin `matrix`，Leader／Worker 启用 custom `agentteams_matrix`；独立 Worker 白名单含 `@admin` 而实际管理员为 `@rv-a-admin` | 安装插件不等于启用插件，各角色组件测试不可混用；账号可登录不等于该 Agent 的访问策略允许。见[Manager](manager-model-live.md)、[模型文件任务](worker-model-file-live.md)。 |
| 删除重建的撤权 | 同名重建后旧 SA 在缓存窗口仍可访问新 Worker，随后 status／ready 变401；旧 Matrix whoami 仍200，旧存储凭据拒绝 | 三类身份不同时失效；新 CR／容器存在不保证旧控制面调用已失效。见[身份补测](worker-identity-recreate-live.md)。 |
| checkpoint 版本 | QwenPaw 2.0.1 的 Controller 代理200正文是HTML，实际未提供 checkpoint JSON | 不能以HTTP200或源码注释证明恢复能力。见[端点实测](checkpoint-capability-live.md)。 |
| 回复关系与session | 普通reply与thread均被实际Worker处理，但出站先建主时间线占位再m.replace自身占位，没有保留原父消息／thread；两者使用同一房间session | Matrix保存关系不等于runtime回传正确关系，也不证明线程或Issue隔离。见[实际回复实验](runtime-reply-thread-live.md)。 |

补充的[原生 DAG 实测](dag-native-live.md)验证合法依赖与非法图拒绝、17个就绪阶段；assigned 仍返回候选，通知去重不证明实际执行去重。[通知结果未知后的恢复](mcp-response-loss-live.md)在 delegate 尚未获得发送返回值时硬退出，两个重试用例都恢复一致；这与更晚回写失败进入不同分支后留下不一致的结果并不矛盾。按原要求逐项保留范围见[完成度审计](completion-audit.md)。

[显式 MCP 配置补测](mcp-config-contract-live.md)已确认REST保存、运行投影、QwenPaw原生DriverCard与工具列表，实际安装客户端调用成功。最初找不到mcporter.json来自探针路径假设错误，QwenPaw 2使用原生MCP客户端；该失败不作为上游缺陷，调用成功也不等于已验证模型权限策略。

## 尚无实现，不能用测试夹具替代的部分

当前仓库没有 RepoMesh Go 产品后端。统一许可／预算／Attempt 门禁、持久业务身份、跨目标整体生效、事务待办、全局原子资源预留、可信多 Issue 消息目标、动态读权与独立验收都没有实现可供联调。原生实验已提供设计输入，不能通过测试脚本自建字典或锁后称这些业务机制已通过。

后续按现行 ADR 实现窄适配：先定义每个权威对象由谁写、如何绑定真实调用者／Attempt、哪些原生路径可达，再落实并发条件和实际执行约束。图复用与跨仓协调职责保持现行决定；本报告没有擅自选定 paused replan 补丁，也没有将所有原生工具开放给 Agent。

容量只报告[实测样本](capacity-live.md)。需要资源强制、统一额度和真实业务负载后才能评价争用、公平性、重验证吞吐和最大承载数。

另已测量[两实际 Worker 并行官方回归](native-regression-load.md)：每边76项通过、耗时2.120／2.070秒，有CPU、内存、可写目录增长及healthz证据。官方测试保留传输替身，因此这是固定组件回归成本，尚无业务重验证调度证据。

[三轮采集计时](observation-latency-live.md)记录Controller查询约4.2—27.0ms、11容器stats取回约2.06—2.77s；这些是查询与宿主采集开销，尚无业务状态到页面可见延迟。[同名Project消歧](project-team-disambiguation-live.md)补齐真实管理接口与六对象hash隔离；其随机元数据夹具不证明RepoMesh业务映射已实现。

## 环境与证据保留

[Docker 启动故障](docker-startup-repair.md)已解决：残留 socket 所在 run 目录封存后恢复启动，实际容器 smoke 通过，没有用恢复出厂解决。后续按独立验证范围清理了 13 个旧容器及活动工作目录；旧共享卷仍被另一项目 API 挂载，待原有确认问题答复，不能宣称全部旧共享数据已清空。[清理记录](environment-cleanup.md)。

新环境未复用旧 shared 卷或工作目录。源码 checkout 保持干净；构建辅助兼容修补仅在独立 build-source，官方 Dockerfile 指纹与源一致。私密配置在 Git 忽略目录；公开报告区分组件 fake、真实服务、脚本启动进程和真正模型工具执行。首次夹具错误、重试、失败回执及中间态均保留。

当前页面、接口和后端接手文档已同步验证入口与主要限制；历史实验原文不改写为新的能力保证。验证脚本的链接／JSON／已知凭据误落检查见 [artifact-check.json](../evidence/artifact-check.json)，独立证据审閱另行记录。

[证据审阅](evidence-review.md)对六份核心报告核查范围与原始 JSON；其中两份由审阅 Agent 先前撰写，因此它是单独复核，不是全部作者独立审计。随后补充的附件与模型取消实验单独标识，未冒称在较早审阅时已经覆盖。

[补测独立复核](supplement-evidence-review.md)由未撰写这三份报告的Agent核对DAG、通知结果未知后恢复、官方回归负载及其原始证据，未发现实质数值错误或越界结论。身份重建、checkpoint和MCP配置不在该三份独立复核范围内。三份现行接手文档的本地链接和验证Python语法检查另见[supplement-handoff-check.json](../evidence/supplement-handoff-check.json)。
