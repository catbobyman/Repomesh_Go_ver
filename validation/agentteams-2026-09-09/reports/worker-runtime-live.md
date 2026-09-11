# 实际 Worker 启动、配置与资源限额验证

日期：2026-09-09。实例a：Controller localhost:28090；Worker：`live-runtime-worker-a`；容器：`rv-a-worker-live-runtime-worker-a`。

结论：实际Worker成功启动并报告Ready，指定镜像、模型配置和插件已投影。**请求的0.5CPU／512Mi限额未落实到Docker及cgroup；短时CPU探针实际获得约1核。** Ready只作为本次真实Worker回报的证据，本实验没有发送模型任务。

## 方法与证据

使用实例a管理员token认证调用真实Controller REST创建唯一Worker，token只读入进程内存，嵌入式Kubernetes管理员token通过容器内curl的标准输入传递，没有写入报告或打印。未重启Controller、Manager或操作其他Worker。

创建体：runtime=qwenpaw、image=`repomesh-validation/qwenpaw-worker:eeaab643`、model=deepseek-chat、state=Running、containerManaged=true、resources.limits.cpu=0.5、resources.limits.memory=512Mi。

[完整HTTP／CR／Docker／容器内证据](../evidence/worker-runtime-live.json)、[脚本退出码](../evidence/worker-runtime-live.exitcode)、[启动验证脚本](../scripts/worker-runtime-live.py)、[就绪后读回与有界CPU探针](../scripts/worker-runtime-postready.py)。

## 观察结果

| 层次 | 实际结果 | 能证明什么 |
|---|---|---|
| REST创建 | 返回201 | Worker资源已接受保存，不等价于已启动 |
| 嵌入式Kubernetes CR | 保存runtime、image、model、Running、containerManaged=true，limits.cpu=`0.5`、limits.memory=`512Mi` | 接口资源请求没有在持久化阶段丢失 |
| Docker实际容器 | StartedAt `2026-09-09T16:41:38.289948479Z`，running，OOMKilled=false | 实际启动成功，镜像ID与构建产物一致 |
| 生命周期HTTP | ensure-ready先返回200／Running，随后status于16:41:51Z报告Ready、containerState=running | Running与Ready是不同阶段，本次约13.5秒后观察到Ready |
| 真实包版本 | QwenPaw2.0.1、qwenpaw-worker0.1.0、AgentScope2.0.4.post1 | 运行容器版本与构建冒烟一致 |
| Controller标准配置 | Worker目录runtime/runtime.yaml的member绑定自身名字、Matrix用户及个人房间；desired model=deepseek-chat、providerId=agentteams-gateway | 配置已投影至实际Worker容器 |
| QwenPaw消费文件 | `.qwenpaw/workspaces/default/agent.json`的active_model=`agentteams-gateway/deepseek-chat` | 模型选择已转换至runtime使用的工作区文件；未触发模型请求 |
| 实际工作区插件 | `.qwenpaw/plugins`包含TeamHarness、WorkerFlow、Matrix Channel三个manifest | 插件已从镜像进入运行工作区 |

镜像ID：`sha256:4951052caa5ee7e3ea33a823f5f630de358bda31cd672d1d4a736d88d2ed0d58`。

## 资源限额：确定不符合请求

Docker实际HostConfig：Memory=0、MemoryReservation=0、MemorySwap=0、NanoCpus=0、CpuQuota=0、CpuPeriod=0、CpuShares=0、PidsLimit=null。

本机Docker实际使用 **cgroup v1／cgroupfs**。最初读取v2的`cpu.max`／`memory.max`为空后，检查`/proc/self/cgroup`与Docker info，改读真实v1对应文件，不能将“文件不存在”直接解释为无限制。

- `cpu/cpu.cfs_quota_us = -1`
- `cpu/cpu.cfs_period_us = 100000`
- `memory/memory.limit_in_bytes = 9223372036854771712`
- `pids/pids.max = max`

这些值不是请求的0.5CPU／512Mi限制。一次2.5秒、单线程的有界忙循环获得 **2.4996655进程CPU秒／2.500011墙钟秒≈1.00核**，进一步反证0.5CPU限制没有生效。没有运行内存OOM或长时间压力测试。宿主机／Docker VM总容量仍会限制整体可用资源，不能把容器未设限理解为物理资源无限。

## 网络与挂载

该容器只连接`rv-a-net`，NetworkMode也是`rv-a-net`。Docker inspect记录的唯一挂载是专属命名卷`rv-a-worker-live-runtime-worker-a-auth`到`/var/run/secrets/agentteams`，读写。没有把项目仓库或Manager工作区挂入该Worker；工作区由运行配置／对象存储初始化。这只验证当前容器的配置事实，不代替跨实例网络和存储攻击面验收。

## 范围结论

AT-01的创建→持久化→运行配置投影、AT-07的真实Running→Ready链路已取得本用例证据；AT-09的原生Docker资源投影缺口已经从组件发现升级为实际运行复现。Controller重启、旧Attempt写入、预算门禁、双入口争抢和模型执行仍需其他专项，不能因本次Ready宣称它们通过。
