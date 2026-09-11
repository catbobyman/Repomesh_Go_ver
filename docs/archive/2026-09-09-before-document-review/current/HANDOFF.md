# RepoMesh 产品与架构设计交接

**页面／接口交接已更新（2026-09-09）：** [完整接手 Prompt](NEXT-SESSION-PROMPT.md)列出通信恢复原文、41项产品／架构必读文件、原型及正文源、持续授权与任务身份、已采用契约／未实现范围、结果和下一步。后端回执已在页面日志 CP15 保存，无待回复设计问题；下一步补齐 Manager 创建／查询 MCP 的完整 Schema 与可信来源操作协议，再深化 Issue 页面及原型。

**最新持续授权：** 用户明确“之后的待决定都批准，按照建议来。”，后续设计按推荐方案对齐、记录并推进，直接报告结果，不再逐项请批。见[采用清单](design-delegation.md)。已有否决、暂缓和业务约束保持；尚未设计／待验证不冒充已完成。

**接口接续：** [创建接口契约 v1](issue-page-create-api-contract.md)及[双入口机制](manager-create-issue-tool-design.md)已采用为设计基线：Manager MCP／页面统一创建、默认新会话和可选已有会话、必要新会话／来源／快照／幂等结果／Issue／主CS／待办同事务、命名与保留策略、提交后异步准备、REST 和 Issue SSE。具体 MCP schema、其他页面接口仍继续设计，未实现。

**关系与状态：** 会话与 Issue 分离，一会话可关联多个独立 Issue；内部仓库事项可关联 GitHub Issue。每项独立计划、验收和默认主 ChangeSet 保留；Issue 专页导航实际主／Leader 房间。自然语言明确目标、歧义先澄清；准备期可保存补充，保存／投递／Manager 接收分开。

**运行入口：** 项目创建不启动。首次保存业务会话及首条消息，或页面建项提交后，异步准备／恢复项目实例及关联主房间，复用已有资源。外部调用在事务后；创建回执不证明运行就绪、模型接收或派工，准备受阻保留业务事实。

**通信与分工：** 页面与“RepoMesh后端架构讨论_1”每次设计直接对齐，按持续授权推进并报告选择。同一主题最多三轮，DESIGN-002／004 历史均 3／3，DESIGN-001／003 均 1／3，不清零。通信原文即时保存，每次自动压缩按[约定](design-communication.md)完整读取双方日志并补恢复记录。页面负责页面专题／契约、页面 prompt／HANDOFF／索引；后端负责后端专题／prompt／ADR，各写各的日志。

**原型完成度：** 当前 repomesh-conversations-issues.html 仍为上一版内存演示，已支持默认新会话创建及独立 Issue 详情／房间导航；可选已有会话、页面提交后的自动准备尚未补入，真实 MCP／REST／SSE 未实现。下一步先补 MCP 完整 schema／可信操作来源，再深化 Issue 页及其他契约，按持续授权推进。

**接手入口：** 完整阅读[页面 prompt](NEXT-SESSION-PROMPT.md)或[后端 prompt](NEXT-BACKEND-SESSION-PROMPT.md)所列原文。新决定以[持续授权清单](design-delegation.md)及具体契约为准；后文旧草稿入口仅作原始背景，按 ADR-0019 及 ADR-0018 的最新补充理解。

**视觉与历史：** 保留用户截图的深色会话式风格，左侧按项目排列会话。2026-09-08 的 [Draft Issue 入口记录](draft-issue-and-room-entry-design.md)保留历史，其聊天与事项混合部分由 ADR-0019 及当前页面专题替代；A／B／C 第一版布局已被否定，不再提供选择。

最新补充（2026-09-08）：用户在页面方案说明后要求“你直接做原型出来我看看”。已制作仅本地模拟的交互原型，见[页面与接口原型记录](page-interface-prototype.md)，包含三种布局及关键业务状态。此为只读设计阶段中经用户明确要求的原型例外，不启动产品实现或远端操作；布局和接口尚未获采纳。读完下列原始基线后继续读该原型记录，依据用户评审反馈逐项讨论。

更新：2026-09-08。本版在 I 主要规则与 J1—J3 确认后重新整理。实际工作区：`D:\Project4work\Repomesh_Go_ver`。

**技术选型已收口，架构方向已确认至 ADR-0019；页面／接口与后端架构分会话协同推进，K 由页面侧继续评审。用户最新要求下一会话继续后端架构，继续停用 `grill-with-docs`。后端当前仅设计及本地文档整理，未开始实现或运行验收。** 决定以用户最新确认、现行 ADR 和专题设计为准。按所接角色阅读相应 prompt，先简述理解，再围绕当前未决问题推进，不重新询问已采用方案。

## 1. 当前进度与范围

| 主题 | 当前状态 |
| --- | --- |
| A—E | 团队执行、验证小组、联调环境、Graph／Loop、draft PR 与审查规则已确认。 |
| ChangeSet | CS1—CS14 全部确认；结构解释完成。F／G 以 CS9—CS12 为准，不整体恢复旧建议。 |
| H：Skill 工程 | H1—H15 方向已同意，见 ADR-0009；**整个模块待定／占位，暂不开发**。只保留文档位置。 |
| I：执行模式与审批 | **当前阶段统一 YOLO**；后续审批模式的主要规则已确认，审批能力后续开发。详见 ADR-0003 第 1.7—1.11 节。 |
| J：项目配置与授权变化 | J1 接入配置、J2 新增仓库、J3 部分授权失效的主要规则已确认；技术接入与恢复细节待细化。 |
| K：Manager 页面与图 | 已有深色项目／会话／独立 Issue／主与 Leader 房间原型，DESIGN-002 第 3／3 轮落地收口。创建与启动适配、创建 REST／Issue SSE 已采用；其他消息及恢复契约按推荐继续设计。 |
| 技术选型 | 整组方案及模块化单体已采用，见[技术选型](technology-selection.md)和 ADR-0010；本轮选型收口。 |
| 已确认架构与待细化范围 | 已有 [v1 讨论稿](architecture-design-v1.md)；受控接入（ADR-0011）、Issue 上游映射（ADR-0012）、三类进程（ADR-0013）、Graph 插件进程内运行（ADR-0014）、按获准轮次下发有限 DAG（ADR-0015）、业务与待办同事务保存（ADR-0016）、Attempt／Worker／容量统一预留及启动前再核验（ADR-0017）、项目先保存及首条草稿后准备实例（ADR-0018）已采用。其余领域模块、上游任务映射细节、具体协议和恢复算法未冻结，随页面与接口设计按需细化。 |

当前导航见 [README](README.md)，后端接手复制 [NEXT-BACKEND-SESSION-PROMPT](NEXT-BACKEND-SESSION-PROMPT.md)，页面／接口接手复制 [NEXT-SESSION-PROMPT](NEXT-SESSION-PROMPT.md)。[整理前快照](../archive/2026-09-08-design-consolidation/README.md)保存本轮修改前文档；旧版 PRD 与原型已移至[历史设计](../archive/legacy-product-design/ARCHIVE-NOTICE.md)。`docs/old_ver/README.md` 和 `changeset-design-discussion.md` 仅为兼容旧链接的入口。

## 2. 接手阅读顺序

按顺序完整阅读，下面的摘要不能代替原文：

1. 本文。
2. [CONTEXT.md](../../CONTEXT.md)，术语表仅放定义。
3. [ADR-0001](../adr/0001-agentteams-issue-concurrency-and-isolation.md)：项目、Issue 入口、团队与隔离。
4. [ADR-0002](../adr/0002-github-app-authorization-and-draft-pr-delivery.md)：GitHub 授权与 draft PR 交付。
5. [ADR-0003](../adr/0003-plan-change-authorization-and-activation.md)：计划许可、生效与 I 的审批规则。
6. [ADR-0004](../adr/0004-acceptance-rule-clarification.md)：缺失业务规则的解释。
7. [ADR-0005](../adr/0005-optional-project-verification-group.md)：可选项目验证小组。
8. [ADR-0006](../adr/0006-manager-entry-modes-and-skill-driven-execution.md)：Manager 交互、当前 YOLO 与 Skill 驱动执行。
9. [ADR-0007](../adr/0007-graph-loop-plugin.md)：Graph／Loop 插件。
10. [ADR-0008](../adr/0008-changeset-attribution-and-history.md)：ChangeSet 归属与交付历史。
11. [ADR-0009](../adr/0009-skill-engineering-deferred.md)：Skill 工程预留设计，整体暂缓开发。
12. [team-execution-policy.md](team-execution-policy.md)：团队执行策略：并发、调度、故障与资源。
13. [verification-node-design.md](verification-node-design.md)：验证节点：检查、结论与必检证据。
14. [integration-environment-design.md](integration-environment-design.md)：联调环境：固定组合、配置与数据。
15. [draft-pr-review-design.md](draft-pr-review-design.md)：PR 审查：draft 时机、检查与反馈。
16. [changeset-design.md](changeset-design.md)：ChangeSet：CS1—CS14 已确认规则。
17. [changeset-structure.md](changeset-structure.md)：ChangeSet 结构说明，字段与接口未冻结。
18. [skill-engineering-design.md](skill-engineering-design.md)：Skill 工程说明与锁定源码依据，待定占位。
19. [project-configuration-design.md](project-configuration-design.md)：项目配置：J1—J3 已确认规则。
20. [AgentTeams 调研](../agentteams-survey-2026-09-07/agentteams-survey.md)。
21. [AgentTeams API／CLI 调研](../agentteams-survey-2026-09-07/agentteams-api-cli-survey-2026-09-07.md)。
22. [技术选型](technology-selection.md)：整组方案已确认，当前转入架构设计。
23. [ADR-0010](../adr/0010-technology-stack-and-modular-monolith.md)：技术栈与模块化单体。
24. [架构 v1 讨论稿](architecture-design-v1.md)：ADR-0011—0018 已确认，其余新增具体建议、理由与待验证项继续讨论。
25. [ADR-0011](../adr/0011-agentteams-controlled-integration.md)：AgentTeams 受控工具与执行接入，必要时维护小范围上游补丁。
26. [ADR-0012](../adr/0012-issue-scoped-upstream-projects.md)：按 Issue 仓库委派范围映射上游 Project、跨仓依赖及多目标应用核查。
27. [ADR-0013](../adr/0013-web-coordinator-host-executor-processes.md)：Web、后台协调与受限主机执行三类进程，同一 Go 工程、配套发布。
28. [ADR-0014](../adr/0014-in-process-graph-plugin.md)：Graph 插件在后台进程内运行，计算、派工和持久状态职责。
29. [ADR-0015](../adr/0015-round-scoped-upstream-dags.md)：当前获准轮次映射为有限 DAG，由 RepoMesh 控制后续轮次。
30. [ADR-0016](../adr/0016-transactional-background-work.md)：业务记录与后台待办同事务保存，提交后执行及未知结果核查。
31. [ADR-0017](../adr/0017-atomic-attempt-resource-reservation.md)：Attempt、Worker 与容量统一预留，环境准备后启动前再次核验。
32. [ADR-0018](../adr/0018-provision-instance-after-first-draft.md)：先保存长期项目，首条需求草稿落库后准备实例。

随后继续按顺序完整阅读：

33. [第一版原型记录](page-interface-prototype.md)：A／B／C 被否定的历史评审，不恢复旧入口。
34. [草稿与房间页面](draft-issue-and-room-entry-design.md)。
35. [后端专项稿](draft-conversation-backend-design.md)：整体 proposed，已同步 ADR-0019，具体启动适配及契约未决。
36. [项目先建立页面记录](project-first-entry-design.md)：项目入口与 DESIGN-001 历史，模型绑定已部分替代。
37. [ADR-0019](../adr/0019-conversation-issue-separation.md)：会话与独立 Issue、内部仓库事项及房间导航。
38. [当前页面专题](conversation-issue-separation-design.md)：当前原型、导航与接口未决。

完整读取并查看该最新页面记录链接的原型。旧原型元素与两张用户截图的准确位置、使用边界见 NEXT-SESSION-PROMPT；它们不是新的业务规则来源。

需要界面参考时再读 [Cursor Dashboard 报告](../../Cursor_Dashboard_Report_2026-09-07/report.md)。它主要记录账号、设置和集成页面，不是 RepoMesh Manager 工作区的已确认方案。历史归档只用于溯源，不恢复其中的旧入口、旧人工门禁或待确认问题。

## 3. 必须保留的执行与交付基线

### 项目、Issue、角色与资源

使用 agentscope-ai/AgentTeams。每个多仓项目独立实例，一个长期 Manager，每仓长期 Team／Leader。首期最多一台服务器，多实例配置和资源隔离；实际容量尚未测量。

Issue 是 RepoMesh 内部的一条统一需求事项，可涉及一仓或多仓，可关联零到多条 GitHub issue 作为来源或跟踪。重复导入先查映射，不自动合并需求；首期不默认启用外部 issue 创建、评论、同步或关闭。

```text
保存项目配置，在管理面检查必要条件（不创建实例）
    |
项目下持续会话：标题、消息、历史与运行关联
    |
首次会话消息或页面建项提交后异步准备，复用已有实例／房间
    |
核验 Manager 与实际主房间就绪 -> 尝试投递会话消息
    |
同一会话可以关联多个独立 Issue，具体工作目标须明确
    |
明确建立某项工作 -> 正式 Issue、主 ChangeSet 与待办同事务保存
    |
按范围委派仓库 Leader，在相应子房间工作
```

所有新 Issue，包括明确单仓，都先由 Manager 接收；Leader 只负责被委派仓库工作。各项执行上下文与工作记录保持独立；多事项主会话到实际 runtime session 的映射待验证。追加消息、重复事件和故障恢复保持原归属，运行失败保留已提交的会话、消息及 Issue／ChangeSet，核查后幂等重试。

Worker 单活跃任务，每个 Attempt 有独立副本、分支、构建目录和执行记录。团队 Worker 并发可设置，默认 1，不包含 Manager／Leader／验证负责人；实际执行还受全局容量、项目额度、有效权限和验证独立性约束。按 Skill 请求能力，优先复用合适空闲成员，由 RepoMesh 实际分配、创建和启动。优先已有候选验证、必要诊断及收尾，同级按等待顺序安排。

Worker 失联先核查旧 Attempt 已停止或失去写入能力，再开替补；无法确认则保留状态不明。验证负责人不可用时 Manager 代行协调；Manager／Leader 优先恢复原身份与上下文，停止相关新派工，在途按有效约束收尾。保存必要证据和产物后回收副本与空闲执行资源，身份、配置及整理后的知识可以保留。Agent 不直接持有宿主 Docker socket；普通容器不承诺 VM 级或恶意多租户隔离，关键数据需服务器外备份。

### Manager、计划与 Loop

人只在主界面与 Manager 对话。YOLO 不弹人工审批、不等待人同意；内部初审和复核不成为人工门禁。缺失业务规则由 Manager 解释并记录来源，不能覆盖已有明确要求或冒充人已确认。触及权限、预算上限或既定验收边界时返回受限／未完成结果，不自行扩大、降低标准或插入人工等待。

Plan Version、获准和生效分别记录。RepoMesh 实际约束计划应用与任务启动；许可记录、聊天或 Skill 文本不能代替执行控制。变更获准后，停止受影响上游 Project 新派工，在途及 submitted 处理到可重规划状态，核对最新状态、应用并读回确认，再按新计划派工。保留拒绝、冲突、失败和结果不确定的历史；不把批准当作生效。

Graph／Loop 采用插件，支持顺序、并行、汇合和有界 Loop。默认修复 3 轮、诊断 2 轮、环境恢复 2 次，实际写入计划；预算或时限先到先停，换计划不清零消耗。连续两轮同一失败且无新增有效证据，结束当前循环。许可及上限内自动运行。无依赖且仍获准的工作可以继续，但受实际上游暂停范围约束。

首期只通过自然语言调整编排，形成版本化提案；直接编辑节点、属性、连线或拖拽编排留待后续。上游 Project 按 Issue 仓库委派范围分别映射的方向已确认（ADR-0012）；标识、Task／Attempt 和验证执行的具体映射及插件契约仍待细化。

### 验证与 PR

项目验证小组默认不启用；启用时固定验证负责人，未启用时 Manager 组织。正式验证执行者与本轮业务作者分离。Leader 提供范围、契约、自测、运行说明及 mock 数据和使用说明；验证侧组织必检清单、独立执行与复核，Manager 核对覆盖、依赖和预算后汇总。缺陷修复归业务 Team，验证侧独立重验。

每个验证 Attempt 独立环境，核对实际固定 commit 组合、配置和数据；未改动但参与联调的仓库也固定基线。mock 的覆盖范围明确，不证明未实际运行的真实链路。验证环境不向业务仓推修复；失败先存日志与现场，再按约束恢复或重建。

五类结果为通过、业务缺陷、环境阻塞、需求待澄清、暂无法判定。必检项必须具备适用于当前组合与前提的有效通过证据，节点才能通过；提交、执行结束或跳过不表示通过。小组停用时停止接新、在途收尾、submitted 继续核对，缺陷和阻塞保留；停用受阻如实显示，重新启用不复活终止的 Attempt。

GitHub App 固定工作权限集，运行时收窄，不能放大发起人的有效 Git 权限。Agent 推自己分支并开 draft PR；Leader 内部初审形成有范围和自测记录的候选后创建 draft。同一 Issue 同仓默认持续更新一个 PR。有效验证、内部复核及必需仓库检查满足后，Manager 推荐审查；首期由人把 draft 转正式 PR，合并由人和仓库规则决定。反馈回原 Issue。YOLO 不授予自动合并权。

### ChangeSet 与历史

Issue 与主 ChangeSet 正式提交时原子登记，可以暂无候选、组合或 PR。Candidate 正式提交即收录，关联 Task／Attempt，未接受也保留；修复形成新候选。Manager 按有效计划、验证范围与前提，从内部初审接受的业务候选中选定正式 Delivery Combination，未修改仓库固定基线；新候选不静默替换在途组合。

代码版本变化建立新组合；验收、Skill、配置或数据上下文变化时新增相应记录并重判证据。PR head、合并结果或实际产物变化均需核对。执行、验证、交付分开汇总，各仓成功不等于整体完成。

CS1—CS14 已全部确认，尤其保留：

- 完成须满足约定交付物、验收及必做事项；代码交付的必需 PR 已由人合并，最终实际组合证据有效。无代码改动按相应交付约定判断；部署另记。
- 按兼容性选合并顺序；部分合并后保留真实成功部分，以实际版本推进剩余工作、重判证据，不自动撤销已成功部分。
- 取消未合并 PR 留原记录；已合并代码撤销由人发起关联恢复 Issue／ChangeSet，Team 出撤销 PR、人合并；首期部署和数据恢复由有权限的人执行并记录。
- 本轮修复沿用原 ChangeSet；完成后新增范围建立关联的新事项，误标完成追加更正。首期无嵌套 ChangeSet。
- Agent 先读带来源引用的摘要，再按需查明细及证据；默认当前 ChangeSet，可在有效权限内查同项目相关历史，首期不默认跨项目查询。
- 幂等落实到独立逻辑操作，同标识不同输入拒绝；并发校验目标修订版本，同目标冲突串行处理。超时或重启先核查结果。
- 保留事实、判断、更正及必要证据，不把摘要猜测当事实。归属、版本、决定及操作结果随项目存续保留，必要验收证据随交付档案保存，临时材料按策略清理并标明可用性。

结构按“稳定归属主记录、关联明细、摘要视图”理解。记录修订信息、候选／组合的代码版本、Plan Version 分开；精确字段名、数据库表、API schema 与示例 YAML 未冻结。

## 4. I：当前 YOLO，后续审批规则已确认

当前项目和 Issue 统一 YOLO，首次计划与后续调整在现有权限、预算和策略内自动判断许可、记录、应用并核对。审批能力后续开发；下表为已确认的后续设计，不能重新列成待决问题。

| 事项 | 已确认规则 |
| --- | --- |
| 首版计划 | Manager 可在已有权限及预算内分析、澄清并准备计划，展示仓库、主要改动、验收、预算及循环上限。有权的人统一批准一次，RepoMesh 应用并读回后启动业务执行；范围和上限内不逐 Worker、验证节点或每轮修复审批。首条 Issue 登记与实例准备不等待尚未形成的计划。 |
| 计划审批人 | 发起人在仍具备相应项目权限时可审批自己的计划；项目管理员或获授项目计划审批权限的人可代审。一名有权查看完整计划且符合资格的人批准即可，记录人、决定与具体版本。代审不借出 Git 权限。 |
| 默认值与覆盖 | 项目管理员或有配置权限的人设置默认模式及允许范围，默认值须在范围内。新 Issue 继承默认，发起人可在允许范围内另选；只允许审批时不能选 YOLO。修改默认只影响后续新 Issue。 |
| 运行中切换 | 符合该 Issue 计划审批资格的人可请求允许范围内的目标模式。停止受影响上游 Project 新派工，在途按有效授权收尾、核对 submitted 后切换，再按新模式处理剩余计划。YOLO 转审批批准剩余计划；审批转 YOLO 保留待审批记录并重判许可，不冒充人工批准。 |
| 允许范围变化 | 新 Issue 遵守新范围；已有 Issue 的模式不再被允许时停止新派工、按既定规则收尾并报告受限，保留原模式及历史，由有资格的人明确切换后继续。放宽只增加选项，不自动切换已有 Issue。 |

切换保留成果、明确要求、拒绝记录与累计消耗，不重启整条 Issue；权限失效优先按 J3 限制实际操作，不能以收尾为由继续无权操作。失败或不确定先核查，不假定已切换或生效。受限 YOLO 不隐式变成人工审批等待。

此前“产品默认审批模式”的建议未采用；后续版本的产品初始默认值未另行冻结。计划审批资格不自动等同于业务验收规则的修改权、Skill 发布权或 GitHub 审查／合并权。

## 5. J：项目配置与授权变化已确认

J1：填写项目名称与用途；关联 GitHub 账号，选择自己和实际有权参与的协作／组织仓库，待接受邀请不算已获权限。账号关联不代替 App 安装授权；用户访问、App 能力、项目范围、本次任务范围共同核验。接入不要求选分支，由 Manager 按 Issue 和明确要求确定目标分支与固定基线，Team 在独立 Attempt 副本执行，不能切公共目录影响其他 Issue。

模型 API Key 在设置中配置，项目使用可用模型配置；执行环境、预算、时限等可继承明确默认值并显示实际值，Worker 并发默认 1、验证小组默认关闭。管理面必要配置检查通过后才允许正式提交可执行 Issue，项目创建不启动实例，原首条草稿准备按 ADR-0018，新会话首条消息及页面建项提交后的触发适配已采用。具体模型服务商、API 地址、密钥归属、共享、存储和运行时传递尚未冻结。

J2：可选仓库列表自动更新，项目范围由用户明确添加。“全部选择”仅选当时的仓库，不含未来新增；加入项目不自动扩大在途 Issue，确需纳入按计划变更及生效规则处理。

J3：授权部分失效时项目部分可用，显示受限仓库、操作权限及原因。只涉及可用仓库的新 Issue 可正常提交。停止已无授权操作，阻塞依赖，无关且仍获准工作可继续；需要重规划仍按受影响上游 Project 收敛。Manager 汇总已完成与受限部分，不插入审批等待、不误标整体完成；保留历史，读取仍遵守当前权限。检测、强制拦截、请求结果核查与授权恢复触发仍待细化，不承诺自动重启已结束 Issue／Attempt。

## 6. H：Skill 工程保留设计位置

H1—H15 完整决定在 ADR-0009。独立维护可复用 Skill，按角色组合，每条 Issue 引用确定版本并附工作说明；一次性要求保留在 Issue，复用改进形成候选。Agent 起草、改进、验证；项目管理员或获授 Skill 发布权限的人发布。平台通用版本由项目明确选用或维护带来源派生版本。

发布、项目默认选用、在途升级、分发配置与实际加载分别处理。评估覆盖成功、业务失败及前提缺失；依赖和来源固定，冲突明确。版本升级遵守计划与证据规则，不静默改变在途依据；第三方来源、失败、停用、回退与历史按 ADR 保留。

**整个模块待定占位，暂不开发。** 当前只保留 ADR、专题、术语和导航，不创建空代码、接口、功能开关，也不开发管理、发布评估、分发加载、版本隔离或页面。启动时间和实施范围另定。

锁定源码显示 Skill 分配／同步主要面向成员工作区；同一长期 Manager／Leader 的同名 Skill 热替换可能影响其他 Issue，这是静态推断。分发成功不等于实际加载；按 Issue 固定版本尚未获运行证明。Worker 创建和 Manager 创建／更新接口不能依赖未接通的 remoteSkills 字段；Controller 与 QwenPaw 行为也不能混同。

## 7. 下一阶段与未冻结内容

用户已采用 React／TypeScript／Vite、React Flow、Go、PostgreSQL、数据库持久队列、REST＋SSE、对象存储，以及模块化单体和后台任务可独立运行的方向，见 [ADR-0010](../adr/0010-technology-stack-and-modular-monolith.md)与[技术选型](technology-selection.md)。选型收口后已讨论下述架构决定；用户最新指定下一会话转入页面与接口设计。具体版本和未点名的库、对象存储产品留待实现细化，不重新询问已采用的技术方向。

受控适配深度已确认，见 [ADR-0011](../adr/0011-agentteams-controlled-integration.md)：保留 AgentTeams 团队、通信和运行生命周期，工具请求及实际执行由 RepoMesh 控制，必要时维护小范围上游补丁。接受相应维护成本，以落实已有权限、计划、预算和任务约束；不把提示词当作实际保证。具体协议和补丁位置仍需细化与验证。

Issue 映射方向已确认，见 [ADR-0012](../adr/0012-issue-scoped-upstream-projects.md)：每条 Issue 按仓库委派范围分别建立上游 Project，跨仓依赖和整体计划由 RepoMesh 管理；不同 Issue 的上游记录分开，仍共享团队并发额度。暂停按完整受影响上游 Project，在途与 submitted 收敛后应用和读回；多目标部分应用保留真实结果，全部必要目标一致后才宣布新版本生效。验证工作的具体上游归属和恢复算法仍待细化。

进程划分已确认，见 [ADR-0013](../adr/0013-web-coordinator-host-executor-processes.md)：同一 Go 工程、配套发布，分别运行 Web、后台协调和受限主机执行进程。Web 处理交互和查询，后台落实有效计划及核查恢复，主机执行管理经核验且明确归属的环境操作。Manager 仍作业务判断，Controller 仍管理其负责的 Agent runtime；Web 和 Agent 不直接持有 Docker socket。具体协议、运行身份、凭据和生命周期明细待细化。

Graph 插件运行方式已确认，见 [ADR-0014](../adr/0014-in-process-graph-plugin.md)：在后台协调进程内按可替换的独立模块运行，随后端发布；插件根据有效计划和已有结果计算依赖、后续节点及停止条件，后台核验权限、预算和容量后实际派工。计划、轮次和累计消耗保存到数据库，重启按记录恢复并核查。接受配套升级和严重插件故障可能影响后台的代价。不重问插件运行位置。

按当前获准轮次向上游下发有限 DAG 的方向已确认，见 [ADR-0015](../adr/0015-round-scoped-upstream-dags.md)：Manager 组织业务安排，Graph 计算流程，后台核验后派工并控制后续轮次。既定范围和上限内推进不新建 Issue、Manager 或业务 Plan Version，保留新 Attempt 与结果；需要 replan 时按完整受影响上游 Project 收敛、应用和读回。具体任务标识、工具协议、更新方法与恢复算法仍待细化，不重问映射方向。

业务记录与后台待办同事务保存已采用，见 [ADR-0016](../adr/0016-transactional-background-work.md)：正式提交将 Issue、主 ChangeSet 和继续处理的待办一起持久化；后台提交后领取、核验、执行并保存结果。提交成功表示已可靠登记，外部结果未知先核查，事务不跨越外部长时间等待。不重问该方向；队列库、领取、重试参数及具体恢复算法仍待细化。

短事务统一登记 Attempt、Worker 占用和容量预留已采用，见 [ADR-0017](../adr/0017-atomic-attempt-resource-reservation.md)：防止并发重复分配同一资源，未取得资源的工作等待并说明原因；环境在事务外准备，实际启动前再次核验。准备失败先核查再释放可释放占用，超时不等于资源释放，接受准备期间占用名额的代价。具体容量口径、锁、代次、执行端协议和恢复算法仍待细化，不重问该方向。

页面／接口侧继续 K 的 Manager 布局、摘要与详情、图、刷新和历史，见[页面 prompt](NEXT-SESSION-PROMPT.md)。后端继续独立事项消息目标、创建及其他后端细化，见[后端 prompt](NEXT-BACKEND-SESSION-PROMPT.md)，按通信约定直接与页面侧对齐，依持续授权采用推荐并报告。Manager 唯一对人窗口、执行／验证／交付分开汇总、摘要可溯源、首期自然语言改图继续有效。采用 SSE 不单独确定刷新、断连恢复和历史交互。

三栏布局只是此前建议，未采用；“项目默认私有、明确邀请成员”也是未确认建议。具体轮询数值、字段、数据库与 API schema 均未确认，不能从旧 PRD 或示例补成已决规则。

页面已完成会话与独立 Issue 专页原型，DESIGN-002 第 3／3 轮落地核对结束。消息目标方向已采用、具体契约待定；DESIGN-004 第 3／3 轮已收口，默认新会话已落实。创建快照及启动适配已采用，仓库事项粒度与恢复等按持续授权继续细化并报告；不进行第 4 轮，不把页面表单或模拟事件整体冻结。

技术细化另行推进：RepoMesh Issue 与上游 Project／房间／session 映射、实际权限和派工控制、资源调度、插件契约、证据存储、事务与恢复；这些未完成不表示已确认的产品规则需要重问，也不授权立即编码。

## 8. 静态证据边界与协作约定

AgentTeams 依据锁定提交 `eeaab64391ccaec9118e84977f538aefd40720d6` 的静态调研，未部署验收：

- Controller replan 在有 in-progress／submitted 时拒绝；pause 不停止在途任务，也不能作为权限撤销的强制保证。不能承诺只暂停某个分支。
- 原生 DAG／Loop、Manager 广泛权限、Dashboard 较新 HITL 不能算作已满足 RepoMesh 完整编排和审批要求。
- history／workflow／artifact 读取不证明实时订阅或可信跨仓汇总已实现；具名 Manager 不证明独立管理身份，QwenPaw 的 session 依据不能直接推广到其他 runtime。
- 旧调研与旧 ADR 中聊天和事项的绑定以 ADR-0019 定点替代为准；ADR-0018 的准备保障保留，新对象启动适配按最新创建契约与 ADR-0018 补充采用。多实例容量、身份隔离、工具约束和恢复仍需运行验证。

用户继续停用 `C:\Users\18092\.agents\skills\grill-with-docs\SKILL.md`，最新指定下一会话继续后端架构设计，页面／接口侧另行协作。继续中文讨论，以具体场景说明系统行为、状态、职责与异常；新决定依用户持续授权采用推荐后写 Markdown，术语表只放定义，独立取舍按需 ADR，图用字符图。接口示例是设计草案，不等于编码或上游能力已实现。

当前授权中文设计与本地 Markdown，并因用户明确要求允许制作可丢弃的本地交互原型。原型仅为“不编码”的局部例外：暂不编写生产代码、安装、部署、接入真实服务、创建真实 GitHub App、写入远端或自动新建 Codex 任务。每轮设计直接同步对方并保存通信，向用户说明设计、文件、接口及全部未决范围，按用户持续授权推进推荐方案。
