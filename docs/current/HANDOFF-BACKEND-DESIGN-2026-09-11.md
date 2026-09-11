# RepoMesh 后端设计交接 · 2026-09-11

交接对象：下一位后端设计师会话。工作区：`D:\Project4work\Repomesh_Go_ver`。本稿根据用户“写一个新的handoff文档，归档旧的，我要交给下一个后端设计师会话了”整理，取代旧交接的阶段状态与接手顺序；旧正文及归档说明见[历史快照](../archive/2026-09-11-backend-design-handoff/README.md)。本稿不是新业务契约，具体字段仍以对应专题为准。

## 1. 接手时先知道这些

- **只做后端设计和中文 Markdown，不动代码。** 不因接手启动实现、安装依赖、部署服务、输入真实密钥、运行模型、重跑历史实验或创建新任务。用户之后明确改变范围时再按新授权执行。
- 第一批项目／列表协议、首批持久化设计、最小消息澄清设计已完成相应范围的技术对齐；模型设置的供应商分栏和参数填写方式也已获用户采用。不要从头重选这些方案。
- **当前没有等待本会话回复的技术提案或分歧。** 最后业务确认是模型设置r3用户采用通知，已记录后端日志CP31，不需要再ACK。随后页面也通知换会话，已核对其交接§3／4并通知双方都需接替，见CP32；交接后的新消息须另行核对，不能假定永远无未回复事项。
- 工程仍为React／TypeScript／Vite与同一Go module三个入口的骨架：`/healthz`只证明Web存活，`/readyz`为503；coordinator与host-executor默认报告未实现并退出，只有`--version`正常返回。业务API、数据库／队列、GitHub、AgentTeams、MCP、消息与Python分析均未接入。
- **技术ACK、用户采用页面、代码实现和真实验证是四件事。** 用户原话“每次到具体的页面设计，需要展示原型和我讨论”继续有效；内部设计无需恢复逐项审批，页面新增呈现仍须展示讨论。

总交接及旧Prompt保留了不同阶段的授权和状态。旧文中“本轮允许骨架编码”“先实现持久化”“会话消息尚无契约”及早期UI待评审描述，不覆盖本次仅文档范围和下述具体完成状态。按章节范围与明确的替代关系判断，不能单看文件日期或整篇accepted／proposed。

## 2. 阅读顺序与唯一来源

先完整读[根README](../../README.md)、[总交接](HANDOFF.md)、[现行索引](README.md)和本稿，再读下表。用户指定的材料必须完整覆盖；其他历史资料按本次拟设计范围追溯。

| 阅读批次 | 文档 | 重点 |
| --- | --- | --- |
| 领域与决策 | [CONTEXT](../../CONTEXT.md)、[ADR索引](../adr/README.md) | 术语、现行取舍及后续替代关系；相关场景再读ADR原文。 |
| 首批业务 | [创建契约v1](issue-page-create-api-contract.md)、[首批浏览器契约](first-batch-browser-api-contract.md)、[首批持久化](backend-first-batch-persistence.md)、[项目配置](project-configuration-design.md) | 创建REST／Issue SSE，项目与列表12端点，唯一关系、固定配置、事务和恢复。 |
| 消息澄清 | [浏览器五端点](conversation-message-clarification-api-contract.md)、[后端内部设计](backend-message-clarification-design.md)、[目标规则](conversation-message-target-design.md) | 已完成的最小r3；不能把全文B05或真实聊天接入一并标完成。 |
| 最新模型设置 | [模型设置](model-connection-settings-design.md)、[后端专项§7.8](draft-conversation-backend-design.md#78-模型设置的上游字段依据与接入边界2026-09-11) | 用户已采用的填写方式、锁定源码映射与专用应用协议缺口。 |
| 继续后端设计 | [后端专项](draft-conversation-backend-design.md)、[架构](architecture-design-v1.md)、[Manager创建工具](manager-create-issue-tool-design.md) | 身份／凭据、模块责任、可信来源、未完成的完整MCP。 |
| 按后续范围 | [Graph／Loop](graph-loop-design.md)、[团队执行](team-execution-policy.md)、[仓库分析](issue-creation-repository-analysis.md)、[ADR0020](../adr/0020-python-repository-analysis-plugin.md) | B06—B08的运行／受控执行／Python边界。 |
| 协作与页面 | [页面交接](HANDOFF-PAGE-API-DESIGN.md)、[页面专题](conversation-issue-separation-design.md)、[原型导航](../prototypes/README.md)、[通信约定](design-communication.md) | 先恢复最终采用范围和文件负责人，再处理新变更。 |

[旧后端Prompt](NEXT-BACKEND-SESSION-PROMPT.md)仅提供历史阅读清单和证据入口，不作为新会话开场指令。接手不要求无差别重读全部历史或运行其中脚本；准备采纳某项上游能力时必须读对应确定源码及证据条件。

## 3. 已完成的设计基线

### 3.1 项目、创建、列表与持久化

RM-B01-04 r2与RM-API-01 r3已对齐并互核，后者第三轮已收口。创建接口v1保持。这里是首批范围内的具体设计完成，B01—B04整体并未全部完成。

- 首批项目owner-only；稳定本地userId绑定外部provider／host／账号ID，login和邮箱不作为身份。GitHub参与资格、用户当前读权、App安装能力、本地项目资格分别判断，不从同仓协作者推导本地成员。
- 一个Issue恰有一个不能改绑的主／来源Conversation，一个Conversation可关联0..N个Issue。Issue×仓库只在实际委派时形成0..1个稳定RepositoryIssue，任务和重试不另造仓库事项。
- 新项目及明确加仓须核实本次完整新范围；unknown不能按允许或静默遗漏处理。App／模型／环境缺失或未知可以保存待配置项目。旧项目失权仓保留，允许修复资料／配置；首批只接受显式`repositoryIdsToAdd`，不提供删仓或整集合替换。
- 敏感内容按只增的ContentRepositoryScope保护；普通自由文本保守纳入保存时项目全仓范围。读取检查整个对象的历史内容范围，缩小当前工作范围不能解密旧材料。
- Issue、主ChangeSet、必要新会话、来源／输入快照、幂等结果、待办及事件同一个PostgreSQL短事务保存。READ COMMITTED、显式锁及最终唯一约束共同保证唯一提交；外部权限查询、实例准备和模型调用在事务外。
- 幂等按入口、主体及相应业务范围绑定原操作；同键同输入回原结果，同键异输入拒绝。未知查询404不证明未提交，410保留墓碑语义，不随手换键重建。内部未提交占位不伪装公开running／failed。
- 有效profile与secret版本固定于configurationRevision；普通资料更新、加仓或后台观察不暗换配置。现行显式完整configuration PATCH重新解析model和execution两项引用，不能拿“execution仍是同id／inherit”保证其实际版本不变。
- 持久待办与业务提交同事务，以稳定原因／类型／目标去重；领取租约、代次与实际资源占用分开。租约过期不证明旧进程停止，外部结果未知先核查原操作。
- 列表默认50、最多100，以稳定ID键集及不透明游标分页；游标绑定主体／查询／范围，空页仍可能有next。敏感候选授权未知按契约503，不伪装空列表；发现接口可明确partial。Issue事件使用每Issue提交顺序计数器，不推导Conversation或Graph SSE。
- 浏览器注销不撤销已提交业务及待办；后台按原actor当前资格核权，不依赖原Cookie继续存活，也不能换系统身份绕过失权。

确切JSON、错误码、事务次序及保留规则见上述三个唯一来源，不以本节摘要替代字段契约。

### 3.2 最小消息与目标澄清

RM-UI-MESSAGE-TARGET r3已完成技术与最终落盘互核。浏览器仅定义已有会话下五个端点：提交消息、查询提交结果、消息列表、单消息、单澄清问题；后端设计覆盖其本地记录、事务和受控目标判断。

- `replyTo`存在时绑定clarificationId与expectedRevision；没有权威selectedIssueId或模型自报actor。候选点击只填入可编辑答复，保存答复不等于目标已核定，更不等于计划或派工生效。
- 服务端生成并绑定源消息、逻辑请求和问题身份；一个问题只有一份有效答复。不同提交键竞争时，胜方整体保存，败方整体409并保留用户输入，不产生孤立消息；同键重放先查原回执。
- 问题为open→answer_saved→resolved；冲突需旧问题superseded与新open问题同事务，来源失效才用invalidated，权限unknown不是业务失效。
- 直接解释只可消费没有问题历史的pending请求及其root消息；存在开放问题不得绕过。答复分支只消费当前answer_saved的唯一答复。两分支保存目标解释和后续核验责任，不直接改计划、准备Worker或派工。
- Manager控制动作必须有可信身份、会话代次、源版本、租约领取代次和持久控制槽位；正文角色声明不是凭据。旧执行者不能写入新的判断，原操作查询另按当前权限处理。
- 成功回执中的answeredRevision固定为答复提交前所消费的问题版本；当前状态另GET，不回写历史回执。每Conversation保存顺序为十进制字符串计数，列表游标有高水位；不新增Conversation SSE。

完整MCP Schema、首次会话／首条消息入口、多来源及跨多Issue请求拆分、更正、实际传输／凭据签发和后续动作仍未完成。这里的目标解释不是完整执行授权。

### 3.3 供应商与模型设置

RM-UI-MODEL-SETTINGS r3技术及落盘已互核；用户在新版原型及模型编辑弹窗展示后回复“ok可以的”，采用当前供应商分栏和模型参数填写方式。最后采用通知见后端日志CP31。

- 供应商是RepoMesh管理分组，可有多个模型，不等于项目唯一modelProfile。应用须明确一个模型及供应商参数、模型参数、密钥版本组成的固定快照；不能通过覆写同一组全局环境变量实现多个隔离引用。
- 当前表单依据锁定源码的自定义OpenAI兼容路径。安装选择`openai-compat`、探测`/chat/completions`、Higress `openai/v1`与OpenClaw `openai-completions`分层表达，不据参考图扩展Anthropic Messages或承诺全部runtime等价。
- 模型ID、contextWindow／maxTokens／reasoning／vision均有源码依据；显示名是RepoMesh元数据，上游没有独立安装环境变量。已知模型值只标锁定源码预设，未知模型显式填写是RepoMesh选择，上游安装器本身仍有默认值。
- 上游启动脚本可能保留已有同ID模型记录；填写／导出能力参数不证明既有runtime已更新。供应商原始Key和runtime网关Consumer／Matrix凭据分开；embedding是独立可选配置，RepoMesh记忆接入未设计。
- 保存、逐模型固定快照测试、用于项目分开。新快照未测试，旧历史观察保留但不移植；草稿不能拿旧值测试／应用冒充新输入。保存或测试未知查原操作，不重复可能收费的请求。
- **应用目标为仅换模型，精确保留原execution引用及有效版本。** 绑定预览模型快照和项目修订，变化后回读重新明确；其他项目与在途Issue不暗换。现行完整PATCH不具备此保证，必须补专用应用协议，不能暗改RM-API-01 r3。

owner、真实密钥只写不回显的方向已确认；具体加密／传输／轮换、共享映射、测试费用与有效期、受控出站、原子应用／幂等恢复和运行传递仍待设计与验证。

## 4. 页面采用状态速查

下表只记录已展示范围。技术ACK不补写用户采用，用户“继续下一项”也不等于接受前一页；除已明确方向外，新页面仍由页面负责人展示讨论。

| 主题与最终轮次 | 用户采用范围 | 原型／说明 |
| --- | --- | --- |
| RM-UI-01 r3，3／3 | “正确”：创建Issue居中弹窗、大小及字段排布 | [创建弹窗](../prototypes/repomesh-issue-modal-prototype.html)；已替代独立全页／三方案。 |
| RM-UI-CONV r1，1／3 | “可以的”：底部关联会话控件与展开列表 | [关联会话](../prototypes/repomesh-issue-conversation-prototype.html)。 |
| RM-UI-SUBMIT r1，1／3 | “确定”：已展示的等待／成功／未知查询文案和按钮 | [提交反馈](../prototypes/repomesh-issue-submit-prototype.html)；完整刷新、404／410、失权、多操作未演示。 |
| RM-UI-DETAIL r1，1／3 | 尚未明确采用详情概览 | [详情](../prototypes/repomesh-issue-detail-prototype.html)；技术已ACK。 |
| RM-UI-PLAN r2，2／3 | “是的”：当轮只读DAG布局与图下节点详情 | [DAG](../prototypes/repomesh-issue-dag-prototype.html)；替代r1简化卡片，真实图协议未完成。 |
| RM-UI-DELIVERY r1，1／3 | 尚未明确采用交付摘要／逐仓折叠 | 同一详情原型中的交付页签。 |
| RM-UI-ROOM-NAV r2，2／3 | “正确的，进行下一项”：悬浮入口、响应式收起与同页右栏 | [会话悬浮入口](../prototypes/repomesh-conversation-dock-prototype.html)；替代r1离页导航。 |
| RM-UI-MESSAGE-TARGET r3，3／3 | 最小技术协议已收口，新控件尚未明确采用 | [消息目标控件](../prototypes/repomesh-message-target-prototype.html)仍是r1展示，不等于r3真实链路。 |
| RM-UI-PROJECT-ENTRY r1，1／3 | “正确”：先选仓库、再填资料及授权提示 | [项目入口](../prototypes/repomesh-project-entry-prototype.html)；不代表真实OAuth／完整发现已接通。 |
| RM-UI-MODEL-SETTINGS r3，3／3 | “ok可以的”：供应商分栏和模型参数填写方式 | [供应商模型设置](../prototypes/repomesh-model-provider-prototype.html)；旧r2弹窗仅历史。 |

右栏查看上下文不替代消息工作目标；切换撤下旧敏感内容、晚到响应不得回填，草稿不随导航丢失，注销／失权仍清敏感数据。Leader房间只读、打开时核资格与实际可进入状态；业务会话可读和DAG可读不必等runtime Ready。原型断点、样例数量和内存状态不冻结业务协议。

## 5. 还缺什么，建议从哪里继续

用户若未另指定主题，建议先补模型设置已暴露的协议缺口，并完成第一批认证／发现接入契约，再推进完整消息与运行。该顺序是接手建议，不自动启动实现，也不是重新开启已收口的UI r3讨论。

| 范围 | 已有成果 | 下一份需要交付的设计 |
| --- | --- | --- |
| B01：身份、权限与模型配置 | 后端专项§7.1—7.4责任／凭据／失权规则，§7.8模型源码依据，模型设置r3 | 真实登录／回调／注销与账号发现契约；供应商、单模型、profile及SecretVersion关系；只写Key提交／轮换／原操作查询；测试权限／费用／有效期／受控出站；精确模型应用的原子比较及恢复。 |
| B02：最小关系 | 首批单主会话、仓库事项基数、只增内容范围、保留规则已具体设计 | 后续执行对象生命周期及运行房间拓扑；不要重新把首批反向基数标未定或擅自扩为多主会话。 |
| B03：事务与后台待办 | 唯一提交、短事务、队列领取及未知核查已设计，DB01—17待执行 | 实现获授权后的迁移／故障验证；外部去重、围栏、实际停止和副作用核查依赖B05—B07，不靠租约宣称完成。 |
| B04：浏览器用例 | 创建v1、首批12端点、查询／事件设计已互核 | 未覆盖的完整会话详情／关联查询、图／房间读取及后续通知；页面维护唯一字段源，后端核对权限与一致性。 |
| B05：消息与Manager | 最小消息澄清五端点及本地控制协议r3已具体设计 | 完整创建／查询MCP input/output与错误；可信运行身份签发、稳定来源操作；首次会话消息、多来源／跨事项拆分、更正、真实投递／处理及晚到归属。 |
| B06：运行准备与受限主机 | 触发时序、进程边界已采用 | Project→实例、Conversation→room/session、Leader共享；有限主机命令／查询、凭据和限额；并发准备复用、就绪依据、停止／回收与重启恢复。无Issue讨论的工具及预算归属也在此闭合。 |
| B07：单仓受控执行 | 原生当轮DAG复用、资源原子预留、计划版本／生效和Loop约束已采用 | 单仓单轮完整时序、Task／Attempt／结果映射；写路径控制、取消与替补、证据采纳、多目标部分应用及换图恢复，再扩跨仓。 |
| B08：仓库分析 | 建项前可选受控Python方向已采用 | 锁定依赖／快照、版本化JSON Schema、作业领取／限额／停止、输出校验／覆盖不足／恢复与创建来源；失败不阻断手动建项，不依赖AgentTeams Ready。 |

下一位若从模型协议开始，先写一份明确标注设计范围的方案：对象与版本关系、每个操作的主体／权限、请求与不可变回执、并发比较条件、未知结果查询和失败矩阵。尤其覆盖“预览后模型被改”“项目被其他操作更新”“执行默认已变但本次必须保留旧有效版本”“密钥失效／测试超时”“项目引用旧快照”这几种情形。浏览器字段先与当前页面负责人核对后落盘，内部表／MCP／Python只由后端维护；不要通过新增字段暗改原12端点契约。

每个可实施批次须有一致的页面状态、数据／事务约束、接口输入输出与恢复、失败验收方案。缺设计写待设计，缺证据写待验证；设计满足条件也不代表本次允许编码。

## 6. 不能丢失的架构与证据边界

- cmd只组装入口；Web、后台协调、受限主机执行共用产品Go module与版本，权限分离。Web／Agent不持有Docker socket，执行器不开放任意宿主命令或挂载。第三方和validation的go.mod仅是遍历边界。
- 每长期项目独立AgentTeams实例、长期Manager和每仓Team／Leader；所有需求经Manager。业务Conversation／Issue、上游Project／room／session／Task／Attempt不能互相当同一身份。内部仓库事项默认不触发GitHub Issue写入。
- 保存项目／空会话／只读访问不启动实例；首次业务消息或页面Issue提交后异步准备。成功提交、实际运行就绪、消息投递／处理、计划生效和派工分开取证，准备失败保留业务事实。
- Graph在后台进程内，仓内有限DAG复用上游，RepoMesh负责跨仓条件、结果采纳和Loop；不自建完整Go DAG引擎。Plan Version、轮次、Task和Attempt分开，ready是候选而非已启动。
- Worker单活跃Attempt，资源预留与待办领取不同；超时／取消不证明旧进程或写入停止，不立即释放名额开替补。YOLO仍受权限／预算／计划／验收约束，Git合并由人处理。
- Skill工程、直接编辑图、后续审批、历史分析／向量库仍延后。仓库分析按ADR0020受控Python方向，不能从旧脚本顺手恢复这些范围。

上游在[来源记录](../../third_party/agentteams-source.json)锁定`517caff9280242a00a4d4c06365352b9e41659c6`，2026-09-11模型字段核对时HEAD一致且干净。下一次涉及源码先查实际HEAD和本地修改；不自动更新main。模型字段核对只读了相关安装器、模板、已知模型、启动及controller代码，不等于所有runtime或实际供应商均验证。

历史真实证据从[骨架阶段证据索引](scaffold-agentteams-evidence.md)、[总交接§6](HANDOFF.md#6-通信现状与证据限制)、[Graph专题](graph-loop-design.md)追溯，保留各自提交和实验条件。关键风险包括：REST拒绝不能覆盖shared写入／原生工具角色覆盖；取消与进程／副作用停止不一致；请求资源值不一定成为真实容器限额；paused replan拒绝及在途／submitted阻止换图；Matrix消息持久化不证明runtime保留reply/thread归属；HTTP200可能返回HTML。后续设计须处理真实写路径和可观察证据，不用提示词或状态字段代替控制。

本设计会话未运行Go/npm、数据库故障注入、真实Key／模型、OAuth、上游安装或runtime验收。DB01—17、AUTH01—12、MC01—24均为**待执行设计用例**。已做的检查为文档链接／JSON／用例编号与源码静态核对；最近模型阶段检查3份后端文档67个本地链接通过。页面报告的Node／390px／浏览器演示仅归页面侧，不计作后端真实验收。本次交接归档检查另见归档说明和日志CP32。

## 7. 新会话身份、协作与文件归属

**2026-09-11接任登记：** 用户已在任务“后端设计师”（`01a08fc8-7eba-7d22-81c6-08e41c107d1a`／local）明确要求“你现在接任后端设计师”。继任后端沿用本节文件归属，自己的记录见[新后端日志CP00](design-communication-backend-2026-09-11.md)。当前完成身份登记及入口阅读，双方原文日志全文和具体契约仍待补读，尚未开展新技术提案或完成协作恢复。下表保留交接时快照；共同通信约定及页面文件由继任页面维护。

下表用于核实接替关系，不代表新会话自动获得旧身份或需要唤醒旧任务。

| 角色 | 交接前任务 | ID／host | 接手处理 |
| --- | --- | --- | --- |
| 退出本轮的后端 | 后端设计师1 | `01a08ae6-5127-7491-a82f-3d63e8aaa58c`／local | 仅历史来源，不再把待办发给旧后端。 |
| 同时退出本轮的页面 | 页面接口设计师1 | `01a08ae6-5127-7491-a82f-3c0c076c45b1`／local | 页面也按用户要求完成新交接，停止编辑；仅历史来源，不再联系其复工。 |
| 接任后端 | 由用户打开的下一会话 | 尚未分配到本文 | 不虚构ID；核实后更新通信角色表／编辑归属和新日志入口，不创建额外会话。 |
| 接任页面 | 由用户打开的下一页面会话 | 尚未分配到本文 | 需要协作时先用任务列表核实实际接任身份／状态及用户授权，再联系新负责人。 |

本次只交付文件，不创建、归档或交接Codex任务本身。已核对新[页面交接](HANDOFF-PAGE-API-DESIGN.md)§3／4的F01—F15待办、版本与已完成范围一致；其§6最初仍记本后端为现任，收到一次状态通知后已改为双方前任，页面启动语及通信约定也已同步，后端已读取核对。以双方实际继任身份为准，不能据旧快照向前任发新工作。既有持续设计授权不恢复更早历史协作者；没有新通信需要时不为了交接循环ACK。

| 唯一负责人 | 文件范围 |
| --- | --- |
| 后端 | 本稿及后端入口、draft-conversation-backend-design.md、backend-first-batch-persistence.md、backend-message-clarification-design.md、architecture-design-v1.md、manager-create-issue-tool-design.md、内部／MCP／Python协议与自己的日志。 |
| 页面 | 浏览器REST／SSE契约、项目／模型／消息／页面专题、页面交接、共同导航和通信约定、HTML原型及页面日志。 |
| 需要先协调 | 新增整文件归属、ADR／CONTEXT改变、跨责任文档的修订。不得同时维护两份字段源或覆盖他人未提交修改。 |

通信沿`【主题ID｜rN｜PROPOSE/ACK/CHANGE/BLOCKED】`，说明结论、影响与文件、需要确认项。发送前保存完整正文，发送后记投递结果，收到后保存原文；投递成功不等于ACK。技术对齐后按唯一负责人落盘，只做一次一致性核对，避免循环回执。

RM-COMM-01 r1（1／3）、RM-PAGE-01 r1（1／3）、RM-B01-04 r2（2／3）、RM-API-01 r3（3／3）已收口；UI各主题最终轮次见§4。第三轮主题不得因新会话、改名或压缩开启第四轮；真正新增的机器协议与原主题未完成依赖要明确界定，不能借新主题推翻旧约定。若确有不能兼容的变化，明确写出替代影响并向用户报告。

原文在[本轮后端日志](design-communication-backend-2026-09-10.md)及[本轮页面日志](design-communication-page-2026-09-10.md)，旧09-09日志只供历史溯源。交接最后业务状态为后端CP31、页面CP28；本次文档交接另在后端CP32与页面CP29记录，双方无待回复业务分歧。按通信约定接替协作时完整读取两份本轮日志；用有界分段避免截断，不能声称工具已截断内容读过全文。此前一次压缩恢复仅读了相关原文的限制已如实保留在日志。新会话另建自己的日志，旧原文不改写；新日志检查点写明接替身份、归属、轮次、最后收发、未回复项、用户采用范围和下一步。

工作区已有大量未提交／未跟踪文件，不能清理、重置或把整个dirty状态当成本会话产出。Git ownership错误只用当前命令／会话信任设置，不改全局配置。纯文档只检查链接、引用、状态和源码事实，不启动服务、不重跑旧实验、不清理共享容器或卷。

## 8. 给下一会话的开场文本

```text
你现在接手 RepoMesh 后端设计。工作区 D:\Project4work\Repomesh_Go_ver。
先阅读 docs/current/HANDOFF-BACKEND-DESIGN-2026-09-11.md，按其中清单核对当前基线。
只产出中文设计文档，不改代码、不启动真实服务或重跑实验。
保留已采用契约、主题轮次与用户页面确认；先核实接替身份及文件归属，再按当前授权继续协作，不自动召回旧后端任务。
先简要报告已经完成、仍缺什么及准备继续的具体设计范围，再推进必要文档；无需重复请求已授权的常规设计选择。
```
