# 单机资源与恢复实测

2026-09-09。本机 Docker Engine 28.0.4 / WSL2，16 个可见 CPU、15.27 GiB 可见内存，cgroup v1。仅测本轮隔离容器；宿主还运行其他项目，未停止它们。以下是低负载验证样本，不能据此承诺最大项目或 Worker 数。

## 采样过程

[原始汇总](../evidence/capacity-summary.json)、[采样器](../scripts/sample-capacity.py)、[汇总脚本](../scripts/summarize-capacity.py)。每次采集 docker stats 后等待 5 秒，实际间隔含约 2–3 秒命令耗时，可能错过间隔内峰值。CPU 的 100% 约为一核，不是整个 16 核宿主的 100%。内存是 Docker 容器记账值；求和不代表唯一物理内存或整机剩余量。

### capacity-model-idle.json

8 组；2026-09-09T16:57:43.338956+00:00 至 2026-09-09T16:58:46.837191+00:00。采样内最大容器内存合计 7447.8 MiB。

| 容器 | 样本 | CPU 均值 / 样本最大 | 内存范围 MiB | 最大 PID 数 |
|---|---:|---:|---:|---:|
| rv-a-controller | 8 | 11.90% / 15.84% | 2224.1–2247.7 | 864 |
| rv-a-manager | 8 | 7.91% / 18.75% | 460.3–469.5 | 44 |
| rv-a-worker-live-runtime-worker-a | 8 | 1.59% / 5.07% | 496.0–496.2 | 32 |
| rv-a-worker-live-twin-leader | 8 | 8.47% / 49.64% | 472.2–473.4 | 44 |
| rv-a-worker-live-twin-worker | 8 | 1.80% / 5.39% | 461.3–461.4 | 34 |
| rv-b-controller | 8 | 10.80% / 19.48% | 1708.0–1947.7 | 853 |
| rv-b-manager | 8 | 5.78% / 15.17% | 422.0–431.2 | 42 |
| rv-b-worker-live-twin-leader | 8 | 4.17% / 12.38% | 471.0–471.3 | 43 |
| rv-b-worker-live-twin-worker | 8 | 2.10% / 7.51% | 468.1–468.4 | 43 |

### capacity-runtime-recovery.json

23 组；2026-09-09T16:50:12.753784+00:00 至 2026-09-09T16:53:16.681968+00:00。采样内最大容器内存合计 7305.0 MiB。

| 容器 | 样本 | CPU 均值 / 样本最大 | 内存范围 MiB | 最大 PID 数 |
|---|---:|---:|---:|---:|
| rv-a-controller | 23 | 36.22% / 303.67% | 1990.7–2168.8 | 877 |
| rv-a-manager | 22 | 10.64% / 102.98% | 25.6–462.5 | 43 |
| rv-a-worker-live-runtime-worker-a | 23 | 6.77% / 84.85% | 470.9–484.2 | 53 |
| rv-a-worker-live-twin-leader | 23 | 2.16% / 14.91% | 472.3–473.0 | 44 |
| rv-a-worker-live-twin-worker | 18 | 12.57% / 99.01% | 155.0–504.4 | 47 |
| rv-b-controller | 23 | 14.46% / 113.27% | 1743.9–1974.3 | 855 |
| rv-b-manager | 23 | 5.45% / 21.44% | 421.8–435.1 | 44 |
| rv-b-worker-live-twin-leader | 23 | 2.16% / 8.45% | 470.9–471.3 | 43 |
| rv-b-worker-live-twin-worker | 23 | 2.51% / 11.54% | 467.8–471.1 | 48 |

### capacity-startup.json

15 组；2026-09-09T16:41:13.298948+00:00 至 2026-09-09T16:43:13.329930+00:00。采样内最大容器内存合计 3859.5 MiB。

| 容器 | 样本 | CPU 均值 / 样本最大 | 内存范围 MiB | 最大 PID 数 |
|---|---:|---:|---:|---:|
| rv-a-controller | 15 | 11.17% / 25.58% | 1890.3–1966.1 | 868 |
| rv-a-manager | 15 | 9.57% / 27.67% | 419.9–442.5 | 45 |
| rv-a-worker-live-runtime-worker-a | 11 | 10.96% / 98.38% | 326.8–470.7 | 42 |
| rv-b-controller | 15 | 10.43% / 18.67% | 978.7–987.7 | 814 |

### capacity-twin-startup.json

15 组；2026-09-09T16:45:13.513185+00:00 至 2026-09-09T16:47:13.540035+00:00。采样内最大容器内存合计 6280.0 MiB。

| 容器 | 样本 | CPU 均值 / 样本最大 | 内存范围 MiB | 最大 PID 数 |
|---|---:|---:|---:|---:|
| rv-a-controller | 15 | 12.72% / 43.85% | 1950.7–2054.1 | 866 |
| rv-a-manager | 15 | 5.96% / 12.84% | 428.1–438.5 | 32 |
| rv-a-worker-live-runtime-worker-a | 15 | 2.26% / 11.07% | 469.4–471.2 | 42 |
| rv-a-worker-live-twin-leader | 15 | 19.25% / 158.09% | 287.2–466.4 | 44 |
| rv-a-worker-live-twin-worker | 1 | 0.00% / 0.00% | 0.0–0.0 | 0 |
| rv-b-controller | 15 | 12.06% / 21.90% | 1888.3–1962.0 | 851 |
| rv-b-manager | 15 | 7.96% / 22.55% | 418.6–433.3 | 43 |
| rv-b-worker-live-twin-leader | 15 | 19.42% / 163.75% | 278.3–470.7 | 43 |

## 响应与恢复

- 两实例基础设施重启至 API 可用约 12.813 / 13.328 秒；该轮未启用 runtime，不能当作完整实例恢复成本。
- [双实例六个模型请求](twin-model-live.md)：观察延迟 3.312–5.578 秒；含 HTTP 与轮询，不是首 token 延迟。四个 Team 请求并发期间 24 个有效 healthz 样本全 200；Manager 并发阶段采样误用路径的限制已单独保留。
- [实际 runtime 恢复](runtime-recovery-live.md)：Worker 14.578 秒、Manager 31.937 秒后回复停机期间保存的 marker；346 个 healthz 样本全 200，b 实例未重启。Worker 55 条 backlog 的完整恢复失败，不能只用最后响应时间认定消息恢复完成。
- Team 从首次尝试到就绪的 160.688 秒包含 Human CR 夹具错误和修正；不是干净启动性能。

## 磁盘和模型用量

[资源清单](../evidence/resource-inventory.json)记录采样时刻、镜像 ID、各容器可写层、挂载、du 和原生 token_usage.json。镜像逻辑大小包含共享层，不相加冒充物理磁盘占用；Controller du 包含服务数据，没有把整个 Docker 虚拟磁盘分摊为项目成本。

原生 token 计数是相应 runtime 累积自报值，包含该环境已有验证调用；不是供应商账单，也不等同当次 marker 的增量。缺失字段或读取失败标为不可用，不记作零费用。请求 deepseek-chat 的直接 provider 冒烟返回模型 deepseek-v4-flash；未据此假定每次 runtime 调用的供应商映射或计价。

### 17:01:56 原生计数快照

采集时间：2026-09-09T17:01:56.604998+00:00。

| runtime | call_count | prompt tokens | completion tokens | 可写层 MiB |
|---|---:|---:|---:|---:|
| rv-a-manager | 5 | 89096 | 216 | 2.70 |
| rv-a-worker-live-twin-leader | 1 | 15724 | 32 | 5.56 |
| rv-a-worker-live-twin-worker | 2 | 30383 | 74 | 5.61 |
| rv-b-manager | 3 | 57137 | 815 | 1.56 |
| rv-b-worker-live-twin-leader | 1 | 15686 | 41 | 5.52 |
| rv-b-worker-live-twin-worker | 1 | 14898 | 70 | 5.53 |
| rv-a-worker-live-runtime-worker-a | 7 | 114228 | 1565 | 5.83 |

这些是该时刻的累计值，不能用 call_count 与六请求数直接相减推定重复执行。Manager准备、其他验证请求及工具循环都可能贡献调用，需按具体trace归属；后续普通reply／thread补测等调用不在这张历史快照内，不能把它作为整个验证期间的最终用量。

## 容量结论与限制

观察范围内两套 Manager／Leader／Worker 可以共同运行并完成少量真实请求，控制面持续响应。但 CPU／内存请求未下发为实际容器限额，原生资源单元也没有 RepoMesh 的全局配额事务。增加 OOM 或长时间压力无法修复这项已确认缺口，本轮没有做破坏性极限测试。

仍需实现并验证全局资源预留、业务预算和实际限制后，再在明确业务负载、模型配额、仓库规模下测试吞吐、尾延迟、公平性、重验证成本和采集开销。本报告不宣布任何固定项目容量。
