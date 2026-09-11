# 旧版 PRD 与原型归档说明

2026-09-08：从 `docs/old_ver` 整体迁入。本批 30 个文件原样保留，包括早期 PRD、可交互原型、历史页面及整理证据。文件中的“当前”“已完成”等措辞属于旧版语境，不代表现行 RepoMesh 设计或实现。

- [原目录索引](README.md)
- [旧原型说明](产品原型/README.md)
- [迁移清单及原文件 SHA-256](../2026-09-08-design-consolidation/legacy-move-manifest.json)
- [现行设计入口](../../current/README.md)

原型仅作历史参考，本次没有运行、修改或继续开发它。原 `docs/old_ver/README.md` 仅保留指向本说明的入口。

## 原有材料限制

历史原型的“观测中心.html”引用的 4 个本地脚本未包含在原目录中：_shared/js/echarts.min.js、_shared/js/mermaid.min.js、assets/charts.js、_shared/js/lightbox.js。迁移清单和内容摘要核对确认迁移未丢失文件；这些原有缺失仅作记录，本次不补装依赖或修复旧原型。当前层级的原型入口与样式／脚本引用保持原样。
