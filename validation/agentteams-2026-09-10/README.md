# AgentTeams 2026-09-10 新版验证

**新版 Controller、CLI、浏览器与 Manager 配置增量验证已执行并记录结果。Manager清空已验证到运行进程内存配置；Mermaid和CLI存在明确失败反例。原业务清单尚未全部完成。**

当前目标已标记为**受阻**：缺少RepoMesh业务实现，且旧共享卷仍被另一项目使用。新版双在线读取、S3内部读取和一次真实推理已补完；恢复条件见[受阻审计](reports/resumed-blocked-audit.md)。

GitHub `agentscope-ai/AgentTeams` main 在本次查询为 `517caff9280242a00a4d4c06365352b9e41659c6`，提交时间 `2026-09-10T02:41:08Z`。新克隆HEAD已独立确认；旧基线 `eeaab64391ccaec9118e84977f538aefd40720d6` 已fetch用于差异比较，没有改变[09-09验证](../agentteams-2026-09-09/README.md)的源码、镜像和原始结果。

目录日期按UTC批次保留。运行中墙钟曾回退约7小时，当前LA本地日期可能为09-09；各证据保留采样原值，跳变前后不能直接用墙钟差推算耗时，详见时钟记录。

与旧基线相比有14个文件变化，涉及Controller Project workflow接口、Mermaid解析、CLI读写及Manager模型提供商清空处理。受影响契约在全新c实例重测；未变化部分保留旧版证据和适用范围，不改写成新版通过。

Docker的旧socket故障在09-10复发；封存运行目录后已恢复Engine。旧a/b验证容器核对ID后停止，本轮使用独立c实例的卷、网络、密钥和工作目录。复发根因未定位，不宣称永久修复。

原业务验收范围以[接入清单](../../docs/current/agentteams-validation-plan.md)与[完成度审计](../agentteams-2026-09-09/reports/completion-audit.md)为准。当前工作树仍无RepoMesh Go业务实现，因此许可、事务、资源预留和业务身份等未验收项继续保留。

## 阅读顺序

| 内容 | 入口 |
|---|---|
| 本轮结果、接入影响和未完成边界 | [验证状态与接手](reports/validation-status.md) |
| 源码差异和官方测试 | [Controller](reports/controller-delta.md)、[Manager／CLI](reports/config-cli-delta.md)、[来源指纹](evidence/source-baseline.json) |
| 新版真实 HTTP、身份和 CLI | [接口实测](reports/controller-api-live.md) |
| 新版两个在线实例的同名范围与凭据重放 | [c/d完整读取矩阵](reports/controller-twin-read-live.md)、[d部署与就绪](reports/deployment-d-readiness.md) |
| Manager CFG-01—05与恢复终态 | [实际配置矩阵](reports/manager-config-live.md) |
| 新版Manager基本模型调用 | [Matrix实际推理](reports/manager-model-smoke-new.md) |
| 旧写路径的有界新版回归 | [生命周期与CAS](reports/controller-upgrade-smoke.md) |
| 真实 API 文本到浏览器解析 | [Mermaid 实测与截图](reports/mermaid-browser-live.md) |
| includeTasks实际S3读取 | [MinIO trace正负对照](reports/mermaid-storage-read-live.md) |
| Docker 故障复发、恢复和旧验证停用 | [环境记录](reports/environment-recovery.md) |
| 验证中途的时钟异常与证书恢复 | [时钟回退](reports/clock-discontinuity.md) |
| 镜像构建和实例启动 | [构建](reports/image-build.md)、[部署与离线检查](reports/deployment-and-offline-smoke.md) |
| 业务实现与旧共享卷的最新前提 | [只读收尾审计](reports/remaining-preconditions.md) |

## 结果快照

- 官方三个 Go 包测试退出0：252个顶层测试、59个子测试通过事件，合计311；不是311项端到端验收。
- 真实 HTTP 51项观察断言成立、真实 SA 经 Team membership 解析为 Team Leader 的31项范围检查成立。观察数包含缺陷确认，不代表产品全绿。
- 后续c/d同时在线矩阵另有313断言成立、260次HTTP；30次双向错实例凭据重放均401，每次来源前后均200，24个对象原始哈希不变。不与旧计数相加成业务验收数。
- Mermaid 11.17.2 浏览器：18例中14例成功、4个保留词 ID 失败；另外将真实 HTTP 的 `end` 正文送入浏览器，1例失败。
- 实际MinIO trace的20检查成立：JSON includeTasks前后均读取TaskMeta，Mermaid true/false有限窗口内TaskMeta HEAD/GET均0；前后probe与正对照确认监听有效。
- `agt get projects ID --team TEAM` 在同名 Project 场景仍返回409；显式 `?team=` 的真实 HTTP 正常。
- `format=json` 返回400；缺省／空 format 返回JSON。Task inspection可能返回原始 TaskMeta 状态，不能与workflow规范化状态混用。
- Manager 显式 `modelProvider:""` 已真实持久为空；省略／null保留。CFG-05恢复后CR、MinIO、桥接配置与QwenPaw进程内存模型均为chat；CFG阶段不以配置读取代替推理，后续基本推理另有专项证据。失效绑定由REST先清空，后续正确CLI为重复清空；独立矩阵已证明CLI非空→空。
- Manager 镜像的 `qwenpaw/agt --help` 成功；`pip check` 因官方 `copaw-worker` 缺 `copaw` 退出1，按原样记录。
- 后续新版Manager已完成一次真实Matrix模型请求，4.141秒返回精确标记；专属会话与用量一致，1次调用、17,666输入／57输出token，未观察到工具调用。先前Console入口503与后置历史关联错误均保留；未重复推理。

`upstream/`、`runtime/`、`private/`排除提交；`scripts/`保存方法，`evidence/`保存命令、输入与输出，`reports/`保存解释，`output/playwright/`保存浏览器截图和日志。公开证据检查覆盖链接、JSON／JSONL语法及本轮和旧轮已知凭据字符串，不等同于未知秘密的穷尽审计。
