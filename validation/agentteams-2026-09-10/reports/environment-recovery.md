# 2026-09-10 环境恢复与旧验证停用

恢复任务时Docker Engine命名管道不存在，官方`docker desktop status`无法读取状态。第一次`docker desktop start --timeout 60`最终退出1，提示仍在启动、超过期限；没有仅据该超时反复重启。

只读检查发现后台进程和Docker WSL发行版仍运行，宿主日志`com.docker.backend.exe.log.0`在`2026-09-10T10:12:28Z`再次记录`OTel manager: removing stale socket`及`userAnalyticsOtlpHttp.sock: The file cannot be accessed by the system`。这个文件创建于09-09的上次恢复过程。说明[昨天的处理](../../agentteams-2026-09-09/reports/docker-startup-repair.md)恢复过运行，但没有消除跨次启动复发的深层原因。

使用官方`docker desktop stop --force --timeout 20`成功停止，确认没有backend进程后，逐一验证以下绝对路径都位于用户Docker目录，且目标不存在：

- 源：`C:/Users/18092/AppData/Local/Docker/run`
- 保留目标：`C:/Users/18092/AppData/Local/Docker/run-stale-20260910`

通过PowerShell `Move-Item -LiteralPath`封存运行目录并创建新的空`run`，随后官方start退出0，Engine再次返回28.0.4。未删除故障文件、镜像、容器卷或Docker数据盘，未恢复出厂设置。复发原因仍未定位，不能宣称永久修复。

引擎恢复后，旧验证a/b的Controller和Manager因原有策略运行，Worker大多停止。为避免新版验证混用旧运行资源，使用[停用脚本](../scripts/retire-prior-runtime.py)逐个核对09-09保存的11个容器ID和镜像ID，先停Controller再停其余运行容器；全部确认停止。证据见[停用记录](../evidence/prior-runtime-retirement.json)。旧容器、卷、镜像和文件均保留，不作为新版验收环境。

该动作只处理本任务已有记录的验证容器，不涉及另一个项目`goai-infra-repomesh-api-1`。新版使用独立c实例与新卷／网络／密钥；旧共享卷的连带清理仍须单独核对，不能从旧验证容器已停止推断共享卷已删除。
