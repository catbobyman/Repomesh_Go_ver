# 实际模型→工具→文件闭环

日期：2026-09-09。实际Worker：`live-runtime-worker-a`。两个独立请求均只发送一次，使用持久事务状态防止未知结果重发，中文请求经过Matrix事件精确读回验证。

## 配置管理员请求：权限拒绝

发送者为实际配置管理员`@rv-a-admin:rv-a.matrix.invalid`，在Worker个人房间要求创建唯一nonce文件。Worker明确回复“您目前没有访问此智能体的权限，需要审批”，文件不存在。没有改allowlist或由验证脚本代写。

只读运行配置显示：自定义`agentteams_matrix`启用，内置matrix禁用；访问白名单为`@admin:rv-a.matrix.invalid`、自身和`@manager:rv-a.matrix.invalid`，真实`@rv-a-admin`进入pending。这是本次配置管理员身份与白名单投影不一致的实际证据，不代表该人类身份已获准使用Worker。

[请求、拒绝及文件不存在](../evidence/worker-model-file-live.json)、[策略只读快照](../evidence/worker-model-file-policy-readonly.json)。收到明确拒绝后结束等待，补做只读文件审计；不把被主动结束的原轮询退出状态误判为运行故障。

## 已获准Manager身份正向对照：最终通过

另读取实际运行Manager已投影的Matrix token，只在内存使用并通过whoami确认发送者为`@manager:rv-a.matrix.invalid`。发送**新的**一次性请求，目标仅为Worker自己的工作区文件，不假冒人类身份权限通过。

请求nonce：`RV_FILE_b87b04847d80`。实际行为链：

1. Worker收到请求并调用`write_file`，参数content精确为nonce。
2. 运行治理日志记录目标在workspace内、`action=allow source=user_rules`。文件实际产生。
3. 初次独立字节读取发现UTF-8 BOM `EFBBBF`前缀，不满足严格字节要求。这个初始失败快照保留。
4. **模型自己**接着调用`execute_shell_command`读取大小／hexdump，发现BOM，再自己调用printf去掉BOM。验证脚本没有执行写入或修复命令。
5. Worker给出最终路径、内容和自行修正BOM的说明；验证脚本随后只读检查文件，严格20字节完全等于nonce，无BOM／无换行。

最终文件：`/root/agentteams-fs/agents/live-runtime-worker-a/.qwenpaw/workspaces/default/validation-model-RV_FILE_b87b04847d80.txt`。

最终SHA256：`1b380152a119d54fce5e54e552aa950508ca5e0b26172e75e2ab9182fa495360`。

[完整Manager对照证据](../evidence/worker-model-file-live-manager.json)包含初始BOM字节、完整Matrix工具轨迹和最终独立字节回读。初始轮询在第一条含nonce的工具事件处提前结束，因此初始结果只代表中间态；随后只读拉取最终时间线并重新读文件，证据同时保留两阶段，不覆盖初始失败。模型最终自检与修正不能被误记为harness代做。

## 范围

正向对照证明这个已获准Manager身份的真实消息能驱动Worker模型、文件工具和有限shell自检完成工作区内文件任务。没有验证外部仓库／网络权限、GitHub交付、任务执行租约或业务验收。人类配置管理员的访问失败仍是独立未解决缺口；不能以Manager正向成功替代它。

[复跑脚本](../scripts/worker-model-file-live.py)；默认使用人类管理员案例，`--manager`使用独立Manager案例，`--audit-only`只复查已有请求／文件，不重新发送。
