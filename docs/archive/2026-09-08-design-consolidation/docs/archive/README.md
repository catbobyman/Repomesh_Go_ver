> 历史快照：2026-09-08 本轮整理前版本，仅供溯源；不作为现行决定或接手指令。见[归档说明](../../README.md)。

# RepoMesh 历史归档

当前设计从 [文档入口](../current/README.md)和[当前交接](../current/HANDOFF.md)阅读。这里保留历史依据，不作为现行规则或已实现能力；历史文件中的 accepted 状态和待确认问题均属于当时语境。

## 2026-09-08：交接文档重新整理

A—E 和 CS1—CS14 已收口，ChangeSet 结构解释完成。当前 [HANDOFF.md](../current/HANDOFF.md) 与[下一会话 prompt](../current/NEXT-SESSION-PROMPT.md)已重写，未决范围更新为 H—K，字段和接口继续标明尚未冻结。

本轮保存的整理前快照：

- [旧 handoff](../../../2026-09-08-handoff-before-consolidation/HANDOFF.md)。
- [旧下一会话 prompt](../../../2026-09-08-handoff-before-consolidation/NEXT-SESSION-PROMPT.md)。
- [旧文档索引](../../../2026-09-08-handoff-before-consolidation/README.md)。

快照相互引用仍指向同批旧文件，其他相对链接已调整；历史 prompt 中的开场动作不作为当前待办。

## 2026-09-08：ChangeSet CS1—CS14 全部确认

[确认前清单](../../../2026-09-08-changeset-cs1-cs14-proposal.md)保留当时的问题和推荐。用户已回复“都采用”，当前规则转入 [ChangeSet 设计](../current/changeset-design.md)，旧讨论路径仅保留文档入口。

## 2026-09-08：ChangeSet 边界确认

[初始 ChangeSet 提案](../../../2026-09-08-changeset-initial-proposal.md)保留边界确认前的讨论原文。当前决定见 [ADR-0008](../adr/0008-changeset-attribution-and-history.md)：沿用 Candidate 和 Delivery Combination，由 ChangeSet 整合归属及交付历史；CS1—CS14 也已全部确认，现行规则见 [ChangeSet 设计](../current/changeset-design.md)，字段示意见[结构说明](../current/changeset-structure.md)。

## 2026-09-08：统一 issue 接收与总责

[单仓直达及 Leader 担任 issue 主责的旧设计](../../../2026-09-08-leader-direct-issue-routing.md)已归档。当前所有新 issue 均先进入独立 Manager 主房间，Manager 始终负责整条 issue，Leader 负责被委派仓库工作；现行规则见 ADR-0001 和 ADR-0006。

## 2026-09-08：Manager 交互与 Skill 归档

此次整理采用 Manager 统一交互、YOLO 无人工门禁和 Skill 动态执行，当前决定见 [ADR-0006](../adr/0006-manager-entry-modes-and-skill-driven-execution.md)。

| 历史资料 | 归档内容与当前去向 |
| --- | --- |
| [v2 交接](../../../2026-09-08-before-manager-skill/docs/HANDOFF-2026-09-07-v2.md) | 旧交接，已由当前 HANDOFF.md 取代。 |
| [v3 交接](../../../2026-09-08-before-manager-skill/docs/HANDOFF-2026-09-07-v3.md) | 含累积补充、旧开场和未更新段落，整体归档。 |
| [旧接手提示](../../../2026-09-08-before-manager-skill/docs/NEXT-SESSION-PROMPT-2026-09-07.md) | 旧的未决清单和门禁规则；使用当前 NEXT-SESSION-PROMPT.md。 |
| [方向修改讨论稿](../../../2026-09-08-before-manager-skill/docs/manager-entry-and-skill-orchestration-proposal.md) | 讨论已收口，现行规则进入 ADR-0006 及相关专题。 |
| [修改前 ADR-0001](../../../2026-09-08-before-manager-skill/docs/adr/0001-agentteams-issue-concurrency-and-isolation.md) | 保留旧交互图、被放弃方案及历史确认；现行 ADR 已同步入口与资源语义。 |
| [修改前 ADR-0002](../../../2026-09-08-before-manager-skill/docs/adr/0002-github-app-authorization-and-draft-pr-delivery.md) | 保留授权讨论历史；当前授权边界未改变。 |
| [修改前 ADR-0003](../../../2026-09-08-before-manager-skill/docs/adr/0003-plan-change-authorization-and-activation.md) | 保留旧 YOLO 人工等待规则及当时的未决项。 |
| [修改前 ADR-0004](../../../2026-09-08-before-manager-skill/docs/adr/0004-acceptance-rule-clarification.md) | 保留缺失业务规则一律由人确认的旧设计。 |
| [修改前 ADR-0005](../../../2026-09-08-before-manager-skill/docs/adr/0005-optional-project-verification-group.md) | 保留逐条确认记录和当时待讨论方向。 |
| [修改前验证节点设计](../../../2026-09-08-before-manager-skill/docs/verification-node-design.md) | 保留旧模式文字及讨论记录；证据和检查门槛继续在现行文档维护。 |
| [修改前术语表](../../../2026-09-08-before-manager-skill/CONTEXT.md) | 保留旧角色和模式定义。 |
| [Cloud Agent PRD](../../../reference/Cloud-Agent平台产品PRD.md) | 历史能力参考，不是 RepoMesh 当前 PRD 或实施范围。 |

归档保留原文内容，添加历史标记并调整必要的相对链接；文档中的旧 Windows 绝对路径和复制用 prompt 按原文保留，不作为当前操作指令。

## 更早资料

- [早期交接](../../../HANDOFF-2026-09-07.md)。
- [旧版设计目录](../../../../old_ver/README.md)：本来已作为历史版本管理，保持原目录。
- AgentTeams 静态调研及 Cursor 界面报告保留在参考资料位置，其用途与当前设计分别标明，未改写为运行验收报告。
