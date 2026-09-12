# RepoMesh 当前交接

更新：2026-09-12。施工进度见[分批 TODO plan](IMPLEMENTATION-PLAN.md)。开始开发时先读[开发前阅读与行动指南](DEVELOPMENT-START.md)，再按[现行索引](README.md)进入唯一专题。旧阶段进度、通信和接手 Prompt 已移入[本次归档](../archive/2026-09-12-development-preparation/README.md)，不再作为当前任务指令。

## 当前完成度

产品仍是 Go 三入口与 React／TypeScript／Vite 骨架。Web 提供静态资源与存活探针；`/readyz` 为 503；协调和主机执行入口尚未实现。已实现 PostgreSQL 连接、显式事务迁移及版本核查，当前只建迁移记录表。没有业务数据库表、真实登录、模型配置、会话或 AgentTeams 运行接入。实际启动见[工程说明](development-scaffold.md)和[数据库说明](database-development.md)。最新验收见[B01 记录](../development/2026-09-12-batch-01/README.md)，旧[骨架验收](scaffold-verification.md)保留为历史基线。

会话与 Issue 分离、页面原子建项、首批项目／列表契约、最小消息与澄清契约均已有列明的采用范围。三进程权限、复用上游仓内 DAG、业务与待办同事务、资源原子预留的方向已采用；Skill 工程暂缓。以[ADR 索引](../adr/README.md)的局部替代关系和各专题具体章节为准。

首批管理范围已经确定；认证、模型保存／测试／应用、配置来源、恢复及详情新增决定见[完整候选包](first-batch-complete-review.md)，仍未整体采用。已采用的 F01—F04 具体 UI、创建弹窗、关联控件、提交反馈、DAG 和 dock 布局保留；原型可点击不代表新协议已采用或实现。

## 最近审查与修订

[09-12 审查修订](design-readiness-revisions.md)补充了 Key 原操作安全终结、Issue 固定配置关联和认证返回候选，修复模型测试观察不一致，并澄清 Skill 验证证据范围。[修订检查](../reviews/2026-09-12-design-fixes/README.md)是文档与内存原型证据，不是数据库或真实模型验收。

可开发已确定的独立管理单元；接收供以后执行的真实 Issue／待办前，须先确定并落实[配置绑定](issue-configuration-binding-design.md)。[五项执行协议门槛](execution-integration-gates.md)仍未全部完成，不能把管理闭环当成 Manager／Worker 工作闭环。

[项目契约检查](../reviews/2026-09-12-project-contracts/README.md)已澄清无变更配置保存、同步旧认证注销步骤及当前设计入口。还须补齐项目预算／时限的只读摘要，以及模型应用预览中原模型的受限形状与历史定位；它们分别影响配置摘要和完整替换预览，不阻止已确定的独立项目管理单元开发。新增候选和 P9 的采用状态保持。

## 当前暂停点

用户要求先暂停施工，再配置 Codex 与 WSL。B00 与 B01 已完成验证，B02 认证尚未开始。数据库测试实例全部停止，本地发布包为 dist/repomesh-0.1.0-b01-20260912。代码和文档已保存到工作区，未提交、未推送；原有未提交修改保留。

恢复前先读[暂停记录](../development/2026-09-12-batch-01/PAUSE.md)及[WSL 建议](wsl-development-recommendation.md)。先确认实际开发目录与工具执行位置，再推进下一批，不从旧 HEAD 克隆替代当前工作区。

## 接续顺序

1. 明确首批候选的采用／调整范围，保持已采用契约的语义和原操作恢复。
2. B00 基线及 B01 数据库基础已通过运行检查。按[施工表](IMPLEMENTATION-PLAN.md)接续 B02 认证，再实现项目、模型配置、Issue 原子创建及查询／恢复。每组独立验证。
3. 再完成 G1—G2 的真实 Manager 往返、G3—G4 的单仓执行，最后完成 G5 的两轮与跨仓恢复。

前端／接口的 F01—F15 去向见[页面交接](HANDOFF-PAGE-API-DESIGN.md)；后端 B01—B08 去向见[后端交接](HANDOFF-BACKEND-DESIGN.md)。归档与契约审查之后已开始分批开发，首先交付数据库基础。新认证、模型及 P9 候选的采用状态保持。

历史依据：[设计采用记录](design-delegation.md)、[整理前交接全文](../archive/2026-09-12-development-preparation/docs/current/HANDOFF.md)、[原始审查](../reviews/2026-09-12-design-readiness/README.md)。历史角色、任务 ID 和技术轮次用于溯源，不自动召回旧协作者。
