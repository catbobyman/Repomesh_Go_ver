# 新版 Manager 配置矩阵：真实 REST、CLI 与 CR

本轮 CFG-01—04 与 CFG-05 **配置保存、投影及运行进程内存配置**验证已完成。CFG-05 经过真实环境时钟中断后的受控恢复；未以配置读取声称模型推理已成功。验证目录名称按原计划保留，原始记录中的 `10:xx UTC` 存在主机时钟偏移，校正后的完成时间为 `2026-09-10 03:44:57 UTC`；时间边界见[时钟中断与恢复](clock-discontinuity.md)。

## CFG-01—04 结果

实际执行时间 `10:27:15—10:27:28 UTC`，exec session `3476` 最终 exit 0。Controller 为 `rv-c-controller`，镜像 `repomesh-validation/embedded:517caff9`，实际 image ID `sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f`。容器内实际 `/usr/local/bin/agt` 的 SHA-256 为 `61caf405a7ff309b872eeff200ee78aae9c9eb0526f051cbc97c0a5592e151e7`。

只创建和修改专属 Manager `cfg-clear-2b043b42f8`，UID `170c88f2-8028-427c-acda-b191a573e181`，全过程 CR 为 `Stopped`、runtime 为 `qwenpaw`。没有启动这个 Manager 的容器、调用模型或触碰旧 a/b 实例。每次状态断言均通过 c 容器内真实嵌入式 Kubernetes TLS API 读取 CR；没有用 ManagerResponse 中缺失的 modelProvider 字段代替读回。

| 用例 | 真实结果 |
|---|---|
| 创建非空 Provider | POST 201，CR 持久化 fixture provider-a |
| 省略 Provider，仅更新 model | model 更新，原 Provider 保留 |
| 显式 `modelProvider:null` | 原 Provider 保留 |
| 数字、布尔、对象、数组 | 四种真实 PUT 均 HTTP 400；每次独立 CR 保持原 model／Provider |
| 非空 Provider 更新 | CR 从 provider-a 变为 provider-b |
| 仅 `modelProvider:""` | HTTP 200，CR 中字段被 omitempty 省略，独立解读为空；model 保持 |
| 重复空串 | 再次正常返回，仍为空且 model 保持 |
| model 与空 Provider 同时更新 | 两字段均按请求持久化 |
| CLI 单独 `--model-provider=` | 真正发出 `{"modelProvider":""}`，真实 Controller 200，CR 清空 |
| CLI 省略该选项 | 真正只发送 model，CR 保留原 Provider |
| CLI 非空选项 | 真正发送指定 Provider，CR 更新 |
| CLI 缺 name／无更新字段 | 均 exit 1，临时 observer 收到 0 次请求，CR 未变 |

CLI 的观察器是 c 容器内临时 localhost 转发器：收到安全 JSON 后立即转发到真实 Controller，使用真实 HTTP 响应，不产生假成功。三个正向命令各转发一次 PUT，两个负向没有 PUT。观察器在命令子进程 finally 中关闭；独立 CR 读回走 Kubernetes API，不走该观察器。

CFG-01—04 结束时将该夹具恢复到初始 model、空 Provider、Stopped，保留 60 条结构化记录。随后进入已授权的 CFG-05 前，按精确 UID 封存并删除这条从未运行的专属 CR，避免与默认 Manager 共同写共享配置；DELETE 200、GET 404，见[安全删除证据](../evidence/control-manager-probe-delete.json)。原始完整 CR 与删除响应保存在本轮受限 private 目录。

- [完整真实矩阵证据](../evidence/control-manager-config-2b043b42f8.json)
- [执行脚本](../scripts/control-manager-config-live.py)
- [首轮预检失败](../evidence/control-manager-config-preflight-attempt-01.json)：新部署使用 `repomesh.validation.run` 与 `.instance`，首版探针误查旧标签键，在任何 Manager 请求前退出。修正为真实 run 标签并额外要求 instance=c 后再执行；未放松镜像／名称／端口限制。

## CFG-05：真实配置生效与恢复结果

只操作新 c 的 `default` Manager，UID `b8aaa1f5-b2c6-45be-b50c-dcc643704acf`；旧 a/b 不变。先核查 private ACL 仅当前用户、SYSTEM 和 Administrators 可访问，再复制此前授权的四字段 Provider 配置。启用脚本核对原 c 镜像、标签、空 Manager 列表、五处挂载、网络和 localhost 端口后，只改必要 Provider、ManagerEnabled、model 和真实 daemon workspace／host-share 字段。原 c 卷、密钥及端口保持原值。启用 session `5195` exit 0。

- [ACL 核查](../evidence/control-manager-private-acl.json)、[Provider 复制指纹](../evidence/control-manager-provider-copy.json)
- [审查计划与精确变更字段](../evidence/manager-enable-plan-c.json)、[执行后证据](../evidence/rv-c-enable-c9bc3fc4db2d.json)、[c 专用启用脚本](../scripts/control-enable-manager-c.py)
- [首次真实投影快照](../evidence/control-manager-projection-state-20260910T103444Z.json)

官方自动创建 `default`，运行容器为 `rv-c-manager`，镜像 `repomesh-validation/manager-qwenpaw:517caff9`，image ID `sha256:8cf1059295e6c172ba30d7e732cc382169678fcb44b2e7f56c159203b0c20b6a`。其实际 bind Source 对应本轮 `runtime/instance-c/workspace` 与 `host-share`，没有回退到 HOME 或旧实例目录。QwenPaw console 仅映射 `127.0.0.1:48099`。

| 步骤 | 独立 CR | 原生配置和运行进程结果 |
|---|---|---|
| 空绑定基线 | model=`deepseek-chat`、Provider 空 | MinIO、bridge、QwenPaw global／effective 均为 chat；base URL 为 `http://rv-c-controller:8080/v1` |
| 绑定已存在的 `openai-compat` 并设 reasoner | PUT 200，Provider 非空，observedGeneration 追上 generation | 官方协调器重建 Manager；MinIO、bridge、QwenPaw 内存均切到 `deepseek-reasoner`。这是配置加载通过，不代表该路径推理通过 |
| 设置不存在的专属 Provider，desired model 改 chat | PUT 200，CR 保存新值；status.message 含该 Provider 解析错误，observedGeneration 落后 | 三次负向样本中共享配置、bridge、运行进程仍保持先前 reasoner；没有把 REST 200 当作实际应用成功 |
| 清空失效绑定 | 时钟恢复后 `03:44:20`，恢复脚本 finally 通过真实 REST PUT 200 写空 Provider 与 chat | 新 Manager 进程加载默认配置；最终 CR generation=observedGeneration=10，错误标志消失 |
| 正确 CLI 重复清空 | `03:44:56`，`agt update manager --name default --model-provider=` exit 0 | 转发观察器记录一次真实 `{"modelProvider":""}`，Controller 200；这是 **REST 已清空之后的重复清空** |
| 最终收敛 | `03:44:57` CR 仍空 Provider／chat | MinIO、bridge、QwenPaw 内存 global 与 effective 均 chat；最终 `/v1` 配置恢复 |

有效绑定与不存在绑定的前段证据见[完整负向样本](../evidence/control-manager-projection-live-a9cb0145a8.json)及[时钟中断前后原始记录](../evidence/control-manager-projection-live-1c70a44f37.json)。REST 首次恢复事实见[恢复尝试 5851098e25](../evidence/control-manager-projection-live-5851098e25.json)，成功的正确 CLI 重复清空与最终四层读回见[最终收敛证据](../evidence/control-manager-projection-live-465dffc7f4.json)。这些连续证据共同构成恢复闭环；未为文案再次制造失效绑定。脚本为 [control-manager-projection-live.py](../scripts/control-manager-projection-live.py)。

### 每层通过到底证明什么

1. **保存**：真正的 Controller REST／agt，配合嵌入式 Kubernetes 独立 TLS CR 读取。ManagerResponse 不含 modelProvider，不能用于代替该层证据。
2. **投影**：MinIO 的 `agents/manager/openclaw.json`，以及 Manager 本地 bridge 生成的 `.qwenpaw/providers.json`。Manager 实际使用这个共享对象，不能套 Worker 的 runtime.yaml 探针。
3. **运行进程内存配置**：QwenPaw 2.0.1 `GET /api/models/active?scope=global` 读取 `request.app.state.provider_manager`；`ProviderManager.get_active_model()` 直接返回内存 `self.active_model`。effective 查询可先读取 agent 配置后回退 global，本例两者相同。实际镜像源码路径、版本、SHA-256 与行号保留在[运行时源码证据](../evidence/control-manager-runtime-source.json)。结合真实新容器身份与 API 读回，可确认新进程已加载选定模型配置。
4. **模型推理**：CFG-05 配置阶段未主动提交额外模型任务或业务工具调用。原生 `welcomeSent=true` 已观察到，启动欢迎流程可能调用 Provider，因此不宣称完全没有模型请求。上述管理 API 不证明一次推理实际采用或成功调用了该 Provider。

非空绑定时观察到 `baseUrl=/v1/v1`，空绑定为 `/v1`。Higress ResolveModelProvider 返回 DataPlaneURL 加 route 前缀，generator 再拼接 `/v1`；这个配置差异成立，但现有 `/v1/` route 仍可匹配，AI proxy 内部可能转换上游路径。**实际推理影响未验证**，不得仅凭重复字符串认定调用失败；详见[Provider URL 独立只读分析](provider-url-analysis.md)。

### 时间中断与最小恢复

第三轮在原始钟面 `10:39:00` 写入不存在 Provider 后，主机与容器 UTC 同时校正到约 `03:39`，已有 c 证书 `NotBefore=10:25:45` 因而尚未生效。真实 TLS 返回 `SSLCertVerificationError` code 9。主任务通过外部 HTTP Date 核对当前时间，不回拨系统时钟，也没有关闭 TLS 验证。[原始中断证据](../evidence/control-manager-clock-interruption.json)

经授权只在 c 内重签现有 `ca.crt` 和 `apiserver.crt`，原证书备份到 c 自有 0700 目录；沿用原私钥，将 NotBefore 调整为当时已核时间减一分钟，subject、issuer、SPKI、SAN／全部 extensions、serial 和 NotAfter 保持相同。其他五个 PKI 文件哈希未变，私钥未导出。随后只向确认由 PID 1 supervisord 托管的 Controller PID 50 发送 SIGTERM；Supervisor 拉起新 PID 7667，旧 Kube 子进程 418 自然退出，新 Kube PID 7682。容器 ID、Supervisor、数据卷和其他服务未重启。

- [续签计划](../evidence/control-pki-reissue-plan.json)、[实际续签与相同公钥指纹](../evidence/control-pki-reissue-applied.json)、[精确进程重载](../evidence/control-pki-process-reload.json)
- [Go 标准库辅助程序](../scripts/control-pki-reissue.go)、[c 专属恢复脚本](../scripts/control-pki-recover.py)
- [最终状态](../evidence/control-manager-final-state.json)：`03:45:23`，TLS 验证开启的 Kube GET 200，CR Running 且 generation=observedGeneration=10，c 两个容器运行；容器内临时 `/tmp/control-pki-reissue` 已移除。证书原件备份和本地源码／构建产物保留。

时间修复只是自有验证环境恢复，不修改上游产品实现。所有原始失败记录保留，时间前后不可直接相减解释业务延迟；统一背景见[时钟中断报告](clock-discontinuity.md)。

### 探针自身的失败与修正

| 原始尝试 | 实际原因与处理 |
|---|---|
| [f2694093c4](../evidence/control-manager-projection-live-f2694093c4.json) | model 变化触发官方 Manager 重建，立即 docker exec 遇到短暂不可用。后来采用有界等待并记录容器 ID；未改运行时文件或产品实现 |
| [a9cb0145a8](../evidence/control-manager-projection-live-a9cb0145a8.json) | 已取得有效绑定和三次真实错误 CR／旧配置保留，但误要求 Docker stdout 包含 embedded 日志。之后改用真实 CR status 的精确 Provider 错误作为依据 |
| [1c70a44f37](../evidence/control-manager-projection-live-1c70a44f37.json) | 外部时钟校正导致 TLS 尚未生效，退出且当时无法恢复；后续仅修复 c 自有证书继续 |
| [clock-restore-cli](../evidence/control-manager-clock-restore-cli.json)、[5851098e25](../evidence/control-manager-projection-live-5851098e25.json) | 恢复探针错误地将 Manager name 当作位置参数；agt 实际要求 `--name`，故未发送 CLI PUT。第二份证据的 finally **REST** 成功清空；之后修正 CLI 并只做重复清空 |
| [465dffc7f4](../evidence/control-manager-projection-live-465dffc7f4.json) | 正确 CLI 与最终配置收敛，exit 0；没有重复前段故障用例 |

CFG-05 原生配置恢复层已完成。RepoMesh 的业务验收仍须其实现完成后单独联调；本报告不将原生能力验证扩展为产品验收或模型推理验收。

## 后续独立推理证据

配置闭环完成后，另按授权在 c/default 原生 Matrix 通道完成一次唯一 nonce 推理，精确模型回复与会话逐轮 token 用量对应，未观察到工具调用。详见[新版 Manager 真实模型 smoke](manager-model-smoke-new.md)。这份独立证据补足默认 chat 推理路径，不改变上述 CFG-05 管理 API 本身只能证明内存配置的边界。
