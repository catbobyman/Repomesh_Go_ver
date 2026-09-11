# 独立 AgentTeams instance-a / instance-b 部署预检

2026-09-09；基线为本轮新克隆的 `upstream`，HEAD `eeaab64391ccaec9118e84977f538aefd40720d6`。本任务只读研究并写此报告；**未运行本文 Docker 命令、没有修改上游源码、没有启动或停止服务**。命令供主执行任务采用并记录实际结果。

## 本轮实际执行入口（后续已编制，尚未运行）

主执行任务随后指定使用 [deploy-instances.py](../scripts/deploy-instances.py)，镜像分别为 `repomesh-validation/embedded:eeaab643`、`repomesh-validation/manager-qwenpaw:eeaab643`、`repomesh-validation/qwenpaw-worker:eeaab643`。实例命名统一 **rv-a / rv-b**；宿主仅发布 a 的 28080/28001/28090/28088、b 的 38080/38001/38090/38088，均监听127.0.0.1。Matrix 6167 和 S3 9000 在容器网络内访问，不额外发布宿主端口。

```powershell
python scripts/deploy-instances.py
python scripts/deploy-instances.py --apply
```

第一条只显示计划；第二条创建/启动明确归属的双实例。默认不读取provider、Manager=false；若明确加入 `--with-provider`，只从现有private/provider.json注入四字段且仍不启Manager。脚本不删除、不拉镜像、不改其他项目资源；已有同名资源必须具备匹配验证标签。secret、env和观测到的daemon bind路径写入private；安全运行清单写evidence。这里只做过AST语法检查，脚本等待主任务审查执行。

**下文保留预检时的手工配方用于解释环境变量和构建依赖；本轮运行的命名、端口与镜像以以上Python脚本为准，不另执行下文的第二套手工实例示例。**

## 1. 结论

不要直接把 `install/agentteams-install.ps1` 连续运行两次作为双实例安装。其网络、Controller 容器名和内部 Controller URL 在 2800—2807、3150—3192 行固定为 `agentteams-net` / `agentteams-controller`，并有针对这些固定名字的升级、清理逻辑。应按同一安装配方直接建立两个独立 embedded 实例，再由各自 Controller 创建 Manager/Workers。

`AGENTTEAMS_RESOURCE_PREFIX` 能区分 Docker Manager/Worker/SA 名，但 **不能改变 Manager 的 Matrix 短名 `manager` 与 Gateway consumer 短名 `manager`**（`internal/service/provisioner.go:1345`）。因此两个实例必须各有独立 Matrix、Gateway、MinIO、CR 数据、网络和凭据；不同 Matrix domain 使完整用户 ID 不同。无需为了短名一致修改上游源码。

先设置 `AGENTTEAMS_MANAGER_ENABLED=false`、不提供 LLM API key，即可检查基础设施、Controller API、鉴权及资源持久化。启用 Manager 和真实 provider 属于下一阶段，不能把基础 health / 2xx 当模型验证。

## 2. 最新源码构建链路

建议首选官方 Dockerfile，固定自定义本地 tag，并记录最终 image ID/digest 与包清单。最新 AgentTeams 快照的官方 QwenPaw Dockerfile 仍默认 `qwenpaw==2.0.1`，不是宣称“最新 PyPI QwenPaw”；不要无依据把依赖升级为另一个未测版本。QwenPaw integration source、TeamHarness 和 Matrix channel 从当前 checkout 构建。

### 2.1 Controller

`agentteams-controller/Dockerfile` 的 build context 是 `agentteams-controller/`，需要 `agent/` 目录；Makefile:150—156 会从 `manager/agent` 临时复制进去。为保持当前 checkout 干净，可以另建构建上下文：

```powershell
$valRoot = 'D:/Project4work/Repomesh_Go_ver/validation/agentteams-2026-09-09'
$valSource = Join-Path $valRoot 'upstream'
$valTag = 'eeaab643-20260909'
$valBuildRoot = Join-Path $valRoot ('build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $valBuildRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $valSource 'agentteams-controller') -Destination (Join-Path $valBuildRoot 'controller') -Recurse
Copy-Item -LiteralPath (Join-Path $valSource 'manager/agent') -Destination (Join-Path $valBuildRoot 'controller/agent') -Recurse
docker build --progress plain -t "agentteams/validation-controller:$valTag" (Join-Path $valBuildRoot 'controller')
if ($LASTEXITCODE -ne 0) { throw 'Controller source build failed' }
```

官方 Dockerfile 使用 Go 1.25，Controller `CGO_ENABLED=1` 静态链接；还构建 `agt`，下载 kube-apiserver v1.31.3 并带入 CRD。不要只把旧镜像 tag 改成新 tag。若采用宿主编译二进制，需核实 Linux 架构、CGO/SQLite 链接和版本，不以 Windows exe 覆盖 Linux binary。

### 2.2 Embedded 与 Manager

在源码根目录运行，确保两个 COPY-from 都引用刚构建的 Controller 镜像：

```powershell
Push-Location $valSource
docker build --progress plain --build-arg "AGENTTEAMS_CONTROLLER_IMAGE=agentteams/validation-controller:$valTag" -f agentteams-controller/Dockerfile.embedded -t "agentteams/validation-embedded:$valTag" .
if ($LASTEXITCODE -ne 0) { throw 'Embedded source build failed' }
docker build --progress plain --build-arg "AGENTTEAMS_CONTROLLER_IMAGE=agentteams/validation-controller:$valTag" --build-arg "BUILTIN_VERSION=$valTag" --build-arg 'QWENPAW_PIP_SPEC=qwenpaw==2.0.1' -f manager/Dockerfile.qwenpaw -t "agentteams/validation-manager-qwenpaw:$valTag" .
if ($LASTEXITCODE -ne 0) { throw 'Manager source build failed' }
Pop-Location
```

`Dockerfile.embedded` 包含基础设施和 Controller，**不包含 Manager Agent**。它以 Higress all-in-one:2.2.1 为底，复制 Tuwunel/MinIO/mc/Element 的 20260216 镜像内容；再复制新 Controller/agt/kube-apiserver/CRD、最新 supervisord、基础设施脚本和 Agent 模板。Manager QwenPaw 是独立 Python 镜像，内置当前 Matrix channel 与 manager-tools 插件；Worker 的 TeamHarness 打包路径见下节，不应假定 Manager 与 Worker 自动拥有同一工具面。

### 2.3 QwenPaw Worker 与 TeamHarness zip

Worker Dockerfile 依赖两个打包产物，必须先由当前源码生成。官方 Makefile:209—216 同时传入名为 `shared` 的 build context。

```powershell
Push-Location $valSource
$env:OUT_DIR = 'dist/adapters/qwenpaw'
ruby plugins/teamharness/adapters/qwenpaw/scripts/build-qwenpaw-plugin.rb plugins/teamharness/plugin.yaml
if ($LASTEXITCODE -ne 0) { throw 'TeamHarness package build failed' }
ruby plugins/workerflow/adapters/qwenpaw/scripts/build-qwenpaw-plugin.rb plugins/workerflow/plugin.yaml
if ($LASTEXITCODE -ne 0) { throw 'WorkerFlow package build failed' }
docker build --progress plain --build-context shared=./shared/lib --build-arg 'QWENPAW_PIP_SPEC=qwenpaw==2.0.1' -f qwenpaw/Dockerfile -t "agentteams/validation-qwenpaw-worker:$valTag" .
if ($LASTEXITCODE -ne 0) { throw 'Worker source build failed' }
Remove-Item Env:OUT_DIR
Pop-Location
```

打包脚本需要 Ruby，zip 不存在时回退 `python3`。这些命令只会生成 dist 构建产物；若主任务要求 checkout 完全无新增产物，可把源码复制到隔离 build context 再打包。Worker 镜像默认不包含 `agt`，读取其 package/version 需用现有 Python/QwenPaw 工具。

### 2.4 旧 v1.2.0 缓存镜像的使用边界

缓存旧 embedded 可用作**基础设施依赖底层的 overlay**，但完整 overlay 至少要替换最新 Controller、agt、CRD、supervisord、4 个基础设施启动脚本、`manager/scripts/lib`、`shared/lib` 和 embedded 所复制的 Agent 模板，并核对 kube-apiserver及基础依赖版本。镜像构建记录必须称“当前源码 overlay + 旧基础依赖”，不能称完全等同官方新镜像。

旧 CoPaw 镜像不能直接充当当前 QwenPaw runtime。仅替换 TeamHarness `.py` 文件也不能覆盖 QwenPaw bridge、Matrix channel、entrypoint、包版本与 zip 安装过程。若全量构建卡在依赖下载，旧镜像可用于明确标记的基础设施/Controller阶段；涉及 runtime/模型的 AT 项保持未验证，直到当前源码 runtime 镜像构建并核验完成。

## 3. 双实例实际配置

以下名称和端口是可执行配方的建议，启动前仍需主任务检查未占用：

| 对象 | instance-a | instance-b |
|---|---|---|
| Controller 容器 | rmv-a-controller | rmv-b-controller |
| 网络 | rmv-a-net | rmv-b-net |
| 资源前缀 | rmv-a- | rmv-b- |
| 数据卷 `/data` | rmv-a-data | rmv-b-data |
| 本地镜像缓存 `/root/agentteams-fs` | rmv-a-agentfs | rmv-b-agentfs |
| Manager 容器（自动） | rmv-a-manager | rmv-b-manager |
| Manager workspace | instances/a/workspace | instances/b/workspace |
| Host share | instances/a/host-share | instances/b/host-share |
| Matrix domain | rmv-a.matrix.invalid | rmv-b.matrix.invalid |
| Gateway / API | 28180 / 28190 | 28280 / 28290 |
| Matrix / MinIO S3 | 28167 / 28100 | 28267 / 28200 |
| Higress / MinIO console | 28111 / 28101 | 28211 / 28201 |
| Element / Manager console | 28188 / 28199 | 28288 / 28299 |

所有宿主发布端口绑定 `127.0.0.1`。相同内部端口可以复用，因为容器及网络分开。Docker daemon/socket 仍是共享高权限面；命名和 bridge 网络不等于已经证明租户隔离。正式 AT-02/09 要验证受控入口和不能越界的实际权限。

### 3.1 环境变量含义

| 环境变量 | 要点及依据 |
|---|---|
| `AGENTTEAMS_KUBE_MODE=embedded` | 各 Controller 启动独立持久 Kube API 数据；config.go:251。 |
| `AGENTTEAMS_DATA_DIR=/data/agentteams-controller` | Controller 数据目录；底层 `/data` 卷不可共享。 |
| `AGENTTEAMS_CONTROLLER_NAME=rmv-a` | 实例标签，HTTP创建和initializer会标记；不替代网络/存储独立。 |
| `AGENTTEAMS_RESOURCE_PREFIX=rmv-a-` | `auth/prefix.go:56,97` 决定默认 Manager 名和各资源前缀。 |
| `AGENTTEAMS_RESOURCE_AUTOPREFIX=true` | config.go:268—277 默认开启；显式设置避免环境继承歧义。 |
| `AGENTTEAMS_PROXY_CONTAINER_PREFIX=rmv-a-worker-` | Worker Docker 容器名前缀。 |
| `AGENTTEAMS_DOCKER_NETWORK=rmv-a-net` | DockerBackend.Create 在请求没指定网络时使用此网络。 |
| `AGENTTEAMS_CONTROLLER_URL=http://rmv-a-controller:8090` | 子容器可达的实例内地址，不能设宿主 localhost。 |
| `AGENTTEAMS_MATRIX_URL=http://127.0.0.1:6167` | Controller内直连 Tuwunel；config.go:438—443 为子容器自动替换成 Controller hostname并保留端口。 |
| `AGENTTEAMS_FS_ENDPOINT=http://127.0.0.1:9000` | Controller内 S3；同样给子容器改 hostname。不能用 Higress 8080。 |
| `AGENTTEAMS_AI_GATEWAY_URL=http://127.0.0.1:8080` | 子容器也经上述改写访问所属 Controller gateway。 |
| `AGENTTEAMS_AI_GATEWAY_ADMIN_URL=http://127.0.0.1:8001` | Controller初始化 Higress console。 |
| `AGENTTEAMS_FS_BUCKET=rmv-a-storage` / `AGENTTEAMS_STORAGE_PREFIX=agentteams/rmv-a-storage` | `agentteams/` 是 mc alias，后面是本实例bucket；两个实例端点和bucket均分开。 |
| `AGENTTEAMS_ADMIN_USER/PASSWORD`、`MINIO_USER/PASSWORD`、`REGISTRATION_TOKEN` | 每实例生成独立值，记录证据时不得输出密码/token。 |
| `AGENTTEAMS_MATRIX_APPSERVICE_ENABLED=true` | 当前默认开启；必须显式提供两枚独立 AS/HS token，否则config.go:456—471 panic。也可第一阶段显式false，但不能把legacy模式结果等同AS模式。 |
| `AGENTTEAMS_MANAGER_ENABLED=false` | 同时跳过initializer默认Manager CR创建与ManagerReconciler注册；不是仅暂时休眠Manager。 |
| `AGENTTEAMS_MANAGER_RUNTIME=qwenpaw` / `MANAGER_IMAGE` | Manager实际运行时与当前构建镜像。 |
| `AGENTTEAMS_DEFAULT_WORKER_RUNTIME=qwenpaw` / `QWENPAW_WORKER_IMAGE` | Worker默认运行时及镜像。当前不选其他runtime时无需先拉全部镜像。 |
| `AGENTTEAMS_WORKSPACE_DIR` / `AGENTTEAMS_HOST_SHARE_DIR` | **Docker daemon 可解析的 host source path**，不是 Controller内路径；见下一节。 |
| `AGENTTEAMS_PORT_MANAGER_CONSOLE=28199` | 最新applyEmbeddedConfig映射到子容器18799；旧注释里的18888不是当前target，见manager_reconcile_container.go:245—256。 |

### 3.2 第一阶段启动示例（没有模型凭据）

以下 PowerShell 从验证根目录执行；secret仅写本地env文件，不输出到终端。环境文件需要沿用当前验证环境的凭据文件权限与忽略规则。

```powershell
$valRoot = 'D:/Project4work/Repomesh_Go_ver/validation/agentteams-2026-09-09'
$valTag = 'eeaab643-20260909'
foreach ($valInstance in @(@{ Id='a'; Base=28100 }, @{ Id='b'; Base=28200 })) {
    $valId = $valInstance.Id
    $valBase = $valInstance.Base
    $valName = "rmv-$valId"
    $valDir = Join-Path $valRoot "instances/$valId"
    $valWorkspace = Join-Path $valDir 'workspace'
    $valShare = Join-Path $valDir 'host-share'
    New-Item -ItemType Directory -Path $valWorkspace,$valShare -Force | Out-Null
    $valSecret = { [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N') }
    $valEnv = @(
      'AGENTTEAMS_KUBE_MODE=embedded', 'AGENTTEAMS_DATA_DIR=/data/agentteams-controller',
      "AGENTTEAMS_CONTROLLER_NAME=$valName", "AGENTTEAMS_RESOURCE_PREFIX=$valName-",
      'AGENTTEAMS_RESOURCE_AUTOPREFIX=true', "AGENTTEAMS_PROXY_CONTAINER_PREFIX=$valName-worker-",
      "AGENTTEAMS_DOCKER_NETWORK=$valName-net", "AGENTTEAMS_CONTROLLER_URL=http://${valName}-controller:8090",
      'AGENTTEAMS_PROXY_SOCKET=/var/run/docker.sock', 'AGENTTEAMS_HTTP_ADDR=:8090',
      'AGENTTEAMS_MATRIX_URL=http://127.0.0.1:6167', "AGENTTEAMS_MATRIX_DOMAIN=$valName.matrix.invalid",
      'AGENTTEAMS_FS_ENDPOINT=http://127.0.0.1:9000', "AGENTTEAMS_FS_BUCKET=$valName-storage",
      "AGENTTEAMS_STORAGE_PREFIX=agentteams/$valName-storage", "AGENTTEAMS_MINIO_BUCKET=$valName-storage",
      'AGENTTEAMS_AI_GATEWAY_URL=http://127.0.0.1:8080', 'AGENTTEAMS_AI_GATEWAY_ADMIN_URL=http://127.0.0.1:8001',
      "AGENTTEAMS_ADMIN_USER=$valName-admin", "AGENTTEAMS_ADMIN_PASSWORD=$(& $valSecret)",
      "AGENTTEAMS_MINIO_USER=$valName-minio", "AGENTTEAMS_MINIO_PASSWORD=$(& $valSecret)",
      "AGENTTEAMS_REGISTRATION_TOKEN=$(& $valSecret)", "AGENTTEAMS_MANAGER_PASSWORD=$(& $valSecret)",
      "AGENTTEAMS_MANAGER_GATEWAY_KEY=$(& $valSecret)",
      'AGENTTEAMS_MATRIX_APPSERVICE_ENABLED=true', "AGENTTEAMS_MATRIX_APPSERVICE_ID=$valName-controller",
      "AGENTTEAMS_MATRIX_APPSERVICE_SENDER_LOCALPART=$valName-controller",
      "AGENTTEAMS_MATRIX_APPSERVICE_AS_TOKEN=$(& $valSecret)", "AGENTTEAMS_MATRIX_APPSERVICE_HS_TOKEN=$(& $valSecret)",
      'AGENTTEAMS_MANAGER_ENABLED=false', 'AGENTTEAMS_MANAGER_RUNTIME=qwenpaw',
      "AGENTTEAMS_MANAGER_IMAGE=agentteams/validation-manager-qwenpaw:$valTag",
      'AGENTTEAMS_DEFAULT_WORKER_RUNTIME=qwenpaw', "AGENTTEAMS_QWENPAW_WORKER_IMAGE=agentteams/validation-qwenpaw-worker:$valTag",
      "AGENTTEAMS_PORT_MANAGER_CONSOLE=$($valBase+99)", 'AGENTTEAMS_DEFAULT_MODEL=qwen3.6-plus',
      'AGENTTEAMS_LLM_API_KEY=', 'AGENTTEAMS_EMBEDDING_MODEL=', 'AGENTTEAMS_MATRIX_E2EE=0',
      "AGENTTEAMS_ELEMENT_HOMESERVER_URL=http://127.0.0.1:$($valBase+67)",
      'AGENTTEAMS_CMS_TRACES_ENABLED=false', 'AGENTTEAMS_CMS_METRICS_ENABLED=false', 'TZ=UTC'
    )
    $valEnvFile = Join-Path $valDir 'controller.env'
    [System.IO.File]::WriteAllLines($valEnvFile, $valEnv, [System.Text.UTF8Encoding]::new($false))
    docker network create "$valName-net"
    docker volume create "$valName-data"
    docker volume create "$valName-agentfs"
    $valDockerArgs = @('run','-d','--name',"$valName-controller",'--network',"$valName-net",
      '--network-alias',"$valName.matrix.invalid",'--env-file',$valEnvFile,
      '-v',"${valName}-data:/data",'-v',"${valName}-agentfs:/root/agentteams-fs",
      '--mount',"type=bind,source=$valWorkspace,target=/root/agentteams-fs/agents/manager",
      '--mount',"type=bind,source=$valShare,target=/validation-host-share",
      '-v','//var/run/docker.sock:/var/run/docker.sock',
      '-p',"127.0.0.1:$($valBase+80):8080",'-p',"127.0.0.1:$($valBase+90):8090",
      '-p',"127.0.0.1:$($valBase+67):6167",'-p',"127.0.0.1:${valBase}:9000",
      '-p',"127.0.0.1:$($valBase+1):9001",'-p',"127.0.0.1:$($valBase+11):8001",
      '-p',"127.0.0.1:$($valBase+88):8088",'--restart','unless-stopped',
      "agentteams/validation-embedded:$valTag")
    docker @valDockerArgs
    if ($LASTEXITCODE -ne 0) { throw "Could not start $valName-controller" }
}
```

Manager不启用不代表Controller不启动：HTTP服务先启动；initializer在后台按 OSS → Matrix/Admin → AppService → Gateway/routes → 可选Manager CR 运行（app.go:154—208，initializer.go:79—138）。因此基础 HTTP health 通过后仍必须查初始化日志；initializer失败是 non-fatal，API活着不代表完整基础设施已经就绪。

### 3.3 Windows workspace 的关键处理

PowerShell installer:3189—3190 将宿主目录直接传进环境变量，Controller `applyEmbeddedConfig` 原样作为 `VolumeMount.HostPath`，DockerBackend:705—706 再拼成bind字符串。本机 Linux Docker daemon的host路径不能凭Windows `D:\...` 猜测。

先让 Docker Desktop CLI 完成上节Controller的bind挂载，再读取其实际源路径：

```powershell
$valInspect = (docker inspect rmv-a-controller | ConvertFrom-Json)[0]
$valDaemonWorkspace = ($valInspect.Mounts | Where-Object Destination -eq '/root/agentteams-fs/agents/manager').Source
$valDaemonShare = ($valInspect.Mounts | Where-Object Destination -eq '/validation-host-share').Source
if (-not $valDaemonWorkspace -or -not $valDaemonShare) { throw 'Required host bind source missing' }
```

把 `$valDaemonWorkspace` 设为 `AGENTTEAMS_WORKSPACE_DIR`，`$valDaemonShare` 设为 `AGENTTEAMS_HOST_SHARE_DIR` 后再启用Manager；分别对b执行。**这些inspect输出需要在实际Manager创建后再核对 `.Mounts.Source` 与哨兵文件可达性**；如果返回格式仍不能由Linux API使用，应先完成daemon路径转换/探针，不自动回退到共享HOME。

目标关系必须是：宿主a/workspace同时映射Controller `/root/agentteams-fs/agents/manager` 与a-Manager `/root/manager-workspace`；a/host-share仅映射a-Manager `/host-share`。不能将环境变量填写成Controller内的 `/root/agentteams-fs/agents/manager`，因为Docker daemon解释的是宿主路径。也不应继承安装器默认的整个USERPROFILE。

## 4. 不用模型先验证，再开启真实 provider

### 基础探针与资源API

```powershell
Invoke-RestMethod 'http://127.0.0.1:28190/healthz'
docker exec rmv-a-controller curl -fsS http://127.0.0.1:6167/_tuwunel/server_version
docker exec rmv-a-controller curl -fsS http://127.0.0.1:9000/minio/health/live
docker exec rmv-a-controller curl -fsS http://127.0.0.1:8080/status
docker exec rmv-a-controller agt get managers
docker exec rmv-a-controller agt get workers
```

`agt` 默认从容器内 `/var/run/agentteams/cli-token` 读取初始化生成的管理token；无需把真实token打印到宿主终端。直接REST写操作可在容器内读取token后发起，记录证据需屏蔽Authorization。先做资源API持久化时，用原生Worker `state=Stopped` 或 `containerManaged=false` 显式限制运行；这只是资源契约测试，不是Ready/执行测试。Manager=false时新建Manager CR不会由ManagerReconciler接手。

### 真实 provider 与 Manager 的开启

1. 在已有每实例env文件上更新 `AGENTTEAMS_LLM_PROVIDER`（OpenAI兼容场景为 `openai-compat`）、`AGENTTEAMS_OPENAI_BASE_URL`、真实 `AGENTTEAMS_LLM_API_KEY` 和实际可用 `AGENTTEAMS_DEFAULT_MODEL`。不使用假key冒充连通。真实key只经受控本地凭据路径注入。
2. 加入上一节取得并核查的 `AGENTTEAMS_WORKSPACE_DIR` / `AGENTTEAMS_HOST_SHARE_DIR`；设置 `AGENTTEAMS_MANAGER_ENABLED=true`。启动前确保两实例Manager host console端口不同。
3. 因环境变量不是热加载，主任务按同一固定配置重建**指定实例Controller容器**，保留该实例数据卷、agentfs卷、workspace及所有secret。不要重新生成secret，不运行全局安装器清理。重建动作由主部署任务执行和记录。
4. initializer在infra就绪后创建 `Manager/default`；已有CR时跳过创建，**不自动用新env改写已有CR的model/runtime/image**（initializer.go:474—477）。若以前已建Manager需经明确API更新其spec并读回，不能以重启env为更新完成。
5. 新Manager由Reconciler创建为`rmv-a-manager`，不会在embedded基础镜像内启动。先核查实际image ID、package版本、mounts、网络、Matrix完整user ID、loaded plugins，再验证真实模型响应和任务执行。

LLM provider设置位于initializer.go:286—426，只在非空API key时尝试建provider及AI route；部分错误只记日志，须用实际模型请求证明可用。`AGENTTEAMS_MANAGER_ENABLED=false`不拦HTTP；`true`也不证明provider就绪或Manager已处理消息。

## 5. 验证时必须保留的差异与限制

- 两实例使用同名 Team/Worker、同仓库测试目标，但完整Matrix身份、网络、bucket、auth token、host workspace和Docker前缀均不同；对方token请求必须失败。
- 停a时b的Controller、Matrix、Manager和Worker不能消失；同一Docker daemon的高权限Controller仍需AT-02旁路验证，不能因为容器名字不同就宣称安全隔离。
- 正式Worker资源字段未投影Docker CPU/Memory限制的问题不由此配方自动修复。可给基础设施容器设独立限额，但不能把这些限额当作Worker/Attempt限额。
- 基础镜像overlay、组件fake、真实服务但无模型、真实模型调用、RepoMesh受控联调是不同证据层级，报告分别记录。
- 当前只是部署预检；本文件中的命令尚未执行，Manager自动创建、HostPath转换及完整runtime加载均要以主执行任务实际结果确认。

## 6. 主要源码依据

- `install/agentteams-install.ps1:3150`：官方embedded参数；`:3259`：socket与挂载；`:3303`：infra等待。
- `agentteams-controller/internal/config/config.go:251`、`:349`、`:362`、`:438`：配置、Manager开关、host路径与子容器地址改写。
- `agentteams-controller/internal/app/app.go:154`、`:173`、`:597`：HTTP启动、initializer和ManagerReconciler开关。
- `agentteams-controller/internal/initializer/initializer.go:79`、`:286`、`:457`：启动顺序、LLM provider条件、Manager/default创建。
- `agentteams-controller/internal/auth/prefix.go:56`、`:97`：默认Manager容器名前缀。
- `agentteams-controller/internal/controller/manager_reconcile_container.go:221`：真实Manager挂载/端口；`internal/backend/docker.go:705`：原样拼接HostPath。
- `agentteams-controller/internal/service/provisioner.go:1345`：Manager Matrix/consumer短名固定。
- `Makefile:150`、`:166`、`:174`、`:209`：官方构建上下文及插件打包。
- `agentteams-controller/Dockerfile`、`Dockerfile.embedded`、`manager/Dockerfile.qwenpaw`、`qwenpaw/Dockerfile`：当前镜像构成。
