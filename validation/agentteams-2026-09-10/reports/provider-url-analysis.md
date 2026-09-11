# Provider 绑定后的 `/v1/v1`：源码与实际路由核查

**可确认二次 `/v1` 拼接确实存在；不能仅据这个字符串认定模型请求必然失败。** 当前真实 Gateway 的 `/v1/` 前缀路由仍会匹配 `/v1/v1/...`，route 层没有观察到 prefix／regex rewrite；但运行中的 AI proxy 插件有独立的 OpenAI 上游 URL 配置，本次没有验证其内部协议路径转换或实际推理结果。因此目前应记为**配置路径差异及兼容性风险，实际推理影响未验证**。

本任务只读源码，登录 Higress Console 后 GET 路由，并 GET 本机 Envoy admin config；未修改 c 的资源／Provider／路由，未调用模型。凭据仅在容器内读取和认证使用，所有输出按安全字段筛选，没有 token、key、password、cookie 或原始 config dump。

## 1. 二次拼接的完整源码链

本轮源码固定于 `517caff9280242a00a4d4c06365352b9e41659c6`：

1. [Higress ResolveModelProvider](../upstream/agentteams-controller/internal/gateway/higress.go#L564)确认 Provider 存在，再找使用该 Provider 的 AI route；取其 `pathPredicate.matchValue`，返回 `IntranetURL = TrimRight(DataPlaneURL, "/") + basePath`，见第 629—637 行。它没有把这个 route basePath 当作已经包含 API 版本的最终客户端 URL。
2. [Manager 配置协调](../upstream/agentteams-controller/internal/controller/manager_reconcile_config.go#L28)将 `modelProviderInfo.IntranetURL` 传给 `ManagerDeployRequest.AIGatewayURL`。
3. [DeployManagerConfig](../upstream/agentteams-controller/internal/service/deployer.go#L1283)继续原样传给 `GenerateOpenClawConfig`。
4. [generator](../upstream/agentteams-controller/internal/agentconfig/generator.go#L40)优先采用请求的 AIGatewayURL；第 129 行配置 `baseUrl = aiGatewayURL + "/v1"`，没有去重现成的 `/v1`。

所以当 DataPlaneURL 是 `http://rv-c-controller:8080`、命中的 route basePath 是 `/v1` 时：

```text
绑定 openai-compat：Resolve → http://rv-c-controller:8080/v1
                    generator → http://rv-c-controller:8080/v1/v1
清空绑定：           默认 Gateway 根 URL → generator 追加 /v1
                    → http://rv-c-controller:8080/v1
```

这解释了 CFG-05 报告的实际配置差异。它不是 JSON 转义、显示截断或仅由字符串相似推断而来。Manager 容器环境还会在绑定非空时使用该 IntranetURL 覆盖 `AGENTTEAMS_AI_GATEWAY_URL`，见 [manager_reconcile_container.go:163](../upstream/agentteams-controller/internal/controller/manager_reconcile_container.go#L163)。本报告没有因此修改任一层的拼接逻辑。

## 2. 实际 route 不会仅因多一个 `/v1` 而匹配失败

[安全 Console／Envoy 证据](../evidence/provider-url-readonly.json)记录：

| 层 | 实际读取结果 |
| --- | --- |
| Higress AI route | `default-ai-route`，upstream provider `openai-compat` |
| Console pathPredicate | `matchType=PRE`，`matchValue=/v1`，`caseSensitive=false` |
| Envoy live route match | 精确 `/v1`，另有前缀 `/v1/` |
| 上述 route 的 prefix／regex rewrite | 未见 `prefix_rewrite` 或 `regex_rewrite` |

因此假如客户端在这个 base URL 后追加 `/chat/completions`，`/v1/v1/chat/completions` 仍落在 `/v1/` 的路由前缀内。**不能声称它因为 route 不匹配而必然 404。** 同时，没有 route 级 rewrite 也意味着目前不能把“Gateway 一定在路由层删掉多余 `/v1`”写成已有事实。

本次未向两个路径发送推理或探测请求；上述请求完整 path 是条件示例，不是假称抓到了实际 Manager 推理流量。

## 3. AI proxy 还有一个未穷尽的路径转换层

[独立安全插件字段](../evidence/provider-url-plugin-fields.json)从 Envoy 当前配置中读取到：

- 已激活 filter：`extensions.istio.io/wasmplugin/higress-system.ai-proxy.internal`。
- Provider `type=openai`。
- `openaiCustomUrl=https://api.deepseek.com/v1`。

这证明数据面不仅是一个原样转发的裸 prefix route，还有 AI proxy 的协议适配层及其上游地址。**它是否根据 API 后缀重建上游 path、是否保留／剥离额外 `/v1`，仅靠这些配置字段不能确定。** 若插件重建路径，重复前缀可能仍得到正常上游请求；若保留完整入站尾路径，则可能把额外版本段带到上游并失败。这里是两种待验证机制，不是已确认该插件采用其中任一种。

本轮源码库没有包含这个正在运行的 Higress Wasm 插件的完整实现。本任务没有用其他版本的互联网源码代替实际模块，也没有用配置中存在 `openaiCustomUrl` 就推导端到端成功。没有输出 Provider 的认证字段。

## 4. 建议记录方式和仍缺的证明

CFG-05 可以确认：“非空 Provider 绑定与空绑定所选择的配置路径不同；清空后生成默认 `/v1`，非空绑定当前生成 `/v1/v1`。”

目前不应写成：“非空绑定必然无法调用模型”“Higress rewrite 已证明正常”“清空修复了实际模型连通”。这些都超出本次只读证据。要确定最终影响，需要核对**实际加载版本**的 AI proxy 路径转换实现，或单独授权并观察完整请求的最终上游 path／响应；不靠再次看相同配置字符串完成验收。本任务没有新增该实验。

安全取证脚本：[路由只读查询](../scripts/provider-url-readonly.py)、[插件路径字段查询](../scripts/provider-url-plugin-readonly.py)。采样记录的系统时钟为 `2026-09-10T03:40:07Z`／`03:40:59Z`，比本轮较早文件的 10:xx 时间小；保留原时间，**不据这些跨时钟快照计算耗时或因果顺序**。
