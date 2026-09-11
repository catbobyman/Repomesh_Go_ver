# 新版 Manager 配置测试脚本预检

2026-09-10。本文件保留的是 **运行前历史计划**；当时脚本仅完成 Python AST 语法检查。之后 CFG01—04 已连接新 c 实例执行完成，实际结果和边界以 [Manager 配置实测](manager-config-live.md) 为准。后续 CFG05 启用与投影验证也记录在该实测报告，本文件不代表当前运行状态。

## 夹具生命周期

Manager 的 API 和 CR Spec 都没有 `containerManaged` 字段；不能套用 Worker 的同名开关。脚本始终创建唯一 `cfg-clear-<nonce>` Manager，指定 `state:Stopped`、`runtime:qwenpaw`，不使用 `default`。

[manager_reconcile_container.go:28](../upstream/agentteams-controller/internal/controller/manager_reconcile_container.go#L28) 对 Stopped 调用 `ensureManagerContainerAbsent`；[welcome:114](../upstream/agentteams-controller/internal/controller/manager_reconcile_welcome.go#L114) 在正常 Docker 状态查询确认容器不运行时跳过欢迎流程。Stopped 仍可先经过 Provider 解析、基础设施和配置写入，**不等于只写一条孤立 CR**，因此脚本只允许新 c 实例，且要求 Controller 环境 `AGENTTEAMS_MANAGER_ENABLED=false`。

每次断言均独立读取嵌入式 Kubernetes CR，固定 Manager UID、Stopped 状态、model/provider/runtime，并检查该专属派生容器不存在。如果出现容器，测试失败而非自行处理其他资源。最后仅把本 CR 复原成初始 model、空 Provider 和 Stopped，保留证据；不删除 Manager，以免触发其可能共用的实例基础设施删除逻辑。

## 运行前限制

- Controller 固定为 `rv-c-controller`，宿主只访问 `http://127.0.0.1:48090`。
- 必须显式 `--execute --expected-image <经过主任务审查的新 embedded tag>`；没有 `--execute` 时仅输出静态计划。
- 执行前检查容器 exact name、Running 状态、实际 image ID 与指定镜像相同、验证标签以及 localhost 48090 → 8090 绑定。默认验证标签值为 `agentteams-2026-09-10`，如主部署使用别值需显式指定并审查。
- 自有 API token 仅从 c 容器读取进内存；嵌入式 Kubernetes token 在 c 容器内部使用，不输出。CR 只返回安全字段，不复制完整 Secret、环境或配置。
- 使用 c 镜像中的 `agt`，记录实际可执行文件路径与 SHA-256。不会访问旧 a/b 实例。

## 已编码的用例

1. 创建非空绑定；省略字段只更新 model；显式 null 保留绑定。
2. 数字、布尔、对象、数组四种错误类型均要求 HTTP 400，随后独立 CR 未改变。
3. 非空替换、仅空串清空、重复清空、model 与清空同时更新。
4. CLI `--model-provider=` 单独更新、非空值、未提供该选项时省略字段。
5. CLI 缺 name／没有更新字段时本地失败，不发 HTTP 请求。

为确认 CLI 空串确实发出，单次 CLI 在 c 容器里的临时 localhost HTTP observer 上运行。observer 只接受本夹具路径及 model/modelProvider 两个字段，记录安全 JSON，然后转发给真实 `127.0.0.1:8090` Controller，返回真实响应；不是返回假成功的 HTTP stub。临时监听器在该 Python 子进程 finally 中关闭。每次 CLI 后再直接读取真实 CR；Manager GET 不返回 modelProvider，因此不以 GET 字段缺失作为清空证据。

## 尚未纳入运行模式的配置投影

脚本只报告 REST／CLI／CR 层，不将 Stopped Manager 的 API 成功说成实际 runtime 已加载。CFG-05 的“清除失效绑定后默认 Gateway 生效”需要先明确：c 实例默认模型与已授权 Provider 已配置、专属 Manager 的有效配置可独立定位，且与后续工作 Manager 不混用。

配置文件投影若在 Stopped 状态已经产生，可先只读检查生成文件；若要验证 runtime 真正加载，必须另行安排这个专属 Manager 的启动，确认容器 image/network/workspace、默认 Gateway 和安全配置读回。该启动模式尚未编码，脚本不会自行启用 Manager、修改 Provider 或发送模型任务。清空绑定也不等于撤销旧 Provider 凭据或路由授权。
