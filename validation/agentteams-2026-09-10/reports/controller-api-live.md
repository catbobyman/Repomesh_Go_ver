# 新版 Controller HTTP、scoped 身份与 CLI 实测

日期：2026-09-10。版本 `517caff9280242a00a4d4c06365352b9e41659c6`，run `d33b63db78`。实例 `rv-c-controller`，API `127.0.0.1:48090`。实际镜像 `repomesh-validation/embedded:517caff9`，镜像 ID `sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f`，容器 ID `cf4981c840f1fb6584fcdf2f27a28c229b72974445f324f386e28aa797ef4e71`。

**新增 HTTP 契约及真实 scoped 读取在本轮样本中按实现工作；同时确认两个问题：有效原生 task ID `end` 经 API 返回的 Mermaid 无法被真实解析器解析；实际 `agt get projects ID --team TEAM` 仍未消除同名 Project 的 409。** 前者不是 HTTP 200 可以证明的渲染成功，后者是既有 CLI detail 路径问题，不误称本次新增回归。

## 实验与身份边界

本轮新建两个 Team `delta-d33b63db78-left/right`，各引用一个新 Worker `delta-leader-d33b63db78-0/1`。两个 Worker 始终 `Stopped`、`containerManaged=false`，没有本轮 runtime 容器。原生登记只用于真实前缀解析及身份归属，不是业务 Project 创建。没有派工、模型任务、服务重启或上游修改，也未操作其他 Agent 的 Manager 夹具。

直接在 `rv-c-storage` 中用临时文件加 **`mc cp` 单段上传**写入 16 个随机范围对象：两 Team 下同名主 Project、一个独立 reserved-end Project，以及 13 份 TaskMeta／诱饵／破损文件。主 Project 为 `delta-project-d33b63db78`；每份实际 key、字节内容和 SHA-256 均保留。原始数据是明确标记的元数据夹具，不声称产物或任务实际执行过。

主 HTTP 请求使用容器 `/var/run/agentteams/cli-token` 的实际管理身份；另分别用匿名和随机无效 token 测认证拒绝。随后使用**Controller 已生成的真实 Worker SA**做 Kubernetes TokenRequest，并走真实 HTTP 认证／角色解析，见后节。凭据只存在进程内存，公开证据没有 token；没有手工构造 JWT、替换 caller 或把 Admin 请求冒充 Worker。

## 主 HTTP 回归

10:26:54—10:27:13 UTC，43 次真实 HTTP，51 项观察断言成立，脚本退出 0，耗时 19.344 秒。检查数包含中间断言与“已观测到缺陷字符串”，**不是 51 项产品验收全部通过**。

| 条目 | 实际结果 |
|---|---|
| 缺省 workflow 与 `format=` | JSON 200，内容一致；缺省不附带 tasks_detail |
| `format=mermaid` | text/plain 200；引号转换为 `#quot;`，换行为 `<br>` |
| Mermaid + `includeTasks=true` | 输出与不带 includeTasks 完全相同；只证明本次输出一致，没有对内部存储调用次数插桩 |
| `format=bogus`、`format=json` | 均 400；旧客户端若传 format=json 需要调整 |
| includeTasks | 原始 TaskMeta status/history 被读取；与图节点状态分开 |
| 两 Team 的同名 Task inspection | 各 200，读取对应 summary/assignee；原始 `in_progress` 保留，图节点同 Task 为 `completed` |
| TaskMeta 缺失／破损 JSON／project_id 不匹配／task_id 不匹配 | 200 返回规范化图状态 `in-progress`，没有泄漏错误对象 summary；global 同名诱饵没有回退进 Team 读取 |
| 缺 TaskMeta 的依赖 | 从 Project 图节点返回前驱列表 |
| history 数组 | 五个输入项保留三项：有效对象、只有 action 的对象、只有非日期 ts 的对象；字符串和没有 ts/action 的对象跳过。不是时间合法性验证或不可篡改审计 |
| history 类型错误（对象而非数组） | 被忽略，history 字段省略；TaskMeta raw `assigned` 保留 |
| 合法归属 TaskMeta 但缺少 status | 响应 status 为空／省略，没有恢复图节点状态 |
| Admin 不指定 Team | 主同名 Project 的 workflow、Task inspection、Mermaid 均 409 |
| 指定不存在 Team／不存在 Project | workflow 与 Task inspection 均 404；不存在 Project + bogus format 先得到 404 |
| task 不在图、非法 task ID | 分别 404、400 |
| 对 inspection 路径 POST／DELETE | 405，未执行 Task 写入 |
| 匿名／无效 token 读取 workflow 与 inspection | 401，只是认证拒绝，不称为 403 角色隔离 |

在所有主请求前后独立 `mc cat` 16 个对象并计算 SHA-256，全部字节不变。response 中的 spec/result/deliverable 路径只是元数据，包括明确不存在的 fixture 产物路径；本轮没有把 inspection 200 当作文件存在性或产物验证。

## 实际 Worker SA 的 scoped 读取

停止且未托管的两个 Worker 已有 Controller 创建的 SA，故无需启动 Worker。先读取真实 SA UID、`agentteams.io/worker` 与 controller 标签，再读取对应 Worker CR UID、Team CR UID 和 `workerMembers.role=team_leader`。对这些**已存在 SA**通过嵌入式 Kubernetes `serviceaccounts/{name}/token` 申请 audience=`agentteams-controller`、600 秒 token；检查 JWT claim SA UID 与实际 SA UID 相同，直接 TokenReview 均 `authenticated=true`。

| 身份 | 实际 SA UID | Worker CR UID |
|---|---|---|
| `rv-c-worker-delta-leader-d33b63db78-0` | `158bc0e4-db85-46af-b306-7bf0652d52ec` | `48fb9d85-3239-4a59-b8aa-d96cd47b5eac` |
| `rv-c-worker-delta-leader-d33b63db78-1` | `f0f7ca7b-7ef4-42aa-be09-9c762eff7b3e` | `ec92bfdc-1fc7-4e96-9759-20b34f4ef660` |

两身份通过真实 Team membership 被 Controller 解析为 **team-leader**。这是真实 Worker SA scoped 身份，不是运行容器实际投影 token，也不是普通 worker 角色的通过证据。

对每个身份分别调用 Task inspection、workflow JSON、workflow Mermaid：

- 显式本 Team：均 **200**，JSON 内容属于该 Team。
- 显式另一个真实 Team：均 **404**，隐藏存在性；不是 401，也不是 403。
- 不提供 Team：均 **200**，只看到本身份所属 Team，不复用 Admin 的歧义范围。

该部分共 18 次实际 scoped HTTP、31 项检查成立，进程退出 0；前后再次核对 16 个 MinIO 哈希均不变。token 没有落盘，公开 TokenReview 只保存安全 status 字段。普通 worker 角色、L2 人类、Manager、所有写权限及新旧 token 撤销不在本轮覆盖范围。

## `end` 的真实 HTTP 与浏览器反例

独立 Project `delta-project-d33b63db78-reserved-end` 包含一个普通标题、`task_id=end` 的合法图节点。真实 workflow JSON 200，单 Task inspection 200。`format=mermaid` 也返回 200，但实际输出包含：

```text
flowchart LR
    end["Ordinary task: pending"]:::ready
```

原始 [API .mmd 字节](../evidence/controller-delta-live-d33b63db78-reserved-end.mmd)共 **411 字节**，SHA-256 `026597812b4c8205cf7070ac2c2ef812621344a8c4da1d60b97ca488b090f0cc`。主 Agent 将这些原始 API 字节送入 Chromium 的 Mermaid 11.17.2，实际 **0 通过／1 解析失败，错误 got end**；见[独立浏览器结果](../evidence/mermaid-api-browser-result.json)。浏览器工作由主 Agent 执行，本报告只引用对应相同 SHA 的结果，不冒称由本脚本完成。

这确认 renderer 对合法 task ID 的 Mermaid 保留词处理存在缺陷，不能沿用文档“任意用户 ID 均可渲染”的普遍保证。未修改渲染器或上游；其他保留词的库级浏览器样本由独立专项报告覆盖，不扩展为本次 HTTP 已逐个测试。

## 两条真实 CLI

CLI 在 rv-c-controller 内使用其默认配置和自有 token；只查询既有本轮资源，没有新建对象。

| 命令 | 结果 |
|---|---|
| `agt get projects delta-project-d33b63db78-reserved-end --mermaid` | exit 0，stderr 空。与 API 字节严格不等，因为 CLI 多一个尾换行；去掉尾换行后完全相同，因此共享相同 `end` 渲染问题。CLI Mermaid stdout 字节 SHA-256（不是 agt 可执行文件哈希）`285bedf65c8de9b417f9463d7ff21b6d4829d7fcc80c6e38d05242b8379f7435` |
| `agt get projects delta-project-d33b63db78 --team delta-d33b63db78-left` | **exit 1、HTTP 409**，提示应提供 ?team=，即使用户已传 --team。对应实际 HTTP 显式 ?team= 成功；CLI detail 路径没有转发该参数，此问题在旧 get.go 也存在 |

## 证据与复现边界

### GET-02 后续只读 CLI 负向（新容器）

2026-09-10 **10:36:13 UTC** 追加两次查询，使用保留的原 Project 元数据。执行前确认 c 已换为容器 `ef17ce71456d5bec7c8f882fd982b3f47985d2ce65cb4b35ac8ea15e00f8d2ca`，StartedAt=`10:34:25.597638797Z`，仍使用上述同一镜像 ID；不同于原轮 `cf4981c840f1…`。两次查询前后该新容器 ID、StartedAt 不变且 running=true。本子任务没有执行重启或资源写入。

| 新容器内的实际命令 | 安全输出与退出状态 |
|---|---|
| `agt get projects delta-nonexistent-94ee8c7011` | **exit 1**，stdout 空，stderr 明确 **HTTP 404 / project not found** |
| `agt get projects delta-project-d33b63db78 --team delta-d33b63db78-left --mermaid` | **exit 1**，stdout 空，stderr 明确 **HTTP 409 / project id is ambiguous across teams; retry with ?team=** |

原始命令、完整 stdout/stderr 和前后容器身份保存在[独立后续证据](../evidence/controller-delta-cli-followup-94ee8c7011.json)。使用新容器内 agt 默认身份配置，没有在命令行传 token。第二条是在原先不带 --mermaid 的负向之外，实际确认 --mermaid 组合也未转发 Team 范围；**这两条独立后续观察不加总到原轮 51／31 检查**，也不把新容器读路径结果倒填为原轮生命周期证据。

- [主 HTTP/存储/容器证据](../evidence/controller-delta-live-d33b63db78.json)、[主脚本](../scripts/controller-delta-live.py)。
- [SA 预检查](../evidence/controller-delta-sa-preflight.json)、[scoped 身份及 HTTP](../evidence/controller-delta-scope-d33b63db78.json)、[容器 TokenRequest 脚本](../scripts/controller-delta-scope-container.py)。
- [实际 CLI stdout/stderr/退出状态](../evidence/controller-delta-cli-d33b63db78.json)、[scope/CLI 编排](../scripts/controller-delta-scope-run.py)。

本轮保留两个 Team、两个停止的 Worker 引用和 16 个有限元数据对象供审计，未删除既有资源。原有状态机、取消副作用、CAS 与身份撤销反例仍按[逐函数差异分析](controller-delta.md)映射旧版证据，没有重复重跑整套模型实验。上述 51/31 检查是新增路径的观察计数，不能用来覆盖浏览器解析失败、CLI 参数缺陷或尚未覆盖的业务验收。

后续独立新 Project 的 pause/resume/replan/cancel、单段条件写与旧 a 凭据拒绝见[最小升级冒烟](controller-upgrade-smoke.md)；不计入原 51／31 项。
