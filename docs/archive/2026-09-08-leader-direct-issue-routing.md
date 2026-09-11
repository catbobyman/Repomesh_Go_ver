# 已归档：单仓直达 Leader 与 issue 主责转移

归档：2026-09-08。此页保留被替换的设计文字，不作为现行规则。当前见 [ADR-0001](../adr/0001-agentteams-issue-concurrency-and-isolation.md)、[ADR-0006](../adr/0006-manager-entry-modes-and-skill-driven-execution.md)及[交接文档](../current/HANDOFF.md)。

## 被替换的规则

以下摘自修改前 ADR-0001：

> | D04 | Issue 统一登记，再按范围分配内部主责 | 主界面统一与 Manager 对话；跨仓或范围不明由 Manager 主责，明确单仓可由 Leader 主责；普通 Worker 不判断整体范围。 |

> | D17 | Issue 采用受控房间与独立角色会话 | 跨仓使用主房间及每仓子房间；内部单仓工作由仓库 issue 房间承载，对人仍是 Manager。单仓 Manager 交互与原生房间/session 映射待验证。Worker 默认复用仓库 issue 房间。 |

> - 单仓 issue 可由 Leader 主责，Manager 保留项目级可见性，不重复审批每个普通任务。

修改前 ADR-0006 还保留：

> - 内部明确单仓工作仍可由 Leader 主责，Manager 负责对人沟通，不重复派发同一工作。主界面统一入口不把所有 issue 合并为一份上下文。

修改前的事项负责人定义：

**事项负责人（Issue Owner）**：
某条 issue 当前唯一的主协调责任人，可以是 Manager 或具备单仓处理条件的 Leader。参与该 issue 的其他 Leader 仍对各自仓库工作负责。
_Avoid_: 多个角色同时声称拥有同一 issue 的最终协调权。

原单仓流转图：

```text
Single-repo internal fast path:
  Intake -> LA/I102 -> A2 -> candidate -> review / verification
         -> LA/I102 -> M/I102 -> Human
  M provides the user conversation; LA owns repo planning and dispatch.
```

## 替代决定与原因

用户指出所有 issue 都应先进入 Manager 的新房间，并在完整方案后回复“是的，采用”。当前规则为：

- 所有新 issue 先登记并持久化，实例就绪后建立独立主房间，首先由项目现有 Manager 接收。
- Manager 从接收到结果汇总始终承担 issue 总责，Leader 负责被委派的仓库工作。
- 新 issue 分开主房间与上下文；同一 issue 的追加消息、重试和重复事件沿用原房间。
- 首条 issue 延迟准备实例、建房失败保留 issue 并幂等重试的边界继续有效。

该取舍增加简单单仓需求的一轮 Manager 接收处理，使入口、房间和总负责关系保持一致。当前文档已移除上述旧例外；具体建房、消息触发及资源映射仍待验证。
