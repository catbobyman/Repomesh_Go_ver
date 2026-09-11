# QwenPaw MCP 配置保存、投影与运行时加载验证

2026-09-09；AgentTeams `eeaab64391ccaec9118e84977f538aefd40720d6`；实际 Worker 镜像 `repomesh-validation/qwenpaw-worker:eeaab643`，容器内 QwenPaw 为 `2.0.1`。

结论：原脚本等待 `mcporter.json` 的探针不适用于本次 QwenPaw 原生路径，不能将其退出 1 判成 MCP 配置功能失败。改用当前原生接口后，REST 保存、runtime.yaml 投影、原生 DriverCard 生成、运行中 QwenPaw 查询远端工具均实测成功；同 Worker 内另启原生客户端进程调用 echo 也成功。没有调用模型，也没有验证模型选择工具、Agent 权限策略或远端鉴权。

## 为什么原探针会失败

原脚本 [mcp-config-contract-live.py](../scripts/mcp-config-contract-live.py) 在 Worker 中递归查找 `mcporter.json`，并计划用 mcporter CLI 调用。第一次错误路径及后续 `--reuse` 的输出都保留；本次没有覆盖原来的 [mcp-config-contract-live.json](../evidence/mcp-config-contract-live.json)。后者已经证明 REST PUT/GET 成功、`runtime/runtime.yaml` 中 `desired.mcpServers` 变更成功，但 20 次采样中没有 mcporter 文件。

当前 Controller 把 Worker `spec.mcpServers` 放入 runtime desired 配置，见 [runtime_config.go:255](../upstream/agentteams-controller/internal/service/runtime_config.go#L255)。QwenPaw 的 apply 流程调用 `_reconcile_mcp_clients`，见 [update.py:1445](../upstream/qwenpaw/src/qwenpaw_worker/update.py#L1445)。该函数通过 QwenPaw 本机 API 列举、创建、更新和删除客户端，并保存受管客户端名称，见 [update.py:1683](../upstream/qwenpaw/src/qwenpaw_worker/update.py#L1683)，并不要求生成 mcporter 文件。

原生 API client 使用 `/api/mcp` 和 `/api/mcp/{key}`，见 [api.py:165](../upstream/qwenpaw/src/qwenpaw_worker/api.py#L165)。`http` 会转换成 QwenPaw 需要的 `streamable_http`，见 [update.py:2104](../upstream/qwenpaw/src/qwenpaw_worker/update.py#L2104)。虽然内部兼容转换函数仍叫 `_mcporter_servers`，函数名不代表其输出持久化为 mcporter 配置。

实际安装的 QwenPaw 2.0.1 将原生 MCP 客户端保存为 DriverCard：`MCPConfigService.create_client` 构造 card 后调用 `save_card`，见 [实际容器源码 config_service.py:258](../evidence/control-mcp-native-runtime-source/app/mcp/config_service.py#L258)。本轮卡片位置为：

```text
/root/agentteams-fs/agents/coverage-mcp-ab69215252/.qwenpaw/workspaces/default/drivers/mcp/validation-contract.yaml
```

`.qwenpaw/config.json` 仍有 `mcp.clients` 等兼容配置结构，但不能仅检查它或者 mcporter 文件来判断这个原生客户端是否加载。

## 纠正探针后的真实结果

Run ID `19ff82a44f`，开始于 `2026-09-09T17:16:02.548961+00:00`。只沿用专用 Worker `coverage-mcp-ab69215252` / 容器 `rv-a-worker-coverage-mcp-ab69215252`。新 helper `rv-mcp-contract-native-19ff82a44f` 使用同隔离网络 `rv-a-net`，提供不要求鉴权、只回显随机标记的 FastMCP HTTP 服务；未发布主机端口。

| 层次 | 实际验证方式 | 实测结果与边界 |
|---|---|---|
| Controller 保存 | PUT `mcpServers`，随后 GET 同一 Worker | 均 HTTP 200，名称、URL、`transport:http` 完全匹配 |
| 运行配置投影 | 从专用 Worker 读取 `runtime/runtime.yaml` 的 `desired.mcpServers` | 第 2 次采样与声明一致；第一次尚为空，说明存在短暂异步收敛 |
| 原生客户端落盘 | 读取自动生成的 DriverCard，仅记录安全字段 | 卡片存在，`protocol:mcp`、`enabled:true`，endpoint 正确，transport 为 `streamable_http` |
| 运行中 QwenPaw 读取客户端 | 本机 `GET /api/mcp/validation-contract` | HTTP 200，客户端 enabled，URL/transport 正确 |
| 运行中 QwenPaw 加载工具 | 本机 `GET /api/mcp/tools/validation-contract` | HTTP 200，返回 enabled 的 `validation_echo` |
| 实际 MCP 工具调用 | 同容器新 Python 进程，使用已安装 QwenPaw `HttpStatefulClient`，URL/transport 从运行中 API 读取，真实 list/call | 返回文本和 structured result 均为 `19ff82a44f`，`isError:false`；helper 日志精确记录 1 次该 nonce |
| mcporter 文件 | 同时保留旧式路径扫描 | 仍为 0 个；在以上原生行为全部成功时无此文件是正常现象 |

运行中 QwenPaw 的 `/api/mcp/tools/{key}` 并非只把保存的名称回显出来。实际路由调用 `MCPConfigService.list_tools`，见 [实际容器源码 mcp.py:73](../evidence/control-mcp-native-runtime-source/app/routers/mcp.py#L73)；后者通过 Driver 系统查询 capability，失败时返回 502，见 [config_service.py:128](../evidence/control-mcp-native-runtime-source/app/mcp/config_service.py#L128)。新 helper 与新 URL 的工具发现成功，支持“原生运行时已加载并可发现这个真实远端 MCP 工具”的结论。

最后一步调用使用实际安装的 [HttpStatefulClient](../evidence/control-mcp-native-runtime-source/drivers/handlers/mcp_stateful_client.py#L697)，以及其原生 [call_tool](../evidence/control-mcp-native-runtime-source/drivers/handlers/mcp_stateful_client.py#L377)。它是实验在 Worker 容器内新建的客户端进程，不是通过模型会话调用，也没有沿 Agent 的 policy / approval / tool-dispatch 链路执行。该 helper 不要求凭据；实验不读取或复制客户端的 header 值，因此不证明 gateway key、Authorization 或 OAuth 配置正确。

## 清理、证据与可复现边界

结束时经 Controller PUT 将该专用 Worker 的 `mcpServers` 恢复为空；第 2 次清理采样确认 desired 列表为空、原生客户端 API 返回 404、DriverCard 已移除。确认 exact helper 名称和本轮验证标签后，仅 stop/rm `rv-mcp-contract-native-19ff82a44f`。没有删除 Worker、没有触碰其他 Worker、没有重启任何已有服务。

- [纠正后的完整安全字段证据](../evidence/control-mcp-config-native-19ff82a44f.json)：保存、投影、原生 API、工具回显、调用计数、配置复原及 helper 删除确认。
- [本轮脚本](../scripts/control-mcp-config-contract-live.py)：与旧脚本分开，固定只操作该专用 Worker，创建新的独立 helper。它在 finally 中恢复配置并清理本次 helper。
- [实际容器 QwenPaw 源码快照和哈希](../evidence/control-mcp-native-runtime-source/manifest.json)：只复制相关 Python 源文件；记录版本与三个文件 SHA-256，不包含配置或凭据。执行后 AgentTeams upstream `git status --short` 为空。

原脚本失败记录是探针适配过程的证据，不能改写为已通过；本轮纠正后的独立证据证明上述限定范围内的正向链路。RepoMesh 的 MCP 安装权限、Issue 隔离、动态工具授权、模型实际使用以及不同 runtime 的配置契约仍需分别验证，不能从这个 QwenPaw 专用用例推断。
