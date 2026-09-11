# TeamHarness 原生工具组件实验

UTC: 2026-09-09T16:21:32.910739+00:00  
源码: `eeaab64391ccaec9118e84977f538aefd40720d6`  
Python: `3.11.7`  
执行入口：真实 `server.call_tool`，继续调用未改写的 projectflow/taskflow/filesync。

**这是已执行的 Python 组件实验。Matrix HTTP 与 mc 文件传输被明确替换为本地 fake；没有部署 Controller、Matrix、MinIO、Agent runtime 或模型。PASS 只表示预期现象成功复现，绝不表示 AT 产品验收通过。**

共 14 项组件实验，预期核对 14 项 PASS，0 项 FAIL。源码 SHA-256 运行前后相同；没有改写上游生产文件。

| 实验 | AT 范围 | 预期核对 | 观察分类 | 观察内容 |
|---|---|---|---|---|
| CONTROL-01 | AT-02 | PASS | GAP_REPRODUCED | Caller role overrides runtime role |
| CONTROL-02 | AT-02, AT-03 | PASS | GAP_REPRODUCED | Paused ready list is empty but direct delegation assigns |
| CONTROL-03 | AT-02, AT-03 | PASS | GAP_REPRODUCED | Worker projectflow replaces paused in-progress DAG |
| CONTROL-04 | AT-04 | PASS | GAP_REPRODUCED | plan_dag reports ok after failed storage push |
| CONTROL-05 | AT-04 | PASS | GAP_REPRODUCED | plan_dag continues after failed authoritative pull |
| CONTROL-06 | AT-04 | PASS | GAP_REPRODUCED | Delayed MCP push overwrites an intervening external pause |
| CONTROL-07 | AT-05 | PASS | GAP_REPRODUCED | Same-Team distinct Projects reuse the same task metadata |
| CONTROL-08 | AT-05 | PASS | SUPPORTED_COMPONENT_BEHAVIOR | Same logical delegation retry reuses assigned event |
| CONTROL-09 | AT-05 | PASS | SUPPORTED_COMPONENT_BEHAVIOR | Distinct upstream task IDs preserve separate attempt records |
| CONTROL-10 | AT-03, AT-11 | PASS | SEMANTIC_BOUNDARY_CONFIRMED | Cancellation persists terminal metadata and rejects later ack |
| CONTROL-11 | AT-02, AT-11 | PASS | GAP_REPRODUCED | MCP completes a Project with an in-progress task |
| CONTROL-12 | AT-02, AT-11 | PASS | GAP_REPRODUCED | Result acceptance defaults to completed without result evidence |
| CONTROL-13 | AT-04, AT-11 | PASS | SEMANTIC_BOUNDARY_CONFIRMED | submit_task can report ok while remote task sync fails |
| CONTROL-14 | AT-02, AT-08 | PASS | GAP_REPRODUCED | Taskflow acknowledgement has no shared Worker busy reservation |

## 可复现方式

在验证根目录运行：

```powershell
python scripts/control-teamharness-component.py
```

每次运行建立独立 evidence/control-workspaces/component-* 文件夹并保留逐例 trace.json、workspace/fake-object-store 任务与 Project 文件。聚合证据为 [control-component-results.json](../evidence/control-component-results.json)。脚本为 [control-teamharness-component.py](../scripts/control-teamharness-component.py)。

## 判定边界

- GAP_REPRODUCED：在原生工具组件入口复现 RepoMesh 规则尚未被该入口执行的缺口；不是已部署系统漏洞复现。
- SUPPORTED_COMPONENT_BEHAVIOR：在 fake 传输下组件的重试或唯一ID行为符合预期；真实 Matrix、存储、授权与重启仍未验证。
- SEMANTIC_BOUNDARY_CONFIRMED：确认元数据及回执语义；cancel 未验证进程停止或资源释放，submit 回执显式返回 synced=false，正确适配端可识别，不能称该回执隐瞒同步失败。
- CONTROL-06 以明确标记的 fixture 写入模拟 Controller 在 MCP 拉取之后成功修改共享对象；未执行真实 REST/ETag/MinIO 交错写。
- CONTROL-14 仅证明两个同 Worker 任务都可被原生工具 ack 为 in_progress，不证明实际模型或命令并行。

## 仍需部署及 RepoMesh 适配联调

AT-02：可信调用身份、Controller/存储/Git/模型权限和网络隔离，原生工具不可绕过实际授权；保留必要心跳和唤醒。
AT-03：真实 REST paused/replan 409、受控恢复窗口、在途收敛、submitted 接收和多目标部分应用、重启恢复。
AT-04：真实 mc/MinIO/Controller 双写、故障和CAS冲突、断网后恢复；本组件 fake 不能替代这些。
AT-05：真实 Matrix transaction 范围、跨团队身份、不同 runtime 工作区同步、持久 Attempt 映射。
AT-08：实际单Worker执行占用、旧执行停止/失去写能力、CPU/内存释放和分支/worktree隔离。
AT-11：真实 artifact、固定组合、作者独立性、证据留存、当前读权及最终业务验收。

## 源码定位

- CONTROL-01: [L471](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L471), [L3628](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3628), [L4100](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4100)
- CONTROL-02: [L2974](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L2974), [L4100](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4100)
- CONTROL-03: [L3265](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3265), [L3397](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3397)
- CONTROL-04: [L3397](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3397), [L3416](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3416), [L3823](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3823)
- CONTROL-05: [L3239](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3239), [L3275](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3275), [L3397](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3397)
- CONTROL-06: [L2505](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L2505), [L3397](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3397), [L3823](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3823)
- CONTROL-07: [L2807](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L2807), [L3811](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3811), [L4131](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4131)
- CONTROL-08: [L4131](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4131), [L4291](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4291)
- CONTROL-09: [L2807](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L2807), [L4049](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4049)
- CONTROL-10: [L4412](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4412), [L3946](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3946)
- CONTROL-11: [L3557](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3557)
- CONTROL-12: [L3042](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3042), [L3073](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L3073)
- CONTROL-13: [L4363](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4363), [L4403](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4403)
- CONTROL-14: [L4339](https://github.com/agentscope-ai/AgentTeams/blob/eeaab64391ccaec9118e84977f538aefd40720d6/plugins/teamharness/mcp/server.py#L4339)
