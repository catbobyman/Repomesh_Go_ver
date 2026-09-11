# 同名 Project 的 Team 消歧与实例隔离

日期：2026-09-09。Run：`f802e49e2a`。上游版本 `eeaab64391ccaec9118e84977f538aefd40720d6`。在已有 a/b 两套 Controller 与 MinIO 中执行真实 HTTP 和存储读回；没有模型调用、派发任务、启动运行容器、重启服务或改上游源码。

**两个实例均确认：同名 Project 不指定 Team 时读和写都返回 409；显式指定 Team 返回正确对象。错误 Team、不存在 Project 返回 404。使用正常单段上传的夹具后，四个主对象的 pause/resume 共八次写入均返回 200，每次只有目标实例、目标 Team 下的那个对象发生变化。**

## 身份与夹具边界

Controller 只扫描实际 Team CR 对应的 `teams/{team}/shared/projects/` 前缀，裸 MinIO 目录不足以进入这条路由。因此本轮在 a/b 分别登记两个同名新 Team，每个引用一个新 Worker：`state=Stopped`、`containerManaged=false`。这只是原生资源登记；Project 的初始 JSON 由验证器直接写入 MinIO，**不是 Project 业务创建流程，也不是 TeamHarness 派工**。

HTTP 使用各实例自己的 Controller 管理 token，MinIO 使用对应 Controller 已有 `mc` 权限。凭据只在进程内存中读取，未输出到证据。本结果不能证明 Worker、TeamLeader 或人类角色的权限边界。实例选择由 API endpoint 和存储 bucket 决定，没有凭空假设 API 接受 `instance` 查询参数。

| 维度 | 本轮实际资源 |
|---|---|
| API endpoint | a：`127.0.0.1:28090`；b：`127.0.0.1:38090` |
| 两边相同的 Team 名 | `coverage-scope-f802e49e2a-left`、`coverage-scope-f802e49e2a-right` |
| 两边相同的停止引用 | `coverage-scope-leader-f802e49e2a-0`、`coverage-scope-leader-f802e49e2a-1` |
| 四个主对象的相同 Project ID | `scope-project-f802e49e2a` |
| 只在每个实例 left Team 存在的对照 ID | `scope-project-f802e49e2a-left-only` |
| MinIO key 模板 | `agentteams/rv-{a或b}-storage/teams/{team}/shared/projects/{project_id}/meta.json` |

共 4 个新 Team CR、4 个停止的 Worker CR、6 个新 Project 元数据对象。每份 JSON 的 title 同时编码实例、Team 与 Project ID，读回时比较这些字段，避免只凭 200 判断“读对了”。`tasks=[]`、`source_room_id` 为空，pause/resume 没有消息接收目标。

## 实际读与拒绝写入

以下表中每项在 a/b 各执行一次；两个显式 Team 的正向读分别执行。

| 请求 | 结果 |
|---|---|
| `GET /api/v1/projects/{主ID}/workflow` | **409**，提示 ID 跨 Team 歧义，应指定 `?team=` |
| 上述 GET 显式 left / right Team | 各 **200**；project_id、team_id、title、status 均与对应远端对象匹配 |
| 主 ID 加本轮不存在的 Team | GET **404**，POST pause **404** |
| left-only ID 加实际存在的 right Team | GET **404**，POST pause **404** |
| 本轮不存在 Project ID 加实际 left Team | GET **404**，POST pause **404** |
| 不存在 Project ID、不加 Team | GET **404** |
| 主 ID 的 POST pause、不加 Team | **409**，没有静默选择首个 Team |

在完成上述所有读请求和拒绝写入后，独立 `mc cat` 六个对象并计算 SHA-256，六个哈希全部与初始基线相同。a/b 使用相同 Team 和主 Project ID，但显式读取的 title 中实例标记分别为 a/b，未读到另一实例内容。

## 首次写入失败与限定继续

首轮夹具上传用了 `mc pipe`，第一次显式 left Team 的 pause 返回 **409 `conflict: project was modified concurrently`**，脚本因原预期 200 而退出 1。首轮 36 项检查中 35 项成立、1 项失败；原始 JSON 的错误与 HTTP 响应完整保留，未改写为通过。

这是已记录的 [LIVE-C06 multipart ETag 限制](controller-live-report.md)：pipe 上传产生 multipart ETag，而 handler 以内容 MD5 构造条件写。继续实验使用同一批自有对象，把**完全相同字节**保存为临时文件后通过 `mc cp` 单段上传。继续前六个 SHA-256 与原始基线一致；换上传方式后六个内容哈希仍全部相同。没有绕过条件写、伪造 HTTP 结果或改变上游实现。

随后对 `(a,left)`、`(a,right)`、`(b,left)`、`(b,right)` 的主对象各执行一次显式 `pause?team=` 与 `resume?team=`：

- 八次 HTTP 均 **200**，返回对应 Team 和原有 title，status 依次 paused / active。
- 每次写后重新 `mc cat` 全部六个对象；**每次恰好一个目标哈希改变**，另五个对象哈希不变，包括另一实例的同名对象。
- 每次目标远端 status 与该操作一致；最终六对象均 active。四个主对象保留真实 API 审计字段，所以不声称最终内容哈希等于初始值。

继续脚本的 27 项检查全部成立、退出 0。它补齐单段上传对象的定向写入对照，不能抵消首轮上传方式兼容限制。

## 原始证据与最终状态

[首轮请求、基线、拒绝写和失败](../evidence/project-team-disambiguation-f802e49e2a.json)；[同字节继续、八次写入、逐次六对象哈希与最终状态](../evidence/project-team-disambiguation-f802e49e2a-writes.json)。

[主脚本](../scripts/project-team-disambiguation-live.py)已将后续复现的夹具上传修正为文件加 `mc cp`；[本轮继续脚本](../scripts/project-team-disambiguation-continue.py)读取首轮证据，拒绝覆盖已存在的继续证据，不创建第二批资源。首轮实际 `mc pipe` 失败与后续脚本修正需结合以上两份 JSON 解读。

最后只读核对四个 Worker 引用均仍为 **Stopped / containerManaged=false**；Docker 全量名称列表没有本轮 nonce 的运行或停止容器。新资源和六份有限元数据保留供复核，没有删除既有 Team，也没有探针后台进程残留。

该结果补齐 AT-05 本次样本的 `(instance, team, project_id)` 读取及低影响写入消歧；未测试 scoped caller 授权、Team CR 名与 effective teamName 不一致、所有 Project 子路由、恶意元数据 team_id 或并发写竞态，不能将其扩展为完整业务身份映射或权限验收。
