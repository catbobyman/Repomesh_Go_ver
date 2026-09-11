> 历史归档（2026-09-08）：仅供追溯，原文中的状态和待决定项不作为现行规则。当前设计见[文档入口](../../../current/README.md)。原位置：docs/NEXT-SESSION-PROMPT-2026-09-07.md。

# RepoMesh 下一会话 Prompt（2026-09-07）

对应 [v3 handoff](HANDOFF-2026-09-07-v3.md)。复制以下内容到新会话；此文件不创建新任务。

```text
请接手 RepoMesh 产品与架构设计，先完整阅读：

1. D:\Project4work\Repomesh_Go_ver\docs\HANDOFF-2026-09-07-v3.md
2. D:\Project4work\Repomesh_Go_ver\CONTEXT.md
3. D:\Project4work\Repomesh_Go_ver\docs\adr\0001-agentteams-issue-concurrency-and-isolation.md
4. D:\Project4work\Repomesh_Go_ver\docs\adr\0002-github-app-authorization-and-draft-pr-delivery.md
5. D:\Project4work\Repomesh_Go_ver\docs\adr\0003-plan-change-authorization-and-activation.md
6. D:\Project4work\Repomesh_Go_ver\docs\agentteams-survey-2026-09-07\agentteams-survey.md
7. D:\Project4work\Repomesh_Go_ver\docs\agentteams-survey-2026-09-07\agentteams-api-cli-survey-2026-09-07.md

以 v3 handoff、当前 ADR 和用户最新确认为准。需要界面参考时读 Cursor_Dashboard_Report_2026-09-07\report.md；旧 handoff、docs\old_ver 和 Cloud Agent PRD 仅作历史参考。

已确认并且不要重复追问：
- 使用 agentscope-ai/AgentTeams；每个多仓项目独立实例、一个 Manager，每仓长期 Team。首条 issue 正式提交并持久化后才准备实例，后续复用。
- 跨仓 issue 使用主房间和每仓子房间，明确单仓可直达 Leader；各 Agent 有自己的 session。Worker 单任务，每次 Attempt 独立副本，全局容量与项目额度共同约束。
- GitHub App 固定工作权限集，运行时收窄且不放大发起人的有效 Git 权限；Agent 推自己的分支、开 draft PR，合并由人和仓库规则决定。
- ADR-0003 已确认计划变更的六条规则：明确版本；YOLO/需要审批两档共用执行约束；批准范围和上限内的 Loop 自动运行；获准与生效分开；冲突和失败保留历史；RepoMesh 实际控制变更应用和任务启动。扩大权限、提高预算上限、放宽已确认验收条件都由人决定。
- 首期只支持自然语言调整编排，形成版本化提案；直接编辑节点、属性、连线及拖拽编排已列为后续待办。
- 验证绑定固定 commit 组合；候选变化重新判断证据有效性；专项验证环境不向业务仓库推送修复。

接口依据是锁定提交的静态调研，未部署验收。Controller replan 在有 in-progress/submitted 任务时拒绝，pause 不停止在途任务；原生 DAG/Loop、Manager 权限和 Dashboard HITL 都不能被描述成已经满足 RepoMesh 的完整编排及审批要求。调研中先准备实例再接收 issue 的旧图按 ADR-0001 D18 纠正理解。

先简述理解，再继续测试、验证与交付设计。建议从 frontend F1 + backend B1 的“支付状态筛选”场景开始，只聚焦一个问题：一个跨仓验证节点应接收哪些输入、产出哪些证据，由谁判断结果？页面结果为空时，怎样区分业务缺陷、测试数据/环境阻塞与需求不清？这些分类和具体门槛是待讨论建议，不是已确认决定。

随后再逐项讨论验证人员职责、联调环境、Graph/Loop 具体行为、人工审查与 PR 时机、人工合并及部分失败、回退与恢复。跨仓验证小组是否常设、首次计划审批及审批人、档位默认值和切换、实时图的具体交互与刷新方式也尚未定稿。

中文讨论，从具体操作场景说明页面、系统行为、状态、职责和异常，每次一个关键问题。新决定经我确认后写入 Markdown；独立主题按需新建 ADR，术语表只放定义，图用字符图。不要把此前建议或上游静态证据自动升级成已确认或已实现能力。

当前仅做设计和本地文档整理，暂不安装、部署、编码、创建真实 GitHub App、写入远端仓库，也不要自动新建 Codex 任务。
```
