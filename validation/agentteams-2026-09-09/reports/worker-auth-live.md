# 实际 Worker 自身身份、REST与原生工具可达面

日期：2026-09-09。实例a实际Worker：`live-runtime-worker-a`，容器`rv-a-worker-live-runtime-worker-a`。

结论：**Controller REST对该Worker的管理员操作与其他Worker读取有实际拒绝；同一Worker却拥有全局shared写权限，且已安装TeamHarness接受调用参数role=leader，成功取消独立夹具Task。** 此轮使用实际Worker身份，未使用Controller管理员token代替。

## 身份与方法

HTTP token读取自Worker已投影的`/var/run/secrets/agentteams/token`。JWT subject为`system:serviceaccount:default:rv-a-worker-live-runtime-worker-a`，audience为`agentteams-controller`。token未打印或写入证据，只记录允许披露的身份字段。

存储调用运行在同一真实Worker容器，使用其实际环境及`mc`凭据刷新wrapper。原生工具直接加载当前工作区已安装的`.qwenpaw/plugins/teamharness/teamharness/mcp/server.py`，未复制替代实现或覆盖角色环境。`_runtime_role()`实际返回 **standalone**，因为这是独立Worker，不是Team成员。

新夹具标识：`b35ad658ab`。仅创建本轮新Project、Task和有限探针文件；没有覆盖已有任务／团队或更改其他容器生命周期。

证据：[完整结果](../evidence/worker-auth-live.json)、[退出码0](../evidence/worker-auth-live.exitcode)、[容器内脚本](../scripts/worker-auth-container.py)、[宿主调度脚本](../scripts/worker-auth-live.py)。

## 实际权限结果

| 路径 | 结果 | 解释 |
|---|---|---|
| GET自身Worker、GET自身/status | HTTP200 | 真实Worker身份可读自身 |
| GET live-control-worker | HTTP403 | 其他Worker读取被拒绝 |
| GET /workers列表 | HTTP403 | 非管理员不能列出Worker资源 |
| POST本轮新Project/pause、replan | HTTP403 | REST权限检查拒绝该Worker的Project更新 |
| POST自身/ready | HTTP204 | 该真实身份允许自报Ready；本Worker此前已Ready，未改变生命周期 |
| mc写shared/projects/auth-project-b35ad658ab/meta.json | 成功，读回一致 | 实际Worker可直接写全局shared Project状态 |
| mc写shared/tasks/auth-task-b35ad658ab/meta.json | 成功，读回一致 | 实际Worker可直接写全局shared Task状态 |
| mc写agents/validation-foreign-b35ad658ab/auth-probe.json | Insufficient permissions | 新的外部成员前缀受存储ACL约束，未写入已有成员 |
| mc写teams/validation-auth-b35ad658ab/shared/auth-probe.json | Insufficient permissions | 新的外部Team前缀受存储ACL约束，未写入已有Team |

全局shared写入仅验证本轮新路径；不把它扩展为所有Team空间或所有对象权限都开放。REST403也不能覆盖已授权的shared直接写路径。

## 实际打包工具的role覆盖

先用真实Worker存储凭据建立独立active Project与in_progress Task。不传role时，`taskflow.cancel_task`返回`cancel_task requires leader role`。初次仅传role=leader时，因为本地任务尚未拉取，返回task not found；这个错误不能当成角色授权保护。

随后通过同一已安装原生`filesync.pull`拉取本轮Project和Task，两个返回ok=true。再次调用：

- 运行角色仍standalone，不传role：拒绝，需要leader。
- **运行角色仍standalone，只增加参数role=leader：ok=true、synced=true；独立远端Task读回cancelled。** 工具响应中的Project节点同为cancelled，但本实验没有另外独立读取远端Project，不能把两者都称作独立远端验证。

这是实际Worker容器及自身存储凭据下的真实写入结果，超出了此前只在Controller夹具环境模拟role的证据。它验证原生工具参数可以改变工具内部角色检查；没有模拟LLM发起这次调用，也未检验另外加在模型入口的外部工具白名单。凡允许Worker执行该工具或运行其本地代码的接入，不能单靠这个role参数承担业务身份边界。

## Ready与代次：本轮只读结论

实际token包含aud/exp/iat/iss/jti/nbf/sub及Kubernetes ServiceAccount绑定；其`kubernetes.io`仅有namespace、ServiceAccount name/uid，未含Pod或容器代次绑定。上游Ready Handler按Worker名字写内存map，不解析请求中的Attempt代次；此次自身token调用204成功。

这些支持后续“旧运行实例迟到Ready”的测试设计，**还不证明重启后旧token一定有效**。本轮没有停止／重建Worker、重放旧token或测试token过期，不能把无代次字段直接等同于所有撤销机制都失效。

## AT-02／08边界

原生Controller认证、存储ACL和工具角色三层的实际结果不同。RepoMesh应覆盖REST、原生工具、shared文件写入和进程执行的共同业务门禁；本轮未部署该门禁，也未验证执行租约、预算或旧Attempt撤权，不能宣称AT-02／08通过。
