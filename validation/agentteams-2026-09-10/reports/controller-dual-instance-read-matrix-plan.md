# 新版双在线实例读取矩阵：执行前计划

状态：此文保留执行前计划；后续已执行，结果见[真实双实例报告](controller-twin-read-live.md)。执行前要求主 Agent 确认 c/d 在线、Kube CA 时间有效且服务稳定；不以 `docker ps` 的相对 Up 文案判断是否重启，使用 ID、StartedAt、running。

脚本：[controller-dual-instance-read-matrix.py](../scripts/controller-dual-instance-read-matrix.py)。必须显式 `--execute`。执行上限 10 分钟，单次进程／HTTP 请求有界；全程无模型任务、Worker runtime 或业务 Adapter。

| 前提 | 内容 |
|---|---|
| 实例 | rv-c-controller API 48090；rv-d-controller API 49090；均为新版基线 |
| 存储 | 分别 rv-c-storage、rv-d-storage；容器内 mc alias agentteams 可用 |
| 认证 | 自有 CLI admin SA token；实际 embedded Kube admin-token 和 CA 能验证读取／TokenRequest |
| 新夹具 | 每实例两个同名随机 Team、两个 Stopped/containerManaged=false Worker 引用；由 Controller 生成 SA |
| 身份证据 | SA UID/Worker 标签/Worker UID/Team UID/实际 team_leader membership；TokenRequest claim UID 匹配、直接 TokenReview 成功 |
| 保密 | 所有凭据只在宿主／容器进程内存；不公开完整 TokenReview 请求或含 token 的响应 |

两个实例使用完全相同的随机 Team、Project、Task 名称，内容以 instance/Team 标记区分。每实例两份 ProjectMeta、八份 Team TaskMeta、两份 global 同名诱饵，共 12 个对象，经 `mc cp` 单段上传。

读取端点组合为 Task inspection、workflow 默认 JSON、workflow Mermaid、workflow includeTasks=true JSON、Mermaid 与 includeTasks=true 组合。

| 调用者与范围 | 预期 |
|---|---|
| Admin，显式左／右 Team | 五种读取均 200，内容精确匹配实例与 Team |
| Admin，省略 Team／错误 Team | 分别 409／404 |
| 左／右真实 SA TeamLeader，本 Team／省略 Team | 200，仅自身 Team 内容 |
| SA TeamLeader，他 Team／错误 Team | 404；不表述为普通 Worker 角色隔离 |
| c→d 与 d→c，Admin 与两 SA，五种读取 | 目标 401；每次重放前后在来源实例同一路由 200，避免把失效凭据拒绝当隔离证据 |
| TaskMeta 缺失／project_id 错／task_id 错 | 图内节点 normalized fallback，无 Team/global 诱饵泄漏 |
| TaskMeta 存在但图中无该 task | 404 |
| 只读结束 | 每实例 12 个原始对象 SHA 与上传字节及读取前一致；容器身份不变；引用仍 Stopped/unmanaged，无 nonce runtime |

这补新版双实例新增读取契约，不重跑模型执行、副作用、取消、故障注入或全角色写权限。Mermaid 只做内容与范围对照，不用 HTTP 200 代替浏览器渲染正确性。includeTasks 输出观察不等价于内部存储读取插桩。未执行时不得把此表当通过结果。
