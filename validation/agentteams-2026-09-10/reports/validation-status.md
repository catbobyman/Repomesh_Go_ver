# 新版验证状态与接手

日期：2026-09-10。固定上游 `517caff9280242a00a4d4c06365352b9e41659c6`。本轮继续用户原验收清单，因官方 main 已推进而新建独立验证目录，重测受影响路径。**当前原生增量已有实际运行证据与失败反例，RepoMesh 业务层验收仍未完成。**

**当前目标状态：受阻，未完成。** 新版独立原生补测已结束；恢复后的连续三回合中，业务实现缺失及旧卷跨项目占用仍未解除，04:01:50 UTC再次核实后已停止自动重复，见[受阻审计与恢复前提](resumed-blocked-audit.md)。

## 本轮实际结果

| 层次 | 结果与限定范围 | 证据 |
|---|---|---|
| 构建／部署 | 三个新版镜像构建成功；Worker构建输入未变，复用固定旧镜像并核对ID。新 c 基础服务、认证API可用 | [构建](image-build.md)、[部署](deployment-and-offline-smoke.md) |
| 官方包测试 | 3包退出0，252顶层＋59子测试通过事件，0失败／跳过；组件用例不替代真实服务 | [结果](../evidence/controller-official-tests-summary.json)、[源码与测试边界](controller-delta.md) |
| HTTP | 51观察成立，含状态回退、history过滤、错误format、Team歧义、只读字节保持和已知缺陷观察 | [接口实测](controller-api-live.md) |
| 实际身份 | 两个真实Worker SA通过真实Team membership成为Team Leader；31检查成立，本Team200、跨Team404；未声称普通Worker或人类业务权限通过 | [scoped实测](controller-api-live.md) |
| 新版双在线读取矩阵 | 新d独立部署；c/d各两同名Team/Project/Task，Admin与两真实SA TeamLeader覆盖五种读取组合及负向，共313断言成立。30次双向错实例重放401，每次来源前后200；24个对象哈希不变 | [矩阵](controller-twin-read-live.md)、[d部署](deployment-d-readiness.md) |
| Mermaid | 18例14成功4失败；有效字符ID `end/subgraph/classDef/graph`是Mermaid关键字；真实API `end` 正文再现解析失败 | [浏览器报告](mermaid-browser-live.md) |
| includeTasks内部读取 | 真实MinIO trace的20检查成立；JSON前后正对照各TaskMeta HEAD/GET一次，Mermaid true/false各窗口为0，Project读取及监听probe均出现。仅限该夹具和有限窗口 | [S3读取实测](mermaid-storage-read-live.md) |
| CLI | 唯一Project Mermaid与API正文仅末尾换行差异；同名Project即使传`--team`仍409 | [CLI证据](controller-api-live.md) |
| 最小升级冒烟 | pause/resume/replan/cancel与单段当前ETag成功／旧ETag412共17观察成立；末尾旧a已停止导致凭据读取失败，脚本整体exit1保留。后补跨实例认证受时钟异常影响，不计干净通过 | [独立报告](controller-upgrade-smoke.md) |
| Manager CFG-01—05 | REST／CLI／CR矩阵完成；实际有效绑定→失效绑定阻断→清空恢复，最终CR、MinIO、桥接与QwenPaw进程内存模型均chat。恢复阶段由REST先清空，正确CLI是重复清空；未另验推理调用 | [完整配置实测](manager-config-live.md) |
| Manager依赖 | QwenPaw2.0.1及新版内置agt可启动help；pip check退出1，缺copaw。未改官方依赖来制造通过 | [离线检查](deployment-and-offline-smoke.md) |
| 新版Manager实际模型 | 原配置Matrix一次消息→4.141秒精确标记，专属原生会话与1次调用的计量一致，17,666输入／57输出token，历史及coordinator均未见工具调用；保持chat。Console503发生任务创建前，后置历史过滤错误通过只读更正 | [基本推理实测](manager-model-smoke-new.md) |

## 对页面、接口和后端接手的影响

1. 浏览器图展示必须处理Mermaid解析失败；HTTP200只表示返回图文本。接入前宜为节点分配独立、安全的展示ID并保持边映射，或处理保留词；本轮没有修改上游实现。
2. 工作流JSON请求省略`format`；显式`format=json`在此版本400，不能把旧版忽略参数的行为当作稳定契约。
3. 后端适配持久绑定`instance/team/project_id`，同名Project通过真实HTTP显式传Team；不要假定当前CLI的`--team`已生效。
4. Task inspection只读已有图和TaskMeta。有效TaskMeta的原始状态、图规范化状态、RepoMesh业务状态是不同来源；history过滤不是可靠业务审计，trace hint不是实际span存在证明。
5. Manager更新需保留“省略／null／空串”区别；显式空串是清空绑定。Manager GET不含该字段，不能凭字段缺失证明清空，也不能凭PUT成功证明进程采用默认Gateway。

非空Provider绑定还观察到`/v1/v1`与空绑定`/v1`的URL差异。[独立路由分析](provider-url-analysis.md)确认前者仍匹配`/v1/`路由，AI proxy还可能内部转换，因此只列兼容性风险，未证明实际推理失败，亦未声称清空修复了模型连通。

## 旧证据如何继续使用

[逐函数差异](controller-delta.md)确认Project解析／Team scope、建图、TaskMeta key、CAS及pause/resume/replan/cancel相关实现未改；TeamHarness server、authenticator、lifecycle handler也未改。09-09的陈旧上传覆盖、取消后副作用、角色入口差异、资源限额、消息恢复和会话关系等反例没有被此次读接口及配置更新修复。

这是源码差异与历史实测的对应关系，**不是在517caff9重新运行这些模型及故障实验**。重新构建Manager还会解析未锁定依赖，版本清单应以本轮实测为准；不能把源文件未变等同于完整运行环境相同。详细旧范围仍见[原清单审计](../../agentteams-2026-09-09/reports/completion-audit.md)。

## 环境与剩余边界

Docker旧socket故障在09-10复发；封存本用户Docker运行目录后恢复Engine28.0.4。没有删除数据盘或恢复出厂，复发根因尚未定位，见[环境恢复](environment-recovery.md)。旧 a/b 的11个已记录验证容器逐个核对ID后停止；保留证据和卷，使用全新c进行本轮实验。

09-10 10:34:55 UTC的[前提复核](remaining-preconditions.md)确认：排除validation和.git、包含通常被ignore的文件后，工作树仍无`.go`／`go.mod`；精确卷匹配确认`agentteams-data`仍由运行中的`goai-infra-repomesh-api-1`挂载。原跨项目清理授权问题没有被“继续验证”自动回答。

业务许可、Plan Version、原子资源预留、可信身份映射、创建事务、REST／SSE持久恢复、动态读权和GitHub交付等，仍需真实RepoMesh实现才能验收。本轮原生夹具不代替这些业务组件；总目标不得因报告完成而标记全通过。审计未识别出上述新版增量以外、能在当前条件补足这些缺口的非重复原生必测项；这不意味着所有可能实验均已穷尽。

本地Mermaid隔离浏览器已关闭，两个临时HTTP监听器已结束；原始浏览器日志和截图保存于本轮output。CFG-05第三轮出现墙钟回退约7小时、Kubernetes证书尚未生效并阻断恢复，见[时钟记录](clock-discontinuity.md)。随后仅续签c的两张证书并重载Controller进程，保留密钥、卷和数据库；03:44:57最终CR generation与observedGeneration均10，各配置层恢复chat。03:45:23开启TLS校验的Kubernetes实际200，c Controller与Manager均Running，临时续签程序已移除，见[最终状态](../evidence/control-manager-final-state.json)。跨此事件不以墙钟差计算耗时，不把证书失败判作Provider清空回归。

后续自动继续原目标时，新建d并完成新版“两个在线实例×两个Team×同名Project/Task”的上述完整新增读取矩阵。其实际双向重放和来源自证不受旧时钟／证书故障污染；上一轮异常条件下的401/200原记录保留，不倒填成通过。Mermaid的includeTasks内部读取已有真实S3 trace，新Manager基本推理也有专属Matrix事件、原生会话及用量三者对应的证据。Console入口默认未配置而503，不代表已配置Matrix不可推理；成功的无工具回合也不能证明所有插件、工具、模型或并发任务兼容。

这些原生补测已完成；此前“新版双在线矩阵未重跑”“includeTasks未做内部观测”“新Manager仅有配置读回”的缺口不再保留为当前未执行项。原业务清单仍缺真实RepoMesh实现，旧共享卷仍有跨项目消费者，总目标尚未全部通过。

最新[收尾检查](../evidence/final-review-continuation.json)于04:00:23 UTC确认：五份接手文档157个本地链接有效，26个Python脚本语法可解析，固定upstream仍干净，c/d及c Manager均运行且RestartCount=0。非validation工作树仍无`.go`／`go.mod`，旧卷的运行消费者仍是GOAI API，没有将前提缺失改写成通过。[报告／证据检查](../evidence/artifact-check.json)另覆盖JSON／JSONL语法、链接及已知凭据误落，实际计数和检查范围以JSON为准；[上次自检](../evidence/final-review.json)保留为历史记录。
