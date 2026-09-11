# 两个测试 Attempt task_id 的真实附件闭环与迟到提交

2026-09-09，run `e0c697152b`，完成于 `16:57:18 UTC`，命令退出 **0**。真实原生 MCP、Matrix 与 MinIO 的正向路径已跑通：6 个附件发布成功，本地／MinIO／mxc 下载字节一致；旧任务迟到重提没有改变新任务的元数据或文件。此结论限于**两个测试编码的不同 task_id**，不是 RepoMesh 已有持久 Attempt 映射、可信身份或验收实现。

## 范围与证据

- 固定上游提交 `eeaab64391ccaec9118e84977f538aefd40720d6`。完整 MCP 源复制到专属 `/tmp/repomesh-artifacts-mcp-e0c697152b`，运行前后 `server.py` SHA-256 与宿主源码一致：`741d211b36a4413e598989c43c9a7735926e18e49787e15a9ef9453d825dc98d`。
- workspace 为 `/tmp/repomesh-artifacts/e0c697152b`。复用上一轮独立 Team 的共享前缀 `agentteams/rv-a-storage/teams/coverage-race-32447df06f/shared`，仅新增 `artifact-e0c697152b-project` 及自己的两个任务目录，不修改之前 Project／Task。
- 新房间 `!CVunAmeB833k3SDSeY:rv-a.matrix.invalid`，测试 Alice 为收件人、Bob 为发布者。通过 Matrix 实际读回确认 `history_visibility=joined`；只让 Alice 退出本房间，其他房间和 Bob 的成员身份不变。
- 委派、ack、submit、check 都通过真实 `server.call_tool`；Matrix 文件上传／事件发送和 mc／MinIO 均真实，**没有 fake、函数包装或故障注入**。本次在 Controller 内独立 Python 夹具运行，不经过真实 Worker 模型／执行工具，也不验证 Worker 自有凭据的最小权限。`role=leader` 为原生工具参数，不当作可信业务角色证明。
- 未请求模型、重启容器或变更服务器配置；没有写入 GitHub。

脚本：[宿主编排](../scripts/control-artifacts-live-run.py)、[容器实验](../scripts/control-artifacts-live-container.py)。

```powershell
python -X utf8 validation/agentteams-2026-09-09/scripts/control-artifacts-live-run.py
```

每次执行使用新 run／房间／Project／task_id。原始[完整请求、响应、字节和哈希](../evidence/control-artifacts-live-e0c697152b.stdout.json)、[stderr](../evidence/control-artifacts-live-e0c697152b.stderr.log)、[退出码](../evidence/control-artifacts-live-e0c697152b.exitcode)、[简表](../evidence/control-artifacts-live-e0c697152b.summary.json)、[房间状态及 6 个 m.file 事件读回](../evidence/control-artifacts-live-e0c697152b-room-check.json)均保存，凭据已脱敏。8 次成功下载的原始文件另保存到 `evidence/control-artifacts-live-e0c697152b-downloads/`。

## 测试身份与真实调用顺序

夹具将同一逻辑任务标记为 `fixture-logical-task-e0c697152b`，用两个显式不同的上游 ID 表示两次尝试：

| 夹具含义 | 上游 task_id | 独立输出范围 |
| --- | --- | --- |
| 旧尝试 | `artifact-e0c697152b-attempt-1` | `shared/tasks/artifact-e0c697152b-attempt-1/` |
| 新尝试 | `artifact-e0c697152b-attempt-2` | `shared/tasks/artifact-e0c697152b-attempt-2/` |

两个 ID 都通过原生 delegate／ack；旧任务先提交 `old-original`，新任务再提交 `new-current`。随后快照新任务远端 `meta.json`、`result.md`、`output.txt` 的全部字节；旧任务以 `old-late-resubmission` 再次调用 submit，最后重新快照新任务作逐字节比较。

这里“旧／新／迟到”由夹具说明和文件内容标识，**没有 RepoMesh 的替代授权、失效代次、持久逻辑 Task 映射或实际业务调度**。旧任务仍处于原生可提交的 submitted 状态，没有先 cancel／complete 再绕过 terminal 检查。本次观察是原生允许的重提；不声称已验证所有已取消旧 Attempt 的迟到路径。

## 六个附件发布与完整性

每次 submit 写入真实 `result.md` 与显式 deliverable `output.txt`，文本包括 run、完整 task_id、修订名和中文。三次 submit 都返回 `ok=true, synced=true, status=submitted`，且各自两个 `publishedArtifacts.status=published`。随后原生 check_task 均返回 `effective=true`、无 validationErrors。

对每个附件独立核对：

1. `sourcePath` 在对应 task_id 目录内，发布文件名包含完整 task_id，TaskMeta 的 project_id／task_id 正确。
2. 收件人以自己的 token 读取真实 event；sender 为测试 Bob、msgtype 为 `m.file`，filename、size、mxcUri 与原生发布回执一致。
3. 附件 `m.relates_to.event_id` 指向该任务的原委派事件，旧／新任务关联没有混用。
4. 使用收件人 token 从 `/_matrix/client/v1/media/download/{server}/{mediaId}` 真实下载；本轮均为 200，没有使用 legacy fallback。下载字节、源文件、真实 MinIO `mc cat` 字节逐一相等。

下表 SHA-256 仅展示前 12 位，完整值及 eventId／mxcUri 见原始 JSON。

| 提交 | 文件下载 | 字节数 | SHA-256 前 12 位 |
| --- | --- | --- | --- |
| 旧首次 | [result.md](../evidence/control-artifacts-live-e0c697152b-downloads/01-result.md) | 119 | `8736243137b8` |
| 旧首次 | [output.txt](../evidence/control-artifacts-live-e0c697152b-downloads/02-output.txt) | 157 | `118606014c26` |
| 新尝试 | [result.md](../evidence/control-artifacts-live-e0c697152b-downloads/03-result.md) | 118 | `a68f73d53e1a` |
| 新尝试 | [output.txt](../evidence/control-artifacts-live-e0c697152b-downloads/04-output.txt) | 155 | `4e27f84ee05a` |
| 旧迟到重提 | [result.md](../evidence/control-artifacts-live-e0c697152b-downloads/05-result.md) | 128 | `5598561f5528` |
| 旧迟到重提 | [output.txt](../evidence/control-artifacts-live-e0c697152b-downloads/06-output.txt) | 175 | `da9b831ff800` |

独立读取新房间 timeline，实际 `m.file` 事件为 **6 条**。旧任务重提发布了两个新 event／mxc，是新的附件发布；本实验没有把内容变化后的再次提交当作完全相同请求重试，因此不据此评价附件接口的跨调用幂等。

## 迟到提交没有覆盖新任务

旧迟到 submit 前后，新任务的三个真实 MinIO 对象字节全部不变：

| 新任务对象 | 前后相同的 SHA-256 |
| --- | --- |
| meta.json | `c939bf4ac3900f2aafb8327bfc9373e126e1ce013b60301729e546e8e1afef00` |
| result.md | `a68f73d53e1acddf1079a3923f56ba0f59f9eb6af877d6327ae846d17458ff87` |
| output.txt | `4e27f84ee05a173e530e044404ca5725c7a05501d53bee1e67067592f90dceea` |

旧任务自己目录中的输出按本次重提更新，Project 最终两个节点均为 submitted，新节点没有被旧 task_id 的提交替换。再次下载旧首次输出的原 mxc，仍为最初的 157 字节／原 SHA-256，未变成晚到的 175 字节内容；这是该时刻旧媒体引用保留内容的证据，不能外推媒体永久保留或不可删除。

这补充了 AT-05 的正向对照：选择不同 task_id 时，本用例的元数据和产物不会发生先前相同 task_id 的跨 Project 复用问题。编码规则、同次逻辑操作重试身份、持久归属与晚到结果是否允许影响当前业务，仍须 RepoMesh 设计／实现。

## 收件人退出后的读取事实

六个附件验证结束后，仅测试 Alice 退出本次新房间。leave 返回 200；Alice 的 joined_rooms 不再含本房；Bob 读取 Alice 的实际成员状态为 `leave`，房间 history_visibility 仍为 `joined`。

随后 Alice 对她在加入期间已经看见的新任务附件执行读取：

- 原文件事件 `$NxZUvLduVFr8iA_VsHnnwaemg0xhtILhrwUb1-FrCx0` 仍返回 200。
- 原已知 mxc 的 authenticated client-media 下载仍返回 200，155 字节和 SHA-256 保持一致；[实际退出后下载文件](../evidence/control-artifacts-live-e0c697152b-downloads/08-output.txt)保留。

这是**已在加入期间可见的历史事件与已知媒体地址**的读取结果，不是“退出后创建的新消息也可见”，也不是跨房间／其他实例越权结论。不能将正常离开房间自动等同于 RepoMesh 业务读权撤销，更不能声称过去已下载或读入模型的数据被收回。若 RepoMesh 要求每次打开证据重新校验当前权限，需要自己的读取入口／适用规则，而不能仅依赖用户是否当前仍 joined。

## 验收边界

本次证明真实原生提交可以完整发布小附件，两个测试编码的 task_id 在这个晚到重提场景下隔离文件和任务元数据，并取得退出后的历史读取事实。没有模型推理、真实 Worker 执行、RepoMesh 持久身份映射、不可覆盖归档、独立验证者或业务验收；原生 submitted／check_task.effective 不能自动转换为 RepoMesh 已接受、已交付或已完成。

源码定位：`plugins/teamharness/mcp/server.py:1405-1459` 上传媒体并发送 m.file；`:1460-1556` 发布文件与错误回执；`:1629-1670` 按任务目录发布 result／deliverables；`:3770-3806` 结果字段／路径格式校验；`:4363-4409` submit 及同步；`:4443-4460` check_task 的 effective 计算。行号对应本报告固定提交。
