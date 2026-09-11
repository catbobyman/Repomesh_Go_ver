# 新版 c/d 双在线实例读取矩阵

新版基线 `517caff9280242a00a4d4c06365352b9e41659c6` 的双实例、双 Team 新增读取矩阵已实际执行。**进程 exit 0，313 个断言成立，0 失败**；这不是 313 个独立业务场景，也不加总到原轮 51／31 项。实际记录 260 次 Controller HTTP，其中 8 次创建停止引用／Team、其余为读取；不包含容器内 Kube 验证请求。用时 57.063 秒，记录时间 2026-09-10 03:50:55—03:51:52 UTC。

[原始证据](../evidence/controller-dual-instance-read-matrix-1cf6fd634d.json)、[执行脚本](../scripts/controller-dual-instance-read-matrix.py)、[执行前覆盖计划](controller-dual-instance-read-matrix-plan.md)。本报告没有修改上游代码或 current 文档。

## 环境与身份来源

| 实例 | API | 容器 ID |
|---|---|---|
| c | 48090 | `ef17ce71456d5bec7c8f882fd982b3f47985d2ce65cb4b35ac8ea15e00f8d2ca` |
| d | 49090 | `d611f0702253daae9c14470773fd448166cd5cdb94ca4130818b0bc49bf394f6` |

两者均实际使用镜像 `sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f`。前后 ID、StartedAt、running=true 不变。c 的 StartedAt 仍是时钟回退前的 `10:34:25Z`，d 是 `03:49:12Z`；不能把 c 的相对 Up 文案或“未来”StartedAt 当作本轮重启证据。测试没有重启任何服务。

执行前，两实例均以实际 Kube admin-token、各自 CA 开启 TLS 校验完成 namespace 读取，均成功。四个新 Worker 由实际 Controller 生成 SA，再通过各自 Kubernetes TokenRequest 申请 1200 秒、audience=`agentteams-controller` 的 token。JWT 中 SA UID 与真实 SA UID 一致；直接 TokenReview 均 authenticated=true。实际 Team CR membership 为 `team_leader`，因此后续结果是 **SA TeamLeader 范围**，不是普通 Worker 角色或运行容器投影凭据。

| 实例／Team | 实际 SA 名称 | SA UID |
|---|---|---|
| c／left | `rv-c-worker-matrix-leader-1cf6fd634d-0` | `92107630-c90d-4673-9b90-5ec513a50963` |
| c／right | `rv-c-worker-matrix-leader-1cf6fd634d-1` | `2971d542-a5a7-4bf9-82d1-620c432feed5` |
| d／left | `rv-d-worker-matrix-leader-1cf6fd634d-0` | `48f8a9fb-6922-4ab1-86a3-5e24e46c2cf6` |
| d／right | `rv-d-worker-matrix-leader-1cf6fd634d-1` | `599e67c8-329e-4fe4-8dcc-dfa60386980b` |

Worker UID、SA Worker 标签、Team UID、membership、token 签发／到期时间和安全 TokenReview 结果均在原始证据中。Admin 使用每个 Controller 的 `/var/run/agentteams/cli-token`；凭据只在进程内存中，公开输出无 token，也未保存完整 TokenReview 请求／响应。

## 同名夹具与实际读取结果

两个实例均登记名称完全相同的 `matrix-1cf6fd634d-left/right` Team、`matrix-leader-1cf6fd634d-0/1` Worker 引用。Worker 始终 `Stopped`、`containerManaged=false`，没有 nonce runtime 容器。每实例同名 Project 为 `matrix-project-1cf6fd634d`；Task 名称统一使用 `matrix-1cf6fd634d-{raw,missing,wrongproject,wrongtask,outside}`。

每实例 12 个对象，共 24 个：两份 Team ProjectMeta、每 Team 四份 TaskMeta、两份 global 同名 TaskMeta 诱饵。Team/实例内容分别标记为 `c|<team>` 或 `d|<team>`。使用真实 `mc cp` 上传原始 JSON；这是直接元数据夹具及最小 CR 登记，**不是业务 Project/Task 创建或模型执行**。原来 c 的 16 个对象和 Manager 配置不属于写入范围。

五种读取组合：

1. `GET /api/v1/projects/{id}/tasks/{taskId}`。
2. `GET /api/v1/projects/{id}/workflow`，默认 JSON。
3. workflow `format=mermaid`。
4. workflow `includeTasks=true`，JSON。
5. workflow `format=mermaid&includeTasks=true`。

两实例 × 三身份 × 五组合 × 四 Team 参数范围，共 **120 次基础矩阵读取**：

| 身份／Team 参数 | 两实例实际结果 |
|---|---|
| Admin，显式 left 或 right | 200；Task summary、JSON node name／team_id、includeTasks TaskMeta、Mermaid 标题均符合正确实例和 Team 标记 |
| Admin，省略 Team | 409，同名 Project 歧义 |
| Admin，未知 Team | 404 |
| 左／右 SA TeamLeader，本 Team 或省略 Team | 200；仅自身 Team 内容，未被另 Team 或另实例同名对象替换 |
| SA TeamLeader，显式他 Team 或未知 Team | 404；是服务的隐藏式范围拒绝，不称为 403 |

另有 **32 次 Task 负向读取**，由每实例 Admin 对两个 Team、两 SA 各自对本 Team 执行：

| 夹具 | 实际结果 |
|---|---|
| graph 有 task，Team TaskMeta 缺失；global 有同 task/project 的诱饵 | 200，normalized `pending` fallback，summary 为空，不回退读取 global 诱饵 |
| graph 有 task，Team TaskMeta 的 project_id 错误 | 200，`pending` fallback，错误 summary 不泄漏 |
| graph 有 task，Team TaskMeta 的 task_id 错误 | 200，`pending` fallback，错误 summary 不泄漏 |
| Team TaskMeta 存在且 project_id/task_id 匹配，但 graph 没有该 task | 404 |

## 双向错实例凭据对照

c→d、d→c，各使用来源 Admin 与两 SA TeamLeader，覆盖五种读取组合，共 **30 次凭据重放**。目标实例全部返回 **401**。每次重放均在来源实例同一路由、同 Team、同凭据执行前后正向请求，两次均 **200**，共 60 次来源自证。

这组证据与[上一轮升级冒烟](controller-upgrade-smoke.md)的异常时钟 401/200 明确分开。此次两个实例同时在线，Kube TLS 校验成功、SA 新签发且直接 TokenReview 正向成功，来源前后可用，因此排除了“未知／已失效来源凭据仅被拒绝”的主要混淆。没有另行对错实例凭据做目标 Kube TokenReview 或捕获验证器内部错误，故结论仍限定为真实 HTTP 的双向身份拒绝，不声称证明具体验签失败原因或所有实例授权策略。

260 次 Controller HTTP 的状态分布：200×150、201×8、404×62、409×10、401×30。除上述 120 基础矩阵、32 负向、90 重放及来源对照外，其余 18 次为两次 Admin 预检查、8 次 CR 创建、4 次初始 Project 不存在检查、4 次最终 Worker 状态查询。

## 独立校验与范围

两实例各 12 个对象都通过独立 `mc cat` 原字节 SHA 核对：上传值、读取矩阵前、读取矩阵后完全相同。最终四个 Worker 引用仍停止且未托管；全局容器名称列表中没有该 nonce 的 runtime。所有新元数据与 CR 留存审计，无模型请求、任务执行、业务 Adapter 或服务生命周期操作。

本次补齐新版两实例×两 Team 的上述新增读取矩阵。Mermaid 范围／标题读取成功不代表浏览器渲染全部正确，已知 `end` 反例见[浏览器报告](mermaid-browser-live.md)。`includeTasks` 输出覆盖不等于内部存储读取插桩；该内部行为后续已由[真实MinIO trace正负对照](mermaid-storage-read-live.md)补证。本轮也不覆盖普通 Worker/L2/Manager 全角色写权限、runtime token 投影、取消副作用、跨对象事务或完整模型生命周期。
