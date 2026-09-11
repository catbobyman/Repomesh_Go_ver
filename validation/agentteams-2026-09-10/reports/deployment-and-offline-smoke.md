# 新版 c 隔离部署与 Manager 离线检查

阶段说明：本报告记录初始部署阶段。下文 Manager 关闭、provider 未注入、容器 ID 与健康快照都是该阶段事实；后续已启用 Manager 并更换 Controller 容器，当前配置与 CFG-05 结果见 [Manager 配置实测](manager-config-live.md)。不把初始状态当作当前状态。

2026-09-10，新上游提交 `517caff9280242a00a4d4c06365352b9e41659c6`。本任务完成了无网络临时容器离线检查，以及全新单实例 c 的基础部署。**基础设施和实际认证 API 已可用；Manager 初始关闭、未注入 provider、没有发送模型请求。** 这不等于 Manager 应用启动、配置回归、模型或 RepoMesh 业务验收通过。

## 镜像与内置 CLI

| 用途 | 实际镜像 | Image ID |
| --- | --- | --- |
| Controller | `repomesh-validation/controller:517caff9` | `sha256:a593143db4881af3e4f2118d30a63c801d8bef9812ffcc94ef8fadd452b3cd42` |
| embedded | `repomesh-validation/embedded:517caff9` | `sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f` |
| Manager | `repomesh-validation/manager-qwenpaw:517caff9` | `sha256:8cf1059295e6c172ba30d7e732cc382169678fcb44b2e7f56c159203b0c20b6a` |
| Worker，源码相同复用 | `repomesh-validation/qwenpaw-worker:eeaab643` | `sha256:4951052caa5ee7e3ea33a823f5f630de358bda31cd672d1d4a736d88d2ed0d58` |

前三个镜像由主任务完成新构建；本任务核对实际镜像身份与 CLI。Worker 是 09-09 的既有镜像，**不是新版新构建**。比较旧 `eeaab643...` 与新提交的 `manager`、`qwenpaw`、`copaw`、`plugins`、`shared/lib`、`.dockerignore`，git diff 文件清单为空。该事实支持原 runtime 源输入未变，但不表示复用镜像刷新了依赖或重新生成了 artifact。

虽然 Manager runtime 源码和 Dockerfile未改，Dockerfile 会从 Controller 镜像复制 `agt`；因此本次没有复用旧 Manager。新 Manager 和新 Controller 镜像中的 `/usr/local/bin/agt` 实际 SHA-256 均为：

```text
61caf405a7ff309b872eeff200ee78aae9c9eb0526f051cbc97c0a5592e151e7
```

## 有限离线 smoke

[脚本](../scripts/manager-offline-smoke.py)使用 `docker run --rm --network none`、不挂持久卷、不传 provider；Manager 临时容器退出后已确认删除。另一个 `--rm --network none` Controller 容器只读取 `agt` 哈希。未修改 shell、源码或镜像依赖。

| 检查 | 实际结果 |
| --- | --- |
| `qwenpaw --help` | 退出 0 |
| `agt --help` | 退出 0 |
| `python -m pip check` | 退出 1；唯一输出为 `copaw-worker 1.0.3 requires copaw, which is not installed.` |

原官方 Manager Dockerfile 对 copaw-worker 使用 `--no-deps`，说明其 bridge 用于 QwenPaw，跳过 CoPaw runtime；该背景不能把非零 `pip check` 改写为全绿。本任务没有为消除元数据缺项安装 copaw。`--help` 也只证明命令入口可加载，不证明外部工具、长驻服务或真实模型调用成功。

实际包版本如下，均由新 Manager 镜像 `importlib.metadata` 读取：

| 包 | 版本 |
| --- | --- |
| QwenPaw | 2.0.1 |
| AgentScope | 2.0.4.post1 |
| MCP / FastMCP | 1.30.0 / 3.4.7 |
| copaw-worker | 1.0.3 |
| loongsuite site-bootstrap / distro / otel-util-genai | 各 0.9.0 |
| loongsuite instrumentation-qwenpaw / instrumentation-agentscope | 各 0.9.0 |
| OpenTelemetry API / SDK / exporter-otlp | 各 1.44.0 |
| Pydantic / HTTPX | 2.13.5 / 0.28.1 |

官方 Dockerfile 未锁住全部依赖。不能因为 Manager 源码没改，就认定新镜像的全部 runtime 依赖与 09-09 一致；后续应以本次版本实测开展回归。[完整离线输出和版本证据](../evidence/manager-offline-smoke.json)。

## 全新实例 c

[部署脚本](../scripts/deploy-instances.py)仅接受 `--instances c`。已执行：

```powershell
python -X utf8 validation/agentteams-2026-09-10/scripts/deploy-instances.py --apply --instances c --wait-seconds 60
```

命令退出 0，在单次 exec 中完成，没有遗留部署运行 session。资源均带 `repomesh.validation.run=agentteams-2026-09-10`、`repomesh.validation.instance=c` 标签；同名资源复用必须通过标签、镜像、配置、端口、网络及数据卷检查。

- 新容器 `rv-c-controller`，ID `cf4981c840f1fb6584fcdf2f27a28c229b72974445f324f386e28aa797ef4e71`。
- 新网络 `rv-c-net`，新卷 `rv-c-data`、`rv-c-agentfs`，本次均为 created；没有复用 a/b 的旧卷或密钥。
- 新目录 `runtime/instance-c/workspace`、`runtime/instance-c/host-share`；新私密材料写入本轮 `private/rv-c-*`。
- localhost 端口：gateway 48080、API 48090、Higress console 48001、Element 48088；48099 仅保留给后续 Manager console。
- Manager 关闭、provider 未注入；Matrix domain 为 `rv-c.matrix.invalid`，存储 bucket 为 `rv-c-storage`。
- 新 `private` 目录沿用旧工具的 ACL 方式：关闭继承，授予当前用户、SYSTEM、Administrators。命令成功；没有输出密钥。后续测试可读取本轮凭据文件，不能取旧 a/b 密钥。

[dry-run](../evidence/deployment-dry-run.json)是构建尚未完成时的原始准备快照，当时 c 资源、private 均未创建，新 embedded/Manager 镜像尚未出现；保留该历史事实，没有覆盖成事后的状态。[实际部署 inventory](../evidence/deployment-instance-inventory.json)记录创建结果与镜像身份。

## 初始化与认证检查

10:25:48 UTC 的首次快照中，API `/healthz`、内部 Matrix `/_matrix/client/versions`、MinIO `/minio/health/live` 均为 HTTP 200；紧随其后的 `agt get workers/managers` 当时退出 1。初始 stderr 未保存，所以**不能确定反推为 token 未生成、URL 或某个具体权限错误**，也没有只凭健康检查放行。

10:26:15 UTC 的[后续原生 CLI 复核](../evidence/deployment-post-start-cli.json)中，两条命令均退出 0，stderr 为空，workers/managers 各为 0。期间本任务没有改 URL、token、权限或配置。

10:26:56 UTC 再直接读取容器内原生 `AGENTTEAMS_AUTH_TOKEN_FILE=/var/run/agentteams/cli-token`，以实际非空 token 对 `http://rv-c-controller:8090` 发起真实只读 HTTP：

| 请求 | 认证 | HTTP |
| --- | --- | --- |
| `/api/v1/workers` | 实际 CLI token | 200 |
| `/api/v1/managers` | 实际 CLI token | 200 |
| `/api/v1/workers` | 不带 Authorization | 401 |

这确认实际 token 与 URL 可用，而且成功不是因为 API 匿名开放。此时 workers count 已为 1、managers 为 0；主任务并行回归已可能创建资源，不能把不同时间点的计数差异误报为部署混入旧卷。该观察不输出 Worker 配置或 token。[认证 HTTP 原始状态证据](../evidence/deployment-authenticated-health.json)。

现可开展新版 Controller API 与 Manager 配置回归；模型验证仍未执行，本报告不宣称其通过。

以上为初始部署完成时的结论。后续 Manager 启用、新 Controller 容器与 CFG-05 实验以 [Manager 配置实测](manager-config-live.md) 为准；本页保留原容器身份、未注入 provider 等历史记录，不覆盖后续状态。
