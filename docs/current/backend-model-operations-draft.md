---
status: proposed
date: 2026-09-11
design_revision: RM-MODEL-API-r1-internal
review_revision: R01-2026-09-12-candidate
implementation: not-started
---

# 首批模型保存、测试与专用应用 · 内部完整待审稿

后端设计师2独占本文件。用户要求一次交付六项全部，本稿提供具体候选而非仅列缺口；M项全部待用户决定，既有模型UI r3、F04目标、项目PATCH及创建契约不被改写。浏览器路径／字段唯一候选由页面在model-settings-browser-api-draft.md维护；本稿只定义内部对象、事务和对外结果应满足的责任。尚无数据库、API、密钥或模型调用实现。

2026-09-12候选修订：按[设计审查R01](../reviews/2026-09-12-design-readiness/README.md#r01key-保存的永久未知状态)补充§3.4原保存终结，替代“含Key保存未知只能查询”的不完整恢复规则。修订仍proposed，不增加历史技术ACK或用户采用记录。Issue的配置归属另见[配置绑定候选](issue-configuration-binding-design.md)，本稿不代定其绑定和运行方案。

依赖[来源稿S01—S08](backend-first-batch-sources-draft.md)。特别是预算：双方已将S05请求次数预算合并为待审推荐，供应商费用只提示“可能发生”；浏览器初稿的金额估算已撤换。金额预算仍是须另审价格／计量的替代，任一方案均未获用户采用。

## 1. 集中裁决编号

| 编号 | 具体推荐 | 代价及替代 |
| --- | --- | --- |
| M01 对象／版本 | 每供应商一个完整不可变快照；每模型稳定行ID及modelProfileId；旧行不能省略形成隐式删除。 | 修改一个连接参数会形成新供应商快照，所有新测试按新快照记录。 |
| M02 保存幂等 | 同actor＋provider_save＋saveId唯一；保存与显式终结竞争同槽位，终态为committed／rejected／closed_without_save。实际保存输入仍用受保护MAC及确切输入核对。 | 终结不需要重收Key；必须以事务阻止迟到保存，不能依赖超时或前端锁。 |
| M03 查询／保留 | 保存／应用回执在主体／项目历史期保存；closed_without_save保留无秘密固定回执和原槽位；测试结果30天，未知责任和不可复用墓碑继续保留。 | 新增原保存终结入口，不撤销已保存配置，不增加测试／应用取消或供应商删除。GET 404仍不能证明未提交，410不复活。 |
| M04 测试预览 | 固定保存快照＋单模型＋5分钟预览＋固定短prompt／至多16输出token（不超保存上限）；明确可能收费。 | 不支持自定义提示、图片／工具／流式或一次测试全部模型。 |
| M05 测试外发 | 先持久登记测试、预算与待办；可能发送后只查原操作，不自动再发。 | 崩溃可能留下需核查的unknown，优先避免重复收费。 |
| M06 测试观察 | queued／running／passed／failed／unknown／rejected对应可证据状态；15分钟只读新鲜度提示，不增加“近期测试通过才可保存／应用／建项”的门槛。 | 通过仅证明这次请求，不证明运行或未来请求成功。 |
| M07 项目专用应用 | 预览固定候选和原项目修订，事务内只替换模型，原execution引用及有效版本原样复制。 | 候选或项目变化须重新预览明确确认；不能复用完整configuration PATCH。 |
| M08 故障／审计 | 用户／版本／政策锁排序、结果不可变、费用责任与运行状态分开；只白名单审计。 | 需要故障注入验证；不把租约当外部幂等能力。 |

上述数字／期限也是候选；完整总包可统一评审，不要求现在逐项停问。现有owner-only与密钥只写目标为基线；新的内部细节仍待明确采用。

## 2. M01：对象与不变量

| 内部逻辑记录 | 内容／唯一约束 |
| --- | --- |
| Provider | providerId、ownerUserId、headRevision、停用／访问代次；providerId不复用。 |
| ProviderRevision | providerId、revision、name、规范化baseUrl、apiFormat、secretVersionId、创建人／时间；完整模型集及参数不可变。 |
| ModelRow | modelRowId、providerId、modelProfileId；稳定ID和profile一一对应，不从外部modelId名字生成。 |
| ModelSnapshot | providerId／providerRevision／modelRowId、外部modelId、displayName、contextWindow、maxOutputTokens、reasoning、vision；同快照外部modelId唯一。 |
| ModelProfileVersion | modelProfileId、providerRevision、modelRowId、secretVersionId及固定参数引用；与该providerRevision同时建立。 |
| ModelOperation | actor、entry、operationId、可空target归属、recordKind、schemaVersion、可空输入比较依据、outcome、不可变回执／墓碑；每作用域唯一。保存输入记录与无输入关闭记录分型，不能为后者伪造Provider或Key依据。 |
| Preview | 随机previewId、kind、actor、固定候选、政策／accessEpoch、project对照（应用时）、expiresAt、consumedByOperation；不是权限token。 |
| ModelTest | testId、actor、providerRevision／modelRowId、预览／政策、状态修订、acceptedAt、实际观察、预算引用、dispatch状态；一个测试一条逻辑外发。 |
| ModelDispatch | testId唯一、externalOperationId、sendPermit、claim代次、可能发送阶段／时间、已观察证据；没有“换代次就算新调用”。 |

ProviderRevision不可变但可用性观察可变化。更新Base URL或Key会形成新的完整快照；即使部分模型参数没变，新测试仍绑定新providerRevision。旧项目／Issue继续固定原profile／secret版本及历史测试，不自动移植。

所有初始候选限制与HTTP稿同步：供应商1..50模型，保存体≤256KiB，Key1..8192 UTF-8字节不trim；新建必须明确replace；更新keep原样沿用既有SecretVersion，replace即使相同明文也生成新版本；不向用户报告“与原Key相同”。已有模型行全量保留，外部modelId可在新快照编辑，stable row/profile不变；禁跨供应商／跨owner引用。

## 3. M02—M03：保存、敏感比较与确定拒绝

### 3.1 原操作和输入比较

保存作用域(actor, provider_save, saveId)；是否新建及providerId为输入的一部分，不能用同键切换目标。应用另用(actor, project, model_apply, applicationId)，测试用(actor, model_test, testId)。先核当前主体／有权结果，再查原操作，之后才核新版本／预览／策略；旧成功不被预览到期或新默认改判。

原保存终结使用同一provider_save槽位，不分配第二个close操作槽位，也不与保存正文比较输入。recordKind=save_input对应committed／rejected，保留既有比较责任；recordKind=save_closed对应closed_without_save，只有actor、saveId、关闭依据与固定时间，不含canonicalInput、HMAC、InputVault或SecretVersion。合法迟到保存读到save_closed先按MODEL_SAVE_CLOSED拒绝，不要求解密或重新输入Key。

规范化规则固定schemaVersion：拒绝重复JSON键及未知字段，保留文本原值，规范化允许的baseUrl尾斜杠；模型行顺序无业务含义，稳定已有行按id、新行按唯一外部modelId排序，但重复成员先拒绝。规范化输入包含secret.mode；replace包含真实UTF-8字节，keep没有value。不同schema保存对应比较器，升级不改判旧输入。

受保护比较建议：
- 为操作生成随机比较密钥，只在SecretStore按operation-input用途封装；ModelOperation只持其引用。
- canonical非秘密字段可随操作保存；秘密贡献用HMAC-SHA-256覆盖带长度编码的用途／原值。无裸Key哈希，不向客户端返回MAC或比较密钥。
- MAC相同后再核确切值：成功replace可解密本次SecretVersion进行恒定时间字节比较；确定拒绝时用短期InputVault中的信封加密确切秘密输入。keep比较原请求意图，不重新解析成当前Key。
- InputVault／比较密钥只供该操作重放比较，用途和actor绑定，不能由通用查询解密；原文不进操作索引／审计／来源／URL／浏览器存储。
- 材料已合法清理时先按墓碑410处理，不再拿新输入比较或执行；根暂时不可用时503，不谎报输入不同。

不可因MAC摘要猜测将来的权限／SecretVersion有效性。同键回执是原写入事实，不保证该Key当前仍能调用。

### 3.2 保存事务

格式／大小／认证失败可在事务前拒绝，但这些错误不表示某个已在途同键操作已终结。能够确定作用域及合法规范化输入后，按actor访问行→操作唯一槽位→Provider→引用可用性／secret元数据的固定次序锁定；创建Provider时由actor／操作槽位串行保护，不用临时供应商名锁身份。

1. 查原committed／rejected／closed_without_save／removed记录；先核当前结果读权。removed走410，closed_without_save走MODEL_SAVE_CLOSED；只有committed／rejected做原输入比较并返回原结果，不再跑新修订检查。
2. 新更新比较expectedRevision并核owner、完整模型集合／合法参数、明确secret意图及当前受控秘密基础。外部模型请求不在保存中执行。
3. SecretStore加密及MAC所需材料可先在内存准备；不对外提交不可回滚的Key创建。密文、SecretVersion和比较引用都在同一PostgreSQL事务写入；失败销毁未入库临时材料。
4. 分配新ProviderRevision，写完整Models／ProfileVersions及secret引用，更新Provider.headRevision；保存不可变committed回执与白名单审计。新保存不创建项目、不更新项目配置、不产生测试或运行待办。
5. 任一约束冲突整体回滚，不能残留新Key或半套模型；唯一约束是最后防线，外键含provider／owner作用域。

### 3.3 “明确未保存”怎样成立

新模型操作允许持久rejected，是独立接口候选，不更改现有三类项目／Issue写接口只有committed查询的规则。

在已经取得操作槽位且输入可比较时，业务修订／受控策略的确定性拒绝可在短事务保存rejected＋原因＋决定时间，不写Provider／Project改动。任何同键稍后到达者都先命中这个终态，不能再提交。这种回执可驱动页面“明确未保存，可重新编辑后新操作”；无原输入的另一种终结证明closed_without_save由§3.4定义，不冒充输入已被业务校验拒绝。

解析失败、身份不明、数据库超时、没有权读取结果、单次查询404以及进程无响应均不是该终态。校验错误不应让用户将旧并发请求视作已停；无法取得唯一槽位或事务提交结果未知，则保持原结果查询。503等可恢复前置错误一般不占永久拒绝槽位。浏览器含Key保存发出后不重收Key重放，可按§3.4明确终结原槽位；只有得到rejected或closed_without_save才可直接回草稿新建操作。

### 3.4 R01：无原输入的原子终结

新增关闭动作只作用于当前actor的原provider_save/saveId，浏览器信封、联合响应及错误由[浏览器稿§3.1](model-settings-browser-api-draft.md#31-r01终结原保存解除未提交操作的未知状态)维护。它不撤销已经提交的供应商版本，不触发模型请求，不取消测试／应用，不依赖原Key、受保护比较密钥或模型出站。

认证先核当前有效主体、模型配置操作资格和Origin／CSRF，不接受客户端actor。已有记录按当前结果读权及实际绑定目标owner核权；空槽位只属于当前actor，不要求Provider存在，不查询或披露另一actor的同名saveId。当前主体无动作资格可403，已有目标不可披露隐藏404，资格未知503；这些结果都不是“原保存未提交”。没有业务Key的关闭仍须普通限流、请求体和审计白名单，不能将任意外部传入的身份写成授权依据。

关闭事务和所有保存、拒绝、清理路径遵守actor访问行→provider_save操作唯一槽位→已绑定Provider／引用记录的公共锁序。不能只对不存在的操作SELECT FOR UPDATE后认定已锁住：同actor访问锁串行保护空槽位，(actor, entry, saveId)最终唯一约束兜底；插入竞争后使用新语句读取赢家。槽位保留在同一短事务内，不能先独立提交“关闭已接收”。

1. 在主库短事务中锁定actor并重核资格，查同槽位。已有committed／rejected，在核权后直接返回不可变原回执；关闭不用原Key做输入比较，也不重新跑当前模型配置条件。已有closed_without_save返回相同closedAt；removed返回有权410。
2. 若另一保存事务尚未提交，关闭必须等待其提交或回滚；锁预算耗尽、主库不可达或事务结果不确定返回RESULT_UNCONFIRMED。不能把“查询看不到未提交行”当作可关闭证据。
3. 在统一锁下确认无终态后，插入recordKind=save_closed、outcome=closed_without_save及固定closedAt。记录必要actor访问依据、关闭原因和白名单审计，与槽位一并提交；target和原输入均为空，不写Provider、ModelProfileVersion或SecretVersion。
4. 提交确认后才返回关闭成功。COMMIT回执丢失时保持未知，GET原saveId或重复同一关闭动作；重复关闭复用原槽位，不分配新关闭键、不修改时间。
5. 原保存在任何密钥持久化或Provider变更前重新读取同槽位；若关闭已提交，无论原输入相同、修改Key或更换providerId均拒绝。事务外准备的密文／MAC材料不得落库，丢弃本次临时材料。关闭之前已持槽的保存若先提交，关闭只能回其committed，不能删除该配置再伪造closed。

该事务的证明是“截至原槽位终结没有保存提交，且将来同键也不能保存”，并不要求查明请求曾否到达HTTP入口。普通GET仍是只读查询，空槽位404不会产生终态。即使请求从未抵达、持槽前503或客户端原输入丢失，用户明确关闭仍能建立终结证明。

此协议只终结指定saveId。不同键是不同业务操作；同一Provider的不同保存仍由expectedRevision和Provider行锁决定先后。多标签不能自动换键逃避unknown或close未确认，服务端也不按供应商名、Key或时间窗口合并不同操作。关闭原操作不会暂停另一合法新操作或删除其结果。

closed_without_save无秘密比较材料，账户有效历史期内保留固定回执及不可复用槽位。普通正文清理可以把committed／rejected变为removed，但不得变成空槽位；对closed的后续历史清理同样保留removed和必要授权归属，不恢复保存资格。最终清理actor须先封闭该身份的全部写入口，且actor ID永不复用。旧保存和close重放命中removed均有权410，不返回closed成功，也不证明历史配置未曾保存。

## 4. M04—M06：固定单模型测试

### 4.1 预览内容与接入规则

预览随机不可预测，TTL候选5分钟；绑定actor、providerRevision、modelRowId、secretVersionId、当前Provider.headRevision、出站／测试／预算政策版本和相关accessEpoch。只允许对当前已保存快照发起新测试，历史版本仍可读原结果。预览创建只保存短期比较上下文，不发模型请求、不预留费用或额度。

固定请求为OpenAI兼容Chat Completions，messages只含user文本“Reply with OK.”，stream=false，无tools／images／自定义header。输出上限取min(16,该模型maxOutputTokens)，期限取已登记政策候选30秒；必须先确认适配器能向所选协议正确映射此限制，不能靠参数名字假设所有runtime／模型都支持。收到完整有效响应视为连通性通过，不要求文本严格等于OK，不把reasoning／vision能力声明当已验证。

推荐预览向浏览器提供“单次请求、可能收费、有限次数预算”及可提交条件；金额估算为空而不是0／免费。采用来源S05之前该取舍仍待用户。没有可运行测试处理器、出站准入、可用秘密／引用或权威剩余额度时canSubmit=false；提交再次核这些条件，不以预览通过授权。无处理器时不先接受一笔永远虚假的测试。

### 4.2 原子登记与状态

测试提交携原testId及previewId和明确confirmPotentialCharge。短事务按actor→操作→Provider／SecretAvailability→Preview→预算窗口／actor未核计数锁定；顺序在所有测试路径一致。

先处理原testId；新操作检查预览主体、期限、固定候选及当前政策未变、当前owner及出站／秘密资格，再检查同actor或同快照已有queued／running／unknown的限制。推荐每actor最多1笔未核清测试及每日20次，都是S05候选，不只在页面禁按钮。

接受时将ModelTest(queued)、原接受事实、1单位预算预留、DurableWork(kind=model_test)和审计同事务保存，并将Preview.consumedBy绑定testId。同预览不同testId不生成第二次调用；返回已有本人testId或确定冲突。202只说明本地登记；登记响应丢失可GET同testId，不再次预留。后台停用后已登记测试保留责任，不能消失。

对外状态由以下事实投影，内部dispatch子阶段不能直接当作HTTP枚举：
- queued：已登记、尚未观察到调用开始，可有受控领取；没处理器不伪造running。
- running：实际传输开始的受控观察已记录，且尚未得到结果；仅取得租约或发送意图不是依据。
- passed：该次请求已取得完整、可解析、符合协议的成功响应。
- failed：该次明确拒绝／错误响应或确定响应格式无效；可能已收费，不能等于预算退款。
- unknown：外部可能发送，未能确认结果；超时、崩溃或响应落库失败都可能触发。
- rejected：已证明没有进入可能发送阶段，或已证明未发出且旧发送权失效，持久终结；不等于“调用失败”。

只记录resultRevision的服务器内部单调序号，再编码不透明值；客户端不能按字典序判断“更高”。单个串行查询、目标／请求代次丢弃迟到响应即可；GET如需并发条件回读可用不透明等值比较，不自行解析序号。测试结果新鲜度15分钟仅提示，历史结果与其observedAt仍保留；不给项目偷偷新增测试门槛。

### 4.3 单次外发及未知

1. coordinator从持久待办领取有限租约，重新核actor、secret、出站、政策及测试状态。未进入发送意图前发现确定条件失效，可原子rejected并释放预留；只有调度异常且无法确认时保留责任。
2. 在短事务内以testId唯一登记externalOperationId和不可再次领取的sendPermit，写may_have_sent，并将预算预留转已消费。发送许可只交给此执行者；后续租约代次不能生成第二张许可。
3. 事务提交后执行者重新验证许可仍有效，再只发一次HTTP请求。关闭HTTP／SDK自动重试、重定向及代理绕过；不能拿上游不支持的幂等头声称收费恰好一次。
4. 传输开始／完成证据由受控适配器写入。不保存上游原始响应正文，保存白名单状态、latency、usage（缺失null）及响应校验结论；响应最多1MiB。
5. 结果事务比较原testId／externalOperationId和未终结目标，记录passed／failed、测试观察、预算状态和完成待办。正常写回需要领取代次；旧领取者迟到可提交受限Observation记录，当前核查者只采纳匹配同一外发的证据，不能令旧领取者覆盖新业务。
6. 已到may_have_sent后崩溃，即使可能实际未发也转unknown／reconciling。首批没有供应商通用结果查询／幂等能力，禁止自动重发；仅GET本地原testId不会触发新模型请求。

若发送进程仍存活但未响应，不因租约过期启动替代调用。后续只有可信外部证据或受控运维核查才能处理unknown；新测试前必须收口原操作的发送权与预算责任。没有确定证据时持续unknown并禁止绕过，不提供“忽略未知再试”按钮。

对长期无法找回结果的unknown，推荐运维可在证明原发送实例已失去调用能力后，以audited_close_unknown追加核查结论，预算按已消费保守保留，测试历史state仍unknown、增加内部resolvedAt与permitRevokedAt；不伪造成failed/passed。此后用户可重新显式确认一笔新测试，仍可能有新费用。该能力仅部署运维、未提供浏览器接口；条件／证据必须记录，不能只点“我确认”就消除正在存活的发送者。

关闭的是本地继续发送的责任，不证明供应商已经停止此前请求；后续新测试可能与远端尚未可知的处理重叠。maxUnresolved限制本地未收口操作数，不宣称供应商实际执行并发上限。迟到的原请求确切结果仍可由当前核查者采纳，保留先前运维关闭审计，不影响任何新测试身份或再次发送。

queued候选最长等待10分钟；超时且证明未进入may_have_sent可以rejected／NOT_STARTED并释放，不能把unknown按年龄转rejected。所有期限和运维关闭策略都属于M05的新候选，需要用户采用。

### 4.4 预算与费用的对外区分

来源S05的预算记账单位为request。登记预留1，may_have_sent转consumed，确定未发可released；外部错误／unknown不自动返还。建议API分开budget状态与charge观察：预算可知已消费1，但实际货币费用仍unknown；usage不是金额账单。不得用settled金额表述一次HTTP错误后的确定收费金额。

若最终用户选择金额预算，必须一并采用可信价格版本、最大输入／输出计量和未知费用预留策略；不能保留浏览器0.01美元示例却让后端只记次数。本稿向页面提出次数方案为首批推荐，并保留用户选择金额方案的代价。

## 5. M07：预览固定及原子保留execution

应用预览由POST生成5分钟短期记录，绑定actor、projectId、projectRevision、configurationRevision、原model引用／版本、原execution引用（完整mode/id）及有效版本／原有效政策快照、候选providerRevision／modelRow／profile／secret、Provider.headRevision及相关可用性代次。

预览只展示当前有权读取的信息。候选必须属于owner有权供应商，旧模型不可披露只显示受限，不阻止有权项目配置修复。原execution有效版本未知无法证明保留，canApply=false；原版本已明确但当前不可用，可保存受限配置，绝不恢复可执行资格。未测试不自动禁止应用。

应用短事务全局锁序：actor访问行→project→operation槽位→Provider及候选profile／secret可用性→Preview；后台停用按相同公共前缀和稳定ID排序，禁止持有secret锁再反向等待project锁。多个项目的来源失效先改观察，相关项目条件逐一更新，不建立相反锁序。

1. 先查原applicationId，核当前结果读权及原输入，重放committed／rejected／removed优先于预览到期。
2. 新操作核Preview属于当前actor／project，未过期且未被另一操作消费；比较projectRevision、configurationRevision、原execution完整引用及有效版本。
3. 比较候选仍为预览固定版本且当前Provider.headRevision未变；同一provider里其他模型更改也会变head，需重新预览，不静默采用旧／新。核当前候选可引用、已知不可用与unknown分别处理；unknown不得当allow。
4. 创建新的ProjectConfigRevision：modelProfile切成reference到稳定profile并固定候选providerRevision／secretVersion；execution完整引用、有效版本及其中预算／时限／并发等固定参数从原配置逐项复制，不访问execution最新默认解析器。
5. 更新projectRevision／creationContextRevision，保存不可变ApplicationResult、配置审计以及预览消费；整个操作原子。不调用现行完整configuration PATCH，不触发实例准备／模型测试／Agent重启。
6. 若所有模型引用及固定版本原本已完全相同，可以no-op成功：保留原configurationRevision／projectRevision，照样保存本applicationId回执和预览消费。此为M07候选细化，HTTP不得一律承诺每次成功修订必变。

比较冲突应在有权取得槽位后保存确定rejected回执，整笔无配置改动。同一预览不同applicationId只许首笔消费；第二笔给确定冲突而非重复应用。应用成功后的原结果只说明当时，读取当前项目另GET；其他项目和既有Issue配置不变。

审计／持久通知不扩充已有Issue SSE的changed枚举。项目配置更新按现行列表刷新；新模型操作不假造Issue.changed。已有Issue创建的事件／后续准备待办仍同事务，不能用模型操作规则削减。

## 6. M03／M08：查询、清理及故障矩阵

所有原操作查询要求当前actor及目标owner资格；应用按当前项目外壳配置资格，不要求先恢复所有旧仓读权，但返回结果不得泄露旧受限仓或模型名称。账户停用／无权隐藏404，外部资格未知503。去除秘密正文不等于可以跨用户公开操作记录。

保存／应用回执保留至其actor／project业务历史期结束；清理正文及比较材料时同事务写removed墓碑，保留作用域、原键、必要结果归属和权限依据。测试结果候选30天；unknown及未清预算／发送责任不能删除，哪怕前端结果已410也有内部责任和墓碑。不因清理允许旧preview／opId再次发模型请求。

| 故障 | 结果与后续 |
| --- | --- |
| 同键不同Key／模型／预览 | 有权比较后409；不会覆写原请求或用新Key执行旧操作。 |
| secret加密或事务失败 | 无半个Provider／SecretVersion；响应不明查原saveId。 |
| 确定修订冲突但另一同键仍在途 | 竞争同一槽位，只有唯一committed或rejected终态；未取得槽位不能先声称终结。 |
| 保存响应丢失，浏览器Key已清 | GET原saveId或明确close原槽位；不重收Key重放，终态确认前不换键保存。 |
| 请求从未抵达／持槽前503，GET持续404 | GET不改事实；close取得同槽位并提交closed_without_save，之后允许显式新操作。 |
| close与迟到保存竞争 | 保存先提交则close回原committed；close先提交则合法迟到保存MODEL_SAVE_CLOSED；保存回滚则关闭可接手空槽位。 |
| 两个close或关闭回执丢失 | 共用原槽位、固定closedAt；GET／重试同close收敛，超时仍未知，不能换键重发保存。 |
| close时无权、错主体或资格未知 | 当前actor隔离，隐藏／拒绝／503；不读他人结果，不把无权当作确定未保存。 |
| closed记录清理后旧保存／close重放 | 有权410及不可复用墓碑，无新Provider／SecretVersion；不将清理解释为未提交。 |
| 测试登记完成进程重启 | 同testId及预算／待办都在；未发送可继续一次，可能发送只核原操作。 |
| 供应商收到请求，结果落库失败 | unknown、保留预算消费与原dispatch；不自动免费重试。 |
| 新ProviderRevision与测试／应用并发 | 事务比较固定head／预览版本；新测试／应用拒绝旧预览；已发旧测试结果仍归旧快照。 |
| execution默认更新、旧有效版本未失效 | 应用复制旧有效版本及参数，不重新解析默认。 |
| execution旧版本当前失效 | 可在明确原版本下保存受限应用，结果不声称canCreateIssue或运行就绪。 |
| 预览过期时重放既有成功 | 原回执优先，不再执行预览校验／重复写入。 |
| 旧发送者或原账号失权后迟到结果 | 不再发新请求；仅受限证据记录、当前核查者处理原责任，用户结果仍核当前读权。 |
| 原结果被清理 | 有权410、旧键不复用；404也不证明可重建。 |

实施时需覆盖并发、进程崩溃、数据库提交响应丢失、DNS变更、日志脱敏、错根、scope与权限隔离测试。当前只完成候选设计，没有执行任何用例。完整运行消费者、Controller／Manager映射与HostExecutor安全调用不由本稿启用。
