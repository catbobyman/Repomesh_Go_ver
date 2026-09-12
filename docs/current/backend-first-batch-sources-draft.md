---
status: proposed
date: 2026-09-11
design_revision: RM-FIRST-SOURCES-r1
implementation: not-started
---

# 首批真实配置与秘密来源 · 完整待审方案

用户要求“你直接给我这六项的全部”，本稿是六项完整评审包的后端来源部分，由后端设计师2独占。所有S编号均为具体推荐、待用户决定；既有约束注明出处，不以本稿改写现行浏览器字段。当前仅页面／API设计，未导入配置、生成密钥或调用外部服务。

本稿细化[接入草案C](backend-first-development-access-draft.md)的未定来源；它与认证A／B不是一次整体采用。模型操作见[内部操作稿](backend-model-operations-draft.md)，HTTP字段由页面负责的唯一草案维护。以下记录名和导入格式是内部／部署候选，不是新增浏览器写入口。

## 1. 本次集中裁决清单

| 编号 | 推荐及范围 | 代价／替代 |
| --- | --- | --- |
| S01 秘密基础 | 首批独立部署根密钥文件＋PostgreSQL中的信封加密；应用用AES-256-GCM保护每条秘密，按用途隔离。 | 部署方负责文件权限、独立备份与恢复；替代是现在接KMS，增加外部服务依赖。 |
| S02 根密钥轮换与停用 | 新根只重包数据密钥；业务SecretVersion不变。业务Key替换则新SecretVersion；两种轮换分开。运维紧急停用走本地代次，不增加浏览器删除／停用UI。 | 需要保留旧解密根直到重包核验；根全部丢失无法恢复秘密，需重连／重新录入。 |
| S03 来源导入 | 部署身份提交版本化执行／预算／App／出站政策清单；校验后短事务整体导入，版本相同内容不同拒绝。 | 初期通过部署工具维护，无完整F06管理页；替代是扩建设置后台。 |
| S04 环境最小集 | 一种受限host-executor环境模板、Worker默认并发1，版本固定且声明上限；不用自由命令或挂载参数。 | 环境模板实际创建／停止仍由运行协议后接，登记不表示Ready。 |
| S05 首批预算 | 明确采用有限“模型请求次数预算”及并发／时限；测试和项目运行分别记账。首批不宣称金额上限或账单结算。 | 次数无法约束供应商每次价格；如果必须以金额为预算，需拒绝此推荐并另审价格／计量方案，不能用本稿冒充金额控制。 |
| S06 App动作策略 | 建项检查Metadata read、Contents write、Pull requests write与当前安装范围；真实动作再次核actor及动作规则。禁管理／合并／强推／workflow修改。 | 需要安装写能力；本地执行规则仍必需，App权限本身不能表达“只许draft PR”。 |
| S07 模型出站 | 首批只允许部署白名单的HTTPS域名＋基础路径，服务端固定解析与校验目标，禁止重定向和内网地址。 | 本地模型服务／任意私网网关本批不接；如需要须单独审批精确目标与隔离。 |
| S08 版本／观察 | 来源完整性与当前可用观察分开；旧项目固定版本不跟随新默认，失效只更新条件代次。 | 用户需显式提交配置／应用才能用新版本，缺项仍可存项目但建项受限。 |

S05的新“次数预算”需要明确用户同意，它没有沿用某个已确认金额数值。已有[团队策略](team-execution-policy.md)的团队上限、全局容量与项目额度取交集，且建项不预留Worker，继续保持。下面每个候选默认值均属于对应S项的可审范围，接受方向不自动接受未指明的数值。

## 2. S01—S02：秘密保存、权限与恢复

### 2.1 具体内部结构

部署在仓库和发布目录之外放置root-key文件；配置只给绝对路径及rootKeyId，不在.env、启动参数或日志放根正文。每个根是密码学随机32字节，文件由专用服务账号只读、部署管理员可更新；Linux模式0600／Windows ACL只授予相应身份，拒绝宽泛读取。首批不自动创建生产根、不把示例字符串当有效密钥。rootKeyId登记指纹校验，启动读到不同正文不得沿同id继续。

每条秘密使用独立随机32字节DEK。秘密正文用AES-256-GCM加密，DEK再由当前rootKey加密。推荐Go标准库NewGCMWithRandomNonce（根module go1.26支持该API）；每次密封由库生成随机nonce并随密文保存，认证标签不可省。每个DEK只密封一份不可变正文；重新加密生成新DEK。根包装次数以持久保守计数控制，候选上限一百万次，达到后拒绝新包装并要求轮换，不能在重启时清零。包装前先在独立持久事务预扣调用额度，随后业务回滚或进程崩溃也不退还；计数包括自检、重包与失败尝试，不能只统计最终保存的SecretVersion。数据库灾备不能证明计数完整时先换新包装根，旧根只解包。[Go认证加密文档](https://pkg.go.dev/crypto/cipher#NewGCMWithRandomNonce)

| 记录 | 内部必要字段／约束 |
| --- | --- |
| SecretVersion | secretVersionId、secretId、ownerKind／ownerId、purpose、ciphertext、wrappedDEK、rootKeyId、encryptionFormatVersion、createdAt；正文及owner／purpose不可变。 |
| SecretAvailability | secretVersionId、enabled、accessEpoch、lastCheck、reason；只更新可用性，不替换正文。 |
| RootKeyRegistry | rootKeyId、指纹、activeWrap、wrapCount、启用／退役审计；实际根正文不入数据库。 |
| SourceImport | importId、actorDeploymentId、schemaVersion、规范化非秘密清单、结果、committedAt；唯一作用域deployment＋importId。 |

AAD使用无歧义长度编码绑定encryptionFormatVersion、secretVersionId、ownerKind／ownerId、purpose；包装DEK的AAD再绑定rootKeyId。读取时从权威记录构造AAD，不能只相信调用方给的owner。认证失败不返回部分明文，不尝试别人的密钥或退回明文路径。

用途至少区分github-user-token、github-refresh-token、github-app-client-secret、github-app-private-key、model-provider-key、operation-input、deployment-signing-key。浏览器永不读取这些正文；API只返回白名单存在／可用状态或无权404。Key保存正文只到TLS下的专用保存请求和受控SecretStore；日志／Tracing／错误转储关闭请求体捕获。此候选不承诺Go内存能物理清零，实施须限制明文存活期和诊断转储。

Web中的秘密模块只向核验后的身份交换、敏感输入比较和写入用例解密；coordinator只向登记过的模型测试／外部动作解密；host-executor不获得用户模型Key或App私钥。三个进程的服务账号权限及部署根分发必须落实，不因为同module就授予任意 handler 或Agent读取。产品运行的有限凭据交付仍受[ADR0013](../adr/0013-web-coordinator-host-executor-processes.md)与后续运行协议约束。

### 2.2 首次设置与轮换步骤

1. 部署管理员离线生成根，登记rootKeyId及指纹，独立于数据库做加密离线备份；只记录备份责任与恢复演练日期，不将根复制到产品包。
2. 启动时检查文件身份／权限和指纹；读一条已知密文做自检。全新数据库尚无密文时写入专用自检密文，不制造用户SecretVersion。
3. 配置部署GitHub App身份及两种秘密：OAuth client secret和App私钥分别封装。模型Key只由用户在模型设置保存，不通过来源清单批量注入或共享。
4. 轮换根先安装新文件／注册新id，切换新包装使用根；旧root仍可解包。后台按记录版本CAS重包DEK，原业务SecretVersion和配置版本不变。
5. 全部引用已重包并完成抽样解密／计数核对后，才允许退役旧根；历史备份所需旧根按备份保留期单独留存。
6. 紧急停用具体业务Key或连接时锁本地可用性记录增加accessEpoch，新测试／新动作停止；旧已发请求独立核查。停用不删除原操作、旧项目引用或测试事实。

根不可读／损坏时，依赖解密的登录交换、Key替换／比较、测试等返回已定义的“秘密来源不可确认”责任，由HTTP草案映射503。元数据或已有受限项目能否读，仍按当前会话／owner判断，不用解密失败冒充账号不存在。若全部根永久丢失，恢复数据库本身不能恢复Key：先使受影响版本不可用，保留引用／回执／未知责任，再要求用户重新录入／同账号重连，不重建旧版本正文。

备份恢复须同时恢复数据库、root清单及所需旧根，并将外部可能已发送操作保持unknown，不以数据库回滚重置计费或再次发送。灾备切换需要停用旧发送实例的能力并核外部状态；本稿不以恢复数据库单独保证外部恰好一次。

## 3. S03—S04：来源清单与原子导入

### 3.1 内部清单schema v1（候选）

来源清单只允许以下字段组，UTF-8 JSON上限1MiB；未知键／重复键／重复id-version拒绝。不接受shell、任意环境变量、容器参数、挂载或明文秘密。

| 顶层组 | 每项必要字段及候选限制 |
| --- | --- |
| schemaVersion／importId | 固定1、UUID；导入回执长期按deployment＋importId保留。 |
| executionProfiles | id、version、name、allowedOwnerIds、templateId／templateVersion、workerConcurrency、projectWorkerLimit、globalCapacityProfileRef、timeLimitPolicyRef、budgetPolicyRef、verificationGroupEnabled。并发均正整数，候选1—16；默认1必须明写。 |
| environmentTemplates | id、version、executorPoolId、approvedTemplateDigest、networkPolicyRef、resourceClassId、enabled；只引用登记的受限模板，不携带任意宿主路径。 |
| timeLimitPolicies | id、version、modelRequestTimeoutSeconds、workerAttemptLimitSeconds；首批候选30和3600，范围分别5—120、60—86400。timeout不是已停止证据。 |
| budgetPolicies | id、version、scopeKind、unit=request、period=utc_day、limit、maxUnresolved、enabled；有限正整数，不接受null／unlimited。测试默认20／天且maxUnresolved=1；项目运行默认1000／天。 |
| capacityProfiles | id、version、workerSlots、enabled；来源为部署方明确核实的容量，不自动按CPU数推断。新部署候选workerSlots=1。 |
| appPolicies | id、version、host=github.com、appId、clientId、callbackUrl、clientSecretRef、privateKeyRef、requiredRepositoryPermissions、deniedOperations；权限矩阵见§5。 |
| egressPolicies | id、version、approvedBaseUrls、allowedPort=443、allowPrivateAddresses=false、followRedirects=false；精确规范化域名及基础路径。 |
| defaultBindings | kind、profileId、profileVersion、allowedOwnerIds；缺省数组为空。首批仅部署执行默认，用户模型默认不开新管理入口。 |

id/version是不可变逻辑身份，不从name／文件路径推算；引用必须同时携带id/version，不能使用latest。导入不登记新的模型供应商Key。deployment秘密引用须指预先受控封装的SecretVersion；文件不存在或引用不匹配不能形成可用App配置。

scopeKind为actor_model_test或project_model_runtime。首批运行预算只配置政策与权威账本结构，不开启运行处理器；额度存在不表示后台能执行。新项目已解析有权政策时，初始账本在项目创建同事务初始化，唯一scope＋period，初始used=0有“此前没有本地操作”依据；不能把供应商已有账单未知解释为0。未解析政策仍按现行规则保存受限项目，不伪造账本／默认额度；后续明确配置时再在同事务初始化或关联原scope窗口。

### 3.2 导入事务与结果

未来提供同产品的部署管理子命令，读取本地文件并以部署凭据操作数据库；首批不暴露Web管理API。本稿只是命令职责，不提供已能执行的命令名或新增第四个服务。

先做schema、模板登记、allowlist、秘密引用和owner存在性检查；外部核验在事务外。短事务按部署／id-version排序锁定，先查同importId：同规范化输入返回原不可变回执，不同输入冲突。新导入把所有新版本、默认映射、允许引用集合、审计与结果一起保存，任一失败整体不激活。相同id/version已有不同内容拒绝；相同内容可复用，不覆写。

激活默认映射只改变今后显式解析的候选。既有ProjectConfigRevision不改；读原配置可提示有新版本，不能暗中重新解析。改变可用性或本地允许引用范围须增加accessEpoch及受影响的creationContextRevision。项目只改name／purpose或加仓不触发配置重解析，沿[持久化§2.4](backend-first-batch-persistence.md)。

回执只包含importId、已登记id/version、默认映射修订、提交时间；无秘密路径或明文。若导入响应丢失，用同一importId查回执；查无记录仍无法证明旧导入不会提交。没有已执行命令／迁移或真实导入验收。

## 4. S05：有限请求预算与权威状态

### 4.1 单位、账本和保守结算

推荐首批把预算具体化为“最多允许发出多少次模型请求”，每次外发消耗1单位；一次测试只有一条请求。它控制RepoMesh请求量，不代表美元／人民币消费上限、不保证供应商免费、不测供应商账单。用户测试前须明确可能收费，费用与实际接入由浏览器测试说明展示。若用户需要金额预算，则S05不能直接采用，必须补价格版本、token计量与账单差异策略。

内部BudgetWindow保存scopeKind／scopeId、policyId/version、UTC窗口起止、limit、reserved、consumed及revision；唯一键是scopeKind＋scopeId＋UTC窗口，不把policyId/version加入唯一身份。ModelDispatchReservation唯一(testId或未来callId)，绑定窗口和1单位。所有增减与相应操作状态在同事务，接受新预留必须满足reserved＋consumed＋1≤当前有效limit。换政策不清零计数：当日新预留同时受窗口登记limit和当前政策limit的较小值约束，窗口登记limit只可原子下调、当日不回升；降低上限至历史占用以下只阻止新增，不改写历史或出现负预留，增加限额从下个窗口生效。每个actor的未核清外发数跨窗口计数，午夜不能清零未知请求以绕过maxUnresolved。

- 接受测试时预留1单位，拒绝不足额度／已有超额未核责任；用户同键重放不再预留。
- 发送前确定取消或未开始终结，可释放；必须证明没有进入可能发送且旧发送权已失效。
- 进入“可能发送”前的短事务将预留转consumed=1；无论最后成功、供应商返回错误、超时或结果丢失，先保守占用，不自动退款或补发。
- 未能证明是否外发时保留消费及未核记录；确定没有发出才能以带证据的调整事件返还。跨日仍归原窗口，不改成今日新调用。
- 外部响应usage只作为事实观察，不用于声称金额结算；额外隐藏调用、供应商重试收费或虚报usage无法由此保证上限，出站适配器必须关闭自身自动重试。

测试使用actor_model_test，项目运行未来使用project_model_runtime，不能借测试绕过项目运行预算或把测试成功当派工许可。首批不开放手工网页充值／退款／账单接口；运维调整须追加原因、操作者及账本事件，不改历史数值。

### 4.2 建项门槛与运行边界

创建Issue仍按现行契约核模型／执行配置、适用预算政策及额度、用户读权和App工作能力。推荐运行额度账本当前可确认且remaining>0，政策启用且范围可用；不足为已知条件不满足，账本读取失败为unknown。建项本身不消耗模型请求、不预留Worker、不保证多条排队Issue各自已有将来预算；实际调用再次原子预留。

S05不会把保存项目／配置也变成消费。缺少有限运行政策或权威账本时不以“未接运行”放宽创建门槛。单纯选可用仓库的Issue不因无关失权仓被禁；新业务及必要事件／待办仍按原事务保存。后台未接时保留INTEGRATION_NOT_AVAILABLE责任，预算剩余不生成preparing／ready。

## 5. S06：GitHub App逐动作规则

首批宿主固定github.com，不接任意Host。外部身份、安装仓库和permission来自GitHub当前查询，不来自浏览器回跳id、自报名称或部署期望。读取观察最多60秒、新写重新核实且距提交≤15秒仍为接入r1候选参数，采用状态与认证后续稿统一；本地accessEpoch改变立即使旧观察失效。

| RepoMesh动作 | App最低候选能力 | 用户／本地限制与失败 |
| --- | --- | --- |
| 登录账号识别 | GitHub App用户授权流程；账号身份查询 | 不把OAuth成功当安装成功；稳定ID绑定，不用email合并。 |
| 发现／仓库元数据读取 | Metadata read；使用用户token实际可见集合 | 用户当前参与／读权，coverage如实partial；App token单独可见不赋用户权。 |
| 新项目／明确加仓 | 本次所有新仓用户读权；App工作能力单独观察 | App不足可存受限项目；用户读权未知整次新增拒绝。 |
| 手动创建Issue | 当前安装覆盖本次每仓；Metadata read＋Contents write＋Pull requests write | 用户读权、owner、配置／额度／会话完整内容范围；不要求runtime、分支或Worker预留。策略不足按现行条件错误，未知503。 |
| 准备时读取源码／基线 | Contents read，绑定目标仓／commit | 原actor当前可读、当前委派／来源；首批管理阶段不真的准备。 |
| 创建／更新任务分支 | Contents write | 原actor须具该写动作资格，分支属于当前Attempt；禁默认／受保护分支、强推、任意删除和其他任务分支。 |
| 开draft PR | Pull requests write；关联分支读取所需Contents | 当前允许计划／Attempt／scope，固定base／head且draft=true；稳定外部操作身份与未知核查，不能盲重开PR。 |
| 读取PR结果 | Pull requests read | 仓库及内容读权；只采纳有归属的证据。 |
| 合并PR／仓库设置／成员管理／workflow修改 | 本地明确拒绝；不因已持Contents write放行 | 首批无对应受控动作，不请求Administration或Workflows写，不提供通用GitHub代理。 |

GitHub文档分别要求创建ref的Contents write与创建PR的Pull requests write；这些细粒度权限并不自动实现RepoMesh的分支／draft限制，故必须由本地动作入口约束。[Git refs](https://docs.github.com/en/rest/git/refs#create-a-reference)、[创建PR](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request)

未来给执行路径的installation token须限定登记仓库和必要权限，短期使用，App私钥及宽范围token不进Agent。GitHub自身是否允许受邀用户在某组织安装、SSO是否满足、分支保护是否允许，均按实际观察；安装申请／外部回跳不能直接写allowed。仓库历史失权后保留本地范围和业务历史，但不披露旧名称／内容。

## 6. S07—S08：出站与可用性检查

模型Base URL只允许HTTPS、无userinfo、query、fragment和非443端口；规范化主机／路径后必须精确命中部署approvedBaseUrls。禁止自由headers、代理地址、重定向、URL中嵌Key；测试路径只在已准入基础路径后追加/chat/completions。配置可保存格式合法但尚未在allowlist启用的连接，显示受限，禁止测试／新执行；不能通过“保存即探测”暗发请求。

外发前解析全部A／AAAA并拒绝loopback、私网、link-local、multicast、保留及IPv4-mapped等绕过地址。连接使用本次已验证IP且仍以原批准主机做TLS校验和SNI；不能校验后让默认dialer重新解析。每次新连接再次检查，禁跨主机跳转和环境代理。30秒请求超时、响应上限1MiB、无自动HTTP重试是首批候选；超时不证明外部停止。[OWASP SSRF防护依据](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

配置checks只表示当前可引用、启用、SecretVersion可用、参数和政策完整，不执行模型请求；已保存快照无测试不自动拒绝项目引用或模型应用。测试通过是特定快照的有限观察，不能豁免当前失权、secret停用、政策变化或预算核验。后续模型运行只在其完整适配／身份／受限执行验收后启用。

## 7. 交付验收与采用边界

本稿已提供来源责任、内部结构、导入过程、具体默认、额度预留和动作策略，供一次性评审。未运行以下验收：

1. 错根／错AAD／跨owner秘密引用均不能解密；数据库备份不含根，根轮换不改项目固定SecretVersion。
2. 相同导入键重放不重复；同id-version异内容及半套无效引用整体拒绝；默认变更不暗换项目。
3. 并发测试不透支，超时保留占用，午夜不清未知；未接处理器不显示调用中或运行就绪。
4. App有权限但actor／分支／draft约束不满足时拒绝；用户token发现不冒充完整账号覆盖。
5. 域名换成内网IP、跳转、代理或混合A／AAAA不能绕过，日志无Key和上游正文。
6. 缺execution／预算／密钥来源时项目可受限保存，Issue按必要条件阻止；实际建项保存全部持久责任。

已阅读现行项目／创建／持久化、模型设置、团队策略、ADR0013及架构受控操作边界。2026-09-11只核Go／GitHub／OWASP官方资料，没有生成真实密钥、导入清单、访问私仓或调用模型。正式采用需用户逐项确定S01—S08；实现仍另做。
