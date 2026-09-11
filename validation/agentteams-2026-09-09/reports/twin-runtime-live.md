# 双实例同名团队与工作目录隔离

2026-09-09。两个实际实例各创建 `live-twin-team`，成员均为 `live-twin-leader` 与 `live-twin-worker`；资源短名称相同，分别属于 `rv-a`、`rv-b`。四个实际容器均来自本轮 Worker 镜像，最终 Ready、团队房间就绪。证据：[twin-runtime-results.json](../evidence/twin-runtime-results.json)。

这里的 Ready 来自逐个成员 `/status`。同一最终快照的 Team 汇总 `readyWorkers` 仍为 0；本轮未证明 Team 汇总计数已收敛，不将成员就绪、房间存在和团队汇总状态混为一个结果。

首次夹具将 bootstrap Matrix 管理员当作 Team.admin，创建 API 接受，但 reconcile 报 Human CR 不存在。修正为每实例先创建独立 `live-twin-human`（L2，仅 accessibleTeams=[live-twin-team]），再以该 Human 的实际 Matrix 身份更新 Team。首次修正错误使用 PATCH，正确方法为 PUT；错误没有改变 Team。完整身份回执仅存 private，公开文件移除密码。[修正证据](../evidence/twin-human-fixture.json)。最终脚本已按此依赖顺序调整；本轮实际 160.688 秒包含失败与修正，不能当作干净启动耗时。

## 实际部署边界

- 四成员的 Docker 网络分别只有 `rv-a-net` 或 `rv-b-net`；Matrix 用户完整 ID 和房间 ID 均带各自域。
- Worker 只挂自身 auth 卷；工作目录在容器文件系统中。不能由“实例有 agentfs 卷”推断 Worker 工作目录也是持久挂载，后续重建恢复须独立验证。
- 两 Manager 控制台分别绑定 `127.0.0.1:28099/38099`，Controller 所发布端口也仅本机。
- **原生 Worker 发布的 8088 端口 HostIp 为空，由 Docker 对所有接口发布随机宿主端口**。因此“本轮所有子容器端口仅绑定 localhost”不成立。真实 inspect 已保留；尚未修改产品以消除此差异。
- 四成员的 Memory、NanoCpus、CpuQuota 均为 0；与独立 Worker 的 cgroup/CPU 负载反证一致，不能证明强制资源隔离。

## 同一 Git 来源的实际文件隔离

[shared-repo-isolation.py](../scripts/shared-repo-isolation.py)新建只含一个文本文件的本地 bare Git 仓库，通过仅连接两验证网络、无宿主端口的只读临时 HTTP 服务提供**同一 URL**。a/b 实际 Worker 各在相同容器内路径 clone，初始 commit 都是 `f04d1b6f92967ddf27358cd6b5a25175697271a2`。

仅在 a 的 clone 修改文本、创建 `only-a.txt` 并作本地 commit 后，a 为 `35e0879cfc4412f317e476e8ebff5cd966c4153a`，b 与只读 origin 仍为初始 commit；b 不存在 `only-a.txt`。这确认这两个实际 clone 的文件和 Git ref 没有互相覆盖。临时服务在 finally 核对容器 ID/标签后停止并移除，夹具源与两个 clone 保留。[原始证据](../evidence/shared-repo-isolation.json)。

Git 操作由验证脚本执行，不是模型工具调用，没有写真实 GitHub；它不证明生产 GitHub 授权、分支映射或 Attempt 工作目录政策已经实现。只读服务同时加入两网络是为了本实验共享代码来源，不代表两实例可相互直接访问控制面。

模型并发与重启恢复有独立报告；本文件不把 Ready、文件隔离或配置名称扩展为整体 AT-09 通过。
