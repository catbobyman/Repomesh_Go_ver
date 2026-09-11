# Manager QwenPaw 镜像与离线冒烟验证

日期：2026-09-09。AgentTeams提交：`eeaab64391ccaec9118e84977f538aefd40720d6`。

结论：镜像已构建，离线CLI启动、桥接模块导入、Manager工具注册所需前置检查通过。**不能标记全部检查通过：`pip check`退出1，原因是官方镜像有意不安装`copaw`，但安装的`copaw-worker`仍声明此依赖。** 未为追求全绿修改依赖或重建镜像；实际服务启动仍需后续验证。

## 构建来源

主Agent使用官方`manager/Dockerfile.qwenpaw`构建，日志保存在[manager-qwenpaw-image-build.log](../evidence/manager-qwenpaw-image-build.log)。本检查没有构建／重构镜像或启动已有实例。

- 标签：`repomesh-validation/manager-qwenpaw:eeaab643`
- 实际镜像ID：`sha256:3d1d4d42b4329577bf5f45743f4aad86da112704e85cca0df8ea7b0373e696ea`
- [实际镜像inspect](../evidence/manager-smoke-image-inspect.json)
- [Dockerfile SHA256对照](../evidence/manager-smoke-dockerfile-identity.json)：构建副本文件与上游原样一致。

## 最小实验与结果

每条命令都在`docker run --rm --network none --entrypoint ...`临时容器中执行，不挂载业务目录和凭据。没有调用模型、访问Matrix或修改当前实例。[全部命令、退出码](../evidence/manager-smoke-summary.json)保留原始结果。

| 检查 | 结果 | 解释 |
|---|---|---|
| 镜像内Python／包版本读取 | 退出0 | Python3.11.15、QwenPaw2.0.1、copaw-worker1.0.3、AgentScope2.0.4.post1、wrapt1.17.3、loongsuite-instrumentation-qwenpaw0.9.0 |
| pip check | **退出1** | 唯一输出为`copaw-worker 1.0.3 requires copaw, which is not installed.` |
| pip freeze | 退出0 | 全部已解析依赖留证，以便复现非锁定依赖版本 |
| qwenpaw --help | 退出0 | QwenPaw CLI可加载，不证明服务已Ready |
| agt --help | 退出0 | 镜像内Controller CLI可执行，不证明API认证／连通性 |
| mcporter --help | 退出0 | CLI可执行，不证明工具路由可用 |
| node --version与npm全局包 | 退出0 | Node20.19.2；mcporter0.13.10、skills1.5.25、@nacos-group/cli1.1.4 |
| 镜像内插件manifest | 退出0 | `/opt/agentteams/plugins`存在Matrix Channel与Manager Tools两个插件，版本均0.1.0 |
| bridge／run_copaw_app／四个Manager工具模块导入 | 退出0 | 本检查范围内未因缺少copaw失败 |
| Manager插件register调用 | 退出0 | 用仅记录注册的API替身执行真实插件register，得到projectflow、taskflow、message、filesync四工具；不实际执行这些工具 |

Manager插件与Worker不同：此镜像带Matrix Channel及Manager Tools源目录，启动脚本再向工作区投影。这里只验证镜像内存在和工具可导入／注册，**未证明实际持久工作区已完成安装加载**。

## pip check失败及版本差异

官方Dockerfile明确用`--no-deps`安装`copaw-worker`作为QwenPaw配置转换桥接模块，并注释不安装`copaw==1.0.2`。但copaw-worker元数据仍声明该依赖，因此pip check不能通过。这是已解释的上游打包元数据缺口，不能据此直接判断Manager无法启动，也不能把它忽略为全绿。真实bridge和Manager工具导入通过，只支持这些执行路径不依赖copaw的较窄结论。

Manager instrumentation没有像Worker一样固定0.6.1，本次解析为0.9.0；Nacos CLI解析为1.1.4，而Worker固定1.1.2。当前镜像虽来自同一AgentTeams源码提交，依赖版本并不完全一致，应在后续运行行为和复现记录中保留这一差异。

关键证据：[包版本](../evidence/manager-smoke-python-metadata.log)、[pip check](../evidence/manager-smoke-pip-check.log)、[完整freeze](../evidence/manager-smoke-pip-freeze.log)、[插件manifest](../evidence/manager-smoke-plugin-manifests.log)、[桥接及工具注册](../evidence/manager-smoke-bridge-tools.log)。

## 仍未覆盖

Matrix登录与消息流、Controller认证、配置转换的完整真实输入、启动脚本热更新、模型请求、工具副作用、Ready回报及重启恢复，均需运行实验。本报告支持进入该阶段，不能替代这些验收。
