# Controller 最小升级冒烟

基线 `517caff9280242a00a4d4c06365352b9e41659c6`；真实 c Controller `ef17ce71456d5bec7c8f882fd982b3f47985d2ce65cb4b35ac8ea15e00f8d2ca`，镜像 `sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f`。执行前后 ID、StartedAt 与 running=true 相同。没有操作 Controller、Manager 或其他容器生命周期。

独立随机 Project 为 `upgrade-smoke-387e374202`，唯一 Task 为 `upgrade-task-387e374202`。使用 `mc cp` 写入 `rv-c-storage/shared/projects/upgrade-smoke-387e374202/meta.json` 与 `shared/tasks/upgrade-task-387e374202/meta.json`；这是 Admin 直接登记的 **global 元数据夹具**，没有创建新 CR、运行 Worker 或模型任务。`source_room_id` 为空。原轮 16 对象不是本次写入目标。

## 真实操作与独立读回

| 操作 | HTTP / 存储结果 |
|---|---|
| 新 Project 初始查询 | 404；确认唯一名称没有既有对象 |
| 初始 `mc cp` | `mc stat` ETag 与上传原字节 MD5 相同，单段对象 |
| REST pause | 200；独立 `mc cat` 显示 paused，SHA 改变 |
| paused 时 REST replan | 409；独立读回原字节与 SHA 不变 |
| REST resume | 200；独立读回 active |
| active 时 REST replan | 200；独立读回唯一 task 新标题 |
| REST cancel | 200；Project node 与 TaskMeta 均 cancelled，TaskMeta reason 正确 |
| 新 Task inspection | 200，显示 cancelled |
| 直接 S3 PUT，`If-Match` 为取消后真实 ETag | 200；只更新该新 Project 标题 |
| 再用同一旧 ETag PUT 不同标题 | **412 PreconditionFailed**；独立 `mc cat` SHA 等于首次条件写入字节，旧写没有覆盖 |

REST 写路径自身使用内部读到的内容 ETag。上述 CAS 对照是在真实 MinIO 对同一个新对象发送 AWS SigV4 条件 PUT，凭据从 c 的既有 mc 配置仅在容器进程内读取。**它证明单段条件存储写的当前值成功、旧值拒绝，并非人为插入 HTTP handler 读写窗口的并发冲突试验**；没有声称客户端 HTTP `If-Match` 被 handler 使用。未重跑 multipart、跨对象故障窗口、模型进程取消或压力测试。

主脚本记录 **17 项检查均成立**，用时 8.047 秒；但整体 **exit 1**，原因是最后尝试 `docker exec rv-a-controller cat ...` 时旧 a 容器已经停止，错误发生在所有写入与 CAS 检查之后。保留[首次原始证据](../evidence/controller-upgrade-smoke-387e374202.json)与[执行脚本](../scripts/controller-upgrade-smoke.py)，未改成 exit 0，也没有为补身份验证重跑写入。

## 旧 a 身份访问新版 c

后续使用 `docker cp rv-a-controller:/var/run/agentteams/cli-token -` 的 tar 流在内存读取原文件，未写凭据文件、未启动 a。对同一 c 新 Task inspection 路由：旧 a 实际 admin SA token 返回 **401**，c 自身实际 token 返回 **200**；前后 a 仍停止，c 身份与运行状态不变。该只读补测 exit 0，见[独立证据](../evidence/controller-upgrade-smoke-387e374202-cross-instance.json)与[补测脚本](../scripts/controller-cross-instance-followup.py)。

旧凭据是 `system:serviceaccount:default:rv-a-admin` 的 SA JWT，非假设的永久静态管理员密钥。安全读取的 claim 中 audience=`agentteams-controller`、exp=`2104331968`，在读取时尚未到期，见[非敏感 claim 摘要](../evidence/controller-upgrade-smoke-387e374202-a-token-metadata.json)。claim 解码未单独验签；a 处于停止状态，本轮没有对 a 再做成功认证或检查吊销状态。因此结论限定为“实际旧 a 文件凭据在 c 新路由被拒绝，而 c 自有凭据通过”，不从单次 401 断言所有可能拒绝原因或新版双实例完整隔离矩阵。各文件保留宿主原始 UTC 时间。身份补测记录 03:39:36 UTC，主写入实验记录约 10:39 UTC；主 Agent 随后确认环境时钟回退约 7 小时，并出现 Kube 证书尚未生效错误。因此 **401/200 只是该异常时钟条件下的实际观察，不计为干净的错实例隔离验收通过**：缓存命中可能维持 c token 的成功，a 的拒绝也可能受到 TokenReview 证书校验失败影响。没有为此重跑写入或启动 a。claim 摘要同样只解释 exp 字段，不消除证书与缓存的不确定性。

## 留存与剩余边界

保留两个专用元数据对象，以及原生 Controller 在此 Project `history/` 下产生的快照。最终 Project active、唯一 node cancelled，TaskMeta cancelled；没有新建模型任务或 CR，没有触碰 Manager 配置。该补测独立于原 HTTP 51 项和 TeamLeader 31 项，不加总为新版全套通过数。

Team 消歧与新读取路由范围见[Controller API 实测](controller-api-live.md)。后续已在新版c/d补齐“两个在线实例 × 两个 Team × 同名 Project/Task”的新路由矩阵，见[独立实测](controller-twin-read-live.md)；`includeTasks`内部读取也已有[真实MinIO trace对照](mermaid-storage-read-live.md)。这些后续结果不改写本页原始错误与时钟污染观察。旧状态机、原生模型取消、缓存撤销、multipart 与故障窗口仍仅按[源码差异映射](controller-delta.md)复用旧版各自范围。
