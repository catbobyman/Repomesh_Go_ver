> 历史快照：2026-09-08 本轮整理前版本，仅供溯源；不作为现行决定或接手指令。见[归档说明](../../README.md)。

# 下一会话接手 Prompt

更新：2026-09-08，Skill 工程待定占位，I 当前全自动，J1—J3 已确认，I 本轮主要规则已收口，后续可继续 K。复制下面整个文本块即可开始下一会话；对应[当前 handoff](HANDOFF.md)。

```text
请接手 RepoMesh 产品与架构设计。实际工作区：
D:\Project4work\Repomesh_Go_ver

目录已整理：当前 handoff、prompt 和专题位于 docs\current；ADR 位于 docs\adr；历史归档位于 docs\archive。

使用 C:\Users\18092\.agents\skills\grill-with-docs\SKILL.md 继续中文设计讨论和文档记录。

先按顺序完整阅读当前文档：
1. docs\current\HANDOFF.md
2. CONTEXT.md
3. docs\adr\0001-agentteams-issue-concurrency-and-isolation.md
4. docs\adr\0002-github-app-authorization-and-draft-pr-delivery.md
5. docs\adr\0003-plan-change-authorization-and-activation.md
6. docs\adr\0004-acceptance-rule-clarification.md
7. docs\adr\0005-optional-project-verification-group.md
8. docs\adr\0006-manager-entry-modes-and-skill-driven-execution.md
9. docs\adr\0007-graph-loop-plugin.md
10. docs\adr\0008-changeset-attribution-and-history.md
11. docs\adr\0009-skill-engineering-deferred.md
12. docs\current\team-execution-policy.md
13. docs\current\verification-node-design.md
14. docs\current\integration-environment-design.md
15. docs\current\draft-pr-review-design.md
16. docs\current\changeset-design.md
17. docs\current\changeset-structure.md
18. docs\current\skill-engineering-design.md
19. docs\current\project-configuration-design.md
20. docs\agentteams-survey-2026-09-07\agentteams-survey.md
21. docs\agentteams-survey-2026-09-07\agentteams-api-cli-survey-2026-09-07.md

需要界面参考时再读 Cursor_Dashboard_Report_2026-09-07\report.md。
以用户最新确认、现行 ADR 和专题设计为准。docs\archive、docs\old_ver、旧 handoff 和归档的 Cloud Agent PRD 仅作历史参考。changeset-design-discussion.md 只是旧链接入口。

目前 A—E、ChangeSet 的 CS1—CS14 和 Skill 工程 H1—H15 的设计方向已同意。Skill 整个模块按用户要求标记为待定／占位，暂不开发；完整规则见 ADR-0009。请先简述理解，再继续未决主题，不重新询问这些已采用的方案。

必须保留的设计：
- 使用 agentscope-ai/AgentTeams，每多仓项目独立实例、一个长期 Manager，每仓长期 Team／Leader。所有新 Issue，包括明确单仓，都先由 Manager 在新的独立主房间接收，并由 Manager 全程统筹。各 Agent 的 Issue session 分开，Leader 只负责被委派仓库工作。
- Issue 是 RepoMesh 内部的一条统一需求事项，可涉及一仓或多仓。它可关联零到多条 GitHub issue 作为来源或跟踪记录；首期不默认启用外部创建、评论、同步或关闭操作。
- 正式提交时原子登记 RepoMesh Issue 与主 ChangeSet，允许暂无候选、组合及 PR。首条 Issue 持久化后才准备实例，Ready 后建主房间，后续复用或恢复。重复事件和故障恢复复用原归属。
- Worker 单活跃任务，每个 Attempt 独立副本。团队 Worker 并发数量可设置，默认 1，不包含 Manager／Leader／验证负责人；实际执行同时受全局容量、项目额度和有效权限约束。按 Skill 动态请求，优先复用合适空闲成员，RepoMesh 实际分配和启动。
- 人只在主界面与 Manager 对话。YOLO 不弹人工审批、不等待人同意；审批模式的待决定事项由 Manager 统一呈现。Agent 内部初审与复核不成为人工门禁。
- YOLO 缺失业务规则时由 Manager 解释并留记录，不覆盖已有明确要求或冒充人已确认；遇到权限、预算上限或既定验收边界时返回受限／未完成结果，不自行扩大、降低标准或插入人工等待。
- 计划版本、获准和生效分开；许可及上限内 Loop 自动运行，冲突和失败留历史。RepoMesh 实际控制计划应用与任务启动。首期只通过自然语言调整编排，直接编辑图为后续待办。
- Graph／Loop 采用插件形式，支持顺序、并行、汇合和有界 Loop；默认修复 3 轮、诊断 2 轮、环境恢复 2 次。预算或时限先到先停，换计划不清零消耗；连续两轮同一失败且无新增有效证据结束循环。
- 项目验证小组默认不启用。启用时有固定验证负责人，未启用时 Manager 组织；正式验证执行者与本轮业务作者分离。停用时停止接新、在途收尾、submitted 继续核对，真实缺陷和阻塞保留。
- Leader 提供运行说明、mock 数据及使用说明；每验证 Attempt 独立环境，核对实际固定 commit 组合、配置与数据。验证环境不向业务仓推修复。五类结果和必检证据门槛已确认，新组合重新判断证据有效性。
- GitHub App 固定工作权限集、运行时收窄且不放大发起人的有效 Git 权限。Agent 推自己分支、开 draft PR，合并由人和仓库规则决定。Leader 初审形成有范围和自测记录的候选后创建 draft；有效验证及必需检查满足后推荐审查，首期由人把 draft 转为正式 PR。
- ChangeSet 整合归属和历史，关联 Candidate、Delivery Combination、依据、证据、PR 和操作；Candidate 正式提交即收录，未被接受也保留历史。正式组合由 Manager 按计划及验证前提从内部初审接受的业务候选中选定，未修改仓库固定基线。
- Agent 先读带来源引用的摘要，再按需查关联记录及证据；默认当前 ChangeSet，可在有效权限内查同项目相关历史，首期不默认跨项目查询。执行、验证、交付进展分开汇总。
- 幂等落实到独立逻辑操作；同标识不同输入拒绝，并发校验目标版本，同目标冲突串行处理。超时或重启先核查结果。保留事实、判断、更正及必要证据，不把摘要猜测当作事实。
- CS1—CS14 包含已确认的完成、合并和恢复规则：必需 PR 人工合并且最终实际组合证据有效，并完成约定交付物、验收及必做事项；部署另记。按兼容性选合并顺序，部分合并后按真实版本推进，不自动撤销成功部分。取消未合并 PR 留原记录；已合并代码撤销由人发起关联恢复事项，Team 出撤销 PR、人合并；首期部署和数据恢复由有权限的人执行并记录。
- ChangeSet 结构按“稳定归属主记录、关联明细、摘要视图”理解。记录修订信息、代码候选／组合版本和 Plan Version 分开；具体字段名、数据库表、API schema 及示例 YAML 尚未冻结。F／G 以 CS9—CS12 为准，不整体恢复旧建议。

Skill 工程 H1—H15 已同意但整体待定占位、暂不开发：独立维护可复用 Skill，按角色组合，每条 Issue 引用确定版本并附工作说明；Agent 起草、改进和验证，项目管理员或有发布权限的人发布项目版本。平台提供通用版本，项目明确选用或维护有来源的派生版本。发布、后续默认选用和在途升级分开；一次性要求不直接改写公共 Skill，不静默改变计划或验收依据，不增加 YOLO 人工等待。

Skill 的内容、评估、依赖冲突、能力分配、临时说明、第三方导入、失败、停用回退及历史规则均见 ADR-0009。当前只保留 ADR、专题、术语及导航位置，不开发 Skill 管理、发布评估、分发加载、版本隔离或相关页面，也不创建空实现、接口或功能开关。启动时间和实施范围以后另定。

AgentTeams 的 Skill 分配及 QwenPaw 加载主要面向成员工作区；同一长期 Manager／Leader 的公共同名 Skill 更新可能影响其他 Issue，这是静态源码推断。分发成功、配置成功和实际加载分别核对；按 Issue 固定版本的实际保证仍需验证。不能依赖 Worker 创建或 Manager 创建／更新接口中未接通的 remoteSkills 字段。

I 当前阶段已确定统一按全自动（YOLO）设计：首次计划及后续调整在既有授权、预算和策略内自动判断、记录许可并应用，不弹人工审批、不等待人同意。用户随后明确继续 I 的设计讨论，并确认后续审批模式下首版计划统一批准一次：Manager 在已有权限及预算内分析仓库、整理并展示涉及仓库、主要改动、验收条件、预算和循环上限；有权审批的人批准后，RepoMesh 应用并核对生效再启动执行，范围与上限内不逐个批准 Worker、验证节点或每轮修复。审批人资格已确认：发起人在仍具备相应项目权限时可审批自己的计划，项目管理员或获授计划审批权限的人可代审；一名有权查看完整计划且符合资格的人批准即可，记录审批人和计划版本，代审不扩大原发起人的有效 Git 权限。项目／Issue 模式覆盖已确认：项目管理员或有项目配置权限的人设置默认模式与允许范围，新 Issue 继承默认，发起人可在允许范围内另选；项目只允许审批时不能选 YOLO，修改默认值只影响后续新 Issue，已有 Issue 保留原模式。

运行中切换已确认：由符合该 Issue 计划审批资格的人发起，目标模式须在项目允许范围内。停止受影响上游 Project 新派工，在途任务收尾并核对已提交结果后切换生效，再按新模式处理剩余工作。YOLO 转审批时统一批准剩余计划；审批转 YOLO 时保留原待审批记录，按权限、预算和策略重新判断许可，不冒充人工批准。保留已完成工作、原决定及累计消耗，不覆盖明确要求或拒绝，不重新开始整条 Issue。允许模式范围变化已确认：新 Issue 按新的允许范围选择；已有 Issue 的模式不再被允许时停止新派工，在途按既定规则收尾并报告受限，保留原模式和历史，由符合该 Issue 计划审批资格的人明确发起切换后继续。放宽范围只增加可选项，已有 Issue 不自动切换。I 本轮主要规则已收口，审批能力仍后续开发；此前默认审批模式的建议未采用。既有 GitHub 人工交付、权限及验收边界保持有效，当前仍不开始编码。

J1 项目接入已确认：关联 GitHub 账号，让用户选择自己的仓库和实际有权限参与的受邀仓库；账号关联不代替 App 安装授权，仍核验发起人的有效权限。项目接入不要求选分支，由 Manager 按 Issue 和已有明确要求确定目标分支及固定基线，Team 在独立 Attempt 副本中执行。模型 API Key 在设置中配置，项目使用可用配置；名称与用途填写，执行环境、预算和时限可继承明确默认值并显示实际值，Worker 并发默认 1、验证小组默认关闭。必要配置检查通过后可提交 Issue，不提前准备实例。完整规则见 project-configuration-design.md。

J2 已确认：仓库可选列表自动更新，项目范围由用户明确添加；全部选择只选中当时的仓库，不自动包含未来新增仓库。新增仓库加入项目不自动改变在途 Issue，确需纳入时按既有计划变更及生效规则处理。J3 已确认：项目显示部分受限并标明仓库、权限及原因；只涉及可用仓库的新 Issue 可正常提交。停止已无授权的操作，依赖它的工作受阻，无关且仍获准的工作可继续；Manager 汇总已完成和受限部分，不插入人工审批等待，不把整体误标完成，保留原有历史。需要重规划时仍按受影响上游 Project 收敛；pause 不停止在途任务，不能作为权限撤销的强制保证。授权检测、实际拦截及恢复触发方式仍需细化。

用户指定回到 I 后，本轮主要规则已确认，下一阶段可继续 K；H1—H15、I 当前全自动及后续审批模式首版计划、审批人、创建时模式覆盖、运行中切换与允许模式范围变化规则、J1—J3 不再重问，Skill 工程保持待定占位：
K：Manager 主界面、摘要与详情、图的查看交互、刷新和历史方式。
建议从 K 的 Manager 主界面布局继续；用户另有指定时调整顺序。K 的三栏布局建议、项目默认私有和邀请成员建议均未确认，不作已采用方案。K 的具体页面交互、刷新及轮询数值等仍未确认。

接口依据是锁定提交 eeaab64391ccaec9118e84977f538aefd40720d6 的静态调研，未部署验收。Controller replan 在有 in-progress／submitted 任务时拒绝，pause 不停止在途任务；应用计划仍按受影响的上游 Project 收敛。原生 DAG／Loop、Manager 广泛权限、Dashboard HITL 不能描述为已满足 RepoMesh 的完整编排和审批要求。旧调研的先实例后 Issue 图按 ADR-0001 D18 纠正理解。

中文讨论，以支付状态筛选等具体场景说明页面、系统行为、状态、职责和异常。默认每次一个关键问题并给建议；用户要求集中讨论时再一次列出。新决定经我确认后写 Markdown，术语表只放定义，独立取舍按需 ADR，图用字符图。

当前只做设计和本地文档整理，暂不安装、部署、编码、创建真实 GitHub App、写入远端仓库，也不要自动新建 Codex 任务。
```
