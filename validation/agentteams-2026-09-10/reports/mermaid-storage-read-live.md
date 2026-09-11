# Mermaid includeTasks：真实 MinIO 读取观测

本轮补上了先前仅靠源码和响应对比尚未证明的内部读取行为。实例 c 的真实 Controller 请求中，JSON `includeTasks=true` 前后正对照均读取目标 TaskMeta；Mermaid `includeTasks=true` 与 `false` 的各自有限观测窗口内，均读取 ProjectMeta，未观察到目标 TaskMeta 的 HEAD 或 GET。不是将输出相同推断为没有读取。

## 实际执行

- 成功 run：`ddb9ad7a3979`，4 次真实工作流 HTTP 请求全部 200，20/20 检查通过，进程单调时钟耗时 7.489 秒。
- Controller：`rv-c-controller`，容器 ID `ef17ce71456d5bec7c8f882fd982b3f47985d2ce65cb4b35ac8ea15e00f8d2ca`；embedded image ID `sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f`，对应本轮固定源码 `517caff9280242a00a4d4c06365352b9e41659c6`。
- 使用 Controller 本地真实 admin token，仅在进程内存读取，请求 `http://127.0.0.1:8090/api/v1/projects/trace-project-ddb9ad7a3979/workflow`。
- 用真实 `mc cp` 写入独占全局元数据：Project `trace-project-ddb9ad7a3979`、Task `trace-task-ddb9ad7a3979`，另加 Project 目录下的 probe 对象。没有创建 Worker、Team、业务任务执行或调用模型。

| 按实际顺序请求 | HTTP | ProjectMeta HEAD / GET | TaskMeta HEAD / GET | 窗口后 probe GET |
|---|---:|---:|---:|---|
| JSON `includeTasks=true`，前正对照 | 200 | 1 / 1 | 1 / 1 | 已观察 |
| Mermaid `includeTasks=true` | 200 | 1 / 1 | 0 / 0 | 已观察 |
| Mermaid `includeTasks=false` | 200 | 1 / 1 | 0 / 0 | 已观察 |
| JSON `includeTasks=true`，后正对照 | 200 | 1 / 1 | 1 / 1 | 已观察 |

两个 JSON 响应的 `tasks_detail` 均包含此 Task 的实际持久元数据。请求前后独立 `mc cat` 读取三个对象，SHA-256 全部一致。

## 观测方法与范围

在 Controller 内运行真实 `mc admin trace --json --all agentteams`，启动后先发送独占 probe GET，确认 trace 中捕获成功才开始 API 测量。每个窗口从发起对应 API 前开始，到收到完整 HTTP 响应后 1.25 秒结束；窗口后再 GET probe，确认监听仍在工作。各请求前另留 0.3 秒间隔。前后两次 JSON 正对照用于检查目标 TaskMeta GET 确实能被当前 trace 捕获。

原始 trace JSON 可能含请求信息，只经过管道进入内存，没有落盘或回显。公开事件严格保留 method、精确目标 path、status、服务器时间与接收时间。路径只接受本次 ProjectMeta、TaskMeta、probe 三个完整 key；其他团队同时运行的流量被丢弃。当前 mc 的扁平 JSON 提供 `api` 而非直接的 HTTP method，因此解析器将已知 `s3.GetObject` / `s3.HeadObject` 映射为 GET / HEAD；未知操作不被当作 GET。此映射在证据中明确记录。

这是特定夹具、具体部署版本、有限窗口内的 S3 读取观测。不能据此保证所有版本、所有项目形态或任意延迟后台作业永远不访问 TaskMeta，也不能将原生工作流渲染算作 RepoMesh 跨仓权限、Issue 归属或重验证调度已实现。没有 fake transport、monkeypatch 或模型调用；元数据是直接写入的隔离测试夹具。

## 首轮失败、监听清理与时间

首轮 `b0d62ab76cd4` 的 mc trace 已有事件，但解析器没有适配扁平 `api` 字段，method 为 null，故 readiness 检查失败；没有发出四个测量 API 请求。保留该失败证据，修正解析器后以新 nonce 执行上述成功实验，没有修改上游代码或服务。

两轮监听分别为容器内 PID 16164、16375，均在 `finally` 向自身进程组发送 SIGTERM 后等待结束（exit 143）。额外只读确认 `/proc/16164`、`/proc/16375` 均不存在。临时本地上传文件由 TemporaryDirectory 清理；六个 nonce MinIO 元数据对象保留供复核，没有触碰其他测试对象。未修改 MinIO audit 配置、重启服务或安装任何依赖。

成功轮实际进程时间戳为 `2026-09-10T03:54:06.399181+00:00` 至 `03:54:13.888507+00:00`。Docker 的现有 StartedAt 为 `2026-09-10T10:34:25.597638797Z`，与当前进程墙钟存在先后倒置，保留原值；耗时仅使用同进程 monotonic，不用这些跨来源时间计算恢复时间或推断服务重建。

## 证据与复现脚本

- [成功轮安全原始事件、HTTP 响应及检查](../evidence/mermaid-storage-read-live-ddb9ad7a3979.json)
- [首轮解析器 readiness 失败记录](../evidence/mermaid-storage-read-live-b0d62ab76cd4.json)
- [实际执行脚本](../scripts/mermaid-storage-read-live.py)：通过 `docker exec -i rv-c-controller python3 -` 将脚本送入容器执行；stdout 仅输出安全证据 JSON。
- 源码补充依据：`upstream/agentteams-controller/internal/server/project_handler.go` 的 `GetProjectWorkflow` 在 Mermaid 分支调用 `buildWorkflow(meta, team, false)`，JSON 分支传入请求的 includeTasks。此源码解释与实测一致，实测结论依据上表真实 S3 事件。
