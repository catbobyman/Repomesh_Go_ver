# Matrix 通道组件验证：AT-06／AT-07／AT-10

执行日期：2026-09-09。上游提交：`eeaab64391ccaec9118e84977f538aefd40720d6`，与本轮主验证锁定的 GitHub main 一致。本报告记录已运行的组件实验，**不代表 AT-06／AT-07／AT-10 的完整业务验收通过**。

## 环境、过程与边界

- Windows、Python 3.11.7。独立脚本位于 [matrix-component-validation.py](../scripts/matrix-component-validation.py)；结构化结果、执行时间和源码 SHA-256 位于 [matrix-component-results.json](../evidence/matrix-component-results.json)。
- 读取上游 `AGENTS.md`、现行验证清单和 `plugins/agentteams-matrix-channel/agentteams_matrix/channel.py`，审查上游 `qwenpaw/tests/test_matrix_overlay.py` 中的测试装载器。
- 复用上游 `_load_overlay_module()` 加载**未修改的完整通道源码**。该装载器用 stub 替代 `nio`、QwenPaw schemas 和 BaseChannel。脚本为外部 BaseChannel 初始化／请求构造提供 fake，使用真实通道构造、消息处理、历史、session 参数构造和发送重试函数。
- Matrix 成员查询、发送、已读、typing、Agent process、入队回调均为显式 fake。没有网络 Matrix、模型推理、QwenPaw 队列消费者、实际 runtime 重启或持久 session 存储。`processed = 0` 说明探针／回调自身不执行模型，不证明真实队列消费者永远不处理。
- 没有修改上游源码、安装依赖、启动或停止 Docker、调用真实模型。沿用本机已有 pytest/httpx；使用进程内 stub，不污染其他 Python 进程。

执行命令（在项目根目录）：

```powershell
python -X utf8 validation/agentteams-2026-09-09/scripts/matrix-component-validation.py
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q -o addopts= -p no:cacheprovider validation/agentteams-2026-09-09/upstream/qwenpaw/tests/test_matrix_overlay.py validation/agentteams-2026-09-09/upstream/qwenpaw/tests/test_matrix_plugin.py --junitxml=validation/agentteams-2026-09-09/evidence/matrix-upstream-pytest.xml
```

两条验证命令退出码均为 0。自建脚本 10 项 `OBSERVATION_CONFIRMED`；上游测试 **39 passed in 2.01s**，[JUnit 记录](../evidence/matrix-upstream-pytest.xml)。上游测试包括静态源码断言与 fake 运行实验，并非全部是集成测试。未把 39 个绿色测试当作业务覆盖证明。

## 实验和结果

| 实验 | 输入／故障注入 | 实际观察 | 对业务要求的含义 |
| --- | --- | --- | --- |
| MX-01／AT-06 | 两个 sender 在同房间分别请求 Issue A/B，再换房间；源事件加 `issue_id` | 同房间 request-builder 参数均为 `session_id=matrix:{room_id}`、`sender_id=room_id`，真实 sender 保留在 meta；`issue_id` 未投影进 meta；跨房间 session/debounce key 不同 | 原生提供房间级会话参数，不提供可信 Issue／仓库／授权绑定。自定义源字段不会自动成为业务上下文。没有推理、权限执行或持久 session 隔离证据。 |
| MX-02／AT-10 | 群聊顺序输入 55 条未 mention 消息，再 mention 触发 Issue B | 未 mention 时未入队；历史只剩第 6—55 条（`history-5` 到 `history-54`）；触发时拼入上下文，入队回调返回即清除历史 | 50 条是内存上下文上限，不是持久投递保证；同房历史会进入当前消息上下文，没有按 Issue 分区。 |
| MX-03／AT-07/10 | 一个通道对象缓存消息后新建通道对象 | 新对象历史为空，后续 mention 不含旧缓存消息 | 证实构造器内存缓冲不跨对象保留；没有测试 Matrix replay 或 runtime 的独立持久 session 恢复，不能据此断言所有历史必丢。 |
| MX-04／AT-06/10 | 普通未 mention、未 mention thread、mention thread、普通 reply | 未 mention thread 被忽略且不缓存；mention thread 入队但不拼房间历史，也不清原房间缓存；普通 reply 拼入历史；thread 入队 meta 的 root 为当前事件 `$thread` | reply 和 thread 的上下文规则不同，不能仅靠外观类似假定一致；跨 Issue thread 需要可信业务归属。 |
| MX-05／AT-07 | 定向 readiness 文本，要求精确返回 READY | 直接发送 READY；入队数 0、process 调用数 0、已读数 0 | 该探针能验证通道特定分支，不证明模型可用或业务处理已开始。 |
| MX-06／AT-07/10 | 普通 mention 请求，消费者不运行 | 顺序为 read receipt → typing → enqueue；process 仍未调用 | 已读先于消费，不应更新成“模型已处理”。 |
| MX-07／AT-10 | 对同一 `$same` event_id 调用消息回调两次 | 队列收到两次 `$same` | 回调级没有事件去重；实际 nio 会否重放、RepoMesh 去重是否生效需要真实投递测试。 |
| MX-08／AT-10 | 先缓存，再在 trigger 的 enqueue 注入异常 | 已读已发送，异常向外传播，缓冲仍保留 | 队列失败时不能用已读当成功；历史保留是局部有利行为，但没有持久 outbox 或恢复确认。 |
| MX-09／AT-10 | 顺序调用；另并发调用并阻塞第一条 read receipt | 顺序调用入队 `seq0,seq1,seq2`；并发注入时为 `second,first` | 通道回调自身没有覆盖外部 await 的顺序锁。这个夹具没有证明 nio 实际并发交付，也未运行 QwenPaw manager queue，不能直接报生产乱序。 |
| MX-10／AT-10 | 第一次发送注入 TimeoutError，后续成功；再次调用发送同一内容 | 单次调用的两次尝试使用相同 tx_id；新一次调用使用不同 tx_id | 原生支持单次发送内部重试标识稳定；跨调用／进程恢复的业务幂等仍需上层持久操作身份。未调用真实 homeserver，服务器去重尚未验证。 |

## 结论与剩余验收

组件事实与之前源码调查一致，并补充了重复回调、队列失败和事务标识的运行证据。10 项观察通过包含“确认限制”，不意味着对应业务约束通过。使用状态应为 **组件验证已执行，完整联调待执行**。

**AT-06 尚需：** 真实同会话交错 Issue、歧义澄清、A 页面操作 B、不同读写权限、迟到结果、工作目录与真实模型/session 归属。原生 room session 参数只能作为输入条件；适配层必须绑定可信 instance/team/project/Issue/Attempt 等身份，并在执行时核验。

**AT-07 尚需：** 首消息／建项并发启动的幂等、部分建房失败、响应丢失、Controller 与 runtime 分别重启、旧 Ready 报告、资源／通道／模型／实际工作四层证据。新建 Python 对象不等同于容器重启测试。

**AT-10 尚需：** RepoMesh 持久 outbox/待办、Matrix 真实事件重放、丢响应后的去重、准备期超过 50 条消息的完整处理、消费者执行顺序、进程崩溃恢复。当前源树的回调组件没有 RepoMesh 业务存储，因此不能证明其未来适配已经正确。

## 复核点

- 原生通道源文件：`plugins/agentteams-matrix-channel/agentteams_matrix/channel.py`。
- 行 295／407—435：history 默认值、构造器内存状态和房间 debounce key。
- 行 1931—2006：缓冲、格式化、拼接和清理。
- 行 2637—2820：事件入口、readiness、mention/thread、read receipt、payload 与 enqueue。
- 行 3120—3149：请求参数与 session 构造。
- 行 3358—3405：thread/readiness 分支。
- 行 4334 起：单次调用生成 tx_id 并复用重试。

定位以上行号时应使用本报告固定提交，不套用到后续 GitHub 版本。原始 JSON 保留源码哈希供复跑核对。
