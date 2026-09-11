# 新版镜像构建

基线`517caff9280242a00a4d4c06365352b9e41659c6`。在独立`runtime/build-source`使用官方Dockerfile构建Controller、embedded和Manager；Dockerfile SHA均与干净upstream相同，[镜像及输入指纹](../evidence/image-build-manifest.json)。

| 镜像 | 构建 | 证据 |
|---|---|---|
| `repomesh-validation/controller:517caff9` | 成功，exit0 | [日志](../evidence/controller-image-build.log)、[退出码](../evidence/controller-image-build.exitcode) |
| `repomesh-validation/embedded:517caff9` | 第二次成功，exit0 | [首轮错误](../evidence/embedded-image-build.log)、[正确上下文日志](../evidence/embedded-image-build-02.log)、[退出码](../evidence/embedded-image-build-02.exitcode) |
| `repomesh-validation/manager-qwenpaw:517caff9` | 成功，exit0 | [日志](../evidence/manager-image-build.log)、[退出码](../evidence/manager-image-build.exitcode) |

[准备脚本](../scripts/prepare-build.py)复制干净源码，并按Makefile前置要求将`manager/agent`复制到Controller构建目录；不修改upstream。Controller的Docker构建上下文为`build-source/agentteams-controller`。

embedded第一次错误使用相同子目录上下文，官方Dockerfile引用的`manager/agent`、`shared/lib`等不存在，因此构建退出1。改用`build-source`根上下文、保持同一Dockerfile和同一新Controller镜像后成功。首轮失败保留，不能归为上游缺文件。Manager也使用根上下文。

Manager官方Dockerfile会复制Controller的`agt`，因此即使Manager runtime源码未变也重新构建，避免携带旧CLI。其QwenPaw主版本仍按官方定义固定2.0.1，但其他未锁定依赖会重新解析，必须在离线冒烟和实际配置测试记录真实版本，不能假定依赖与09-09相同。构建中的Node版本不满足部分npm包engine要求的警告保留，不修改官方镜像以隐藏警告。

Worker没有复制此次变更的Controller二进制，相关构建输入无差异，因此使用09-09固定镜像并明确复用来源；不重新贴新版标签假装重构。部署脚本会核对其实际image ID。

Dockerfile的`AGENTTEAMS_AUTH_TOKEN_FILE`为令牌文件路径，不是令牌值。BuildKit的SecretsUsedInArgOrEnv告警按原样保留，构建没有传入业务凭据或模型密钥。镜像成功构建只证明构建完成，不代表运行或业务验收通过。
