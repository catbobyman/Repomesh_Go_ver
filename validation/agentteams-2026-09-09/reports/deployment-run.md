# 最新源码部署执行记录

2026-09-09，进行中。GitHub默认分支main已在线确认并克隆到`upstream/`，提交为`eeaab64391ccaec9118e84977f538aefd40720d6`。

## 构建

[prepare-build.py](../scripts/prepare-build.py)复制干净源码到独立`runtime/build-source`，按官方Makefile先补`agentteams-controller/agent`。不修改上游checkout。[上下文证据](../evidence/build-context.json)记录提交与Dockerfile指纹。

首次Controller构建漏掉Makefile此前置目录，报`/agent: not found`，过程保留于`evidence/controller-image-build.log`。补齐后第二次构建成功，日志为`evidence/controller-image-build-02.log`。

| 镜像 | 当前结果 |
|---|---|
| repomesh-validation/controller:eeaab643 | 官方Dockerfile构建成功；ID `sha256:9c89e9800590e12b824703e5d62aa05d41259f5ae48b93015a1a0abd7ee6ddfa` |
| repomesh-validation/embedded:eeaab643 | 官方Dockerfile引用上行新Controller构建成功；ID `sha256:84ec2dfd1c8062785e867f2d6f6ce0875d1a67fab7106d54f257c2326966a150` |
| repomesh-validation/qwenpaw-worker:eeaab643 | 构建已完成，镜像／包／CLI检查见[Worker构建报告](worker-image-build.md) |
| repomesh-validation/manager-qwenpaw:eeaab643 | 官方 Dockerfile 构建成功；ID `sha256:3d1d4d42b4329577bf5f45743f4aad86da112704e85cca0df8ea7b0373e696ea`；[包与 CLI 检查](manager-image-build.md) |

Worker插件打包经历Windows python3应用别名和zip参数不兼容；构建辅助修补、原始验证器、ZIP完整性及官方Dockerfile一致性均有[单独记录](worker-image-build.md)。QwenPaw包遵循当前AgentTeams Dockerfile固定2.0.1，不随意升级依赖。

## 双实例实际启动

已运行`python scripts/deploy-instances.py --apply --wait-seconds 20`，两个容器均启动成功并返回HTTP health200。[真实部署清单](../evidence/deployment-instance-inventory.json)包含container/image ID、独立卷、网络、工作目录、端口与实际状态。

- `rv-a-controller`：本机API28090、Gateway28080；b对应38090、38080。
- 所有发布端口绑定127.0.0.1。各自新data/agentfs卷、宿主workspace/host-share、Matrix domain和secret；不挂旧工作目录或旧共享卷。
- 初期Manager=false且无provider，以便把基础设施、真实传输和模型行为分别验证。
- 两边Matrix版本、MinIO健康和Controller资源API实测可用；空Worker／Manager列表已确认。
- 默认`supervisorctl status`无法找到默认socket；此命令不是该配置下的有效健康探针，改以各服务真实端点和Controller API检查。

两个实例重启后的持久化已验证，见[真实Controller报告](controller-live-report.md)和[真实Matrix报告](matrix-live-report.md)。该轮重启发生在启用 Manager 之前，不能替代 runtime 恢复验证。

## Manager 与 Worker 后续启用

两个 Controller 已分别经 `enable-managers.py` 读回预检后替换，保留本实例的全部卷、密钥、端口与网络，仅加入已有 provider、启用 Manager、将子容器挂载路径改为实际 Docker daemon 路径。原部署清单是首次启动快照；后续身份以 `evidence/rv-a-enable-53f195c69712.json`、`evidence/rv-b-enable-00218d0aac0b.json` 为准。预检修复了 `docker inspect` 挂载数组顺序不稳定造成的误拒绝，比较仍保留全部条目和字段。

实例 a 的 Manager 已真实回复中文唯一 marker，见 [Manager 模型报告](manager-model-live.md)。实际启用 QwenPaw 内置 `matrix` 通道，已安装的 `agentteams_matrix` 插件没有被当前 Manager 配置启用；两个通道的组件证据不可混用。Manager 控制台实测绑定 `127.0.0.1:28099`。

实例 a 的 [真实 Worker](worker-runtime-live.md) 已进入 Ready，实际 Gateway 模型配置及插件目录可读。但请求的 `0.5 CPU / 512Mi` 未投影为 Docker/cgroup 限额，2.5 秒 CPU 探针证实未限额。这是已复现的原生缺口，不能标记为资源强制验收通过。

双实例相同名称 Team／Leader／Worker 正在独立夹具中验证；运行与资源证据持续保存。

## 模型连接前置检查

已有模型连接配置经忽略Git的private文件读取。一次最小真实请求返回200和`VALIDATION_OK`，请求模型`deepseek-chat`，服务端返回模型名`deepseek-v4-flash`，总计20 tokens，耗时18.047秒。证据：[provider-smoke.json](../evidence/provider-smoke.json)。这是直接provider检查，不等同AgentTeams Gateway或runtime已通过。
