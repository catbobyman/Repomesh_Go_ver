> 历史归档（2026-09-08）：仅供追溯，原文中的状态和待决定项不作为现行规则。当前设计见[文档入口](../../../../current/README.md)。原位置：docs/adr/0001-agentteams-issue-concurrency-and-isolation.md。

---
status: accepted
date: 2026-09-07
---

# ADR-0001：基于 AgentTeams 的团队组织、Issue 并行与单机隔离

RepoMesh 使用 AgentScope 团队的 AgentTeams 作为协作基础，采用“一个多仓库项目对应一个 Manager、一个代码仓库对应一个 Team”的长期组织模型。多个 issue 通过独立的协调会话、任务记录和执行工作区推进，而不是为每条 issue 复制 Manager、团队或整套平台。

多项目部署进一步确定为：一个 RepoMesh 统一管理多个多仓库项目，每个独立项目对应一套独立 AgentTeams 实例；多个实例可以位于同一台服务器，实例内复用本项目的 Manager 与仓库 Teams。房间是 issue 上下文边界，不是项目权限或数据隔离的替代品。

本记录汇总本轮产品讨论中确认的设计方向。`accepted` 表示产品设计已接受，不表示代码已经实现、部署已经完成或上游能力已经通过运行验证。

## 1. 背景与适用范围

- 用户当前最多使用一台服务器，需要支持多仓协作和多个 issue 同时在途。
- 希望新建 issue 像 coding agent 新开会话一样，拥有独立上下文，而不是把所有要求追加到同一条聊天。
- 仓库团队应长期复用，不能因每次需求重复建立而丢失职责和知识归属。
- AgentTeams 的资源对象、会话、运行进程和访问权限是不同层次，不能互相替代。
- 前述 Cloud Agent PRD 是能力参考，不是直接照搬的实现范围；旧版 RepoMesh 文档作为历史依据保留。
- 本期不承诺不可信多租户隔离，不承诺一 Agent 一 VM，也不以增加服务器为前提。

术语定义见 [RepoMesh 领域语言](../../CONTEXT.md)。

## 2. 已接受的决策

| 编号 | 决策 | 原因与边界 |
| --- | --- | --- |
| D01 | 使用 `agentscope-ai/AgentTeams` 作为协作基础 | 复用角色、团队、通信和运行生命周期能力；不平行重造一套团队系统。 |
| D02 | 一个多仓库项目由一个 Manager 负责 | Manager 负责跨仓范围与项目级协调；不是每个 issue 一个 Manager。 |
| D03 | 一个 Team 长期负责一个仓库 | Leader 负责协调，Worker 执行；Team 不等于共享容器或共享工作目录。 |
| D04 | Issue 统一登记，再按范围路由 | 默认 Manager 接单；满足明确单仓条件的 issue 可直达 Leader，不直接交普通 Worker 判断整体范围。 |
| D05 | 每个 issue 有独立的协调上下文和状态 | 同一角色可参与多个 issue，但不能把它们混成一个聊天上下文。 |
| D06 | 协调采用短轮事件驱动，执行按容量并行 | 派工后结束本轮协调；结果或阻塞事件触发下一轮，不因等待一个 issue 而阻塞其他 issue。 |
| D07 | 一个 Worker 同时只有一个活跃执行任务 | 空闲检查与占用由后台统一保证，不能靠多个会话各自判断。 |
| D08 | 每个任务尝试使用独立代码副本与结果记录 | 不同 issue、任务和重试不能共享脏工作区。 |
| D09 | 跨仓读与跨仓写分离 | Team 默认只修改本仓；需要修改其他仓库时升级给 Manager。 |
| D10 | 多仓工作区用于受控集成验证 | 检出固定候选组合进行验证，不建立可随意跨仓修改的超级开发成员。 |
| D11 | 一期使用单机容器方案 | 沿用 AgentTeams 单机架构，不以 Kubernetes 或逐 Agent 虚拟机为起点。 |
| D12 | 多业务项目隔离与多 issue 并行分开设计 | 多 issue 复用本项目的 Manager 和 Teams；独立业务项目采用独立实例，不按 issue 复制实例。 |
| D13 | 一个 RepoMesh 管理多个项目，每项目一套 AgentTeams 实例 | 同机部署完整的项目级协作服务和数据边界，不仅新增房间或具名 Manager。 |
| D14 | 初期基础服务也按实例分开 | Controller、Matrix、存储与网关按项目实例配置；接受重复基础开销，避免先开发共享服务的多租户体系。 |
| D15 | 全服务器容量由 RepoMesh 统一约束 | 全局执行上限叠加项目额度；项目登记数量不等于同时启动或执行数量。 |
| D16 | 项目生命周期与实例运行状态分开 | 支持先登记、按需启动与保留数据停机；新项目不是自动立即启动全部成员。 |
| D17 | Issue 默认采用主房间加仓库子房间的受控会话拓扑 | Manager 主责的 issue 建主房间，每个受影响仓库建子房间；明确单仓快速路径以仓库 issue 房间作为主房间。Worker 默认加入仓库 issue 房间，不为每个 Task 或 Attempt 建房。房间生命周期与业务映射由 RepoMesh 控制。 |
| D18 | 已配置项目在首次提交 issue 时延迟准备 AgentTeams | 保存项目草稿、完成仓库授权和必要配置都不启动实例；第一条 issue 被正式提交后先持久化，再幂等触发本项目实例准备。准备成功后才创建 issue 房间并路由，失败时保留 issue 等待重试。 |

## 3. Issue 接入与责任规则

### 3.1 入口与路由

所有入口先进入 RepoMesh 的 issue 接入层，完成来源识别、去重、权限核验、issue 登记和主会话建立。统一接入不是要求所有 issue 都必须经过一次 Manager 模型调用。

| 条件 | 主负责人 | 行为 |
| --- | --- | --- |
| 跨仓或影响范围未知 | Manager | 澄清或调查范围，形成跨仓计划，向相关 Leader 委派仓库工作。 |
| 用户明确限定单仓，且影响判断未发现跨仓依赖 | 对应 Leader | 本仓拆解与派工，项目总览仍记录该 issue。 |
| 单仓执行中发现必须越出已授权仓库范围 | 从 Leader 升级给 Manager | 先确认范围变化；未经授权不跨仓修改。 |

仅因为 issue 创建在某个 Git 仓库里，不足以判定它是单仓需求。默认入口保持 Manager，单仓直达是一条有条件的快速路径。

### 3.2 主负责人唯一

- 一条 issue 同一时刻只有一个主负责人，Manager 与 Leader 不能重复派发同一份工作。
- 跨仓 issue 的主负责人为 Manager，各 Leader 对自己的仓库工作负责。
- 单仓 issue 可由 Leader 主责，Manager 保留项目级可见性，不重复审批每个普通任务。
- 责任升级保留原 issue、会话历史、任务和产物，不另造一条无关联的新 issue。
- 后续评论回到原 issue；重复事件不重复开单。重派或重试产生新的执行尝试，不创建新的 Manager。

### 3.3 Issue 处理流程图

```text
[User / Issue Event]
          |
          v
[RepoMesh Intake]
[Identify + Deduplicate + Authorize]
          |
          v
[Create / Update Issue + Main Session]
          |
          v
<Explicit single-repo scope, no cross-repo dependency?>
          | No / Unknown                  | Yes
          v                              v
[Manager Session: Issue I]      [Leader Session: Issue I / Repo R]
[Clarify scope + Coordinate]              |
          |                              |
          v                              |
[Delegate repo work to Leaders]          |
          |                              |
          +--------------+---------------+
                         |
                         v
           [Repo-scoped plan + Task dependencies] <------------+
                         |                                     |
                         v                                     |
          [Capacity queue + Atomic Worker allocation]          |
                         |                                     |
                         v                                     |
            [Worker: isolated Task / Attempt]                  |
                         |                                     |
                         v                                     |
               [Submit candidate + Evidence]                   |
                         |                                     |
                         v                                     |
                  [Leader initial review] -- Rework -----------+
                         |                                     |
                         v                                     |
              [Independent verification]                       |
              [Multi-repo: fixed combination] -- Failed -------+
                         |
                         v
          [Issue Owner checks acceptance conditions]
                         |
                         v
            [Required approval + Scoped delivery]
                         |
                         v
                [Issue result + Evidence]

Side paths:
  Scope expansion -> Manager -> Scope confirmation -> Replan
  Missing input   -> Wait on this Issue only -> Resume on event
  Pause / Stop    -> Affect this Issue's tasks only
  Retry exhausted -> Block / Human decision; no unlimited loop
```

图中的计划、审核和验证都是逻辑步骤，不要求每一步新建一个常驻 Agent。交付动作按本 issue 的验收条件执行；生成候选或 PR 不自动等于允许合并，也不自动关闭外部 issue。

## 4. 团队组织与任务流转

### 4.1 长期组织与短期上下文

- Manager、Team、Leader、Worker 是长期身份与职责。
- Issue Session 是某个角色参与某条 issue 时的独立上下文，不是新的角色实例。
- Task 是有明确输入、输出和验收条件的工作单元；Attempt 记录一次执行。
- 确定的任务依赖可以采用 DAG；需要边做边判断的修复过程可采用有停止条件的 Loop。
- RepoMesh 的长期多仓项目，不直接等同于 AgentTeams 内部的每条 `Project` 执行记录；具体映射需要接入适配，不能仅凭同名绑定。

### 4.2 团队组织与流转图

```text
Human
  |
  v
RepoMesh Project P  [Repo A + Repo B + ...]
  |
  +-- Manager M  [one persistent identity]
        |
        +-- Session M / Issue I101
        +-- Session M / Issue I103
        |
        +-- Team A  [owns Repo A]
        |     |
        |     +-- Leader LA  [one persistent identity]
        |     |     +-- Session LA / I101 / Repo A
        |     |     +-- Session LA / I102 / Repo A
        |     |
        |     +-- Worker A1  [one persistent identity]
        |     |     +-- Session A1 / I101 / Repo A
        |     |     +-- Task T1 / Attempt 1 -- private clone
        |     |
        |     +-- Worker A2
        |           +-- Session A2 / I102 / Repo A
        |           +-- Task T2 / Attempt 1 -- private clone
        |
        +-- Team B  [owns Repo B]
        |     |
        |     +-- Leader LB
        |     |     +-- Session LB / I101 / Repo B
        |     |
        |     +-- Worker B1
        |           +-- Session B1 / I101 / Repo B
        |           +-- Task T3 / Attempt 1 -- private clone
        |
        +-- Integration Worker  [on demand, not a repo-owning Team]
              +-- I101: Repo A @ SHA-A + Repo B @ SHA-B
              +-- isolated services / test data / reports
              +-- no business-repo push or merge permission

Cross-repo flow:
  M/I101 -> LA/I101 -> A1 -> candidate -> LA/I101 -> M/I101
         -> LB/I101 -> B1 -> candidate -> LB/I101 -> M/I101
  M/I101 -> Integration Worker -> evidence -> M/I101 -> Human

Single-repo fast path:
  Intake -> LA/I102 -> A2 -> candidate -> review / verification
         -> LA/I102 -> Human
  Project overview records I102; M does not duplicate its dispatch.
```

组织图表示责任关系，不代表所有容器同时常驻，也不代表图中不同 session 必须同时进行模型推理。Worker 在不同时间可参与不同 issue，但同一时刻只承担一个活跃执行任务。

## 5. 会话与多 Issue 并行

### 5.1 会话边界

用户侧为一个 issue 提供一张工作页和一条主会话。Manager 主责的跨仓或范围不明 issue，在内部使用一个 issue 主房间和每个受影响仓库一个仓库 issue 子房间；明确单仓快速路径以该仓库 issue 房间作为主房间，由 Leader 主责，不额外触发 Manager 协调会话。

```text
Cross-repo or scope-unknown Issue I101
|
+-- Main Room R-I101
|     +-- Manager M -> Session M / I101
|
+-- Repo Room R-I101-A
|     +-- Leader LA -> Session LA / I101 / Repo A
|     +-- Worker A1 -> Session A1 / I101 / Repo A
|           +-- Task T1 / Attempt 1 -> private clone
|
+-- Repo Room R-I101-B
      +-- Leader LB -> Session LB / I101 / Repo B
      +-- Worker B1 -> Session B1 / I101 / Repo B
            +-- Task T2 / Attempt 1 -> private clone

Explicit single-repo Issue I102
|
+-- Primary Repo Room R-I102-A
      +-- Leader LA -> Session LA / I102 / Repo A
      +-- Worker A2 -> Session A2 / I102 / Repo A

Manager M sees I102 in the project overview but is not invoked to redispatch it.
```

- 一个角色参与多个 issue 时，分别加载各 issue 的目标、计划、决策和进展。
- RepoMesh 负责创建或授权创建房间、邀请成员、设置权限，并持久化 project、issue、repository、agent、room 与 session 的映射。Manager 或 Leader 可以提出建房需求，但不能绕过 RepoMesh 形成无归属的业务房间。
- 房间存在、Agent 被邀请或加入，都不等于其模型 session 已创建。按当前 QwenPaw 路径，Agent 第一次处理该房间内的有效消息时，才按 room_id 查找或创建自己的 session。
- 同一房间中的 Manager、Leader 和 Worker 各自维护本地 session；它们共享房间消息，不共享同一个模型上下文、隐藏推理或未发布的工具结果。
- `@Agent` 用于选择和触发接收者；在新房间第一次有效触发可能导致该 Agent 建立 session，在已有房间再次 `@` 只继续原 session，不产生 Task 或 Attempt 子会话。普通回复或 Matrix thread 也不作为新的 session 边界，除非后续适配显式改变 session key。
- Worker 默认加入所属仓库的 issue 房间。同一 issue 内的 Task 与 Attempt 由 RepoMesh 任务记录、独立工作副本和执行环境隔离，不为每个 Task 或 Attempt 默认新建房间。
- 只有敏感权限、超大上下文、专项集成验证或其他明确隔离需求，才按策略创建专用 Task / Attempt 房间；该房间仍需登记父 issue、Task、Attempt 和结果回流目标。
- 常设 Team Room 承载团队公共信息，不混放所有 issue 的完整执行上下文。
- 可复用的是经过整理的项目或仓库知识；其他 issue 的临时指令、待批请求和未完成计划不作为共享长期记忆。
- 所有任务通知与结果都显式关联 issue、仓库、任务和尝试，不根据最近聊天猜测归属。
- 新房间需要配套成员权限、消息触发与结果路由；只新建房间或增加一个聊天标签不算完成适配。

### 5.2 事件驱动协调

Manager 或 Leader 完成当前判断与派工后结束本轮协调。任务结果、阻塞、用户输入或其他有效事件到达时，再进入对应 issue 的上下文。

多个 issue 可以同时在途；不同 Worker 可并行执行。即使 Manager 的模型调用短轮串行，也不能让其在等待某个 Worker 时阻塞所有其他 issue。

### 5.3 全局调度约束

1. RepoMesh 后台维护成员占用和执行容量，领取时原子确认；不同协调会话不能各自认为同一成员空闲。
2. 资源不足时进入可解释的队列。初期从少量执行槽位开始，具体数量按服务器配置和构建峰值验证，不在本 ADR 固定数值。
3. 重型集成验证需要多服务资源时，可减少其他构建并发，保护控制服务。
4. 等待人工回复的 issue 不阻塞无关 issue；保存必要检查点后释放可回收资源。
5. 暂停禁止该 issue 新派工；如需停止在途任务，必须追踪停止确认，不能把“已发消息”视为“进程已停止”。
6. 重派后旧尝试迟到的结果保留历史，但不得覆盖当前有效结果或自动推动后续任务。
7. 一项任务的完成仅解除相关依赖，不自动宣布整个 issue 完成。

### 5.4 同仓并行与合入

- 两个 issue 可以分别在本仓独立副本中开发，不因使用同一仓库就强制全程串行。
- 明确存在先后依赖或高风险冲突时，应建立依赖或串行安排，不隐式假定另一 issue 已完成。
- 候选组合、合入顺序和基线变化必须可追踪；无文本冲突也不代表无语义冲突。
- 新基线或组合变化后重新判断并执行必要验证，不能复用失效证据。

## 6. 单服务器执行与隔离

一期采用 AgentTeams 单机容器基础：Manager、Leader 和 Worker 分别运行，控制服务常驻，任务执行按容量启动或回收。模型走外部 API 是当前资源规划假设；若本机还承担模型推理，需重新核算容量。

### 6.1 隔离规则

| 边界 | 设计要求 |
| --- | --- |
| 代码与工作目录 | 每个 Task Attempt 使用独立 clone、分支和构建目录；不挂载整个项目或其他成员的工作区。 |
| 重试与恢复 | 新尝试不默认继承脏工作区；复用已保存候选或检查点时明确来源。 |
| 进程与容量 | 独立容器与显式资源限制；控制磁盘和日志增长，不让单任务耗尽控制服务资源。 |
| 网络 | 禁止任意成员互连，按需放行协作和工具服务；集成服务进入本轮专用网络。 |
| Git 写权限 | 通过受控交付能力验证任务归属，禁止执行成员使用全项目长期高权限凭证。固定 App 权限集、运行时收窄及 draft PR 边界见 [ADR-0002](0002-github-app-authorization-and-draft-pr-delivery.md)。 |
| 产物 | 自己提交区可写，他人的已提交结果只读；已接受证据不能被执行成员覆盖。 |
| 宿主机控制 | Agent 不直接持有宿主 Docker socket；容器创建由可信控制服务校验允许的镜像、挂载、网络和资源。 |
| 长期数据 | 团队身份、配置、经整理知识及历史证据独立保留；临时执行环境可回收。 |

目录命名不是授权，聊天约定不是访问控制，上述约束必须由实际挂载、服务端权限和调度逻辑执行。AgentTeams 默认设置不视为已满足这些要求。

一期优先独立 clone；不把共享 Git 管理数据的 worktree 当作安全边界。后续可优化缓存，但不得把公共可写缓存变成跨任务污染通道。

### 6.2 跨仓验证

仓库 Team 默认只修改本仓，可按授权读取其他仓库的只读快照和契约。跨仓集成由 Manager 调度专项验证 Worker，按固定 commit 组合检出多个仓库，使用隔离测试数据和临时服务。

验证环境可以产生本地构建及测试文件，但没有向业务仓库推送或合并修复的权限。发现问题返回对应 Team 修复，新候选形成新组合后重新验证。

### 6.3 回收与安全等级

- 停止进程、删除工作副本、删除历史证据是不同操作，不应绑定成一次无差别清理。
- 回收临时工作区前确认候选、日志、报告和必要检查点已保存；不能假定尚未同步的数据会自动持久化。
- 同机对象存储不是异机备份，关键状态需要服务器外的备份位置。
- 普通容器共享宿主机内核，不能表述成独占 VM 同级隔离；一期面向可信组织内部协作，不承诺恶意多租户隔离。
- 更强沙箱或 VM 是未来可替换的执行后端，不改变长期团队与 issue 会话模型。

## 7. 多仓库项目的独立实例隔离

### 7.1 已确认的层级

本节已由用户明确确认，不再只是未来部署方向。一个 RepoMesh 可以管理多个独立多仓库项目，每个项目对应一套独立 AgentTeams 实例；实例内部一个 Manager、多支仓库 Team、多条独立 issue 会话。

| 新增对象 | 创建或分配什么 | 主要边界 |
| --- | --- | --- |
| 独立多仓库项目 | 独立 AgentTeams 实例 | 管理身份、团队、权限、配置与项目数据。 |
| 项目内的仓库 | 本项目的一支 Team | 仓库责任与授权范围。 |
| 项目内的 issue | 独立协调会话、计划和任务记录 | 对话上下文与工作状态，不创建新 Manager。 |
| 一次任务尝试 | 独立工作副本与执行环境 | 未提交改动、进程及构建状态。 |

“实例”指完整的项目级协作服务与数据，不是一个房间，也不只是 Manager 容器。多个实例可以共用一台服务器，但不因此共享彼此的项目访问权限。

### 7.2 同机多实例部署字符图

```text
One Linux Server
|
+-- RepoMesh                                  [shared platform]
|     +-- Users / Project authorization
|     +-- Project -> Instance mapping
|     +-- Global execution capacity / Queue
|
+-- Project A -> AgentTeams Instance A
|     +-- Embedded Controller A
|     |     +-- Matrix A / Storage A / Gateway A
|     +-- Manager A
|     +-- Team A1 -> Repo frontend
|     +-- Team A2 -> Repo backend
|     +-- Issue rooms / Sessions / Task attempts
|     +-- Network A / Volumes A / Credentials A
|
+-- Project B -> AgentTeams Instance B
      +-- Embedded Controller B
      |     +-- Matrix B / Storage B / Gateway B
      +-- Manager B
      +-- Team B1 -> Repo client
      +-- Team B2 -> Repo service
      +-- Issue rooms / Sessions / Task attempts
      +-- Network B / Volumes B / Credentials B

Authorized request:
  User -> RepoMesh -> Project authorization -> Server-side mapping
       -> Selected instance -> Issue session -> Team / Worker

No default direct access:
  Instance A -X-> Instance B data / credentials / control APIs
```

图中网络阻断和授权是实施目标，需要实际策略与测试保证。初期 Controller、Matrix、存储和网关按实例分开；可复用同一镜像，但不共享可写配置和数据卷。RepoMesh 入口及全服务器容量管理共用，不要求每个项目再部署一个 RepoMesh。

### 7.3 新建项目与实例生命周期

1. 用户先保存项目基本信息，RepoMesh 建立稳定项目 ID，项目处于草稿状态；此时不创建 AgentTeams 实例。
2. 用户完成仓库授权，以及首期要求的成员、模型与执行预算配置。必要配置未完成时，不允许正式提交可执行 issue。
3. 配置完成后，项目进入“已配置、实例未创建”的待启动状态；RepoMesh 建立受控的项目到实例映射，但仍不占用本项目的常驻 AgentTeams 资源。
4. 用户正式提交第一条 issue。RepoMesh 先完成来源识别、权限核验、去重和 issue 持久化，将其标记为等待项目准备，再幂等触发本项目实例创建。
5. RepoMesh 创建本项目实例、Manager 和仓库 Teams，并执行服务、身份、权限、消息和存储就绪检查。只有全部必要检查通过，实例才进入 Ready。
6. 实例 Ready 后，为已登记的首条 issue 创建对应房间和 session 路由，继续范围判断、计划和派工；实例准备失败时保留 issue，不重复建单，并提供可解释的重试入口。
7. 后续 issue 复用同一实例。若实例处于保留数据的停止状态，则启动并恢复原实例，不另建一套 Manager 或 Teams。

```text
[Save Project Basics]
        |
        v
[Draft: Required Configuration Incomplete]
        |
        v
[Authorize Repositories + Required Settings]
        |
        v
[Configured: Instance Not Created]
        |
        | Submit first Issue
        v
[Register Issue: Waiting for Project Setup]
        |
        v
[Provision Instance + Manager + Teams]
[Readiness and Permission Checks]
        |
        +-- Failed --> [Setup Failed]
        |                 +-- keep Issue + evidence
        |                 +-- retry same provisioning operation
        |
        v
[Ready: Create Issue Rooms + Route Registered Issue]
        |
        v
[Quiesce Work + Persist State]
        |
        v
[Stopped: Project and Data Retained]
        |
        +---- next Issue ----> [Start Existing Instance + Readiness Checks]

Open Issue page / type draft != submit Issue
Repeated submit / retry      != duplicate Issue or Instance
Stop instance                != delete project or historical evidence
```

这是 RepoMesh 的产品生命周期设计，不是对 AgentTeams 默认安装器自动完成上述流程的承诺。触发点是用户正式提交第一条 issue，不是打开 issue 页面、输入尚未提交的草稿或仅完成仓库授权。前端重复提交、事件重放和人工重试必须复用同一 issue 与同一项目实例准备操作。停机前处理在途任务并确认必要状态已保存；不得以回收资源为由隐式删除项目或产物。

### 7.4 必须隔离的内容

| 内容 | 每项目实例的要求 |
| --- | --- |
| 容器与入口 | 唯一容器名称、网络及宿主机端口；实例地址和服务发现指向正确项目。 |
| 工作与持久数据 | 独立数据卷、Manager 工作目录、成员状态、任务工作区和产物位置。 |
| 消息 | 独立 Matrix 服务及其账号和房间数据；不同服务内的同名角色不视为同一个项目身份。 |
| 凭证 | 独立存储、网关、控制接口凭证；Git 授权只覆盖本项目明确接入的仓库。 |
| 访问路由 | RepoMesh 服务端先验证用户项目权限，再选择实例；客户端不能任意指定实例地址或凭证绕过权限。 |
| 宿主机控制 | 不向项目 Agent 暴露 Docker 控制权；可信控制服务限制可管理容器、挂载、网络和资源的范围。 |

部署时需要参数化名称、目录、端口、服务地址与凭证，并核查单机脚本和后台创建逻辑中的固定配置。仅改一个前缀或重复运行默认安装器，不算完成多实例适配。

实例控制服务仍属于可信管理面。若共用宿主容器引擎，仅分离项目网络和数据卷不足以约束高权限的容器创建接口；必须限制相关 API 的暴露和调用参数。本方案不承诺不同实例之间达到 VM 级或恶意租户级隔离。

### 7.5 全服务器容量与项目额度

- RepoMesh 统一管理全服务器执行上限，各项目再配置各自额度；不能让每个 Manager 都按独占整台服务器计算资源。
- 任务只有同时满足全局容量、项目额度、成员空闲和依赖条件时才能启动。
- 实例数量、处于运行状态的实例数量、活跃 Worker 数量分别统计；额度不足时排队，不能绕过全局限制。
- 容量规划同时计入常驻基础服务、协调 Agent、构建测试和集成服务，不只计算 Worker。
- 允许先登记多个项目、按需启动实例，并对不活动实例保留数据停机。可承载数量待服务器规格与负载验证，不在此承诺固定项目数。

### 7.6 两个项目引用同一远端仓库

项目本地环境隔离，不会复制或隔离远端 Git 仓库。两个项目都获得同一仓库授权时，其远端提交和目标分支仍是共享事实。

- 各实例仍保有各自的团队身份、工作副本和本项目凭证，不能借共享远端仓库读取另一项目的私有会话或产物。
- 任务分支必须能区分项目、issue 和执行工作，避免不同项目重名覆盖。
- 通过受控交付流程协调同一远端仓库的合入、基线更新和必要重新验证；具体机制待实现验证。
- 不能将“本项目环境独立”作为忽略另一项目已合入变更的理由。

### 7.7 取舍与替代方案

初期选择独立实例，接受重复基础服务的内存、维护和启动成本，以避免先开发共享 Matrix、存储、网关及 Controller 的多租户体系。

单实例多 Manager 的资源复用效率可能更高，但当前源码的具名资源支持不足以证明完整隔离。若未来改走该路线，需补齐身份、工作空间、团队归属和权限过滤，并另行记录取代本选择的 ADR；不能在 issue 并行或资源优化中隐式改为共享管理域。

## 8. 上游依据与未验证能力

AgentTeams 源码核查快照：`eeaab64391ccaec9118e84977f538aefd40720d6`（2026-09-05）。以下是本轮只读核查结果，不替代部署和端到端验证，也不保证后续版本保持相同行为。

| 已核查事实 | 设计影响 | 依据 |
| --- | --- | --- |
| Manager 容器可以按资源名称区分，但管理身份并未完整隔离。 | 不以创建多个具名 Manager 作为项目隔离方案。 | [身份与容器命名](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/agentteams-controller/internal/auth/prefix.go) |
| Manager 创建逻辑仍使用固定 Matrix 用户及 Gateway consumer；Manager 授权为完整访问。 | 独立资源名字不代表独立管理域。 | [身份创建](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/agentteams-controller/internal/service/provisioner.go#L1345)、[授权](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/agentteams-controller/internal/auth/authorizer.go#L47) |
| Embedded Manager 启动使用公共工作目录与控制台端口配置；TeamSpec 未提供明确 managerRef。 | 单机多 Manager 还有部署冲突与团队归属问题。 | [启动配置](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/agentteams-controller/internal/controller/manager_reconcile_container.go#L223)、[资源定义](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/agentteams-controller/api/v1beta1/types.go#L424) |
| QwenPaw 的 Matrix 通道按 room_id 构造 session，并按房间键协调请求；同房不同发送者的消息对同一个 Agent 落入同一房间会话，但不同 Agent 仍各自维护本地会话。 | 多 issue 放同一个 Team Room 不会自动隔离；共同可见消息也不等于多个 Agent 共享同一模型上下文。需建立 issue、角色、房间与会话的显式映射。 | [会话构造](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/agentteams-matrix-channel/agentteams_matrix/channel.py#L3120)、[房间请求键](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/agentteams-matrix-channel/agentteams_matrix/channel.py#L425) |
| Manager 已有独立 Project Room、计划和元数据机制。 | 可作为 issue 协调接入基础，但仍需 RepoMesh 的关联和路由适配。 | [项目管理](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/manager/agent/skills/project-management/SKILL.md) |

实现前必须验证：

1. 选定运行时的不同 issue 会话确实分离，长期记忆和文件不会悄悄混用；QwenPaw 证据不能直接套用到其他运行时。
2. 新建 issue 的自动建房、成员授权、真实消息触发、Leader 派工和结果回流可完整闭环；仅邀请或加入房间不应被误报成 session 已就绪。
3. “Manager 主房间 + 每仓 issue 子房间 + Worker 默认复用仓库 issue 房间”的拓扑不会破坏 AgentTeams 原生 Team Room 派工规则或产生重复处理。
4. `@Agent` 只触发目标 Agent 并继续正确的房间 session；未被触发成员的历史缓冲、普通回复和 Matrix thread 不会造成错误新建、错误归属或上下文泄漏。
5. 不同房间模型调用的实际并行行为、限额与失败恢复；不同 session 标识不是并发性能证明。
6. Docker 后端的资源限制、网络策略、挂载、凭证和存储权限真正生效。
7. Worker 重建与工作区清理能保留应保留的数据，又不会恢复不该继承的脏状态。
8. 暂停、停止、重派、超时和迟到结果在多 issue 条件下保持正确归属。
9. 同机创建两个实例时，名称、网络、端口、工作目录、数据卷、凭证及控制请求不串用；项目越权访问被服务端拒绝。
10. 跨实例全局执行容量与项目额度同时生效；停止或恢复一个实例不错误操作另一实例的容器和数据。
11. 同一远端仓库被两个项目接入时，任务分支不会重名覆盖，合入后的基线变化触发必要重新验证。

## 9. 最小验证场景

| 场景 | 预期结果 |
| --- | --- |
| 同一项目同时接入一条跨仓 issue、一条明确单仓 issue | 分别由 Manager 和对应 Leader 主责，登记在统一项目总览。 |
| 创建 issue 房间并邀请 Agent，但尚未发送有效触发消息 | 房间和成员关系已存在，但 UI 不把该 Agent 的 session 标成已创建或就绪。 |
| 已配置项目尚未提交任何 issue | 项目及仓库授权保留，AgentTeams 实例、Manager 和 Teams 尚未创建，不占用本项目常驻实例资源。 |
| 用户首次正式提交 issue | RepoMesh 只登记一条 issue，将其置为等待项目准备，并只触发一次项目实例创建；Ready 后才建房和路由。 |
| 首次 issue 触发实例准备失败后重试 | 原 issue、失败证据和项目身份保留；重试不生成第二条 issue、第二套实例或重复 Manager。 |
| 跨仓 issue 创建主房间和两个仓库子房间 | Manager、两个 Leader 及参与 Worker 分别使用正确房间下的本地 session；消息与结果能回到同一父 issue。 |
| 同一 Worker 先后参与两个 issue 的仓库房间 | 两个 issue 的目标和历史不混用；同时只能领取一个活跃任务，另一任务按容量排队。 |
| 普通任务在仓库 issue 房间内派发 | 不额外创建 Task 房间；Task 和 Attempt 仍有独立记录、工作副本、结果与验收证据。 |
| 同一 Leader 同时参与两条 issue | 目标、计划、审批和结果分开；不为每条 issue 新建 Leader 身份。 |
| 两个会话同时申请同一空闲 Worker | 只允许一个成功占用，另一个进入队列；无重复执行。 |
| 同仓两个任务分别修改代码 | 未提交修改、依赖和运行进程不串扰；最终合入前处理基线和冲突。 |
| 一条 issue 等待人工输入 | 其他无关 issue 继续；等待原因可见。 |
| 暂停 issue A，issue B 仍执行 | 只禁止 A 新派工，并明确显示 A 在途任务是否已停止，不停掉整个 Team。 |
| 重派后旧尝试迟到提交 | 旧结果可追溯，但不能覆盖当前有效结果或解除新计划依赖。 |
| 集成验证后一个仓库候选发生变化 | 形成新组合，不把旧组合的通过结果当作新组合的证明。 |
| 重复收到同一 issue 事件 | 更新已有 issue，不重复创建会话、计划或执行尝试。 |
| 同一服务器登记并启动两个独立多仓项目 | 生成两个独立实例及其 Manager、Teams、消息和数据边界，共用 RepoMesh 入口。 |
| 项目 A 的用户或 Agent 试图访问项目 B | 无授权的请求被拒绝，不因篡改实例地址或对象标识而成功。 |
| 项目 A、B 同时申请剩余的一个全局执行槽位 | 最多一个任务获准启动，另一个排队；不各自按本项目容量越过全局上限。 |
| 停止实例 A 后继续使用实例 B | B 不受错误停止、凭证删除或数据清理影响；A 的项目记录和已保存数据保留。 |
| 两项目各自修改同一远端仓库 | 分支与工作副本独立，合入受协调，新基线所需验证不能被跳过。 |

## 10. 取舍与后果

不采用以下默认方案：

- **每 issue 新建 Manager 或整套 Team**：将短期工作误建模为长期组织，增加资源与身份管理成本。
- **所有 issue 共用一个 Manager/Team 聊天上下文**：容易发生指令、审批和任务状态串扰。
- **每个 Task 或 Attempt 默认新建房间**：虽然增加会话隔离，但会造成房间、权限、结果回流和重试映射快速膨胀；普通任务改由仓库 issue 房间承载，执行环境另行隔离。
- **每个 issue 都必须经过 Manager 的完整规划流程**：明确单仓工作产生不必要的协调开销，因此保留受约束的 Leader 快速路径。
- **直接把普通 Worker 当业务入口**：让执行成员承担跨仓范围和最终协调责任，破坏职责边界。
- **同仓成员共用可写目录**：未提交代码、依赖和构建状态相互污染。
- **一期逐 Agent VM 或直接上 Kubernetes**：当前单机条件下先以容器与并发约束落地，但不冒充 VM 安全等级。
- **独立项目只增加房间或具名 Manager**：无法提供所需的完整管理身份、数据与权限边界，初期采用独立实例。

代价是 RepoMesh 必须承担真实的接入与执行约束：会话映射、成员占用、容量队列、任务尝试、权限、候选组合和证据关联不能只留在提示词中。单机资源决定同时执行数量，但不限制产品只能容纳一条在途 issue。

## 11. 与既有文档的关系

- 保留 [旧版团队、智能体与执行](../../../legacy-product-design/05-团队智能体与执行.md) 的仓库常设团队、层级协作、单成员单活跃任务和尝试历史思想。
- 将旧版团队公共房间补充为“长期公共信息 + issue 独立协调上下文”，不是删除历史沟通记录。
- [Cloud Agent 平台 PRD](../../../reference/Cloud-Agent平台产品PRD.md) 继续作为能力参考；其中隔离环境和多仓工作区按本 ADR 的组织与责任边界落实。
- 本 ADR 是本轮重构的设计基线，不代表所有旧功能已迁移，也不把尚未验证的上游行为写成已实现功能。

## 12. 决策补充记录

- 2026-09-07：将本轮曾暂记为 D19 / 第 6.4 节的仓库授权决定拆出为 [ADR-0002](0002-github-app-authorization-and-draft-pr-delivery.md)，相关规则、待验证项及验收场景在新文档维护；本 ADR 保留 D01–D18，已确认设计内容不变。

- 2026-09-07：用户确认多项目隔离方案。扩充第 7 节，明确一项目一独立 AgentTeams 实例、同机多实例、按需生命周期、全服务器容量及共享远端仓库边界；新增 D13 至 D16、部署与生命周期字符图及对应验收场景。原有 issue 流程和团队流转设计保持不变。
- 2026-09-07：用户确认默认 issue 房间与 session 拓扑。新增 D17：Manager 主责的 issue 使用主房间和每仓子房间；明确单仓快速路径以仓库 issue 房间作为主房间；Worker 默认复用仓库 issue 房间，不为普通 Task 或 Attempt 建房。补充房间邀请、首次有效消息、`@Agent` 与 Agent 本地 session 的关系，并明确由 RepoMesh 控制房间生命周期和业务映射。
- 2026-09-07：用户确认项目延迟准备方案。新增 D18：项目先保存草稿并完成仓库授权与必要配置，期间不创建 AgentTeams；用户正式提交第一条 issue 后，RepoMesh 先持久化 issue，再幂等准备本项目实例，Ready 后建房并路由。失败与重试保留原 issue 和项目身份，不重复创建实例。
