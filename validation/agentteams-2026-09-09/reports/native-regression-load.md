# AT-12 固定官方回归工作量的实际运行成本

最终测量 run `23cb82e0a1`，完成于 `2026-09-09T17:12:49Z`。在已运行的 `rv-a-worker-live-twin-worker` 与 `rv-b-worker-live-twin-worker` 中，**同一套 76 项上游官方测试各执行一次，双方均退出 0，76 passed、0 failed/error/skipped**。两份回归实际重叠约 2.070 秒；测试进程均已退出，两个 Worker 的 container ID、StartedAt 保持不变且仍运行。

该结果量化的是固定官方组件回归的成本。没有 RepoMesh 重验证调度、模型调用、业务派工、全局配额争用或最大容量实验。

## 工作量与隔离方式

测试来自本轮锁定上游 `eeaab64391ccaec9118e84977f538aefd40720d6`，原样复制到两个容器各自 `/tmp/native-regression-23cb82e0a1/repo`。没有改测试断言或上游实现。复制文件 SHA-256 清单保存在 [summary](../evidence/native-regression-load-23cb82e0a1-summary.json)。

| 官方测试文件 | 每实例测试数 | 主要覆盖 |
| --- | ---: | --- |
| `test_mcp_workspace.py` | 1 | Worker shared workspace 选择 |
| `test_pull_project.py` | 15 | 权威图拉取、plan 渲染、字段保留与工具入口拉取 |
| `test_trace.py` | 46 | active Task 选择、span 标注、延迟标注、session 隔离、生命周期与 debug 配置 |
| `test_trace_integration.py` | 9 | 真实 OTel SDK 的本地 Task 生命周期 span 导出 |
| `adapters/qwenpaw/test_adapter.py` | 5 | QwenPaw 公共扩展接口注册与适配合同 |

这是**官方组件／本地集成测试原样运行**，其中官方 fixtures 保留了 FakeFilesync、Matrix 通知替身及相关 monkeypatch；OTel integration 使用镜像中真实 OTel SDK。不能将 76 passed 解释为 76 次真实 MinIO、Matrix 或 Worker 业务闭环。测试进程使用清洁环境、独立 HOME/TMPDIR/cache/pycache/basetemp；没有传入容器业务 token、真实共享前缀或模型配置。未修改团队、真实 Task、Controller 配置或生产 venv。

两个镜像的系统 Python 和 QwenPaw Python 均为 3.11.15，均缺 pytest；Ruby 也缺失，所以没有运行 Ruby 工具回归／打包测试。QwenPaw venv 已有 MCP、YAML、OTel 依赖。使用宿主现有纯 Python pytest 9.0.3、pluggy 1.6.0、iniconfig 1.1.1、packaging 25.0、pygments 2.20.0，以及 pytest 顶层 `py.py` shim，复制至测试目录 `deps`，仅通过该进程 PYTHONPATH 加载。**没有下载依赖或安装到生产环境**。事后[依赖复核](../evidence/native-regression-load-dependencies.json)确认原 Python 环境仍无 pytest。自动 pytest 第三方插件加载被关闭。

## 最终测量结果

| 指标 | 实例 a Worker | 实例 b Worker |
| --- | ---: | ---: |
| 官方结果 | 76 passed | 76 passed |
| 进程墙钟耗时，含 pytest 启动 | 2.120 s | 2.070 s |
| pytest 子进程 user+system CPU | 2.137 CPU-s | 2.103 CPU-s |
| pytest 子进程最大 RSS | 69,676 KiB | 65,892 KiB |
| 整个容器采样窗口 CPU 消耗 | 2.219 CPU-s | 2.192 CPU-s |
| 容器平均 CPU，100% 为一个核 | 102.3% | 103.6% |
| 约 100 ms 区间的最高容器 CPU | 132.3% | 129.0% |
| 容器内存：开始／采样峰值／结束 | 521.8／597.2／537.2 MiB | 527.6／602.6／543.4 MiB |
| cgroup memory failcnt 增量 | 0 | 0 |
| 容器 CPU／内存采样点 | 22 | 21 |
| 专属可写目录文件数增量 | 474 | 474 |
| 专属目录逻辑内容增量 | 8,409,217 B，约 8.020 MiB | 8,409,217 B，约 8.020 MiB |
| 专属目录分配块增量 | 9,674,752 B，约 9.227 MiB | 9,674,752 B，约 9.227 MiB |

CPU／内存使用实际容器 cgroup v1 的 `cpuacct.usage`、`memory.usage_in_bytes`、`memory.stat` 与 failcnt，约每 100 ms 采样。容器统计包含已有 QwenPaw 和观测进程，不是纯 pytest 独占消耗；单独的 child CPU 和 max RSS 来自 `getrusage(RUSAGE_CHILDREN)`。CPU 平均窗口 a 约 2.170 秒、b 约 2.116 秒，包括末尾目录统计，与 pytest 墙钟窗口略有差异。内存包含文件页缓存；使用本轮 `memory.usage_in_bytes` 样本的最大值，**没有将容器生命周期累计 max_usage 当作本轮峰值**。采样峰值也不等于连续瞬时真峰值。

目录增长计入测试文件、pytest 临时数据和首次导入生成的 pycache；基线已经包含上游副本、隔离依赖和 input tar，最终 `result.json` 在目录统计完成后才写入，因此没有包含在该增量内。它是两个专属目录的增长，不是整个 Docker 磁盘、镜像拉取成本或长期回归产物累计量。目录和证据保留便于审计，没有后台测试进程残留。

## 并发与健康证据

两个 pytest 进程通过同一开始时刻并行启动，实际重叠 `2.069893` 秒；没有循环制造负载。主机对 a/b API `/healthz` 各约每 200 ms 发起一次真实 HTTP 请求，从启动前持续到两份结果收集结束。

| 健康指标 | a | b |
| --- | ---: | ---: |
| 全观察窗口样本 | 23，全部 200 | 23，全部 200 |
| 在各自 pytest 执行区间内的样本 | 9 | 9 |
| 最大请求耗时 | 21.2 ms | 36.4 ms |

健康路由是已确认的 `/healthz`，没有复用此前误用 `/health` 的样本。这里证明样本中未见故障；短于采样间隔的瞬断、其他用户请求延迟和饱和容量不在结论范围。

## 准备过程的失败与测量修正

1. run `e9c910152d` 的隔离 pytest 副本最初漏了顶层 `py.py`，两边在约 0.515 秒内导入失败，**零测试执行**；进程均退出。原始 [a JSON](../evidence/native-regression-load-e9c910152d-a.json)／[b JSON](../evidence/native-regression-load-e9c910152d-b.json)保留完整错误。宿主收集不存在的 JUnit 时也报错，该轮没有完整健康 summary，不用于资源或健康通过结论。
2. 补齐宿主已有 shim 后，run `87570f7d8b` 两边均 76 passed，耗时各约 2.319 秒，48 个健康请求均 200。但测量器仅识别 cgroup v2，当前实际为 v1，所以该轮没有容器 CPU／内存字段。其 [summary](../evidence/native-regression-load-87570f7d8b-summary.json)及 a/b JSON 保留，不用后验数据补写过去的资源样本。
3. 只修正测量器对 v1 的读取，以新的专属目录运行最终 `23cb82e0a1`，取得上表完整测量。两次成功轮次的测试结果分开保留；最终结论不是把多轮最快值拼成一个结果。未改服务、测试逻辑或生产依赖。

## 证据与 AT-12 边界

原始容器结果：[a](../evidence/native-regression-load-23cb82e0a1-a.json)、[b](../evidence/native-regression-load-23cb82e0a1-b.json)；[JUnit a](../evidence/native-regression-load-23cb82e0a1-a-junit.xml)、[JUnit b](../evidence/native-regression-load-23cb82e0a1-b-junit.xml)；[连续健康与文件摘要](../evidence/native-regression-load-23cb82e0a1-summary.json)；[派生指标与进程／容器身份复核](../evidence/native-regression-load-23cb82e0a1-metrics.json)。执行代码为 [host runner](../scripts/native-regression-load-run.py)、[container runner](../scripts/native-regression-load-container.py)、[只读汇总脚本](../scripts/native-regression-load-summarize.py)。

本次补上 AT-12 的“两个实际 Worker 上，同一套有意义官方回归的并行耗时、CPU、内存、可写目录增长和健康样本”。**仍未验证 RepoMesh 专属重验证任务调度、业务优先级／公平性、全局 last-slot 原子配额、模型与长任务争用、取消回收、硬内存上限或压力拐点**；不能据此给出最大支持人数或将 AT-12 整体标记业务验收通过。
