# Controller Project / workflow 新旧差异与回归范围

比较基线：`eeaab64391ccaec9118e84977f538aefd40720d6` → `517caff9280242a00a4d4c06365352b9e41659c6`。日期：2026-09-10。先只读检查 Git 差异、完整函数及测试源码，随后按追加授权运行三个受影响包的官方测试；**未构建镜像、未启动或修改服务，未修改 upstream**。静态结论、官方组件测试通过和仍待执行的真实服务回归在下文分别标明。

结论：新版主要增加 Project 的展示和检查入口，**没有修改此前实测的 DAG 推进、Team 消歧、暂停／重规划／取消写路径或认证缓存机制**。09-09 的旧版证据应保留版本标签；不能因新增 history 字段、trace 提示或 Mermaid 输出，就把旧版发现的执行取消、恢复、身份、资源限制缺口标成修复。新增端点本身必须补测权限和同名对象归属。

后续追加授权的真实 rv-c HTTP、SA scoped 身份和 CLI 实测已单列在 [controller-api-live.md](controller-api-live.md)，包括已确认的 `end` Mermaid 解析缺陷与 CLI detail 不转发 --team。下文静态清单保留为差异分析依据，实际已覆盖范围以该实测报告为准。

## 实际变更

Controller 共 12 个文件有变更；另有中英文 `project-workflow-api.md` 更新。完整仓库差异没有 TeamHarness、Worker runtime、Dockerfile 或依赖锁文件变更。

| 变化 | 新契约及兼容影响 | 精确源码 |
|---|---|---|
| `GET /projects/{id}/workflow?format=mermaid` | 返回 `text/plain; charset=utf-8` 的 Mermaid；`includeTasks=true` 在此分支被忽略。缺省或空 format 仍 JSON。**非空 `format=json`、`bogus` 等从旧版忽略参数变为 400**，客户端不能用 `format=json` 显式选 JSON。资源解析与访问检查在 format 校验之前，因此不存在／歧义项目可先返回 404／409。 | [GetProjectWorkflow:633](../upstream/agentteams-controller/internal/server/project_handler.go#L633)，Mermaid 分支 674，非法格式分支 692 |
| 新 `GET /projects/{id}/tasks/{taskId}` | 路由采用 `RequireAuthz(ActionGet, "project", projectNameFn)`；handler 再解析 Project 范围、检查 task 是否在当前 DAG 或 loop 图中。非法 task ID→400；不在图中→404。新增的是读取接口，没有接受／取消／执行动作。 | [http.go:118](../upstream/agentteams-controller/internal/server/http.go#L118)、[GetTaskInspection:1014](../upstream/agentteams-controller/internal/server/project_handler.go#L1014) |
| 单 Task 状态来自两种记录 | TaskMeta 缺失、格式错误或不匹配 task_id/project_id 时，200 返回图节点摘要及**规范化状态**；合法 TaskMeta 存在时，以其**原始 status**覆盖，并补充 spec、summary、result、deliverables、cancel_reason、history。依赖始终来自图节点。缺少 TaskMeta 不等于不存在任务，也不证明有实际产物。 | [project_handler.go:1076](../upstream/agentteams-controller/internal/server/project_handler.go#L1076)、所有权比较 1092、原始 status 覆盖 1095、响应 1118 |
| 范围限定与 trace | TaskMeta 经原有 `taskMetaKeys(taskID, team)` 只读所属 Team 或 standalone 全局路径，Team 项目不回退到 global。`trace` 只含 project_id/task_id，**不含 instance、team、trace ID、后端 URL，也没有查证 span 存在**；跨实例同名过滤仍需外层上下文。 | [taskMetaKeys:1346](../upstream/agentteams-controller/internal/server/project_handler.go#L1346)、[taskTraceHint:238](../upstream/agentteams-controller/internal/server/project_handler.go#L238)、响应 1118 |
| `tasks_detail.history` 与检查接口 history | 从已有 TaskMeta 读取 ts/from/to/actor/action/note；跳过非对象，以及 ts 和 action 同时为空的条目。没有在读取侧强制 50 条上限、时间格式、顺序、状态迁移合法性或 append-only 不变量。 | [taskDetail:203](../upstream/agentteams-controller/internal/server/project_handler.go#L203)、[readTasksDetail:948](../upstream/agentteams-controller/internal/server/project_handler.go#L948)、[parseTaskHistory:982](../upstream/agentteams-controller/internal/server/project_handler.go#L982) |
| API 与 `agt --mermaid` 共用渲染器 | CLI 仍取 workflow JSON，再转 typed Snapshot，本地渲染；没有改为请求 format=mermaid。ready 覆盖状态样式，增加六种状态颜色；ID 非字母数字下划线连字符映射为 `_`，碰撞加后缀；标签换行变 `<br>`、双引号变 `#quot;`、反斜杠丢弃、控制字符变空格。旧 CLI 文本输出和直接使用 task ID 作为 Mermaid node ID 的假设均不再可靠。 | [get.go:125](../upstream/agentteams-controller/cmd/agt/get.go#L125)、[mermaid.go:62](../upstream/agentteams-controller/internal/workflow/mermaid.go#L62)、标签 100、RenderMermaid 125 |

新 Snapshot 虽有 Assignee 和 Conditional 字段，渲染器没有把负责人加入标签，也没有为 conditional edge 选择独立线型；所有 edge 都输出 `-->`。它是展示 helper，不是新的调度或权限判断层。

## 对 09-09 证据的影响

通过 `git show` 提取同名完整 Go 函数逐字比较，以下函数新旧相同：`teamProjectPrefixes`、`resolveProjectMeta`、`resolveSingleProjectMatch`、`buildWorkflow`、`taskMetaKeys`、`writeProjectMeta`、`PauseProject`、`ResumeProject`、`ReplanProject`、`CancelTask`。`plugins/teamharness/mcp/server.py`、`internal/auth/authenticator.go`、`internal/server/lifecycle_handler.go` 全文件也逐字相同。

| 09-09 证据 | 本次判断 |
|---|---|
| [原生 DAG](../../agentteams-2026-09-09/reports/dag-native-live.md)：assigned 仍候选、submitted 不解锁、Project completed 与 Task submitted 并存 | 没有状态计算或 Task 写入修复。新版单 Task 检查可能显示 raw submitted，而 workflow 节点显示 completed；应补一个接口并列读回，不能把 UI 两种状态误解为新回归或已统一。 |
| [Team 消歧](../../agentteams-2026-09-09/reports/project-team-disambiguation-live.md)：无 Team 409、显式 Team 正确、a/b 隔离 | 原有解析函数未变；旧实测仍限定旧端点和旧镜像。必须将相同 `(instance, team, project_id)` 对照扩展到**新增 task 检查和 Mermaid 分支**，尤其错误 Team、同名 task 和 global 诱饵。 |
| [Controller 实测](../../agentteams-2026-09-09/reports/controller-live-report.md)：pause/replan 状态条件、旧覆盖写、multipart ETag 409 | 对应写路径未变，不能宣布修复。读新字段不能改变存储 CAS、跨对象原子性或 multipart 兼容。升级后做有界冒烟即可，不必为纯展示增量重演全部故障注入。 |
| [MCP 进程中断恢复](../../agentteams-2026-09-09/reports/mcp-response-loss-live.md)、[Controller/MCP race](../../agentteams-2026-09-09/reports/controller-mcp-race-live.md) | MCP 源码未变；相同 token/room/task transaction 的限定恢复，以及更晚上传失败留下 Project planned 的缺口均未被该增量改变。 |
| [模型任务取消](../../agentteams-2026-09-09/reports/model-task-cancel-live.md)、[文件副作用](../../agentteams-2026-09-09/reports/worker-side-effects-live.md) | 没有新增进程中止、执行租约或产物验证。history/trace 读取不证明取消会停止工具进程，也不证明 result_path/deliverables 对应文件存在。 |
| [身份重建](../../agentteams-2026-09-09/reports/worker-identity-recreate-live.md)、[同容器 Ready](../../agentteams-2026-09-09/reports/worker-ready-restart-live.md)、[运行资源](../../agentteams-2026-09-09/reports/worker-runtime-live.md) | 身份缓存、Ready 与资源投影实现未变；本次不能把旧现象抹掉。新增读取入口需要单独权限验证；完整 Worker 生命周期重测不属于这个展示增量的首要成本。 |
| [76 项官方回归成本](../../agentteams-2026-09-09/reports/native-regression-load.md) | 旧报告是旧运行实测，不是新 Controller 单元测试结果。原 76 项 Python 测试不会覆盖新增 Go handler / renderer，不能用其通过数代替新版验收。 |

**history 写入尚未落地。** 新源码注释及文档注明等待 transition engine；本次仅添加 reader/schema。当前 CancelTask 在 [2739](../upstream/agentteams-controller/internal/server/project_handler.go#L2739) 附近仍只改 task status/cancel_reason/replacement_task_id 等并写对象，没有追加任务 history；TeamHarness 源码也没有本次改动。不能把文档示例里的三条迁移历史当作本版本实际生成的审计。Project `history/` 快照与 Task `history[]` 是两个不同记录，不能混用。

## 新增测试的实际证明边界

| 测试源码 | 覆盖及缺口 |
|---|---|
| [project_handler_test.go:4048](../upstream/agentteams-controller/internal/server/project_handler_test.go#L4048) `TestGetProjectWorkflow_MermaidFormat`、`:4102` Invalid | 内存 OSS、fake K8s、直接调用 handler、手工注入 Admin caller；覆盖基础样式、ready、边、Content-Type 和一种非法 format。未覆盖实际路由鉴权、Team 歧义、缺省 JSON 兼容、format/includeTasks 组合或真实 Mermaid parser。 |
| [project_handler_test.go:4122](../upstream/agentteams-controller/internal/server/project_handler_test.go#L4122) 六个 GetTaskInspection 测试 | 覆盖详情/history 过滤、依赖与 trace、TaskMeta 缺失、task 不在图、非法 ID、loop、Team 不回退 global。没有新端点的 scoped caller 401/403/404、同名多 Team 409、错误 project_id/task_id 元数据、存储非 NotFound 错误或 malformed JSON 测试；没有验证真实状态迁移产生 history。 |
| [workflow/mermaid_test.go](../upstream/agentteams-controller/internal/workflow/mermaid_test.go) | 7 个顶层测试，含 7 个 malicious-title 子样本；检验字符串片段、行结构、ID 碰撞及样式。**没有运行 Mermaid 解析器／浏览器**，不能据此接受文档“任何畸形标题都不可能改变结构／任意 ID 都有效”的普遍保证。 |
| [cmd/agt/mermaid_test.go:14](../upstream/agentteams-controller/cmd/agt/mermaid_test.go#L14) `TestCLIMermaidPath` | 手工 JSON→map→Snapshot→renderer，替代原两个旧 helper 测试；未真正执行 Cobra 命令、HTTP 请求或 API/CLI 输出对照。 |

一个具体测试标注问题：`TestRenderMermaid_NilSnapshot` 实际传入 `&Snapshot{}`，不是 nil；`RenderMermaid(nil)` 会在读取 `s.Next` 时解引用 nil。正常 API/CLI 都创建非 nil Snapshot，所以本次不把它列为已证实 HTTP 故障，但该测试不能证明其注释所称的 nil 防护。

## 优先回归清单

### P0：新增 API 契约与隔离

1. 对同一真实 MinIO 夹具分别请求缺省 JSON、`format=`、`format=mermaid`、`format=json/bogus`，校验响应类型、200/400；对不存在和同名歧义 Project 明确验证 404/409 与格式错误的优先顺序。Mermaid 加 `includeTasks=true` 不应读取或附带 TaskMeta。
2. 新 Task 检查路由走真实 auth middleware：Admin 正向、无 token／错实例 token、实际允许与不允许的 scoped caller；不要从旧 workflow 的 Admin 成功外推 Worker 授权。
3. 复用“两个实例 × 两个 Team × 同名 project/task”最小夹具：无 Team 409，显式 Team 精确读回，错误 Team／不存在 task 404；设置不同 Team/global 的同名 TaskMeta 诱饵，确认不串对象、不回退。并验证 graph membership 与 TaskMeta 中 project_id/task_id 双重归属。
4. 状态语义：图节点 completed、TaskMeta submitted 的既有分离；TaskMeta 缺失／破损／归属错误时的 normalized fallback；合法 TaskMeta 缺失 status 时实际返回值。`in_progress` 与 `in-progress`、`assigned` 与 `delegated` 不能统一当一个字符串枚举。检查 history 缺省省略、错误条目处理与无 span 时 trace 仍只是 hint。

### P1：展示正确性与升级冒烟

5. 对真实相同 JSON 通过 API Mermaid 和实际 `agt ... --mermaid` 比较输出，允许 CLI `fmt.Println` 额外尾换行；检查状态类、ready 优先、paused/loop/空图、ID 碰撞稳定映射。用目标页面实际 Mermaid 版本解析包含引号、换行、控制字符、Unicode、HTML/entity 和保留词候选 ID 的样本；不能仅测字符串 contains。
6. 新增及相关旧 Go 官方包测试**已完成，见下一节**。后续真实服务 pause/resume/replan/cancel 与 single-part 条件写已执行，见[最小升级冒烟](controller-upgrade-smoke.md)；17 项检查成立但首次脚本因旧 a 停止、取凭据失败而 exit 1，随后只读身份补测 exit 0。Team 消歧和新读取路由见[HTTP/身份/CLI 实测](controller-api-live.md)。没有注入新版 handler 并发读写窗口，CAS 证据是实际 MinIO 条件 PUT 与独立字节校验。原生 DAG/MCP/Worker 实现未变，无需将全套模型实验作为此次新展示功能的前置要求。

## 本轮官方测试结果（已执行）

在新版 `upstream/agentteams-controller` 执行原样命令：

```text
go test -p 2 -count=1 -json ./internal/server ./internal/workflow ./cmd/agt
```

Go 为 `go1.26.4 windows/amd64`。2026-09-10 10:15:01—10:15:23 UTC，整个命令连同版本读取墙钟约 22.217 秒，**进程退出 0，三包全部 PASS**。JSON 共 252 个顶层测试通过、59 个子测试通过，即 311 个 pass 测试事件；0 fail、0 skip。顶层和子测试不能相加后声称 311 个独立端到端场景。

| 包 | Go package elapsed |
|---|---:|
| `internal/server` | 0.701 s |
| `internal/workflow` | 0.692 s |
| `cmd/agt` | 6.874 s |

原始 [JSONL](../evidence/controller-official-tests.jsonl)、[stderr](../evidence/controller-official-tests.stderr.log)、[退出状态与计数摘要](../evidence/controller-official-tests-summary.json)、[执行脚本](../scripts/controller-official-tests.py) 均保留。stderr 记录 Go 自动获取锁定的 Cobra 模块；未改依赖声明或生产环境。测试后 upstream `git status --short` 仍为空。

这些结果包含新增 Mermaid/TaskInspection/Manager Provider 清空测试，并验证已有三个包的官方回归在此主机可通过；未补造尚缺的测试，也没有验证真实 MinIO、真实 token 权限、实际 CLI HTTP 联调或浏览器 Mermaid 解析。此句的范围仅是官方包测试自身。后续 [HTTP/身份/CLI](controller-api-live.md)、[浏览器](mermaid-browser-live.md)及[升级冒烟](controller-upgrade-smoke.md)已经完成相应有界实测，发现 end 解析失败与 CLI --team 409，不能写成展示集成全部通过。P0的双在线新增读取矩阵后续已在新版c/d完成，见[313断言实测](controller-twin-read-live.md)；错实例补测限定为旧 a 实际凭据对 c 新 Task 路由 401 的观察（a 未在线重新验权，且发生时钟回退／证书未生效事件，不能算干净的隔离通过）；includeTasks的内部读取后续已有[真实S3 trace](mermaid-storage-read-live.md)，结论限定到实际夹具和有限窗口。上述清单保留原计划含义，以后续证据界定已做范围，不倒填为所有条目通过。

### 邻接变更：Manager Provider 清空

这不是 Project/workflow 改动，但同一 Controller 增量另有实际更新契约：`UpdateManagerRequest.ModelProvider` 从 string 改成 `*string`，显式 `"modelProvider":""` 清空绑定，字段缺省／JSON null 不修改；CLI 新增 `--model-provider`，只有 flag 被显式指定才写入请求。见 [types.go:197](../upstream/agentteams-controller/internal/server/types.go#L197)、[resource_handler.go:697](../upstream/agentteams-controller/internal/server/resource_handler.go#L697)、[update.go:211](../upstream/agentteams-controller/cmd/agt/update.go#L211)。测试 [resource_handler_test.go:648](../upstream/agentteams-controller/internal/server/resource_handler_test.go#L648) 与 [update_test.go:10](../upstream/agentteams-controller/cmd/agt/update_test.go#L10) 覆盖清空；升级配置流程应补缺省／空／非空／null 区别。未在本次只读差异分析中操作 Manager。

所有 Git 读取均显式使用 `-c safe.directory=D:/Project4work/Repomesh_Go_ver/validation/agentteams-2026-09-10/upstream`。旧结论的原始证据保持在 09-09 目录；本报告不替换它们，也不将新版官方组件测试计数转换成真实服务验收通过数。
