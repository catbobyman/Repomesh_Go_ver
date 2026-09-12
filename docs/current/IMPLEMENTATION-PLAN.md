# 分批施工 TODO plan

更新于 2026-09-12。 当前按用户要求暂停施工，先准备 Codex 与 WSL 设置。B00、B01 已验证，B02 尚未开始。用户已授权按批次开始开发，并要求每组验证。本表是施工进度来源，设计语义仍以链接的专题为准。状态为 TODO、IN_PROGRESS、VERIFIED 或 BLOCKED。只有验收证据齐全的组可以标为 VERIFIED。

## 执行步骤

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame
- [x] Phase B: Design the workflow
- [x] Phase C: Run the loop
- [x] Phase D: Keep the audit trail
- [x] Phase E: Verify and hand back

采用 figure-it-out 组织本次分阶段施工。每组先记录预期行为，再实现、运行验证、独立复核，最后更新本表。已完成组的证据保留，下一组重新确认依赖。当前轮次交付目标为 B00 与 B01，先建成可重复验证的数据库基础，再接首个业务闭环。

## 批次表

| 批次 | 状态 | 交付范围 | 前置条件 | 必须通过的验收 |
| --- | --- | --- | --- | --- |
| B00 | VERIFIED | 源码和工具基线、批次表、验证入口与工作区隔离 | 保留现有未提交修改 | 六项工程命令；现有 Web 探针；现有三入口行为；记录版本和结果 |
| B01 | VERIFIED | PostgreSQL 连接、显式迁移与版本核查、独立临时数据库验证 | B00；完成实现方案比较 | 真实数据库连接；重复和并发迁移；故障回滚；迁移历史不匹配拒绝；超时；二进制启动与退出；readyz 仍为 503 |
| B02 | TODO | GitHub 登录、会话、固定返回目的地、Origin 与 CSRF、仓库发现 | B01；收口认证候选的实施范围；真实 GitHub 配置 | 登录及重连；旧回调和旧注销晚到；跨账号隔离；凭据刷新并发；授权未知不误判；登录 UI 实测 |
| B03 | TODO | 待配置项目的创建、列表、资料编辑、明确增仓与原操作恢复 | B02；已采用项目和持久化契约 | 同键同输入 20 并发一次提交；异输入冲突；丢回执和重启可查；旧回执稳定；增仓失败整体回滚；限制仓库不影响资料修复 |
| B04 | TODO | 模型与执行配置来源、不可变版本、秘密保存和安全终结 | B03；收口配置来源和秘密存储候选 | 保存与终结互斥；迟到保存不能复活；秘密不出现在日志和页面缓存；默认更新不暗换固定版本 |
| B05 | TODO | 模型单次测试、专用应用、预算与时限只读摘要 | B04；补齐 C05 和 C06 字段契约 | 测试未知不重发；快照隔离；只换模型保留 execution；无变化保存不造修订；受限原模型预览不泄露 |
| B06 | TODO | 手动 Issue 原子创建、必要会话、主 ChangeSet、来源、范围与持久待办 | B05；采用并落实 P9 固定配置绑定 | DB01 至 DB08 和 CB01 至 CB05；任一写入失败全回滚；创建与换配置并发绑定完整版本；不伪造运行接入 |
| B07 | TODO | Issue 列表、最小详情、已有会话只读、rooms 分读、SSE 与恢复页面 | B06；收口详情和恢复候选 | 当前完整内容范围核权；分页隔离；401 和失权清缓存；旧响应隔离；SSE 失效通知与快照重读 |
| B08 | TODO | 首批管理闭环整体验收与配套发布验证 | B02 至 B07 | 登录、项目、配置、建项、查看、编辑全流程；故障和恢复矩阵；完整工程检查及打包；记录未接入运行状态 |
| B09 | TODO | G1 与 G2，真实 Manager 会话往返 | B08；完成对应执行协议 | 固定配置实际消费；可信消息与工具关联；外部投递、回复及重启恢复独立取证 |
| B10 | TODO | G3 与 G4，受限宿主下单仓单轮执行 | B09；全部写入路径与生命周期确定 | 派工、提交、停止、写权限撤销、回收；REST、MCP、shared 旁路验证 |
| B11 | TODO | G5，两轮执行与跨仓恢复 | B10；合法换图和部分应用协议确定 | 两轮换图；双仓失败；部分应用恢复；证据、验证和交付一致 |

C05 为项目预算与时限实际参数的只读契约缺口。C06 为原模型受限形状及历史定位缺口。详见[契约审查](../reviews/2026-09-12-project-contracts/README.md)。它们进入 B05 的前置项，不阻塞 B01。历史文档的后端 B01 至 B08 编号与本表的施工批次编号不同。

## 当前吞吐与文件归属

- Blocking first steps. 先跑 B00。B01 的接口形状由两个只读候选比较后确定，数据库实际可运行是验收前置。
- Independent workstreams. 主代理维护计划、运行隔离数据库、负责集成；实现代理在独立 Git worktree 中写数据库代码与其测试；复核代理只读。
- Shared mutable state. 当前工作区已有文档改动。保留原样，不整体暂存或提交。实现分支只交回列明的文件，主代理在实现代理结束后集成。
- Smallest safe decomposition. B01 只解决连接、迁移与核查，不提前建未定的模型、OAuth、Issue 或运行表。后续业务表跟随所属用例增加。

## B00 与 B01 TODO

| 项目 | 状态 | 验收证据 |
| --- | --- | --- |
| 保存工作区基线和工具版本 | VERIFIED | [工作区基线](../development/2026-09-12-batch-01/baseline.json)和[工程检查](../development/2026-09-12-batch-01/b00-checks.json) |
| 六项基础检查与当前运行探针 | VERIFIED | [工程检查](../development/2026-09-12-batch-01/b00-checks.json)和[运行探针](../development/2026-09-12-batch-01/b00-runtime.json) |
| 数据库实现方案比较及接口草图 | VERIFIED | [实现方案](../development/2026-09-12-batch-01/design.md) |
| PostgreSQL 连接与迁移实现 | VERIFIED | [实现与范围](../development/2026-09-12-batch-01/README.md) |
| 真实数据库重复、并发、回滚及历史不匹配验证 | VERIFIED | [12 组 PostgreSQL 实测](../development/2026-09-12-batch-01/b01-verification/checks.json) |
| Web 二进制命令和兼容启动验证 | VERIFIED | [命令、重启和 HTTP 验证](../development/2026-09-12-batch-01/b01-verification/checks.json) |
| 独立代码与记录复核 | VERIFIED | [代码和脚本复核、证据补全](../development/2026-09-12-batch-01/review.md) |
| 更新 README、HANDOFF 和本表 | VERIFIED | [结构检查](../development/2026-09-12-batch-01/structural-checks.json)和[打包结果](../development/2026-09-12-batch-01/release-verification.json) |

## 每组验证规则

代码检查覆盖实际改动。影响入口、前后端或发布链路时执行完整六项工程检查。数据库能力必须在独立 PostgreSQL 中实测，跳过集成测试不等于该组通过。UI 组须实际操作页面，外部集成组区分测试替身与真实服务证据。每组保存命令、版本、退出码和结果，失败修复后重跑受影响检查。未实现能力保持真实未接入状态。

本次实施记录使用[decision log](../development/2026-09-12-batch-01/decisions.tsv)。后续组各自建立记录目录，再在本表挂接证据。
