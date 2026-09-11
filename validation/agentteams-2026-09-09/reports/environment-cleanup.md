# 旧环境清理记录

2026-09-09，状态：独占 AgentTeams 容器已清理；跨项目共享卷待用户确认。

清理前核对 [容器清单](../evidence/environment-before-cleanup.json)，记录镜像、标签、挂载和网络，不保存环境变量秘密。旧镜像均为 v1.2.0。新的 `upstream/` 是 GitHub 当时最新 main 的独立克隆，不复用旧 checkout。

## 已执行

1. 只把旧 Controller 中的模型提供商、URL、模型名和调用凭据保存到忽略 Git 的 `private/provider.json`，供同一服务的后续验证使用；不输出凭据。
2. 先停止旧 `agentteams-controller`，再停止其 Manager、8 个测试 Worker／Leader及 `repomesh-demo-controller-fwd`，避免旧协调器继续创建工作。
3. 移除 Controller、Manager、两个处于 Created 状态的旧 Manager、8 个 Worker／Leader和转发容器，共 13 个。命令额外包含一次误重复拼接的不存在名称，Docker 返回 No such container；实际目标随后均移除，复查未发现旧 AgentTeams 容器。
4. 验证绝对路径后，将 `C:/Users/18092/agentteams-manager` 改名为同父目录下的 `agentteams-manager-retired-20260909`，封存旧会话／工作文件，新的验证不挂载此目录。

## 共享资源限制

删除 `agentteams-data` 时，Docker 明确返回 volume is in use，使用者是另一项目的 `goai-infra-repomesh-api-1`。该容器 Compose 标签指向 `D:/Project4work/GOAI-infra-repomesh/compose.yaml`。没有强行删除这个项目的 API 或数据；已向用户询问是否连带清理旧演示服务。

旧 `agentteams-net` 同样仍被该 API 使用，暂保留。新实例将使用独立命名的网络、卷、存储桶、凭据及工作目录，不能与这些共享旧资源混用。

`D:/Project4work/AgentTeams` 存在未提交研究、原型和笔记，因此保留源码资料。其他无关项目的容器、数据库、镜像及 Docker 数据盘没有清理。旧镜像是缓存，新的 AgentTeams 镜像从最新源码构建并单独命名。

清理范围尚有共享卷待定，不宣称已经清空整台机器或所有旧演示环境。
