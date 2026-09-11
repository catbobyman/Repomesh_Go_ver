# 三份补测报告的独立证据复核

复核日期：2026-09-09。复核者：`controller_contracts` Agent。**我未撰写以下三份报告**；本次只读核对其正文与对应现有 JSON，重新计算部分计数及资源指标，没有重跑测试、访问运行服务或扩大覆盖范围。其他报告不包含在本次复核。

结论：**未发现会改变三份报告主要结论的实质数值错误或超出所列证据的通过声明。** 这属于对已保存证据的一致性复核，不是独立复现实验。

| 报告及证据 | 复核结果 |
|---|---|
| [dag-native-live.md](dag-native-live.md)；[主 JSON](../evidence/dag-native-live-ec283964ba.json)、[transaction JSON](../evidence/dag-native-live-ec283964ba-tx-audit.json) | 确认 46 项检查均成立、17 个就绪阶段；74 条 trace 实际分为 40 次原生工具、32 次 mc、2 次 Matrix HTTP。四类拒绝前后两份图文件哈希一致；assigned 仍候选、submitted 不解锁依赖、最终 Project 节点 completed 而 Task submitted 与正文相符。重复委派复用事件与另行两次 PUT 幂等分开记录，最终四条消息、原事件一次。没有把候选并行或消息去重升级为实际任务并行、执行去重或 RepoMesh Adapter 验收。 |
| [mcp-response-loss-live.md](mcp-response-loss-live.md)；[原始 JSON](../evidence/control-response-loss-fecb288f32.stdout.json)、[summary](../evidence/control-response-loss-fecb288f32.summary.json) | 两次中断均 exit 86、stdout 0 字节；本地及远端均为 Project planned / Task prepared 且无 eventId。重试均 exit 0，四个元数据读回均为 assigned；每任务前后各一个通知事件、发送 helper 两次。空目录用例实际 0 文件，封存的三文件哈希一致。报告准确说明注入是 helper 已收到真实 HTTP 成功响应、delegate 未取得返回值时进程退出，未声称网络丢包、服务重启或消费者恰好执行一次。 |
| [native-regression-load.md](native-regression-load.md)；[a](../evidence/native-regression-load-23cb82e0a1-a.json)、[b](../evidence/native-regression-load-23cb82e0a1-b.json)、[summary](../evidence/native-regression-load-23cb82e0a1-summary.json)、[metrics](../evidence/native-regression-load-23cb82e0a1-metrics.json) | 两边 JUnit 均 76 项，按文件计数 1+15+46+9+5；均 exit 0、无失败或跳过。从原始时间戳重算重叠为 2.069893 秒；从 cgroup 点重算 CPU 为 2.218751 / 2.191663 CPU-s，平均 102.261% / 103.587%，与正文舍入一致。峰值为 597.160 / 602.570 MiB，目录增量均 474 文件、8,409,217 逻辑字节、9,674,752 分配字节；健康样本各 23 个 200，其中测试区间各 9 个，最大延迟 21.224 / 36.350 ms。正文保留组件测试替身、采样窗口、页缓存及短时健康观察边界，没有推导业务负载容量或 AT-12 整体验收。 |

复核不能证明原始执行环境没有未记录因素，也不能替代尚未实现的 RepoMesh 业务许可、调度、租约和副作用去重联调。三份报告当前均已保留这些限制，无需因本次复核改写其主要结论。
