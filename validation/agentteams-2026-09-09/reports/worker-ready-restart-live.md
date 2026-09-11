# 同一Worker运行重启与旧身份Ready报告

日期：2026-09-09。仅对授权的`rv-a-worker-live-runtime-worker-a`执行一次`docker stop -t 5`与一次`docker start`，finally恢复运行；未删除资源或容器、未改CR state／allowlist、未轮换凭据，也未操作其他实例生命周期。

结论：**容器确实停止时，重启前取得的Worker自身ServiceAccount token仍可读取自身状态并提交Ready（204）；同一容器启动后，同一旧token仍能提交Ready，当前投影token与旧token相同。** 这证明本次同容器运行重启不自动使该身份失效，Ready报告没有按该次运行代次拒绝旧身份。

## 身份与原始证据

开始前只读取Worker实际投影的`/var/run/secrets/agentteams/token`到宿主验证进程内存，所有HTTP请求使用这个相同token。日志只记录token是否相同的布尔值，不保存或打印token。

[脚本](../scripts/worker-ready-restart-live.py)、[完整Docker与HTTP时间线](../evidence/worker-ready-restart-live.json)、[退出码0](../evidence/worker-ready-restart-live.exitcode)。

## 真实时间线（UTC）

| 时间 | 操作与结果 | 同时Docker状态 |
|---|---|---|
| 16:54:47 | 开始，旧StartedAt=16:41:38 | running=true |
| 16:54:50 | 唯一一次stop完成 | running=false，status=exited |
| 16:54:51.036 | 旧token GET自身/status：200，phase=Running、containerState=stopped | 仍明确停止 |
| 16:54:51.270 | 旧token POST自身/ready：**204** | 仍明确停止 |
| 16:54:51.502 | 再GET/status：200，phase=Running、containerState=stopped | 仍明确停止 |
| 16:54:52.433 | finally已start恢复 | 同一容器ID、StartedAt变成16:54:51.893，running=true |
| 16:54:52.670 | 比较当前投影token | **same_projected_token=true** |
| 16:54:52.884 | 同一旧token再次POST自身/ready：**204** | running=true |
| 16:54:53.134 | GET/status：200、phase=Ready、containerState=running | running=true |

每个HTTP响应后均独立Docker inspect，确认停止窗口没有被Controller自动拉起破坏。没有反复stop或延长停止窗口。

容器ID全程为`e51d7a087095fcedcade03df7b30b7759d8ed708881d1b8e644cfa38d75f3050`。最后Docker确认running=true。

## 解释与限制

停止时status接口没有把Ready报告直接显示成Ready，因为它也检查backend是否running；但phase仍是CR里的Running，需结合containerState=stopped解读。Ready报告本身返回204，不能证明发报时进程活着或新runtime已处理模型请求。

重启后观察到Ready涉及原有内存Ready状态及本轮旧token自报，并非独立验证新runtime完成初始化。这个实验故意检验旧报告入口，不应把其结果当作新运行代次真实就绪的凭证。

**仅覆盖同一Worker、同一容器ID的stop/start。** 未删除重建ServiceAccount或Worker CR，未测试过期token、凭据主动轮换或token撤销，不能扩展为这些情形下旧token也一定有效。它也没有验证完整RepoMesh Attempt租约机制；若要求运行代次隔离，需增加代次绑定和独立可核查就绪证据后再测。
