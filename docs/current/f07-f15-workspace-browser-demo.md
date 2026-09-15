# F07—F15 工作区：页面元素 → API → 假数据前端演示

更新：2026-09-15。这是会话、Issue 与交付范围的**浏览器演示基线**，不是 B07—B11 产品实现，也不改写 [API 设计](api-design.md) 的 `/api/v1` 44 表方案。

入口：`npm --prefix web run dev` 后打开 [http://127.0.0.1:5173/demo/workspace](http://127.0.0.1:5173/demo/workspace)。页面只通过 `fetch('/api/...')` 读写；Vite 中间件用内存假数据实现同一形状。制作记录见 [本轮记录](../development/2026-09-15-f07-f15-workspace-demo-01/README.md)。

## 工作流程

1. **拆页面元素**  
   从 F07—F15 原型列出可见区块、动作和必须回读的事实（标题、仓库、会话关联、消息、房间观察、只读图、交付摘要）。不把原型里的模拟成功当成已实现协议。
2. **对已采用契约**  
   浏览器字段仍以 [首批契约](first-batch-browser-api-contract.md)、[Issue 创建契约](issue-page-create-api-contract.md)、[消息／澄清契约](conversation-message-clarification-api-contract.md)、[仓库分析补充](issue-creation-repository-analysis.md) 为准。能复用的端点不另起一套 JSON。
3. **只补页面缺口**  
   工作区页头、只读 DAG、验证与交付页签在已采用契约里没有完整浏览器形状。本演示用只读扩展端点填上，并标明“演示扩展 / 非产品冻结”。
4. **前端只打 API**  
   React 工作区不读内存 store。列表、详情、创建、发消息、分析、图和交付都走 `web/src/workspace/client.ts`。假服务在 `web/src/workspace/mock/server.ts`。
5. **可验证**  
   解析器与 mock 有 `web/src/workspace.test.mjs`；浏览器走 `/demo/workspace` 的场景条，确认 Network 里出现对应 `/api` 请求。

F11 更正已发生工作、F12 真实进房、F13 动态换图、F14 真实验证流水、F15 真实 Python 扫描均未做。SSE 未接，刷新靠显式 GET。

## 页面元素与 API

| 范围 | 页面元素 | 使用的接口 | 来源 |
| --- | --- | --- | --- |
| F07 列表 | Issue 标题、编号、仓库数、主 ChangeSet、记录已建立 | `GET /api/projects/{projectId}/issues` | 首批契约 §8 |
| F07 会话栏 | 会话标题列表 | `GET /api/projects/{projectId}/conversations` | 首批契约 §8 |
| F07 工作区页头 | 会话标题、关联 Issue | `GET /api/projects/{projectId}/conversations/{conversationId}` | **演示扩展**（列表契约没有正文与关联） |
| F08 创建弹窗 | 标题、目标、仓库勾选、新建／已有会话、提交 | `GET .../issue-creation-options`、`GET .../issue-creation-conversations`、`POST .../issues`、`GET .../issue-creations/{id}` | 创建契约 |
| F09 最小概览 | 记录已保存、运行观察、目标、仓库、关联会话、主 CS | `GET /api/issues/{issueId}`、`GET /api/issues/{issueId}/rooms` | 创建契约 §7；运行观察不写入创建状态 |
| F10 消息 | 气泡、Issue 卡片、发送框 | `GET/POST .../messages`、`GET .../message-submissions/{id}` | 消息契约 |
| F10 澄清 | 候选 Issue、引用当前问题版本再答复 | `GET .../clarifications/{id}`；POST messages 带 `replyTo` | 消息契约 |
| F11 多 Issue | 一条会话关联多条 Issue（只读） | 会话快照 `linkedIssues` | 演示扩展；更正协议不做 |
| F12 悬浮入口 | Issue 详情、DAG、Leader 只读且不可进 | rooms.leaders 的 `canEnter=false` | 创建契约 §7 房间观察；无房间正文 API |
| F13 只读 DAG | 节点、依赖、节点说明 | `GET /api/issues/{issueId}/plan-graph` | **演示扩展**；只读，无编辑图 |
| F14 验证／交付 | 组合、独立验证、交付、逐仓证据 | `GET /api/issues/{issueId}/delivery` | **演示扩展**；无 deliver 写接口 |
| F15 仓库分析 | 按钮、建议、应用后附带来源 | options.`repositoryAnalysis`；`POST/GET .../repository-analyses`；创建可选 `repositoryAnalysisId` | 分析专题 §4 |

演示专用控制：`POST /api/demo/workspace/reset` 只重置内存种子，不是业务资源。

写操作要求 `X-CSRF-Token: demo-csrf` 与 `Idempotency-Key` UUID，错误形状沿创建契约 `{error:{code,message,fieldErrors,requestId}}`。

## 与 `/api/v1` 方案的关系

[API 设计](api-design.md) 把顶层工作事项写成 `tasks`，消息挂 `/api/v1/messages`，且附录记录**没有会话实体**。F07—F15 原型和已采用浏览器契约以 Project / Conversation / Issue 为用户对象。本演示跟页面契约，不把工作区改接到未实现的 `/api/v1`。对应关系仅作阅读：Issue ≈ 顶层 task，主 ChangeSet ≈ `change_sets`，DAG ≈ `plans.taskDag` 的只读投影，交付摘要 ≈ change set / validation 的只读拼装。产品落库仍以方案与后续采用为准。

## 前端路由

| 路径 | 画面 |
| --- | --- |
| `/demo/workspace` | 默认会话 `conv_1` |
| `/demo/workspace/conversations/{id}` | 会话工作区 |
| `/demo/workspace/issues` | Issue 列表 |
| `/demo/workspace/issues/{id}` | 最小概览 |
| `/demo/workspace/issues/{id}/plan` | 只读 DAG |
| `/demo/workspace/issues/{id}/delivery` | 验证与交付 |

该前缀绕过 GitHub 登录，避免假数据演示依赖 B02。
