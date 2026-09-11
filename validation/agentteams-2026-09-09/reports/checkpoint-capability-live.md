# 实际 checkpoint 代理与 runtime 能力

2026-09-09。AT-01／07 的只读能力核对。当前实际 Worker 镜像内 QwenPaw 为 **2.0.1**，Controller 的 checkpoint 代理注释描述 **2.1** 的 workspace checkpoint。已通过运行端点核查，不能依赖代理路由存在就宣称能够恢复 checkpoint。

## 实际请求

对象为已有 `rv-a-worker-live-twin-worker`，未修改配置、建立快照、恢复或重启。Controller 请求使用本轮管理员身份；直接请求仅访问本机该 Worker 已发布端口。

| 请求 | HTTP／类型 | 实际内容 |
|---|---|---|
| Controller `/api/v1/workers/live-twin-worker/checkpoints/status` | **200、application/json** | **1073 字节 HTML，无法解析 JSON** |
| Controller `/api/v1/workers/live-twin-worker/checkpoints/graph?limit=5` | **200、application/json** | 同一 HTML |
| 实际 Worker `/workspace/checkpoints/status`／`graph?limit=5` | 200、text/html | 同一 SPA 页面 HTML |
| 实际 Worker `/api/workspace/checkpoints/status` | 404、application/json | 未找到，不是有效 checkpoint 响应 |
| Worker `/openapi.json`／`/api/openapi.json` | 404 | 接口目录不可用；不能据此把 API 数量记作零 |

四个 200 响应的完整 body SHA-256 相同：`c8ec29b49d5525861c641a68659db9b38302fd9550563db545213434a0af20fe`。这是前端回退页通过代理返回的实证，**不是 checkpoint 图为空或 checkpoint 健康正常**。代理将 Content-Type 设为 application/json，没有保证响应体真是 JSON。

只读扫描实际已安装的 `qwenpaw/app/**/*.py`，未发现包含 checkpoint 的文件。该范围与版本及端点结果相互支持；没有把扫描扩大为该镜像所有依赖都不存在任何同名能力。

## 证据与限制

[脚本](../scripts/checkpoint-capability-live.py)、[原始响应形态、哈希与源码清单](../evidence/checkpoint-capability-live.json)。第一次仅测试代理、原始 runtime 路径及 `/openapi.json`，结果保留在[初次快照](../evidence/checkpoint-capability-initial.json)；随后补 `/api` 前缀与实际源码清单，没有更改产品以得到成功。

结论限于锁定源码所构建的此镜像：**这两条代理当前没有提供可用的 checkpoint JSON 契约**。尚未测试另一版本、更换 runtime、真正 snapshot／restore，不能从此断言这些未来组合也不支持。若后续恢复设计依赖 checkpoint，必须先固定包含该能力的实际版本并重新验证端点及恢复副作用。本轮同容器 stop/start 的成功不依赖 checkpoint，也不能替代删除重建后的状态恢复。
