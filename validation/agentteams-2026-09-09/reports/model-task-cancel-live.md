# 同一原生Task的实际模型工具进程取消实验

日期：2026-09-09。AgentTeams提交：`eeaab64391ccaec9118e84977f538aefd40720d6`。AT-08取消边界。

**结论：同一个真实委派Task触发模型执行后，原生cancel_task已把该Task持久化为cancelled，但其实际模型工具进程继续写文件。停止进程的是随后验证脚本的明确清理SIGTERM，不是原生取消。** 本次闭环使用真实模型启动writer，没有用外部harness进程代替。

## 同一任务的关联证据

| 身份 | 本次唯一值 |
|---|---|
| 实际发送身份 | `@manager:rv-a.matrix.invalid`，使用运行Manager投影token |
| Project | `modelcancel-project-MCANCEL_507f3a36e7` |
| Task | `modelcancel-task-MCANCEL_507f3a36e7` |
| 唯一委派事件 | `$guWw_Vc14yGh5i238rZhcuqrBXbqsnOBrT3EpJ8a6aE` |
| 实际接收Worker | `@live-runtime-worker-a:rv-a.matrix.invalid` |
| 个人房间 | `!AsuaO41O0nFzAc0djd:rv-a.matrix.invalid` |
| 唯一文件目录 | `/root/agentteams-fs/agents/live-runtime-worker-a/.qwenpaw/workspaces/default/validation-modelcancel-MCANCEL_507f3a36e7` |
| heartbeat内容 | 每行`MCANCEL_507f3a36e7` |
| 模型启动PID | **1806** |

原生TeamHarness `delegate_task`在实际Manager容器执行，使用未修改上游工具及Manager自身Matrix／存储身份，返回ok=true、synced=true及上述事件ID；远端Task记录同一事件ID、目标Worker和spec路径。请求正文的完整spec在Matrix精确读回一致。总共一次delegate，没有另发普通聊天请求来替代Task委派。

实际Matrix响应显示Worker模型调用`execute_shell_command`启动Python，命令包含上述唯一目录。独立容器内观察到该目录下PID文件及nonce心跳，且`/proc/1806/cmdline`匹配唯一目录。验证脚本从未创建writer进程或写heartbeat内容。

## 实际时间线（UTC）

1. **17:00:47**：原生委派成功，Task状态assigned，通知已发送给实际Worker。
2. Worker模型开始执行前台Python工具命令；请求明确每秒一行、25次结束且最长30秒，不后台启动、不自动重试、不访问网络／仓库。
3. 观察到至少两行nonce和活PID后，先读取同一Task的远端元数据，再原生调用该Task的cancel_task。
4. 取消返回ok=true、synced=true；独立MinIO读回Task及Project节点均为cancelled。
5. 取消完成后的第一次观察：PID1806仍活，**5行**；3秒后同一PID仍活，**8行**。路径匹配、所有行nonce均一致。
6. **17:00:59**：finally清理，核对PID的cmdline包含唯一目录后，验证脚本仅向PID1806发送SIGTERM。
7. **17:01:00**：PID不存在，最终9行。Worker模型收到工具exit143，随后只读检查目录并报告Task ID、PID1806和9/25行；未自动重启writer。
8. 最后再次读取原生元数据：Task仍cancelled。

模型最终描述“被取消／中断”，但仅凭这句话不能认定原生cancel已停止进程。独立时间线明确显示cancelled之后继续写入，真正停止来自步骤6的harness清理。该区别已保留在证据中。

## 执行状态的额外边界

模型进程实际运行时，远端Task仍为 **assigned**，没有观察到ack_task把它更新为in_progress。此次取消作用于原生assigned Task，并没有注入或伪造ack。它仍然是同一次原生委派驱动的真实模型工具进程；同时说明原生任务元数据不自动等同于实际执行状态。

因此，本次证明的是**该默认集成路径下，Task取消没有自动联动停止已经执行的模型shell工具进程**。未覆盖另加执行租约／取消适配器后的行为，也不证明每一种runtime、所有工具或不同状态均有相同行为。

## 范围、清理与交付

新Project／Task及目录均为本轮独占，未覆盖旧实验、用户仓库或外部GitHub。实际writer约9秒后已清理，未超过30秒；宿主总等待界限180秒，实际本轮约14秒完成主实验。未重启Worker或任何实例。

[完整原生Task／Matrix事件／PID／字节行数证据](../evidence/model-task-cancel-live.json)、[运行退出码0](../evidence/model-task-cancel-live.exitcode)、[宿主观察与清理脚本](../scripts/model-task-cancel-live.py)、[实际Manager原生工具脚本](../scripts/model-task-cancel-manager.py)。

该结果补齐先前“独立进程取消”和“模型文件执行”之间的实际关联。配置人类管理员被白名单拒绝的缺口仍保留；本例使用已有获准Manager身份，不代表人类权限问题已解决。
