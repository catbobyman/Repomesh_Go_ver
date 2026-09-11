# AT-10 普通 reply／thread 的实际部署链路补测

执行窗口 `2026-09-09T17:21:31Z`—`17:21:52Z`，exec session `94191`，退出 0。对已有 a twin Worker **仅发送两条低负载、唯一标记的真实模型请求**，分别携带普通 `m.in_reply_to` 和 `m.thread` 关系；两条均精确读回原始 content，实际 custom handler 日志、QwenPaw session 日志、模型历史及 Matrix 回复互相对应。没有重启、第三类请求、工具任务或业务状态修改。

**两种入站格式均可获得目标模型回复；本轮出站没有沿用原父事件／thread root，而是新建主时间线占位消息，再以 `m.replace` 更新。两者实际共享 room session，不能当作 thread／Issue 会话隔离已实现。**

## 环境、发送策略与来源

- 运行容器：`rv-a-worker-live-twin-worker`。
- 实际 sender：`@live-twin-human:rv-a.matrix.invalid`；目标：`@live-twin-worker:rv-a.matrix.invalid`。
- 使用已存在的测试 Team room：`!Ff6iZ4IGTwHpkhX922:rv-a.matrix.invalid`，不进入其他项目房间。
- readonly agent 配置确认 `agentteams_matrix.enabled=true`、`matrix.enabled=false`，不是 Manager builtin channel 路径。
- 部署 channel 源码 SHA-256 为 `a9a67fed5032e3fcbc0f149f075774fd251dac34c5c3b5bb0155931d32b96197`，与本轮锁定上游 `plugins/agentteams-matrix-channel/agentteams_matrix/channel.py` 一致。

[执行脚本](../scripts/runtime-reply-thread-live.py)复用 private 中已有的测试 Human token，每条消息发送前持久保存唯一 transaction ID、完整 intended content 和 attempted 标记；未知发送不会重发。标准 Matrix HTTP 实际发送，未用 fake transport。两个请求顺序执行，每个最长观察 180 秒；实际首个 marker 回复约 3.7 秒，随后额外观察至少 4 秒以收集编辑后的内容。没有重新请求模型。

普通 reply 使用 `m.relates_to.m.in_reply_to.event_id`；thread 在此基础上增加 `rel_type=m.thread`、`event_id=<原根事件>`、`is_falling_back=true`。两者都显式包含 `m.mentions.user_ids=[目标 Worker]`，避免无提及被原生群聊门禁忽略。body 使用新的短标记并要求仅回复该标记、不调用工具／创建资源／委派或联系成员。测试是直接 Matrix JSON 关系，不包含某个客户端额外生成的富文本引用 fallback UI。

两类均引用此前 a Worker 冒烟中的已有 Human 事件：

```text
$2WvYBuOQBOPoTAea7PFYlQWNHyTLGh_r4DrYZ5QGemw
```

没有为本次创建额外模型根消息。原父事件完整内容及每次关系均保存在[原始证据](../evidence/runtime-reply-thread-live.json)。

## 两条实际模型链路

| 检查 | 普通 reply | thread |
| --- | --- | --- |
| 新 marker | `RV_RT_REPLY_890eb5443b` | `RV_RT_THREAD_cb88e4c2a9` |
| 入站 event ID | `$NqrHyg2tw4RZ07yA2wmzZZPuqeTA3A6lQ8qsFIlBiaQ` | `$k2-7G-hi4qdl-BCb3K5cyR8c8vC1EaH4FOTpYZa6Gi4` |
| body／mention／relation 精确读回 | 全 content 一致 | 全 content 一致 |
| custom `_on_room_event` 实际日志 | 17:21:31，匹配 sender、room、marker，`is_dm=False` | 17:21:41，同样匹配 |
| 首个目标 marker 回复耗时 | 3.719 s | 3.703 s |
| SQLite user / model_turn seq | 7 / 8 | 9 / 10 |
| 最终 Matrix `m.new_content.body` | 严格等于新 marker | 严格等于新 marker |

SQLite `conversation_history` 的这四行包含两次真实 user content 和两次 `kind=model_turn, role=assistant`，并非 readiness 直回。原始 model_turn 在 marker 后另有 HTML 注释，最终 Matrix 渲染内容去除了注释。因此“Matrix 最终可见 body 严格只有 marker”为 2/2；**不能说原始模型输出字节也严格只有 marker**。四个相邻 seq 为 user/model/user/model，没有插入的工具历史行；本次没有主动发起工具任务。

## 出站 relation 的实际结果

每个请求均产生两个目标 Worker 事件：一个主时间线 `m.notice` 占位“处理中...”，以及一个 `m.replace` 更新该占位的最终 marker 内容。

| 入站类型 | 新占位 event ID | 最终编辑 event ID | 编辑指向 |
| --- | --- | --- | --- |
| reply | `$cJmyI1to20Sa4JxHticxvDZQty5ECE-187uKj3aHE5s` | `$mAE0RtW4k0FGDLcgn1qKqsVwN1wkf_aPvhL-ZjELToE` | 自己的新占位 |
| thread | `$apqT4Yk-s3svN-sCSofWCylzzsOalsWR6-0_WzYVazs` | `$p_msVQykosx5Lhv-zfuYP2m_OidkqFH9hHCu7aXq3gc` | 自己的新占位 |

两个初始占位均无 `m.relates_to`；最终编辑关系只有 `rel_type=m.replace` 和自己的占位 ID，`m.new_content` 中也无原父／thread 关系。因而当前观测范围内：

- 普通 reply 入站能触发模型，不代表出站是对原事件的普通 reply。
- thread 入站能触发模型，不代表输出继续挂在原 `m.thread` 根下。
- 不能把 `m.replace` 所携带的自身占位 ID 误读成原业务 thread 的归属。

这与部署源码相符：`_is_thread_event` 按 `rel_type == m.thread` 判断入站；`_on_room_event` 对 thread 采用不同的群聊缓存路径，但 payload 只把当前入站 event ID 放入 `thread_root_event_id`。出站 `_apply_thread_relation` 要求明确的 `matrix_thread_root_event_id` 或 own thread context，不直接使用该 inbound 元数据。原始证据包含实际部署文件的相关行。

本次没有插桩记录 `_is_thread_event` 的布尔返回，也没有构造额外的缓存对照消息。**两种入站格式的实际处理已被证实；具体缓存跳过／保留差异仍以源码与早期组件测试为依据，不把这两次模型回复当作所有缓存分支都已实测。**

## 实际会话归属与 AT-10 边界

两次 `scroll: wiring components` 运行日志都记录：

```text
session_id=matrix:!Ff6iZ4IGTwHpkhX922:rv-a.matrix.invalid
```

SQLite 四行均使用该 session ID，`agent_id=default`。因此本次实际普通 reply 与 thread **共享这个 room session**，并未按各自 reply event 或 thread root 新建会话。该结论来自实际运行日志和持久历史，不只是从源码推导。

AT-10 可增加“部署 custom Worker 对两种有提及的入站关系完成真实模型回复、出站 relation 与 room session 已核查”。当前仍没有 RepoMesh Issue／round／Attempt 映射实现，也未验证跨 Issue 受控会话隔离、输出归属校正、rich-reply 客户端兼容、无提及 thread 负例、不同 thread 并发或缓存所有变体。不能将本报告升级为 AT-10 整体业务验收通过。
