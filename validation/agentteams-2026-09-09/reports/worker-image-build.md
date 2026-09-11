# QwenPaw Worker 镜像构建记录

日期：2026-09-09。源码基线：AgentTeams `eeaab64391ccaec9118e84977f538aefd40720d6`。

## 构建输入与范围

在 `runtime/build-source` 副本使用官方 `qwenpaw/Dockerfile` 原样构建，目标镜像 `repomesh-validation/qwenpaw-worker:eeaab643`。未修改 `upstream`，未装系统服务，未使用业务凭据。Dockerfile 默认 QwenPaw 包版本是 **2.0.1**；最新 AgentTeams 提交与最新 PyPI 包不是同一个概念，本实验服从当前上游官方构建定义。

## Windows 打包兼容修复

初始阻碍：WindowsApps 的 `python3` 别名不可用；`.cmd` 映射单行可运行但 Ruby `Open3.capture3` 的多行 Python `-c` 内容经 cmd 丢失；主机 `zip` 不支持上游使用的 `-y`。

仅在构建副本三份 Ruby 辅助脚本把命令字符串 `"python3"` 改为 `ENV.fetch("AGENTTEAMS_BUILD_PYTHON", "python3")`。本次进程设置 `AGENTTEAMS_BUILD_PYTHON=D:/Anaconda3/python.exe`，使 Ruby 直接调用原生 exe，完整保留多行参数。进程 PATH 前置既有隔离 `build-tools/zip.cmd`（退出1），触发**官方脚本本来提供的 Python zip fallback**。没有改变打包内容、绕过官方 validator 或修改系统 PATH。

三份辅助脚本是 TeamHarness build、TeamHarness validate、WorkerFlow build；完整变更见[Windows构建辅助补丁](../scripts/worker-packaging-windows.patch)，该补丁只应用于构建副本。执行官方 builder 后，TeamHarness validator 返回 `ok: qwenpaw teamharness 0.1.0`；生成 TeamHarness 120691 字节、WorkerFlow 22709 字节 ZIP。另独立读取 ZIP，检查 CRC、所有成员路径、单一顶层 manifest、所有 `.py` 语法并记录 SHA-256。

证据：[官方打包日志](../evidence/qwenpaw-packaging.log)、[产物完整性和manifest](../evidence/qwenpaw-packaging-verification.json)。

## 镜像构建

从 `runtime/build-source` 执行：

```powershell
docker build --progress plain --build-context shared=./shared/lib -f qwenpaw/Dockerfile -t repomesh-validation/qwenpaw-worker:eeaab643 .
```

构建完成，退出 **0**。镜像标识：`sha256:4951052caa5ee7e3ea33a823f5f630de358bda31cd672d1d4a736d88d2ed0d58`。原始日志：[qwenpaw-image-build.log](../evidence/qwenpaw-image-build.log)、[退出码](../evidence/qwenpaw-image-build.exitcode)、[实际镜像inspect](../evidence/qwenpaw-image-inspect.json)。[Dockerfile身份对照](../evidence/qwenpaw-dockerfile-identity.json)确认构建副本与上游文件SHA256相同。

## 构建后冒烟检查

在镜像临时容器中执行，均使用`--rm --network none`，不挂业务目录或凭据。结果见[命令与退出码](../evidence/qwenpaw-smoke-summary.json)。

- 实际 Python **3.11.15**、QwenPaw **2.0.1**、qwenpaw-worker **0.1.0**、AgentScope **2.0.4.post1**、wrapt **1.17.3**、QwenPaw instrumentation **0.6.1**。见[版本回读](../evidence/qwenpaw-smoke-python-metadata.log)，完整依赖保存在[pip freeze](../evidence/qwenpaw-smoke-pip-freeze.log)。
- `pip check`退出0，报告无依赖冲突；`qwenpaw --help`、`mcporter --help`、`skills --help`、`nacos-cli --help`均退出0。
- 安装目录中存在 TeamHarness、WorkerFlow、Matrix Channel 三个插件manifest，见[镜像内插件清单](../evidence/qwenpaw-smoke-installed-plugins.log)。官方Dockerfile的插件安装步骤已实际执行成功。
- npm实际包为`mcporter@0.13.10`、`skills@1.5.25`、`@nacos-group/cli@1.1.2`。构建时`commander@15.0.0`声明Node>=22.12，而基础镜像Node为20.19.2，产生EBADENGINE警告。上述CLI可启动，但不能据此证明全部子命令兼容，后续使用场景仍应覆盖。没有为消除警告改动官方Node版本。
- 初始冒烟误用`nacos --help`，因无该可执行文件退出127。读取包bin映射后确认实际名称为`nacos-cli`，纠正命令后退出0；原始失败日志保留，这属于验证脚本命令名错误，不是镜像缺包。

镜像构建及离线冒烟完成，不代表真实模型调用、Matrix通信、配置热更新或RepoMesh业务门禁已经通过。
