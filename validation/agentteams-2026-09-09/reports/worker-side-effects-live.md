# 实际 Worker 文件副作用与结果元数据验证

日期：2026-09-09。上游提交：`eeaab64391ccaec9118e84977f538aefd40720d6`。涉及AT-08／11及受控执行边界。

结论：原生取消会阻止后续ack／submit，但不会停止本实验放入真实Worker容器的独立文件写进程。另复现了**取消后Project节点仍可被accept改为completed、Task元数据仍为cancelled**，以及**产物缺失／Matrix上传失败仍可得到submit ok=true与SUCCESS**。必须分别核查流程状态、产物发布结果和业务验收证据。

## 实验边界

在实际运行的`rv-a-worker-live-runtime-worker-a`内创建有限heartbeat进程，仅写`/tmp/repomesh-worker-side-effects/f5834a8696/heartbeat.txt`，没有访问用户仓库或GitHub。进程由验证脚本通过docker exec启动，**不是模型发起的任务，也没有RepoMesh执行租约或进程关联机制**。它检验“仅更新原生任务取消状态是否会撤销一个已存在Worker进程的文件写能力”，不能代替完整模型任务取消联调。

TeamHarness调用在Controller容器内执行未修改上游`server.call_tool`，通过真实mc／MinIO及Matrix工作。复用此前专用夹具房间与存储布局，新增唯一Project `sidefx-project-f5834a8696`及三个新task_id，不覆盖此前夹具证据。任务分配给夹具Matrix用户，未向实际Worker发送模型任务。密钥只通过标准输入传入，输出按已知token脱敏。

代码：[主脚本](../scripts/worker-side-effects-live.py)、[容器内原生工具脚本](../scripts/worker-side-effects-container.py)。完整原始结果：[worker-side-effects-live.json](../evidence/worker-side-effects-live.json)，执行[退出码0](../evidence/worker-side-effects-live.exitcode)。

## 1. 取消与实际进程写入

先通过真实delegate／ack使夹具Task进入in_progress；启动真实Worker容器内的heartbeat进程，再调用原生cancel_task。取消响应ok=true、synced=true，远端Task为cancelled。

进程PID1976；取消前7行，取消完成时15行，之后25行，进程仍存活。每行只是递增数字，不包含业务数据。finally读取PID并核对`/proc/<pid>/cmdline`包含本次唯一夹具路径后发送SIGTERM；docker exec退出143。后续检查原PID不存在，Worker容器仍running。

此结果证明原生取消并不自动关联并终止该独立进程；不证明模型工具自身的取消处理一定相同，也未验证原生取消后网络token、Git权限或模型预算是否撤销。Worker、Controller和Manager未被终止或重启。

## 2. 迟到提交与接受结果

同一已取消Task随后调用：

| 操作 | 实际响应 | 远端状态 |
|---|---|---|
| ack_task | ok=false；cannot update terminal task: cancelled | 保持cancelled |
| submit_task（SUCCESS） | ok=false；cannot update terminal task: cancelled | 保持cancelled |
| projectflow.accept_task_result（accepted=true） | **ok=true** | **Project任务节点completed；独立Task元数据cancelled** |

所以taskflow的终态检查不能推广为所有工具写路径都有相同防护。此处是对真实取消状态的后续调用，尚未涉及多线程网络竞态；已经足以复现跨对象终态不一致。RepoMesh应在接受结果入口校验当前Task／Attempt身份与取消状态，不能仅信Project节点。

## 3. 缺失产物与上传失败

使用两个独立新Task，保持原本正常MinIO读写：

| 场景 | submit_task返回 | publishedArtifacts | 后续事实 |
|---|---|---|---|
| 声明合法任务内路径missing.txt，实际没有文件 | **ok=true、synced=true、status=submitted、result_status=SUCCESS** | status=failed；artifact file not found；mxcUri／eventId为空 | accept_task_result仍ok=true，Project节点completed |
| 本地有36字节文件，仅本次Python进程将Matrix上传token替换为无效值 | **ok=true、synced=true、status=submitted、result_status=SUCCESS** | status=failed；Matrix artifact publish failed: HTTP401；mxcUri／eventId为空 | 原生Task元数据已持久化，不能称为Matrix交付成功 |

上传失败使用真实Matrix HTTP401，未修改服务器、用户真实token或mc存储凭据，并在finally恢复该进程原token。`synced=true`表示任务共享存储同步，不等于Matrix附件发布；`result_status=SUCCESS`是调用者声明，缺少文件或发布失败并不自动把它变为失败。

上述附件错误在返回体中并未隐藏，正确接入应读取并处理`publishedArtifacts`，再核实可读取的产物与来源。不能把最外层ok直接显示为已交付，也不能认为原生accepted就是独立验收。

## 过程记录与剩余范围

第一次启动脚本时，此前Controller临时目录中的MCP副本已不在，import失败；当时未创建任何heartbeat进程或Task。随后把未修改上游MCP复制到本实验独占`/tmp/repomesh-sidefx-mcp`，再次执行完成。初始脚本错误保留于[initial-harness-error.log](../evidence/worker-side-effects-initial-harness-error.log)，不归因于上游业务故障。

本实验未执行模型请求、生产仓库写入、GitHub交付、跨实例访问、真正租约撤销或多Attempt竞争。它补强原生取消和结果元数据边界，不能将完整AT-08／11判为通过。
