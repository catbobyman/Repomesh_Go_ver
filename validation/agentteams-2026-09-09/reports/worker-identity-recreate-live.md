# 删除同名重建后的旧 Worker 身份

日期：2026-09-09。版本：`eeaab64391ccaec9118e84977f538aefd40720d6`。仅创建、删除并同名重建本轮专用 Worker `coverage-identity-recreate-f4228d9b`，使用实际 QwenPaw 镜像、既有 `deepseek-chat` 配置；没有发送模型任务，没有操作其他 Worker、Manager 或 Controller 生命周期。

**真实删除重建后，旧 SA 身份在 Controller 认证缓存有效窗口内仍可访问同名新 Worker；跨过 5 分钟窗口后旧 SA status/ready 均变为 401。旧 Matrix token 仍可完成 whoami，而旧 MinIO 凭据已无法读写。** 三种身份的撤销语义不同，不能以其中一种代替另外两种判断。

## 方法与证据

资源编排使用 Controller 管理身份；权限探针使用容器实际投影的自身 SA token、Matrix token 和存储密钥，分别在重建前私密快照，重放时保持字节不变。存储请求由标准库 SigV4 客户端签名，未经过会刷新凭据的 `mc` 包装器。只访问此 Worker 专用对象 `agents/coverage-identity-recreate-f4228d9b/validation-identity-f4228d9b/probe.json`。

[主实验脚本](../scripts/worker-identity-recreate-live.py)、[不可刷新存储探针](../scripts/identity-storage-snapshot.py)、[缓存窗口脚本](../scripts/worker-identity-cache-window.py)、[公开脱敏时间线](../evidence/worker-identity-recreate-live.json)、[主实验退出码](../evidence/worker-identity-recreate-live.exitcode)、[缓存窗口退出码](../evidence/worker-identity-cache-window.exitcode)。凭据仅保存在排除提交的 private 状态中，公开证据不含 token、密钥或原样 TokenReview 对象。

## 删除与身份变化

17:05:25 UTC 原生 POST 创建返回 201；17:05:47 DELETE 返回 204；17:05:51 独立确认 Worker CR=404、ServiceAccount=404、Docker 容器不存在，随后才于 17:05:52 用完全相同短名称重新创建。

| 标识 | 删除前 | 同名重建后 |
|---|---|---|
| Worker CR UID | `340d319d-8227-465e-8fdc-141a0ee7dd8c` | `d2f0e129-6bd3-482b-b554-f6448817951a` |
| ServiceAccount UID | `344874e7-a428-46c7-8484-a46a32ef9562` | `72a403b8-7207-47f7-9cef-893902a9dad8` |
| Docker ID 前缀 | `845aace484a9` | `2424b3b982ce` |
| StartedAt UTC | 17:05:27.793675403 | 17:05:54.8704811 |

SA token、Matrix token、存储 secret 均发生变化；存储 access key 相同。相同 access key 不代表相同凭据仍有效。完整 Docker ID 与镜像 SHA 保存在公开证据中。

## 同一快照的实际权限

| 时点及身份 | 自身 status | 自身 ready | Matrix whoami | 专用对象 GET / PUT |
|---|---:|---:|---:|---|
| 删除前旧身份成功基线 | 200 | 204 | 200 | 200 / 200 |
| 删除完成后旧身份 | 404，Worker 不存在 | **204** | 200 | 403 / 403，`InvalidAccessKeyId` |
| 同名重建后旧身份 | **200** | **204** | 200 | 403 / 403，`SignatureDoesNotMatch` |
| 同名重建后新身份 | 200 | 204 | 200 | 首次 GET 404 `NoSuchKey`；PUT 200；再 GET **200** |

旧身份在删除完成后拿到的 status 404 是业务资源不存在，并非认证失败；同一时刻 ready 仍返回 204。新凭据最初的对象 GET 404 是对象不存在，随后写入、读取成功，不能误判成新身份没有存储权限。旧 Matrix whoami 返回相同账户 `@coverage-identity-recreate-f4228d9b:rv-a.matrix.invalid`；这里只测账户认证，没有发消息，也没有测试该旧 token 的房间写入权限。

17:06:38 直接向嵌入式 Kubernetes 发 TokenReview 绕过 Controller 认证缓存：旧 token 因实际 SA UID 与 token claim UID 不一致被拒绝，新 token `authenticated=true`。旧结果的 `authenticated` 字段被服务端省略，公开证据显示 null 并保留明确 UID mismatch 错误；不把 null 本身当作独立错误码。

## Controller 缓存窗口

源码 [authenticator.go](../upstream/agentteams-controller/internal/auth/authenticator.go) 默认缓存 TTL 为 5 分钟；命中时直接返回缓存身份，命中不延长到期时间。实验未重启 Controller、未清缓存、未轮换 token。

有界进程以首次实验观察到旧 token 成功的 **17:05:46.145105 UTC** 为锚点，观察至该时刻 +330 秒，间隔最多 30 秒。这个锚点不是服务端精确入缓存事件：Worker 启动自报可能已经提前填充缓存，实验没有对其插桩。因此只报告实际响应转换所在的采样区间，不宣称精确毫秒的撤销延迟。

| UTC 时间 | 距锚点秒数 | 身份及路由 | 实际结果 |
|---|---:|---|---|
| 17:07:26—17:09:56 | 100.174—250.279 | 旧 SA GET status，每 30 秒 | 每次 200 |
| 17:10:26.439 | 280.294 | 旧 SA GET status | **200** |
| 17:10:56.465 | 310.320 | 旧 SA GET status | **401** |
| 17:11:16.146 | 330.000 | 旧 SA GET status | 401 |
| 17:11:16.178 | 330.033 | 旧 SA POST ready | **401** |
| 17:11:16.215 | 330.070 | 新 SA GET status | **200**，Ready / running |
| 17:11:16.482 | — | 旧 Matrix whoami | **200**，相同账户 |
| 17:11:16.815 | — | 旧存储 GET 专用对象 | **403**，`SignatureDoesNotMatch` |

因此，本次旧 SA 通过 Controller 的可接受窗口确实结束：最后一次成功和首次拒绝落在锚点 +280.294 至 +310.320 秒之间。独立 TokenReview 的 UID mismatch，加上未清缓存的实际 HTTP 转换，与默认 5 分钟认证缓存一致；不能把短窗口内的 200/204 表述为旧 SA 永久有效。缓存进程正常退出 0。

## Ready 的含义与范围

[lifecycle_handler.go](../upstream/agentteams-controller/internal/server/lifecycle_handler.go) 的 Ready handler 通过权限中间件后按 Worker 短名称设置内存标记，没有在该 handler 重新检查 CR UID、容器 ID 或运行代次；status 则读取当前 CR 并聚合 backend 状态。这与“删除后旧身份 ready=204，同名重建后旧身份 status=200”的实际结果一致。新容器的 Ready 展示不能据此当作新代次独立初始化证明。

本实验覆盖一次真实原生删除与同名重建，区别于[同一容器 stop/start](worker-ready-restart-live.md)。没有实现或验证 RepoMesh Attempt 租约，没有测试所有其他 API、过期 JWT、任意跨 Worker 授权或永久撤销性质。旧 Matrix token 有效和旧存储拒绝都仅指本次观察区间。

最终 17:11:23 UTC 独立 Docker inspect：专用新容器仍为 `2424b3b982ce…`、StartedAt 仍为 17:05:54.8704811、running=true；本轮没有遗留运行中的探针进程。保留这个专用新 Worker 与有限测试对象供复核，没有删除其他资源。
