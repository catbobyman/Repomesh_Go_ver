# 新版 Manager：一次真实模型 smoke

2026-09-10 `03:57 UTC`，已重建并恢复配置的 **c/default Manager 完成一次真实模型推理**。专属 Matrix 请求得到精确 nonce 回复，且与同一原生会话的 assistant 消息和逐轮 token 用量对应。没有以 health、Ready 或模型配置 GET 替代推理证据。

## 结果与归属

| 项目 | 实际结果 |
|---|---|
| 部署 | `rv-c-manager`，image `repomesh-validation/manager-qwenpaw:517caff9` |
| 实际 image ID | `sha256:8cf1059295e6c172ba30d7e732cc382169678fcb44b2e7f56c159203b0c20b6a` |
| 容器 ID | `ca0b7cc01d9df7959471674d8eb4057912fa5c64904741b19318a2fde1a3fe52`，与 CFG05 恢复终态一致 |
| Manager | Controller `default`；runtime agent `default`；Matrix `@manager:rv-c.matrix.invalid` |
| 测试发送者 | 本任务创建的 c 管理员 `@rv-c-admin:rv-c.matrix.invalid` |
| 专属房间 | `!1kMUI31V0S5xQhDgD7:rv-c.matrix.invalid`，发送前 joined_members 恰好为上述两人 |
| 请求 event | `$iispgL3u_vTJFnCj3qcG57cGSJgxXZQPBBNOoQDA6YU` |
| 响应 event | `$rgSZYuc1Z5U8Q56wAeUJk1t4GBQVGZ7_rv_Ct3VDiSE` |
| 精确回复 | `RV_MODEL_MATRIX_NEW_5f5be6136b0e` |
| 可见响应耗时 | 4.141 秒，harness 单调时钟测得，包含实际发送与轮询开销 |
| 原生 chat ID | `79165eb0-2c66-4cfd-8b9f-2427b0712660` |
| 原生会话 | `matrix:!1kMUI31V0S5xQhDgD7:rv-c.matrix.invalid` |
| 逐轮实际用量 | Provider `agentteams-gateway`，model `deepseek-chat`；prompt 17,666、completion 57、total 17,723 tokens |
| 工具证据 | 本轮原生历史仅一条 user、一条 assistant；function／MCP／plugin／tool 消息 0；该会话 tool coordinator 0 |
| 终态 | global active model 保持 `agentteams-gateway / deepseek-chat`，Manager 容器仍运行 |

逐轮用量来自本轮 assistant 的 `metadata.metadata.qwenpaw_turn_usage.usage`。同一 runtime 的累计用量从 0 增加到 1 次，prompt／completion 增量也分别为 17,666／57，与本轮记录吻合。累计数仅作为旁证，归属以唯一 nonce、Matrix 双 event、原生会话及 assistant 的逐轮 metadata 为准。短输入仍携带 Manager 的系统提示词与原生上下文，所以并非只有 nonce 本身消耗输入 tokens。

[最终只读确认与完整本轮消息](../evidence/control-manager-model-smoke-confirmed.json)保留上述证据；[首次有效 Matrix 提交与响应](../evidence/control-manager-model-smoke-matrix.json)记录发送、UTF-8 精确读回及原始事件。

## 唯一有效提交及探针边界

1. 先尝试原生 `POST /api/console/chat/task`，请求指定唯一测试 user/session 与 `X-Agent-Id:default`。实际返回 **503 `Channel Console not found`**。实际配置中 console.enabled=false、matrix.enabled=true；新 QwenPaw 源码在查找 Console Channel 后即返回，尚未执行 get_or_create_chat、创建 task 或调用 stream_one，因此没有 task_id、没有这条请求的模型推理。未启用 Console、未改模型配置、未重试该 API。[原始拒绝记录](../evidence/control-manager-model-smoke-new.json)、[实际通道配置与新镜像入口源码](../evidence/control-manager-model-entry-source.json)
2. 沿既有 Matrix 通道只发送 **一次有效 nonce 请求**，明确要求不得调用工具、读写文件、检查仓库、派工、创建资源或联系别人。验证脚本先确认自有管理员身份和仅两人的专属房间，再发送，并通过原生 event GET 确认请求内容未发生编码变化。之后只查询该房间、该消息和对应会话，未重复发送。
3. Manager 在 `03:57:12` 返回精确 nonce。随后首版后置历史探针错误地用发送者 Matrix user ID 过滤 chat，因而断言失败；**这发生在真实响应之后，不是模型失败**。QwenPaw 此 Matrix 会话的原生 chat.user_id 实际是 room ID。后来使用已确认的专属 room ID 进行只读关联，找到唯一含该 nonce 的 user→assistant 本轮历史。没有再提交推理。[只读确认脚本](../scripts/control-manager-model-smoke-confirm.py)

本轮计数明确为：**1 次在创建任务／模型前被拒绝的 Console API 请求，1 次有效 Matrix 推理提交，0 次模型重试**。原始脚本退出记录保留，不把探针错误抹成一次无中断成功。有效提交与只读补证均已结束，无运行中的测试后台任务；该原生会话保留作证据，没有删除用户或房间。

脚本：[Console 一次尝试](../scripts/control-manager-model-smoke-new.py)、[Matrix 一次有效提交](../scripts/control-manager-model-smoke-matrix.py)。秘密仅保存在本轮已验证 ACL 的 private 目录，公开证据不包含登录 token、Provider key 或 headers。

## 结论范围

这一证据证明 **本轮实际新镜像的 c/default Manager，通过已配置 Matrix 通道和默认 chat Provider 完成一次可归属的推理并返回结果**。它补足[配置验证报告](manager-config-live.md)原先只到运行进程内存配置的范围。它不代表 Worker、新增其他 Provider、非空绑定 `/v1/v1` 路径或 RepoMesh 业务接入均已验收。

本次 smoke 没有工具调用记录，也没有更改 Provider／model 配置或服务状态。此前原生启动的 welcome 可能调用 Provider，不能据本轮计数宣称整个部署生命周期总共只有一次调用。非空绑定 URL 影响仍以[独立只读分析](provider-url-analysis.md)的未验证边界为准。
