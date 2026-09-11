# Controller / MinIO 真实服务实验

日期：2026-09-09。镜像从 GitHub main `eeaab64391ccaec9118e84977f538aefd40720d6` 构建。两个独立 embedded 实例，Manager禁用。本报告没有使用假HTTP、假存储或mock Handler。

脚本：[controller-live-validation.py](../scripts/controller-live-validation.py)。最终证据：[controller-live-results.json](../evidence/controller-live-results.json)，23条请求／观察记录，脚本退出0。

| 实验 | 实际结果 | 判定和边界 |
|---|---|---|
| LIVE-C01 | a/b本地API自有管理令牌200；不带令牌或使用另一实例令牌均401 | 此两实例Controller管理令牌隔离通过；不证明Worker角色和全部入口受控 |
| LIVE-C02 | 首次创建Worker201；重复创建409后读回成功。真实CR保留model、runtime、resources、Stopped和containerManaged=false，但remoteSkills为空 | 原生创建忽略remoteSkills已在持久CR复现；未启动此Worker，故不证明资源限额落实 |
| LIVE-C03 | 普通文件上传后，pause/replan/resume/replan依次200/409/200/200，新计划通过MinIO读回 | 原生状态衔接限制确认；没有引入RepoMesh适配 |
| LIVE-C04 | 读取active旧文件，REST pause200并读回paused，随后真实mc cp旧文件，最终状态变回active | 普通覆盖写确实能覆盖更新后的暂停；此实验使用管理员存储写入，不冒充已测试Worker凭据路径 |
| LIVE-C05 | a中创建的Project，a可读；b使用自有有效令牌读同名Project为404 | 独立实例存储和列表范围的此场景通过 |
| LIVE-C06 | mc pipe同一小JSON生成`-1`结尾multipart ETag，无并发时REST pause返回409；同字节改为文件+mc cp后可正常更新 | 额外上传方式兼容限制。上游普通PutObject使用文件+mc cp，不能把此结果描述为所有原生pause必失败 |

## 初次失败与修正

- [attempt-01](../evidence/controller-live-attempt-01.json)：公共API鉴权／创建成功；读取底层CR时未提供embedded Kubernetes token，curl返回22。补充容器内读取本实例管理token，通过stdin传给curl，未输出凭据。
- [attempt-02](../evidence/controller-live-attempt-02.json)：最初fixture用mc pipe，REST更新均冲突。真实mc stat显示multipart ETag；检查`contentETag`按内容MD5构造条件，改用与上游相同的文件上传方式作对照。原现象作为LIVE-C06保留，没有更改上游生产代码或掩盖失败。

底层CR读回是有本机管理权限的诊断路径；完整业务请求经过真实Controller认证中间件。固定数据均为本轮`live-control-*`测试对象。

## 故障恢复

[重启脚本](../scripts/infrastructure-restart-validation.py)顺序重启a/b，检查实际容器StartedAt变化、旧API管理token、持久Worker列表和Project。[恢复证据](../evidence/infrastructure-restart-results.json)：

- a恢复API耗时12.813秒，b为13.328秒；包含停止／启动和首次认证请求恢复。
- 重启a期间b健康采样全部200，重启b期间a同样全部200，未重启的一方StartedAt不变。
- Project记录持久保留。
- [真实Matrix恢复](matrix-live-report.md)另确认两实例55条消息、旧token、tx_id幂等及旧sync游标。

这些恢复测量不包括Manager／Worker启动或模型处理时延，不能直接作为AT-12完整容量结论。
