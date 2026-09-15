# RepoMesh 当前交接

更新：2026-09-14。本次B05/B06五项设计收口基于`43d8c2a`。产品运行结果沿用各报告锁定的源码版本，本次未重跑验收。

开发从[全局阅读指南](AGENT-READING-GUIDE.md)、[计划导航](../plan/README.md)和[现行专题索引](README.md)进入。批次依赖及验收入口统一维护在[施工计划](../plan/IMPLEMENTATION-PLAN.md)。

## 当前完成度

| 范围 | 状态与已交付内容 | 依据与限制 |
| --- | --- | --- |
| B00、B01 | VERIFIED；工程基线、PostgreSQL 连接与显式迁移 | [数据库基础记录](../development/2026-09-12-batch-01/README.md)。 |
| B02 | IN_PROGRESS；本地认证、会话、授权恢复和仓库发现已实现；外部验收 PAUSED_BY_USER | [采用范围](b02-authentication-adoption.md)、[本地记录](../development/2026-09-12-batch-02/README.md)。完整外部验收未通过，历史失败和恢复责任见下节。 |
| B03 | INTEGRATED_LOCAL_VERIFIED；项目创建、列表、资料编辑、明确增仓、固定配置及原操作恢复 | [主目录集成](../development/2026-09-12-b03-integration-01/README.md)、[最终独立复核](../development/2026-09-12-b03-integration-01/FINAL-INDEPENDENT-REVIEW.md)。非整批业务 VERIFIED。 |
| B04 | INTEGRATED_LOCAL_VERIFIED；D01—D04、U04.1—U04.4 授权范围已结束 | [采用记录](b04-model-sources-adoption.md)、[验收报告](../development/2026-09-13-b04-acceptance-01/README.md)。模型供应商保存、安全终结、不可变版本、六个 HTTP 端点及部署来源导入已实现。非整批 VERIFIED。 |
| B05、B06 | B05 已缩减，B06 产品实施 TODO | B05 当前只保留运行政策、C05/C06 只读与专用模型应用；独立模型测试、handler、SendPermit、unknown 关闭和测试观察整体延期，额度窗口移交 B10。B06 只依赖 B05 固定 execution 政策，不依赖模型测试或额度窗口。历史收口仍保留为演进记录；当前范围见 [B05 设计](../api-database/b05.md)。 |
| B07—B11 | 后续实施 TODO | Issue 查询、管理闭环及真实运行接入未完成。B09 的四项数据兼容问题仅有静态部分覆盖，完整 G1、G2 未完成。 |

B04 验收报告的运行基线为 `621592d`，包含收口后保存校验留页与 vault 不变量修复。报告记录 Go 测试 260 通过、0 失败、2 跳过，前端测试 32 通过；具体跳过原因、S01—S12、浏览器夹具与历史失败以报告为准。这些结果不证明真实供应商 Key、真实模型请求或计费可用。

`businessReady=false`，`/healthz` 只表示 Web 存活，`/readyz` 仍为 503。host-executor 尚未实现。Issue、真实消息、AgentTeams 运行、Docker 执行和受控 Python 仓库分析尚未接入。

## B02 外部暂停与恢复责任

用户已解除 B03 等待 B02 整批 VERIFIED 的旧顺序条件，并决定优先开发主要功能。今后真实账号验证只使用主账号 A。跨账号 LIVE-05 和 LIVE-08-USER-READ 为 DEFERRED_BY_USER，不计为 PASS，不自动建立下一轮第二账号实验。

LIVE-09、LIVE-10 的既有通过结果保留。second-account-02 的 LIVE-05 为历史 FAIL、LIVE-08 为 NOT_RUN，外部恢复记录为 RESTORE_IN_PROGRESS，见[暂停交接](../development/2026-09-12-b026-second-account-02/PAUSE.md)。原记录中的 B installation、协作者、OAuth grant 和 App 可见性仍需在获授权的恢复任务中逐项核查；没有新的证据证明已清理。

历史 PID、浏览器 target、账号状态和端口只代表记录时刻。本次没有核查这些服务是否仍在运行，不据旧 PID 操作环境，也不恢复旧观察器或账号流程。

## 后续实施入口

1. 先核对[施工计划](../plan/IMPLEMENTATION-PLAN.md)中的批次和依赖，再按本次用户授权确定范围。
2. 进入 B05 前，按当前缩减范围重新采用运行政策、专用模型应用与 C05/C06，并对齐已实现的 B04 类型与版本语义。旧设计中的单模型测试不再随 B05 自动采用；临时 `agt llm-preflight` 只是受控运维工具，不是产品验收或真实运行放行。
3. 进入 B06 前，按[B06 设计](../development/2026-09-13-b04-b06-design-01/B06.md)与[配置绑定专题](issue-configuration-binding-design.md)收口 P9。接收真实 Issue 与待办前落实配置关联。
4. 运行接入按[执行门槛](execution-integration-gates.md)分阶段推进。Graph 保持后台协调进程内模块，仓内 DAG 复用上游；Skill 工程仍暂缓。

工程命令与配置见[根 README](../../README.md)。当前主开发副本为 `/home/xubohan/projects/Repomesh_Go_ver`；历史 B03 worktree、旧发布包、秘密配置和实验记录保留，不自动重新合并、覆盖或清理。

## 历史与文档整理

2026-09-13，施工计划、设计分工、开发行动指南和 AgentTeams 验证清单迁至 `docs/plan/`。B03、B04 旧任务提示已归档。整理前的累计交接和原始字节见[本次归档](../archive/2026-09-13-plan-organization/README.md)，此前文档演进见[历史总导航](../archive/README.md)。

页面 F01—F15 入口见[页面交接](HANDOFF-PAGE-API-DESIGN.md)，旧后端 B01—B08 专题入口见[后端交接](HANDOFF-BACKEND-DESIGN.md)。这些专题编号与施工计划编号分别解释。历史任务指令、协作名单和运行记录不自动成为新的授权。

## B00-B11 API 与数据库文档入口

新增 [API 与数据库设计目录](../api-database/README.md)，包含 HTML 与同内容 Markdown，覆盖共同规则和 B00 至 B11。B08 复用前序接口与表进行验收设计，B10 的基础执行身份由 B11 复用。章节分别标明实现、采用与候选状态；文档制作不代表 B05-B11 产品实现或业务验收完成。制作结果和复核限制见 [本轮记录](../development/2026-09-15-api-db-catalog-01/README.md)。

## B05-B11 物理合表入口

[B05-B11 物理合表与表清单](b05-b11-storage-consolidation.md) 记录 2026-09-15 的当前设计：63 条历史候选中 9 条模型测试专用提案延期，54 条活动映射加 3 张必需新表形成 30 张当前目标表；B05 4 张、B10 11 张。B01-B04 的 36 张手册基线表、0007 扫描表 1 张与 0008 决策链 3 张保持不动；手册范围 66 张，全仓含扩展 70 张。机器清单与静态校验见 [table-manifest.json](../api-database/table-manifest.json)；历史制作记录不代表当前延期项已实现或数据库行为已验证。
