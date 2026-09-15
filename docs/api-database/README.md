# B00-B11 API 与数据库设计

人读 [HTML 设计手册](./index.html)，按批次查看 API、字段、关系、事务、恢复和设计理由。AI 或代码审阅者读取下面的 Markdown。HTML 与 Markdown 共用内容，不单独维护两套契约。

## 按批次阅读

| 文件 | 内容 |
| --- | --- |
| [共同规则](./foundations.md) | 采用状态、业务身份、持久操作、权限、版本、清理与执行边界 |
| [B00](./b00.md) | 已有实现。工程入口、版本信息、健康探针和可重复验证 |
| [B01](./b01.md) | 已有实现。PostgreSQL 连接、迁移历史和显式迁移命令 |
| [B02](./b02.md) | 已有实现。认证、会话、仓库发现和秘密基础；外部验收仍暂停 |
| [B03](./b03.md) | 已有实现。项目管理、多仓关系、固定配置与原操作回执 |
| [B04](./b04.md) | 已有实现。配置来源与秘密保存，保留当前接口和持久化 |
| [B05](./b05.md) | 模型测试、预览、应用、预算与 unknown 核查 |
| [B06](./b06.md) | Issue 原子创建、固定配置绑定、回执与持久待办 |
| [B07](./b07.md) | Issue 列表和详情、会话只读、房间观察、SSE 与恢复页面 |
| [B08](./b08.md) | 管理闭环验收与配套发布检查，复用前序 API 和表 |
| [B09](./b09.md) | Manager 会话与 G1/G2 |
| [B10](./b10.md) | 受限宿主单仓单轮执行与 G3/G4 |
| [B11](./b11.md) | 两轮执行、跨仓协调与恢复 G5 |

## B05-B11 物理合表与表清单

用户已授权 B05-B11 的物理合表设计。原有 63 张候选或提案表按同一业务事实、写入者与生命周期合到 34 张：B05 9 张、B06 6 张、B07 1 张、B08 0 张、B09 6 张、B10 10 张、B11 2 张，净减 29 张，约 46%。合表只改变物理承载，已采用的逻辑身份、唯一性、作用域、事务、恢复和清理语义不变；B05-B11 的候选、提案、未实施与验收状态也不因合表升级。B10 的 `business_plan_versions` 显式承载原目录漏登的业务计划版本实体，与执行层技术 `plan_revisions` 分离；B10 实施时给 B06 新 `issues` 增补 `current_business_plan_version_id`、`business_plan_pointer_revision`、`next_business_plan_version_index` 三列，不增加 B06 表数。B05 的 `policy_imports` 承接 schema2 导入回执；B10 的 `change_set_versions` 显式承载 candidate 与 combination 两个子型。规则和逐表映射见 [B05-B11 物理合表专题](../current/b05-b11-storage-consolidation.md)。

表数按源码和清单分开计数。手册 B01-B04 基线 36 张，来自 `0001` 至 `0006` 迁移，其中 35 张业务表加 1 张系统表 `public.repomesh_schema_migrations`；`0007_scan_catalog.sql` 有 1 张手册外扫描表 `repomesh_scan.repositories`，`0008_decision_chain.sql` 有 3 张手册外决策链表 `public.decision_chain_nodes`、`public.decision_embeddings`、`public.feature_settings`，两者各自成组，都不计入 B05-B11 的 34 张。加上设计 34 张，手册范围合计 70 张，全仓含扩展合计 74 张。机器可校验清单是 [table-manifest.json](./table-manifest.json)，每张目标物理表只在所属批次正文用独立一行声明：

```text
物理表：`repomesh_issues.issues`
```

跨批次复用不重复声明，B00-B04 与 B08 不写声明。HTML 首页的“设计专题”“文档卡片”“说明表格”只是文档统计，不是 API 数或已实现表数。

## 使用边界

本目录是长期维护的设计阅读入口。既有实现和契约按来源整理，本次新设计逐项标记为提案。已采用语义仍以 [current 索引](../current/README.md) 所指向的专题和采用记录为准。任何新提案都不会因生成 HTML 自动成为产品采用决定。

修改既有契约时先修改拥有该契约的专题，再同步本目录的摘要和字段卡。新提案在采用前由本目录维护，采用后更新专题与采用记录并写明替代关系。每次同步都检查批次状态和源码事实，不能只刷新生成时间。

本次制作依据当前工作树，包含此前未提交的 B05/B06 设计收口。B04 的本地验证属于已有证据，本次没有重跑。B05-B11 的设计和验证清单不能作为产品已实现或已验收的证明。

## 更新与检查

从仓库根目录执行以下命令。文档工具只使用 Python 3 标准库，不修改产品数据库。

```bash
python3 docs/api-database/render.py
python3 docs/api-database/render.py --check
python3 docs/api-database/verify_renderer.py
python3 docs/api-database/verify_design.py
python3 docs/api-database/verify_design_tests.py
```

第一条命令从 foundations.md 和 b00.md 至 b11.md 生成 index.html。第二条命令检查内容同步和本地链接，不写文件。生成失败时先修正文档或工具，再重新生成。不要手工修改 index.html。

第三条命令验证生成器对陈旧文件、缺失章节、坏链接、重复标题及换行格式的处理。它使用临时副本，不修改设计正文。它验证文档工具，不代替 API 与数据库语义复核。

第四条命令是日常检查，校验表清单、迁移事实、合表前正文快照、正文声明和 HTML 统计口径。清单按显式迁移清单分组：`0001` 至 `0006` 是手册基线，`0007` 是扫描表，`0008` 是决策链表；漏登记的迁移或未归组表直接失败，不会默认并入手册基线。它默认不读取历史 baseline，不把产品代码冻结带进每次文档更新；`--strict` 用于交付冻结时把待办视为失败。本轮合表的受保护文件范围审计单独执行：

```bash
python3 docs/api-database/verify_design.py --baseline docs/development/2026-09-15-table-consolidation-01/baseline.json
```

这些检查只做静态文档和源码清点，不执行迁移，也不证明数据库行为已经验证。

最后一条命令在临时副本上给清单器和声明校验注入漏映射、重复声明、错误批次、缺失必需实体和受保护文件改动，断言关键错误会被拦住；它不修改仓库正文。

正文使用标题、段落、列表、管道表格、围栏代码、链接、粗体和行内代码。HTML 用章节目录、白色卡片与字段表呈现。表格中的文字竖线写成 &#124;，避免被当作列分隔符。

生成检查不能证明 API 的业务正确性。发布前仍要对照来源复核状态、字段和恢复约束，并实际打开 HTML 检查布局。目录制作证据见 [制作与复核记录](../development/2026-09-15-api-db-catalog-01/README.md)，本轮合表清单与统计证据见 [合表制作记录](../development/2026-09-15-table-consolidation-01/README.md)，上游 `0008` 三表引起的统计同步见 [主分支同步记录](../development/2026-09-15-table-consolidation-main-sync.md)。
