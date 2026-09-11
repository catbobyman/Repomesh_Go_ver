# 整理前快照：README.md

归档日期：2026-09-08。本文保存本轮交接重写前的内容，其中的“当前讨论位置”、开场动作和待办表属于旧会话语境。

当前入口：[新交接](../../current/HANDOFF.md)、[新会话 prompt](../../current/NEXT-SESSION-PROMPT.md)、[当前文档索引](../../current/README.md)。原文内容保留，必要的相对链接已调整；历史路径和代码块按原文保留。

---

# RepoMesh 当前文档

更新：2026-09-08。当前阶段为产品与架构设计及本地文档整理，未实施或运行验收。

## 当前阅读入口

| 文件 | 用途 |
| --- | --- |
| [当前交接](HANDOFF.md) | 已确认基线、当前讨论位置、剩余问题和技术证据边界。 |
| [领域语言](../../../CONTEXT.md) | 仅含概念定义。 |
| [ADR-0001](../../adr/0001-agentteams-issue-concurrency-and-isolation.md) | 项目与团队、所有 issue 的 Manager 统一接收与总责、独立主房间、隔离和延迟启动。 |
| [ADR-0002](../../adr/0002-github-app-authorization-and-draft-pr-delivery.md) | GitHub App、有效 Git 权限与 draft PR 交付边界。 |
| [ADR-0003](../../adr/0003-plan-change-authorization-and-activation.md) | 计划版本、按模式判断许可、获准与生效、冲突及真实执行控制。 |
| [ADR-0004](../../adr/0004-acceptance-rule-clarification.md) | 缺失业务规则按模式决定：审批模式经 Manager 请人，YOLO 由 Manager 解释并记录。 |
| [ADR-0005](../../adr/0005-optional-project-verification-group.md) | 默认关闭的项目级验证小组、分工、动态成员、归属与重验、启停及异常。 |
| [ADR-0006](../../adr/0006-manager-entry-modes-and-skill-driven-execution.md) | Manager 唯一对人窗口、人工门禁模式、Skill 驱动动态执行。 |
| [ADR-0007](../../adr/0007-graph-loop-plugin.md) | 已确认的 Graph／Loop 行为、默认上限及插件方向；接口和上游映射未验证。 |
| [ADR-0008](../../adr/0008-changeset-attribution-and-history.md) | ChangeSet 稳定归属、记录整合、查询、幂等及已确认的交付与恢复边界。 |
| [团队执行策略](../../current/team-execution-policy.md) | A：数量设置默认 1、调度、不可用和资源回收。 |
| [联调环境](../../current/integration-environment-design.md) | C：固定基线和组合、独立环境、Leader 提供 mock 数据、核对与清理。 |
| [PR 审查](../../current/draft-pr-review-design.md) | E：draft 创建和持续更新、审查门槛及反馈。 |
| [ChangeSet 设计](../../current/changeset-design.md) | CS1—CS14 全部已确认：外部关联、组合、状态、幂等、合并恢复、查询及记录保留。 |
| [ChangeSet 结构](../../current/changeset-structure.md) | 归属主记录、关联明细、摘要与支付筛选示例；精确字段和接口未冻结。 |
| [测试与验证节点](../../current/verification-node-design.md) | 输入、必检清单、固定组合、证据、检查结论与覆盖。 |
| [接手提示](NEXT-SESSION-PROMPT.md) | 可复制的新会话上下文，不创建任务。 |

## 参考证据

- [AgentTeams 调研](../../agentteams-survey-2026-09-07/agentteams-survey.md)与[接口调查](../../agentteams-survey-2026-09-07/agentteams-api-cli-survey-2026-09-07.md)：锁定提交的静态记录，不等于部署验收；早期实例启动图按 ADR-0001 D18 使用。
- [Cursor Dashboard 报告](../../../Cursor_Dashboard_Report_2026-09-07/report.md)：界面参考，不证明 RepoMesh 的编排、授权或交付已经实现。

## 历史资料

[归档索引](../../archive/README.md)集中列出旧交接、旧开场、已收口讨论稿、修改前快照和历史 PRD。历史状态、未采纳方案和过时问题不作为当前设计，也不据此恢复已移除的人工门禁。当前决定以用户最新确认和上表中的现行文档为准。
