# 新版第二在线实例 d 的部署与前提

2026-09-10 03:49—03:50 UTC。为完成此前未复跑的新版双在线读取矩阵，新建 d，保留已恢复的 c 和旧 a/b 证据。版本仍固定 `517caff9280242a00a4d4c06365352b9e41659c6`，没有使用浮动镜像或重新构建产品代码。

## 部署范围

[独立d脚本](../scripts/deploy-instance-d.py)从本轮已执行的 c 部署脚本复制，仅调整允许的实例名、独立49000端口段与证据文件名；原 c 脚本不变。两者都要求精确验证标签，禁止复用他人卷／网络，不执行删除或pull；d的Manager关闭，未注入Provider。

[执行前计划](../evidence/deployment-d-dry-run.json)确认`rv-d-controller`、`rv-d-net`、`rv-d-data`、`rv-d-agentfs`均不存在，四个端口可用。随后实际执行：

```powershell
python -X utf8 validation/agentteams-2026-09-10/scripts/deploy-instance-d.py --apply --instances d --wait-seconds 60
```

exec session62455最终退出0。新卷、网络、工作目录和私密材料只位于本批次的d命名空间；私密目录ACL限制为当前用户、SYSTEM和Administrators，材料不进入报告。API49090、Gateway49080、Console49001、Element49088均仅绑定127.0.0.1；Manager Console49099只是预留。

实际d容器ID为`d611f0702253daae9c14470773fd448166cd5cdb94ca4130818b0bc49bf394f6`，StartedAt=`2026-09-10T03:49:12.3564951Z`；镜像ID为`sha256:6c5f7158d972810fc0e6676fa40d509f163a23f11bc73dfd881b0705deeeb42f`，与c相同。[完整安全部署清单](../evidence/deployment-d-instance-inventory.json)。没有启动d的Manager、Worker或模型任务。

## 实际就绪证据

初始Matrix versions、MinIO live、Controller healthz均200；紧随初始化的agt workers/managers各exit1，错误原因未由那次摘要确定，保留原记录。03:50:01再次调用时两条均exit0，d的workers/managers为0；c为既有2个停止Worker引用、1个运行Manager。未据初始healthz200直接认定认证就绪。

随后两实例均使用各自真实Kube admin-token、各自CA并保持TLS验证开启，读取Teams实际200。初版不带token的Kube health探针exit1；补测确认两者匿名health均401，这是认证拒绝，并非证书尚未生效。见[首次前提快照](../evidence/twin-read-preflight.json)、[认证与TLS补证](../evidence/twin-read-preflight-authenticated.json)。

c的容器ID、StartedAt、RestartCount=0始终一致，没有新的容器重启或OOM；其StartedAt来自[时钟回退](clock-discontinuity.md)前，Docker人类可读的“Up不足一秒”不能作为重启证据。d按修正后时间新签证书，未进行人工续签。

此报告只证明两个实际Controller可在线认证访问及部署范围；跨实例、跨Team和元数据读取结论由后续双在线矩阵证明，不由同镜像或healthz外推。保留c Manager既有配置，新测试仅使用独立元数据夹具。
