> 历史快照：2026-09-08 本轮整理前版本，仅供溯源；不作为现行决定或接手指令。见[归档说明](../../README.md)。

# RepoMesh 当前文档

本目录为 docs/current/。上一级 [docs 导航](../README.md)连接本目录、ADR 与历史资料。

更新：2026-09-08，Skill 工程待定占位，I 当前全自动，J1—J3 已确认，I 本轮主要规则已收口，后续可继续 K。当前阶段为产品与架构设计及本地文档整理，未实施或运行验收。

A—E、CS1—CS14 及 Skill 工程 H1—H15 的设计方向已同意。**Skill 工程待定／占位，暂不开发**，规则保存在 ADR-0009。I 当前统一全自动（YOLO），审批能力后续开发；已恢复 I 的设计讨论并确认后续审批模式首版计划统一批准一次、审批人资格、创建时模式覆盖、运行中切换及允许模式范围变化，见 ADR-0003、ADR-0006。J1 项目接入、J2 新增仓库及 J3 授权部分失效的主要规则已确认；I 本轮主要规则已收口，下一阶段可继续 K；K 尚未确认。ChangeSet 精确字段和接口未冻结。

从[新 handoff](HANDOFF.md)了解完整基线；开启下一会话时复制[接手 prompt](NEXT-SESSION-PROMPT.md)中的文本块。整理前版本已[归档](../../../2026-09-08-handoff-before-consolidation/README.md)。

## 当前阅读入口

| 文件 | 用途 |
| --- | --- |
| [当前交接](HANDOFF.md) | 已确认基线、H／I 延后范围、J 已确认规则、K 待讨论事项及静态证据边界。 |
| [领域语言](../../CONTEXT.md) | 仅含概念定义。 |
| [ADR-0001](../adr/0001-agentteams-issue-concurrency-and-isolation.md) | 项目与团队、所有 issue 的 Manager 统一接收与总责、独立主房间、隔离和延迟启动。 |
| [ADR-0002](../adr/0002-github-app-authorization-and-draft-pr-delivery.md) | GitHub App、有效 Git 权限与 draft PR 交付边界。 |
| [ADR-0003](../adr/0003-plan-change-authorization-and-activation.md) | 计划版本、按模式判断许可、获准与生效、冲突及真实执行控制。 |
| [ADR-0004](../adr/0004-acceptance-rule-clarification.md) | 缺失业务规则按模式决定：审批模式经 Manager 请人，YOLO 由 Manager 解释并记录。 |
| [ADR-0005](../adr/0005-optional-project-verification-group.md) | 默认关闭的项目级验证小组、分工、动态成员、归属与重验、启停及异常。 |
| [ADR-0006](../adr/0006-manager-entry-modes-and-skill-driven-execution.md) | Manager 唯一对人窗口、当前全自动与审批能力延后、Skill 驱动执行。 |
| [ADR-0007](../adr/0007-graph-loop-plugin.md) | 已确认的 Graph／Loop 行为、默认上限及插件方向；接口和上游映射未验证。 |
| [ADR-0008](../adr/0008-changeset-attribution-and-history.md) | ChangeSet 稳定归属、记录整合、查询、幂等及已确认的交付与恢复边界。 |
| [ADR-0009](../adr/0009-skill-engineering-deferred.md) | Skill 工程 H1—H15 预留设计；整个模块待定占位、暂不开发。 |
| [团队执行策略](team-execution-policy.md) | A：数量设置默认 1、调度、不可用和资源回收。 |
| [联调环境](integration-environment-design.md) | C：固定基线和组合、独立环境、Leader 提供 mock 数据、核对与清理。 |
| [PR 审查](draft-pr-review-design.md) | E：draft 创建和持续更新、审查门槛及反馈。 |
| [ChangeSet 设计](changeset-design.md) | CS1—CS14 全部已确认：外部关联、组合、状态、幂等、合并恢复、查询及记录保留。 |
| [ChangeSet 结构](changeset-structure.md) | 归属主记录、关联明细、摘要与支付筛选示例；精确字段和接口未冻结。 |
| [Skill 工程](skill-engineering-design.md) | 待定占位专题：组织与场景说明、锁定源码证据，完整预留决定见 ADR-0009。 |
| [项目配置](project-configuration-design.md) | J1 项目接入、J2 新增仓库、J3 项目部分可用及按影响范围受限；技术接入与恢复细节待细化。 |
| [测试与验证节点](verification-node-design.md) | 输入、必检清单、固定组合、证据、检查结论与覆盖。 |
| [接手提示](NEXT-SESSION-PROMPT.md) | 已重写的可复制新会话 prompt，含有序阅读清单和下一阶段范围，不创建任务。 |

## 参考证据

- [AgentTeams 调研](../../../../agentteams-survey-2026-09-07/agentteams-survey.md)与[接口调查](../../../../agentteams-survey-2026-09-07/agentteams-api-cli-survey-2026-09-07.md)：锁定提交的静态记录，不等于部署验收；早期实例启动图按 ADR-0001 D18 使用。
- [Cursor Dashboard 报告](../../../../../Cursor_Dashboard_Report_2026-09-07/report.md)：界面参考，不证明 RepoMesh 的编排、授权或交付已经实现。

## 历史资料

[归档索引](../archive/README.md)集中列出旧交接、旧开场、已收口讨论稿、修改前快照和历史 PRD。历史状态、未采纳方案和过时问题不作为当前设计，也不据此恢复已移除的人工门禁。当前决定以用户最新确认和上表中的现行文档为准。
