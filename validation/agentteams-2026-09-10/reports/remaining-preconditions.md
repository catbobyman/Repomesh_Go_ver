# 收尾前提的只读复核

取证时间 `2026-09-10T10:34:55Z`。本次仅扫描工作树、读取文档／已有证据，并精确查询旧命名卷的消费者；**没有访问或修改实例 c 的配置／资源、运行新测试、启动容器或请求模型**。CFG-05 由其他执行方负责且任务发出时仍在运行，不把其报告的过渡状态当作新缺陷或本审计完成事项。

[安全结构化证据](../evidence/remaining-preconditions.json)保存扫描命令、退出码、结果、仅包含允许字段的卷消费者、所审阅文档的哈希／修改时间和剩余范围判断。它是一个时间点的前提审计，不是新的产品验收结果。

## 1. 当前非 validation 工作树没有 Go 产品源码

工作目录 `D:\Project4work\Repomesh_Go_ver`，实际执行：

```powershell
rg --files --hidden --no-ignore -g '!validation/**' -g '!.git/**' -g '*.go' -g 'go.mod' .
```

退出码 **1**，stdout 和 stderr 均为空，匹配文件 **0**。`--no-ignore` 使被普通 ignore 规则忽略的文件也纳入查找；显式排除 `validation/**` 以及 Git 元数据，避免把上游 checkout、测试辅助 Go 程序或构建副本当成 RepoMesh 产品实现。

这个扫描只证明上述工作树范围内没有 `.go`／`go.mod`，不是对所有语言、其他仓库或外部部署的否定。结合当前 [HANDOFF](../../../docs/current/HANDOFF.md)第 5、55、116 行明确记录的“没有 RepoMesh Go 产品实现”“真实接口／权限／数据库事务未实现”，当前没有可用于完整 AT 业务验收的本仓库受控适配实现。未借用另一项目的运行容器替代本项目证据。

## 2. 旧卷仍有运行中的跨项目消费者

先执行精确卷过滤，再对候选 container inspect 的 Mounts 做二次判断，要求 `Type=volume` 且 `Name=agentteams-data`，不是仅凭名称相近匹配：

```text
docker ps -a --filter volume=agentteams-data --format {{.ID}}
docker container inspect <返回的容器ID>
```

公开结果仅保留以下字段；没有输出环境、凭据、其他挂载或容器配置：

| name | id | state | mountdestination |
| --- | --- | --- | --- |
| `goai-infra-repomesh-api-1` | `dc5e0235fa51b5f7ad7bee5171cb35fff0f8c8fc7eee3b25eb97388551b475c9` | `running` | `/agentteams-data` |

因此旧卷仍被这个 GOAI 命名的运行容器实际挂载。此次只确认挂载消费者，未探测应用读写流量或推断其数据价值。要完成原先“全部旧环境清空”仍需解决该跨项目占用及相应清理授权；本任务未停止它、卸载卷或删除数据。

## 3. 原清单剩余项是否还有应立即补跑的独立原生项

对照 [09-09 完成度审计](../../agentteams-2026-09-09/reports/completion-audit.md)、原验收清单 §3—5，以及本轮 Controller／CLI／Mermaid／Manager 差异报告，**未识别出一个既属于原清单尚缺的必要条件、又可在不实现业务控制／不扩展范围的情况下独立运行，并能新增非重复验收证据的原生项**。

这不是“任何额外实验都不可能有价值”，也不表示 AT-01—12 已全部通过。具体判断如下：

| 原剩余范围 | 已有依据／缺口 | 为什么不再自行补跑 |
| --- | --- | --- |
| AT-02／03：许可、旧计划、预算、资源占用、跨仓前驱、计划多目标生效 | 原生旁路、DAG 推进、陈旧写与多目标反例已有实测；缺 RepoMesh gate、版本／事务及启动再核验 | 再发一次 marker 或造一个 fake Adapter 不能验证不存在的业务门禁 |
| AT-05／06／07：Issue／round／Attempt 绑定、歧义目标、首次创建事务、持久待办 | Task ID 跨 Project 碰撞、同 Team／不同 Team 读写、真实 room session 及恢复有证据；业务映射与创建事务未实现 | 需要真实产品标识、权限／路由及事务；另一套原生短名称不能代替 |
| AT-04：MCP 延迟覆盖及存储失败 | 真实 CAS／MCP 交错、未同步结果及响应未知已有原始记录 | 新版逐函数差异未修复这些路径；重复原反例不改变结论 |
| AT-08：取消／断网／替补以及原子最后槽位 | 实际模型启动进程在元数据取消后仍工作、双 ack、身份删除重建均有证据；完整 Attempt 排他和资源回收准入未实现 | 原生负例已经否定无条件保证；追加断网后替补要有业务冲突判据，不能自行造调度器 |
| AT-09：限额与实例隔离 | 双实例同名成员／同仓 clone、跨凭据、停止恢复和无限 cgroup／短负载反证已记录 | 没有相关投影修复，不用 OOM 或更大压力重复证明未限额 |
| AT-10：普通回复、thread、消息恢复与业务重放 | 两次部署 Worker 实际模型回复已补；输出关系未保留，共用 room session；55 条持久消息仅尾 9 条恢复回调 | 原生范围已有明确记录；outbox、补拉与业务 exactly-once 仍没有实现，不能重跑相同消息冒充修复 |
| AT-11：产物、状态及当前读权 | 实际文件字节、上传失败仍接受、Task/Project 状态差异、退房后媒体仍可读等已测 | 固定组合证据、动态业务读权和交付转换缺实现；更多文件样本不能补齐 |
| AT-12：回归和采集成本／全局争用 | 两个真实 Worker 各 76 项官方回归、资源／目录／健康采样及原生查询采集耗时已有记录 | 固定工作量已量化；额度争用吞吐需要尚无实现的全局调度，未获新的最大压力目标 |
| AT-01：checkpoint 及后置 runtime／Skill／HITL | 当前 QwenPaw 2.0.1 checkpoint 端点缺失已有证据；原清单明确后置其他 runtime、Skill 工程等 | 升级 runtime、恢复后置项或搭建新平台是新范围，不由审计推定 |

本轮新增 Controller Task inspection／workflow、scoped 身份、真实 CLI 和 Mermaid 解析已经由主任务及另一 Agent 取得新证据，含应保留的 Mermaid 保留词失败与 CLI `--team` 未转发问题。这些失败不能被“测试结束”覆盖，也无需本审计重复执行。

CFG-05 的 Provider 清空后实际配置投影由其负责方继续。**若该项只走 Stopped 配置投影，不能因此宣布新 Manager 应用完整启动或模型运行已验收**；新镜像 runtime 加载的结论必须由其实际覆盖层级决定。本审计不抢占该资源、不提前判定结果，也不为扩大覆盖自动追加模型任务。

## 4. `pip check` 缺 copaw 的实际影响与边界

沿用已完成的[新 Manager 离线证据](../evidence/manager-offline-smoke.json)，没有重新运行容器或模型：

- `qwenpaw --help` 退出 0；说明安装的 QwenPaw CLI 入口及该次帮助路径能加载。
- `agt --help` 退出 0；这是 Go CLI，不能用来证明 Python runtime 依赖无问题。
- `pip check` 退出 1，唯一输出：`copaw-worker 1.0.3 requires copaw, which is not installed.` 这是实际声明依赖不满足，不能写作全绿。

源码解释了为何出现这个组合：`copaw/pyproject.toml` 第 13 行仍声明 `copaw==1.0.2`；官方 `manager/Dockerfile.qwenpaw` 明确以 `--no-deps` 安装 copaw-worker，并说明其 QwenPaw bridge 不需要 CoPaw runtime。实际 `copaw_worker/run_copaw_app.py` 的入口调用 `runpy.run_module("qwenpaw", ...)`；`bridge.py` 的常量修正引用 `qwenpaw.constant`。这是“包名／旧依赖元数据”和当前 QwenPaw 运行入口不同的源码依据。

可确认：缺 copaw **没有阻断已执行的 QwenPaw 帮助命令**，亦未阻断独立 Go CLI；不能仅凭 `pip check` 就断言整个 QwenPaw Manager 一定无法启动。反过来，这也**没有证明所有 bridge、工具插件、依赖导入或模型路径都不需要 copaw／不存在其他兼容问题**。当前版本里任何真正引用 copaw 的未覆盖路径仍可能失败，必须按实际入口验证；不能为修饰检查结果随意安装它并改变依赖解析。

新 Manager 的 AgentScope、FastMCP 和 instrumentation 等实际版本已在离线证据中固定。与旧源码相同不代表新依赖组合等同旧镜像；本审计保留这一风险边界，不把帮助命令或 CFG-05 配置成功提升为所有 runtime 路径兼容。

当前收尾仍需保留两类未完成前提：跨项目旧卷清理的授权／占用，以及 RepoMesh 业务实现与受控联调。此报告没有修改 current docs、README、实例 c 或其他项目。

## 后续补测后的前提复核

随后继续原目标，新增d并实际完成[双在线新增读取矩阵](controller-twin-read-live.md)、[Mermaid的真实S3读取观测](mermaid-storage-read-live.md)及[新版Manager一次真实推理](manager-model-smoke-new.md)。这些是另外执行的实测，不是上文只读审计产生的结果；它们分别关闭原先新版双实例、内部读取与新Manager默认推理路径的证据缺口。

04:00:23 UTC的[新收尾快照](../evidence/final-review-continuation.json)重新扫描仍无本仓库Go业务实现，精确查询仍确认旧共享卷被运行中的GOAI API挂载。这两类前提未被原生补测替代。各Agent的测试进程和临时监听均已结束，验证实例及自有元数据保留供审阅，未对其他项目清理。
