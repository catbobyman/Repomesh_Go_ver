# Manager modelProvider 清空与 CLI 变更：新版差异核查

本文件是本轮执行前的 **历史静态差异分析与测试设计**，比较旧基线 `eeaab64391ccaec9118e84977f538aefd40720d6` 与新 HEAD `517caff9280242a00a4d4c06365352b9e41659c6`。写作时未运行测试、启动服务、修改上游或调用模型；下面的代码推导与待测清单保留当时语境。后续 CFG-01—05 已实际执行，最终结果以 [Manager 配置实测](manager-config-live.md) 为准：保存、投影及运行进程内存配置层已完成，不代表模型推理已验证。全部新版验证见[本轮索引](../README.md)。

比较使用 `git -c safe.directory=D:/Project4work/Repomesh_Go_ver/validation/agentteams-2026-09-10/upstream -C ... diff <old> <new>`，新仓库 `status --short` 为空。两基线之间只有一个提交 `fix(controller): allow clearing Manager model provider (#1232)`，共 14 个文件变化；提交标题之外还包含 Project workflow／Mermaid 变更。本报告覆盖配置清空、CLI update/get 及与它们直接相关的最小验证。

## 1. 修复了什么

旧 `UpdateManagerRequest.ModelProvider` 为 `string`，Handler 只在非空时写入，导致请求 `{"modelProvider":""}` 虽可返回成功，却无法清除已有绑定。新版把字段改为 `*string`，Handler 在指针非 nil 时写入解引用值，显式空字符串现在能够成为实际更新值。[请求类型](../upstream/agentteams-controller/internal/server/types.go#L195)、[更新 Handler](../upstream/agentteams-controller/internal/server/resource_handler.go#L680)。

| JSON 请求中的 modelProvider | 旧代码 | 新代码的可推导行为 |
|---|---|---|
| 字段省略 | 保留旧值 | 保留旧值 |
| `null` | 解码后空值，不更新 | nil，不更新；**不是清空命令** |
| `""` | 不更新，旧绑定仍在 | 显式写空，清除 Manager Spec 绑定 |
| `"provider-b"` | 更新为该字符串 | 更新为该字符串 |
| 数字、布尔、对象或数组 | 字符串解码失败 | 指针目标字符串解码失败，Handler 返回 400，尚未写资源 |

这是 **Manager 单一字段的更新语义修复**。Worker `UpdateWorkerRequest.ModelProvider` 仍为 string，Worker Handler 仍只处理非空值，见 [types.go:36](../upstream/agentteams-controller/internal/server/types.go#L36) 与 [resource_handler.go:233](../upstream/agentteams-controller/internal/server/resource_handler.go#L233)。Manager 的 `model`、`runtime`、`image`、`soul` 也仍只处理非空值，不能将新行为概括为“所有字段均能显式清空”。Manager 创建接口没有变为指针模型。

空串也不是“删除模型提供商或撤销所有凭据”：这里改变的是 `Manager.Spec.ModelProvider` 的名称绑定，未增加 Provider 删除、旧 route 授权撤销或 runtime 内部状态回滚逻辑。它与 Controller 环境中的 provider 设置、QwenPaw 配置里的 `providerId=agentteams-gateway` 不是同一个字段。

绑定非空时，Manager reconcile 先解析 Provider；解析失败会提前返回，见 [manager_controller.go:137](../upstream/agentteams-controller/internal/controller/manager_controller.go#L137)。因此清除已经删除或错误的 Provider 名称可以移除这一解析前置条件，这是修复针对的恢复路径。实际配置是否恢复默认 Gateway、旧 runtime 配置是否刷新，仍需观察 reconcile 后的结果；Handler 的 200 不证明这些步骤完成。[配置投影](../upstream/agentteams-controller/internal/controller/manager_reconcile_config.go#L28)、[容器 URL 覆盖](../upstream/agentteams-controller/internal/controller/manager_reconcile_container.go#L163)。

## 2. CLI update 与 GET 读回的边界

`agt update manager` 新增 `--model-provider`。它使用 Cobra 的 `Flags().Changed("model-provider")` 判断用户是否明确指定，区别于已有字段使用的 `setIfNotEmpty`。[update.go:209](../upstream/agentteams-controller/cmd/agt/update.go#L209)

```text
agt update manager --name <fixture> --model-provider=          # 发送显式空串
agt update manager --name <fixture> --model-provider=provider-b
agt update manager --name <fixture> --model known-good-model # 不发送 modelProvider
```

单独指定 `--model-provider=` 已形成一个更新字段，不需要再附带 `--model` 才能绕过“至少一个字段”的检查。缺少 `--name` 或完全没有更新参数仍应在 CLI 本地拒绝。自动化必须保留“省略／显式空串”区别；把所有未填写值都序列化成空串，会在新版意外清除已有绑定。

**关键读回限制仍未修复：** [ManagerResponse](../upstream/agentteams-controller/internal/server/types.go#L211) 不包含 `modelProvider`；GET 单个 Manager、列表及 `agt get managers -o json` 因此都不能直接证明绑定已清空。PUT 返回 `manager/<name> configured` 也不是运行时生效证据。新增服务端测试使用底层 Kubernetes client 读取 Manager CR 来断言修复，后续真实验证应采用相同层级的独立 CR 读回，仅输出该安全字段和必要关联字段。

## 3. CLI get 实际改动是 Project Mermaid 展示

`get.go` 的变化没有增加 Manager Provider 显示。改变的是 `agt get projects <id> --mermaid`：仍请求 JSON workflow，然后把通用 map 重新序列化为 `workflow.Snapshot`，调用与 Controller 共用的 `workflow.RenderMermaid`。[get.go:121](../upstream/agentteams-controller/cmd/agt/get.go#L121)

新的展示行为包括：六类节点状态样式、ready 样式优先；任务 ID 的字符规范化和规范化后冲突后缀；标题的引号、换行、反斜杠和控制字符处理；空图仍输出图头与样式定义。[共享 renderer](../upstream/agentteams-controller/internal/workflow/mermaid.go#L128)

这改变的是图文本展示，不能当成 DAG 依赖校验、候选就绪、业务派工或 Loop 状态机的修复。新 renderer 的字符串测试也不是实际 Mermaid 引擎解析或浏览器安全验收。

另一个与 CLI 使用直接相关的现有限制：`--team` 只附加到项目列表查询；单项目 workflow 路径在 [get.go:123](../upstream/agentteams-controller/cmd/agt/get.go#L123) 没有附加 Team。故 `agt get projects <同名ID> --team <team> --mermaid` 不能仅凭参数存在就声称使用了明确 Team。两 Team 同名 Project 的 API 消歧验证与 CLI 透传应分开；这一点本次没有修改，但新 Mermaid CLI 验证不能遗漏它。

## 4. 新测试覆盖到哪一层

| 测试 | 已写入的断言 | 没有证明什么 |
|---|---|---|
| [TestUpdateManagerCanClearModelProvider](../upstream/agentteams-controller/cmd/agt/update_test.go#L10) | httptest 服务捕获真实 CLI 命令生成的 PUT，确认 model 及显式 `modelProvider:""` | 服务端使用的是 `{}` 假回执，没有真实 Controller、CR 或 runtime |
| [TestUpdateManagerClearsModelProviderWhenExplicitlyEmpty](../upstream/agentteams-controller/internal/server/resource_handler_test.go#L648) | Handler 更新后从 fake Kubernetes client 读回，model 更新、旧 Provider 变空 | 真实持久化、权限中间件、reconcile、Gateway 或 runtime 生效 |
| 原有 [TestCreateAndUpdateManagerPersistsModelProvider](../upstream/agentteams-controller/internal/server/resource_handler_test.go#L609) | 创建非空绑定、更新另一个非空绑定 | 省略、null、类型错误、仅清空、连续更新的兼容性矩阵 |
| [TestCLIMermaidPath](../upstream/agentteams-controller/cmd/agt/mermaid_test.go#L14) | map → JSON → typed Snapshot → renderer 的内存转换及状态样式 | 未执行 Cobra 的完整 CLI 请求，也未验证 `--team` URL |
| [workflow renderer tests](../upstream/agentteams-controller/internal/workflow/mermaid_test.go#L8) | 状态、空图、恶意标题样例、ID 清洗冲突等字符串断言 | 未运行外部 Mermaid 解析器；名为 NilSnapshot 的测试实际传 `&Snapshot{}`，不是 nil 指针 |

这些测试本次只读过，没有运行。不能把新增测试存在写成新版服务已通过。

## 5. 最小必测正负用例

以下测试无需真实模型推理。配置写入只应落在专属夹具 Manager，不使用两套工作 Manager；运行态投影另由主验证流程在明确的隔离环境安排，避免为了测试字段而触发无关模型会话。

| 编号 | 最小输入／前提 | 通过依据 | 覆盖层 |
|---|---|---|---|
| CFG-01 正向清空 | 初始 CR `modelProvider=provider-a`、model=m1；PUT `{ "modelProvider":"" }`，再重复一次 | 两次正常响应；独立 CR 读回空绑定，model、runtime、image 保持原值；GET 未返回该字段不算读回失败也不算证明 | 真实 REST／CR；修复主场景及重试 |
| CFG-02 省略／null 对照 | 各自从非空绑定开始，先 PUT `{ "model":"m2" }`；另 PUT `{ "modelProvider":null }` | 第一项只改 model；第二项不清空 Provider；独立 CR 保留 provider-a | 真实 REST／CR；防意外清空 |
| CFG-03 非空与非法类型 | PUT 新非空字符串；随后逐项发送数字／对象代表性错误类型 | 新字符串正确持久；错误类型 400，CR 字段不变。未知 Provider 名称若允许保存，只记录稍后解析失败，不能误判为“REST 已验证 Provider 可用” | 真实 REST／CR；兼容及负向 |
| CFG-04 CLI 请求语义 | `--model-provider=` 单独使用、非空、完全省略；再缺 name／无更新参数 | 前三项请求分别为显式空、新值、字段不存在；负向 CLI 不发 PUT。随后用新版实际 agt 对专属 Controller 执行一次空串更新并独立读取 CR | CLI 编码＋真实服务最小闭环 |
| CFG-05 生效边界 | 专属 Manager 曾有失效 Provider 绑定；清空并保留一个配置有效的 model | CR 确认空值；后续 reconcile 不再报该旧名称解析失败，生成配置／实际安全 URL 选择与默认路径一致。无需模型；若只验证到 CR，则本项仍标未运行 | 配置投影，不能被 CFG-01 代替 |
| GET-01 Mermaid 正向／防回归 | 同一专属合法图含 ready 与 completed 节点、点号和下划线冲突 ID、带引号／换行的中文标题；另空图 | CLI 和 API 共享 renderer 的文字内容一致（容许 CLI Println 多一个末尾换行）；节点／边身份不合并、状态样式正确、标题不扩展成结构；普通 JSON 输出保持结构契约 | CLI／HTTP 展示，不验证执行 |
| GET-02 CLI 负向与 Team | 不存在 ID；两 Team 同名 ID，调用 `agt get projects <id> --team <team> --mermaid` 并记录实际请求；用 REST 显式 team 作对照 | 不存在图返回可辨失败；记录 CLI 是否透传 Team。按当前源码预计 detail 丢失 Team，不能把 REST 消歧成功当作 CLI 通过 | CLI 路由契约；可复用主侧同名夹具 |

顺序宜为官方针对性单测 → CFG-01—04 真实静态资源 → CFG-05 配置读回 → GET-01—02。可先运行的官方命令如下，**本报告未执行**：

```text
go test ./cmd/agt -run 'TestUpdateManagerCanClearModelProvider|TestCLIMermaidPath' -count=1
go test ./internal/server -run 'TestCreateAndUpdateManagerPersistsModelProvider|TestUpdateManagerClearsModelProviderWhenExplicitlyEmpty' -count=1
go test ./internal/workflow -run TestRenderMermaid -count=1
```

上述命令工作目录为新版 `upstream/agentteams-controller`。官方用例缺失的负向矩阵与真实持久化读回应保留为独立证据，不修改上游实现来制造通过。

## 6. 对 09-09 证据的影响

09-09 的 [Manager 模型验证](../../agentteams-2026-09-09/reports/manager-model-live.md)记录了 `agt get managers -o json` 的 model/runtime/image 和真实回复；[启用预检](../../agentteams-2026-09-09/reports/manager-enable-preflight.md)记录的是 Controller 环境中的 provider 四字段及默认 model。它们没有覆盖 Manager CR 的非空 `modelProvider` 清空，因此新修复没有推翻旧观测，但旧报告也不能为 CFG-01—05 提供通过证明。GET 原本不返回该字段，进一步限制了旧读回的证据范围。

09-09 的 [QwenPaw MCP 配置验证](../../agentteams-2026-09-09/reports/mcp-config-contract-live.md)仍证明旧组合的 `mcpServers` 保存、desired 投影、原生 DriverCard／tools API 和实际客户端调用。此次差异没有修改 QwenPaw、TeamHarness 或 MCP 配置更新实现，不能把这一结果误标为受 Manager modelProvider 修复影响；同样不将旧镜像的通过结果改写为新版运行证据。

旧版“资源限额未投影、MCP 绕过暂停、陈旧上传覆盖、Worker 多活跃和消息恢复缺口”等结论不在这次配置修复范围。CLI Mermaid 展示升级也不关闭任何 RepoMesh 许可、身份、持久事务或业务验收缺口。新版最小增量应集中在上表，按每层实际读回记录，而不是重跑无关模型 marker。
