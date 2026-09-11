# 独立实例 Manager 启用脚本预检

2026-09-09。脚本为 [enable-managers.py](../scripts/enable-managers.py)。本次只读核对现有 Docker 状态并运行离线保护条件测试，**尚未运行该脚本的 plan 或 apply，没有停止、移除、创建或启动任何容器**。

## 当前核实结果

- `rv-a-controller` 与 `rv-b-controller` 都挂载本轮独立 workspace 与 host-share；真实 Linux daemon Source 分别是 `/run/desktop/mnt/host/d/Project4work/Repomesh_Go_ver/validation/agentteams-2026-09-09/runtime/instance-a/…` 和 `instance-b/…`。与各自 `private/rv-?-hostpaths.json` 完全匹配。未采用 HOME、旧 Manager 目录或未确认的 Windows 路径回退。
- 各实例现有挂载为自己的 `rv-?-data`、`rv-?-agentfs`、workspace、host-share 和 Docker socket，共五项；独立网络、Matrix domain alias 与 localhost 端口保持不变。
- 通过各自容器内真实 `agt get managers -o json` 读取，当前两实例 Manager 列表均为空。这里仅记录检查时刻状态；脚本会在计划生成和停机前重新检查。
- 新脚本 AST 语法通过，七项离线检查通过：原始布局、错误实例标签、过期镜像、错误数据卷、HOME 路径回退、额外 env/端口、计划后容器 ID 改变。最后一项确认不会调用 stop/rm。测试入口为 [control-enable-managers-safety.py](../scripts/control-enable-managers-safety.py)，不调用真实 Docker，不写凭据。

## 主任务先审查 a，再执行

从验证根目录运行：

```powershell
python scripts/enable-managers.py --instances a
```

默认模式只读取状态，写 `evidence/manager-enable-plan-a.json`，并输出脱敏计划与 `review_sha256`。它不会输出 API key、provider endpoint、密码或令牌。计划明确列出 env 改动键、公开配置、image ID、原 container ID、保留卷/网络/端口/挂载。Manager/Worker 本地镜像尚未完成时仍可查看计划，但 `apply_ready=false`；镜像就绪后须重新生成计划。

主任务检查计划后，使用该次指纹：

```powershell
python scripts/enable-managers.py --instances a --apply --review-sha256 <本次计划指纹>
```

仅 a 的验证完成后，对 b 执行相同两步，将 `--instances a` 改为 `--instances b`。脚本没有默认实例；也支持显式 `--instances a,b`，但本轮按 a 后 b 进行。

## 重建边界

脚本读取已有 secret、env、hostpaths、provider 四字段，不生成任何新秘密。只允许从原始 `Manager=false / 无 provider` 配置进入启用状态。所有网络、卷、容器必须已存在且带本轮与实例标签；当前 Controller 必须使用本地最新 embedded 镜像 ID。现有 effective env、五项挂载、执行参数、网络 alias、重启策略、四个 localhost 端口都必须符合原部署。额外或不同配置触发拒绝，避免重建时悄悄丢弃。

预期 env 变化只有 provider 四字段、`MANAGER_ENABLED=true`、明确的 `MANAGER_MODEL`、已观测的 `WORKSPACE_DIR/HOST_SHARE_DIR`。当前 Manager/Worker tag、默认 runtime、Matrix/MinIO 凭据及其余配置全部保留。显式 `MANAGER_MODEL` 与 provider `DEFAULT_MODEL` 相同，避免旧默认模型介入。

执行前再次核对原容器 ID、标签、image ID、env、挂载、端口/网络、三个本地镜像 tag 的 ID，以及 Manager CR 仍为空。之后仅 `stop --time 30 <原 Controller ID>`、`rm <原 Controller ID>`；不使用 `--force` 或 `--volumes`。按观测挂载源、相同数据卷/网络/alias/localhost 端口重建固定 image ID 的 Controller，创建后校验实际 env 与挂载，再启动。脚本不会向同实例其他容器发出 stop/rm，也不会向其他实例发出动作；Controller 启用后由上游自行 reconcile 创建默认 Manager。

## 证据、失败与后续验证

完整的前后 inspect 和含凭据 env 仅保存在原先已收窄权限的 `private/rv-?-enable-<指纹前缀>*`。公开的 `evidence/rv-?-enable-<指纹前缀>.json` 记录每个执行阶段、前后 ID、挂载与脱敏配置。原始 env 私有备份保留；启用后的 env 更新到原 `rv-?-controller.env`，hostpaths 的状态更新但路径值不变。初次部署 inventory 是历史证据，不覆盖成运行验收结果。

失败时记录已完成阶段并停止，不擅自删除已创建的新容器或自动回滚。卷/工作目录/secret 保持；主任务应先 inspect 本实例 Controller，再决定恢复方式。不能把启动成功当作 Manager Ready、挂载可读、模型响应或 RepoMesh 验收。

启动启用的 Controller 可能触发 Manager 引导和 provider 活动；此脚本不发送任务。后续应检查默认 Manager CR 的 image/runtime/model、Manager 实际容器 image ID、自己的 network、两个 child bind Source、自己的 Matrix 身份、Gateway provider 路由，以及真实模型回执。只有这些后续实验才能证明运行链路。

源码依据：`upstream/agentteams-controller/internal/config/config.go:349-366` 读取 Manager 开关/模型/hostpath；`internal/initializer/initializer.go:457-513` 在开关启用后创建 default Manager，已有 default 则直接跳过；`internal/controller/manager_reconcile_container.go:221-260` 将 hostpath 原样用于 Manager `/root/manager-workspace` 与 `/host-share`，并仅监听 localhost Manager console。Controller 资源或容器健康不等于这些步骤完成。
