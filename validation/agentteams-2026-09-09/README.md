# AgentTeams 最新版本接入验证

开始日期：2026-09-09。状态：原生实验记录已收拢；完整 RepoMesh 业务验收与旧共享卷清理尚未完成。

目标：按 [AT-01—12 清单](../../docs/current/agentteams-validation-plan.md) 实际验证，清理确认属于旧验证的运行资源，记录实验过程和结果。组件测试、原生部署和 RepoMesh 适配联调分别记账，不以模拟测试代替真实运行证据。

GitHub `main` 已通过 `gh api` 查询，当前提交为 `eeaab64391ccaec9118e84977f538aefd40720d6`，提交时间为 2026-09-05。证据见 [upstream-main.json](evidence/upstream-main.json)。已通过 `gh repo clone -- --depth 1` 建立新的 `upstream/` 副本。

- `scripts/`：可重复执行的实验。
- `evidence/`：原始请求、输出和结构化结果，屏蔽秘密。
- `reports/`：实验报告、失败分析和覆盖缺口。
- `runtime/`、`private/`：不纳入 Git 的运行数据和凭据。

旧 `D:/Project4work/AgentTeams` 工作树存在未提交的研究和原型资料，保留。[清理记录](reports/environment-cleanup.md)列出已移除的13个旧容器、封存工作目录，以及仍由其他项目挂载的共享卷。

[Docker 启动故障](reports/docker-startup-repair.md)已修复，实际隔离容器 smoke 通过。原生运行环境已建立，未完成的共享清理与业务验收依赖分别保留。

当前逐项结果与覆盖缺口见 [AT-01—12执行状态](reports/validation-status.md)；所有实验的“复现成功”与业务“验收通过”分开记录。

需要核对是否漏掉原要求时，读[按原清单复核完成度](reports/completion-audit.md)。它细分 DAG、配置生效、身份重建、未知结果恢复及尚无实现的业务条件，保留未完成项。

快速接手先读[验证发现与接手边界](reports/findings-and-handoff.md)。实际双实例、模型工具、权限、并发写、消息恢复和资源报告均由该页进入；不能把已复现的原生缺口标成 RepoMesh 产品通过。
