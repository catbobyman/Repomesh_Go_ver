# Manager 真实模型冒烟与实际通道偏差

2026-09-09，实例 a。**Manager 已通过修正后的中文指令冒烟：发送事件逐字读回一致，并收到精确唯一 marker。** 同时确认当前实际消息由 QwenPaw 内置 Matrix 通道处理，不能把本轮 READY 回包认定为 AgentTeams 自定义通道的无模型 readiness 分支。初次中文转义错误及原始事件仍保留，纠正实验使用新 marker，没有重复发送旧请求。

## 固定事实与执行路径

`agt get managers -o json` 读到 Manager `default`，runtime `qwenpaw`、model `deepseek-chat`、image `repomesh-validation/manager-qwenpaw:eeaab643`、phase Running；真实身份 `@manager:rv-a.matrix.invalid`，房间 `!cstiVyQcRNbIj1a5r3:rv-a.matrix.invalid`。

用实例 a 配置中的管理员测试身份 `@rv-a-admin:rv-a.matrix.invalid` 密码登录获得独立 token。凭据仅从 private 文件读取并通过 stdin 发往容器内 curl；不改 allowlist、模型配置或实例状态。发送前保存 sync cursor、唯一 tx_id；每种请求只提交一次，后续仅轮询 cursor，不因等待而重发。

脚本：[manager-model-live.py](../scripts/manager-model-live.py)。[全部脱敏事件与结果](../evidence/manager-model-live-results.json)、[发送事件实际读回](../evidence/manager-model-live-sent-readback.json)、[实际 runtime 日志摘录](../evidence/manager-model-live-runtime-excerpts.json)。

## 消息与响应

| 项目 | 请求 | 真实 Manager 回应 |
| --- | --- | --- |
| 定向 READY probe | `2026-09-09T16:41:11.778316Z`；event `$Rr0jHqpEmWm_TnfdltuE4rakmGu_C0qbEuKzUnK3b-g` | 4.703 秒后收到 `READY`；event `$4CCIg-aUg77JKjvLzHeMT9H2RfEnWRVUmP06Md-HBtg` |
| 唯一 marker 模型冒烟 | `2026-09-09T16:41:17.000692Z`；event `$cwiLJPMu4j-ht7B1SUbnBRoe19I80rSk_8SqGsJ0lSI` | 3.531 秒后收到精确文本 `RV_MODEL_A_20260909_becbad5b`；event `$6t9jx_biH7eEBHWjCgjHZyHDgWtEJa_ZnHZcPb-3LO8` |

两条回应的 sender 均为目标 Manager，room 与目标房间一致。时长为轮询观察延迟，不是精确模型首 token 延迟。实际模型调用的费用、token 数和工具调用数不由 Matrix 消息证明。

## 发现 1：实际 handler 来自内置通道

请求发生时日志明确显示：

```text
/opt/venv/qwenpaw/lib/python3.11/site-packages/qwenpaw/app/channels/matrix/channel.py:2460
_on_room_event ... is_dm=True
```

READY 请求后还出现 ResourceGovernor 与 context history 初始化日志；回应包含 `formatted_body`。这与此前组件测试的 AgentTeams 自定义通道 `_send_plain_text` 直接回包形态不同。因此本报告只记录“READY 可见”，**不声称 READY 已绕过模型**。镜像里存在／加载插件不等同该插件被选为当前消息 handler，实际生效配置需要继续核查。

日志还提示 sandbox 不可用（无法读取 `/sys/kernel/security/lsm`），fallback 将升级为 ASK。本轮 marker 请求不要求工具，不能证明真实工具执行可无交互完成，也不能据此宣称沙箱有效。

### 实际配置和上游原因已完成只读核查

[完整只读证据](../evidence/manager-model-live-channel-selection.json)由 [manager-channel-readonly.py](../scripts/manager-channel-readonly.py)采集，未修改配置、激活插件或重启服务。

1. 容器安装的 QwenPaw 版本是 **2.0.1**。`config.json` 和 `workspaces/default/agent.json` 均为 `channels.matrix.enabled=true`，**没有 `channels.agentteams_matrix` 配置**。
2. 插件实际存在且注册成功：16:39:51 安装 `agentteams-matrix-channel`；16:40:04 日志明确 `registered channel 'agentteams_matrix'`。因此不是插件文件没复制或导入失败。
3. QwenPaw registry 的内置键 `matrix` 映射 `.matrix.MatrixChannel`；自定义插件注册键为 `agentteams_matrix`。两个键不同，**当前不存在同键覆盖冲突**。registry 对同键插件会跳过，但本实例不符合该条件。
4. ChannelManager 依次检查通道是否 available、有对应配置且 `enabled`。当前只有 builtin 的 `matrix` 满足已配置启用条件；“插件已注册”不会自动把 `channels.matrix` 改名或启用另一 key。
5. Manager 上游启动脚本先运行 `python -m copaw_worker.bridge --profile manager`；bridge 的配置投影明确写入 `channels.matrix`，随后启动脚本的 DM auto-reply 补丁仍写 `.channels.matrix.groups`。插件复制／注册发生在后续步骤，但没有将 Manager 配置迁移至 `agentteams_matrix`。容器内实际 `bridge.py` 与 `start-qwenpaw-manager.sh` SHA-256 均与锁定上游源码一致。

所以本轮从官方锁定源码配方构建的 Manager 走 builtin，是**桥接配置选择了 builtin key，而独立插件只有注册没有启用配置**；不能将它描述为“插件覆盖失败”。这是本轮实际镜像和固定提交的结论，没有读取或断言其他远端发布标签的镜像行为。Worker 的 `qwenpaw_worker/update.py` 则明确同步 `agentteams_matrix`，Manager 与 Worker 不能仅因使用同一 QwenPaw 版本就假定采用同一 Matrix 实现。

## 发现 2：夹具 UTF-8 传输修正

初版通用 Matrix curl 配置构造使用外层 `json.dumps` 默认 ASCII 转义。curl config 不理解 JSON `\uXXXX`，导致中文被传成 `u8fd9u662f...`；ASCII marker 保留，Manager 最终确实返回 marker。

按 event ID 读回原始请求确认：probe 输入与预期一致；模型输入与预期中文不一致。不能将初次试验描述成“正确中文无工具指令完整通过”。已把外层序列化改为 `ensure_ascii=False`，没有修改上游或重新发送旧事件。未来纠正实验应使用新的独立 marker，并先读回请求文本核对传输。

### 纠正实验已执行

使用新 marker `RV_MODEL_UTF8_20260909_2e0601f5`，通过 [manager-model-live-corrected.py](../scripts/manager-model-live-corrected.py)只发送一次。发送前确认待发送字符串包含原中文，发送后按 event ID 从真实 Matrix 读回并逐字比较，**完全一致**：

```text
这是隔离验证，只回复 RV_MODEL_UTF8_20260909_2e0601f5，不调用工具或创建资源。
```

- 请求时间：`2026-09-09T16:43:37.642117Z`。
- 请求 event：`$nV1IJJBwravosFC4yK1y5hFSiB1tPO3rAIY4g1zgzHs`。
- 3.797 秒后收到目标 Manager 精确回复 `RV_MODEL_UTF8_20260909_2e0601f5`。
- 回复 event：`$epO8xXljo_Si422twVhtphcBijzfyo0CCAFXGGSZRTo`；sender `@manager:rv-a.matrix.invalid`；room 与目标一致。
- 命令退出码 0；[独立纠正证据](../evidence/manager-model-live-corrected.json)保留请求、实际读回、回包与唯一 tx_id。

这次证明正确中文输入到实际 Manager 响应的冒烟闭环。响应符合不调用工具的简短指令，但本实验没有独立审计全部后台工具事件，因此不以“只看到短回包”证明后台工具调用数绝对为零。

## 当前证据能证明什么

- 实际 Manager 收到测试房间消息并返回唯一、非 READY 的 marker，较资源存在、Running 或探针回包提供了更强的真实响应证据。
- 默认部署所选 Matrix handler 与先前验证的自定义通道不一致，应纳入 AT-01“配置实际加载”验收，不能将组件结论直接套到本次运行。
- 正确中文指令冒烟现已通过；插件若将来切换后的 readiness 路径、真实工具／Worker 执行、RepoMesh 业务权限和重启恢复仍需各自证据。本报告不将它们合并宣称通过。
