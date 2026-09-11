# 整理前快照：NEXT-SESSION-PROMPT.md

归档日期：2026-09-08。本文保存本轮交接重写前的内容，其中的“当前讨论位置”、开场动作和待办表属于旧会话语境。

当前入口：[新交接](../../current/HANDOFF.md)、[新会话 prompt](../../current/NEXT-SESSION-PROMPT.md)、[当前文档索引](../../current/README.md)。原文内容保留，必要的相对链接已调整；历史路径和代码块按原文保留。

---

# RepoMesh 当前接手提示

更新：2026-09-08。对应 [当前交接](HANDOFF.md)，复制以下内容可继续设计讨论；本文不创建新任务。

```text
请继续 RepoMesh 产品与架构设计。工作区为 D:\Project4work\Repomesh_Go_ver。
先完整阅读：
1. docs\HANDOFF.md
2. CONTEXT.md
3. docs\adr\0001-agentteams-issue-concurrency-and-isolation.md
4. docs\adr\0002-github-app-authorization-and-draft-pr-delivery.md
5. docs\adr\0003-plan-change-authorization-and-activation.md
6. docs\adr\0004-acceptance-rule-clarification.md
7. docs\adr\0005-optional-project-verification-group.md
8. docs\adr\0006-manager-entry-modes-and-skill-driven-execution.md
9. docs\verification-node-design.md
另读 docs\adr\0007-graph-loop-plugin.md、docs\adr\0008-changeset-attribution-and-history.md、docs\team-execution-policy.md、docs\integration-environment-design.md、docs\draft-pr-review-design.md，以及已确认的 docs\changeset-design.md 和字段尚未冻结的 docs\changeset-structure.md。
10. docs\agentteams-survey-2026-09-07\agentteams-survey.md
11. docs\agentteams-survey-2026-09-07\agentteams-api-cli-survey-2026-09-07.md

以用户最新确认和现行文档为准。docs\archive、docs\old_ver 及归档的 Cloud Agent PRD 只作历史参考；不要从旧开场重新讨论已确认内容。需要界面参考再读 Cursor_Dashboard_Report_2026-09-07\report.md。

已确认：
- 每项目独立 AgentTeams 实例、一个 Manager，每仓长期 Team/Leader。首条 issue 正式提交并持久化后才准备实例，后续复用。
- 所有新 issue（包括明确单仓）先进入独立的 Manager 主房间，由项目现有 Manager 接收并始终承担 issue 总责。Manager 按范围委派一个或多个 Leader，Leader 负责仓库工作；用户始终在主房间与 Manager 对话。
- 每条 issue 使用独立主房间和所需仓库子房间，各 Agent/session 分开。追加消息、重试和重复事件沿用原主房间；建房失败保留 issue 并幂等重试，不重复建房或创建新 Manager。
- 团队和验证流程由 Skill 指导并记录版本；按仓库及任务请求 Worker，优先复用合适空闲成员，必要时申请创建。RepoMesh 实际分配、创建和启动，控制单活跃任务、独立 Attempt、全局容量、项目额度及权限。
- YOLO 不弹人工审批、不等待人同意。缺失业务规则由 Manager 选择并记录解释后继续，不覆盖已有明确要求，也不冒充人已确认。
- YOLO 触及权限、预算上限或已明确验收条件的边界时返回受限或未完成结果，不自行扩大或降低标准。审批模式由 Manager 在当前会话呈现需要用户决定的事项。
- 版本化计划、获准与生效分开、许可范围内 Loop 自动运行、冲突及失败留历史、RepoMesh 实际控制执行。首期仅自然语言调整编排，直接编辑图为后续待办。
- GitHub App 固定权限集，运行时收窄且不放大发起人的有效 Git 权限；Agent 推自己分支、开 draft PR，合并由人和仓库规则控制。YOLO 不授予合并权。
- 验证输入、必检清单、五类检查结果、固定组合证据及覆盖门槛已确认。验证环境不向业务仓推修复；新候选重新判断旧证据适用性。
- 项目级验证小组可选启用，启用时有固定验证负责人。正式验证执行者与本轮业务作者分离；清单、执行、复核、定位及修复后重验职责见 ADR-0005。负责人复核是 Agent 内部工作，不要求用户逐项确认。
- 关闭小组时停止接新工作，未启动任务交回 Manager，在途收尾、submitted 继续核对，再完成停用。

用户最新确认 A—E：
- A1：Worker 数量可在设置中调整，默认 1，沿用 A1 的团队并发上限语义。A2—A5：调度、不可用和资源回收按团队执行策略。
- B1：验证小组默认不启用。B2—B4：项目配置权限、停用受阻和重新启用按 ADR-0005。
- C1—C6：固定基线与完整组合、每验证 Attempt 独立环境、实际版本核对、保存证据后清理；C4 指定 mock 数据由 Leader 提供。
- D1—D7：顺序、并行、汇合及有界 Loop；默认修复 3 轮、诊断补证 2 轮、环境恢复 2 次；预算时限先到先停，累计消耗不清零；Graph／Loop 采用插件形式，接口和上游实现待验证。
- E1—E5：Leader 初审后创建 draft，同仓持续更新；有效验证和必需仓库检查满足后推荐审查；首期人转换 draft 状态；反馈回原 issue。

ChangeSet 边界已确认：一个 issue 默认一个主 ChangeSet，保留同一身份和多轮历史；各交付动作独立记录并处理幂等。用户明确其是变更归属与记录整合，串联 issue、仓库、PR、既有 Candidate、Delivery Combination 和交付历史。不另建一套重复的候选版本模型，Candidate 提交不等于已交付，组合变化仍需重新判断证据。定义和关系见 CONTEXT.md 与 ADR-0008，不重新追问该边界。
创建时机已确认：issue 正式提交并持久化时建立主 ChangeSet，允许暂时没有候选、组合及 PR；后续关联产物，重复事件和恢复复用既有归属，不改变实例准备时机。用户同时确认 ChangeSet 用于方便 Agent 查看和溯源。
Agent 读取方式已确认：先读带来源引用的摘要，再按需查询关联的结构化记录及原始证据；摘要结论可定位到来源，缺失证据如实显示。查询范围已确认：默认当前 ChangeSet，可在既有权限内按 Issue、仓库、commit、PR 查询同项目相关历史，首期不默认跨项目查找。精确查询字段和工具接口仍待细化。
Candidate 收录时机已确认：正式提交即关联到所属 ChangeSet，不等待检查接受；后续未被接受也保留来源、检查结果及历史，修复产生的新候选另行记录。收录不自动代表接受、入选组合、通过验收或达到 PR 创建条件。
这里的 Issue 是 RepoMesh 内部的一条统一需求事项，可涉及一仓或多仓，与 GitHub 单仓 issue 分开。已确认可关联零到多条外部 issue 并记录来源／跟踪关系，重复导入先查映射；首期不默认启用外部创建、评论、同步或关闭操作。
用户已全部采用 CS1—CS14，涵盖外部关联、重开、组合、验证记录、PR 版本关联、状态、事实与判断、幂等并发、完成条件、合并顺序、部分失败、恢复、查询范围和记录保留。详见当前 ChangeSet 设计，不重新询问是否采用。
当前用户询问 ChangeSet 结构。逻辑结构说明以稳定归属主记录、关联明细和可追溯摘要解释已确认规则；字段命名、记录拆分和示例仍是结构建议，数据库表及 API schema 未冻结。Issue 与主 ChangeSet 原子登记、目标版本校验和冲突操作串行处理是已确认要求，实现仍待验证。
F／G 的合并恢复议题以已确认的 CS9—CS12 为准，不整体恢复其他旧建议。H／I／J／K 明确后续再谈，不把项目默认 YOLO、首次计划审批、全部仓库新增范围、页面轮询数值等旧建议升级为决定。

接口依据是锁定提交静态调研，未部署验收。Controller replan 在有 in-progress/submitted 时拒绝，pause 不停止在途任务。原生 DAG/Loop、Manager 权限、Dashboard HITL 不能描述为已满足 RepoMesh 要求。调研的早期实例启动图按 ADR-0001 D18 纠正理解。

中文讨论，每次一个关键问题，以实际场景给建议；不重复追问已确认内容。新决定经我确认后写 Markdown，术语表只放定义，独立主题按需 ADR，图用字符图。
当前只做设计和本地文档整理，不安装、部署、编码、创建真实 GitHub App、写远端仓库或自动新建 Codex 任务。
```
