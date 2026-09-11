# 原生观测查询与本机采集耗时：三轮只读实测

2026-09-09，采样窗口 `17:20:56.694083—17:21:03.671565 UTC`。补充 AT-12 的原生查询／采集开销证据，不测 RepoMesh 状态产生到入库、业务判断或页面可见的延迟。

三轮中，实例 a/b 的 Controller Worker 列表请求均返回 HTTP 200；每轮对本次固定选中的 11 个 `rv-a-*` / `rv-b-*` 容器运行一次 `docker stats --no-stream`，均退出 0、返回 11 个样本。没有修改资源状态、发起模型请求或重启服务。准备阶段仅只读获取自有 Controller 凭据和一次容器清单，不计入下面查询时间。

| 查询 | 第 1 轮 | 第 2 轮 | 第 3 轮 | 三点中位数 |
|---|---:|---:|---:|---:|
| Controller a `GET /api/v1/workers` | 19.382 ms | 5.504 ms | 4.199 ms | 5.504 ms |
| Controller b `GET /api/v1/workers` | 4.425 ms | 4.664 ms | 27.020 ms | 4.664 ms |
| Docker stats，固定 11 容器 | 2769.724 ms | 2058.126 ms | 2077.989 ms | 2077.989 ms |

每轮顺序为 a HTTP、b HTTP、Docker stats；共 6 次 Controller GET 和 3 次 stats，没有为改善结果追加轮次。三点的最小／中位／最大值仅描述本次样本，不是分位数、性能上限或服务保证。

## 计时含义

- 每条记录同时保留 UTC 开始／结束时间和 `perf_counter_ns` 单调时钟 elapsed；耗时以单调时钟为准。UTC 仅用于关联，两个墙钟读数的差可能与高分辨率计时略有差异。
- **Controller 查询结束**指响应体已全部读入宿主 Python 内存，计时不包含随后 JSON 解码。它包含客户端调用、本机 HTTP 传输和 Controller 处理，不是隔离出来的服务端 CPU 时间。响应 Date header 不是业务状态产生时刻。
- **Docker 采集结束**指 Docker CLI 子进程已经退出，stdout 已完整进入宿主采集器。它包含子进程创建、Docker Engine stats 等待及采集返回，不包含之后 JSON 解码；没有把这个值当作容器自身状态更新延迟。
- 这段窗口内其他已运行的验证服务继续存在，因此不是无背景负载的基准。stats 本身也产生少量观测开销。

与此前 [capacity-live.md](capacity-live.md) 中约 2–3 秒 Docker 采样命令开销的说明一致，本次补上了每次明确的查询开始／完成与耗时，不依赖从相邻采样间隔反推。

## 输出摘要与一次解析错误

Docker 输出保留安全字段：容器名称／ID、CPU%、内存使用、PID、网络和块 I/O，以及原 stdout 字节数和 SHA-256；固定容器清单也已保存。HTTP 保留状态码、响应 Date、正文长度和 SHA-256，不保存令牌、header 值或完整业务配置。

首版探针把 Worker 列表响应按数组／`items` 解码，而真实 Controller 使用 `WorkerListResponse{Workers, Total}`，见 [resource_handler.go:200](../upstream/agentteams-controller/internal/server/resource_handler.go#L200)。因此首版输出中的 `worker_count:0` 与空 Worker 摘要是探针错误，**不能解释为实例没有 Worker**。计时在 JSON 解码前结束，HTTP 200、正文长度／哈希及耗时不受此错误影响。a 三轮正文均为 3282 字节，b 均为 1694 字节。

保留首版原始文件，并在独立纠正副本中把失效的 Worker 数量与明细标为不可用。由于没有保存原始 HTTP 正文，不伪造历史数量或用新查询补作旧快照。脚本解析已修正，但没有再执行；因此严格维持三轮上限。

- [纠正标注后的完整记录](../evidence/control-observation-latency-20260909T172056Z.corrected.json)：9 次查询原始时间戳、单调耗时、安全摘要及解析错误说明。
- [首版原始记录](../evidence/control-observation-latency-20260909T172056Z.json)：保留错误字段供追溯；引用 Worker 内容时须采用上面的边界。
- [采集脚本](../scripts/control-observation-latency-live.py)：只读 GET、Docker inventory 和 stats，无资源写入或业务事件生成。

## 未验收的业务延迟

当前仓库没有 RepoMesh 业务采集器、状态持久化服务或真实页面订阅链路。因此“上游状态产生 → RepoMesh 采集 → 入库／事件发布 → 页面可见”的各段及总延迟仍未验收，也没有用虚构流程代替。后续实现后须统一来源时间与采集／入库／可见时间的定义，再测排队、故障恢复、重复观察和实际负载；本次数据只填补原生查询及本机获取结果的有限成本证据。
