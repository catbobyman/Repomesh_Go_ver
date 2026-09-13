# RepoMesh

多仓库协作产品，采用 React／TypeScript／Vite 与同一 Go 工程的三个入口。已实现 PostgreSQL 迁移、认证秘密基础、GitHub App 登录／重连、服务端会话、授权恢复页面与后台仓库发现。B03 项目管理代码已集成，提供待配置项目创建、列表、资料编辑、明确增仓、固定配置引用和原操作恢复；主目录已 INTEGRATED_LOCAL_VERIFIED。B04 已采用 D01—D04 并落地模型供应商保存、六个 HTTP 端点和 `repomesh-web sources` 导入；本地验证有缺口，非整批 VERIFIED。`businessReady=false`。范围见[项目开发说明](docs/current/project-development.md)和[B04 采用记录](docs/current/b04-model-sources-adoption.md)。本地验证、真实 GitHub 验收与整批 VERIFIED 分别记录；Issue、运行和 AgentTeams 集成尚未实现。现行产品决定见 [文档导航](docs/README.md)，工程职责及扩展边界见 [开发说明](docs/current/development-scaffold.md)。

首次接手项目可按 [Agent 全局阅读指南](docs/current/AGENT-READING-GUIDE.md) 阅读产品、架构与实现材料；具体实施顺序见开发前行动指南。

## Codex 项目插件

本仓库通过项目级配置启用 pstack 0.9.28，包含 54 个开发辅助技能。在本项目的 Codex 任务中选择 `pstack:poteto-mode` 使用；安装范围、固定来源及 Windows 限制见[插件说明](.agents/plugins/README.md)。这是开发工具配置，不改变产品 Skill 模块暂缓的决定。

## 开发与检查

当前主开发副本为 `/home/xubohan/projects/Repomesh_Go_ver`，D 盘原工程保留。本次接手已直接核实 WSL2 Linux、工具路径及桌面项目绑定的 SSH 主机 `repomesh-wsl`。其他 Windows 项目继续使用本地 Codex，无需全局切换 Agent／终端。此前登录故障已恢复，见 [SSH 接入记录](docs/development/2026-09-12-wsl-ssh/README.md)。用户已确认 B02 最小实施包，本地实施与独立验证已通过；真实 App 材料、HTTPS 和专用服务已配置，完整真实验收待补。采用范围见 [B02 采用记录](docs/current/b02-authentication-adoption.md)，原本地证据见 [B02 记录](docs/development/2026-09-12-batch-02/README.md)，当前外部进度见[真实验收 02](docs/development/2026-09-12-b026-live-02/README.md)。Windows／Linux B01 与浏览器结果见 [WSL 环境验收](docs/development/2026-09-12-wsl/README.md)。

WSL 中执行完整数据库批次检查：

```bash
pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B02 -PostgresBin /usr/lib/postgresql/17/bin
```

正式业务开发前先读[开发前阅读与行动指南](docs/current/DEVELOPMENT-START.md)，按[分批施工 TODO plan](docs/current/IMPLEMENTATION-PLAN.md)查看范围、依赖和验证结果。旧交接、协作日志和被替代原型已移入[历史归档](docs/archive/2026-09-12-development-preparation/README.md)。

要求 Go 1.26 或以上、Node.js 22.12 或以上、npm；配套打包脚本使用 PowerShell 7（`pwsh`）。B02 数据库验收还要求启用 cgo 和可用的 C 编译器。当前工具版本与检查结果见 [B02 记录](docs/development/2026-09-12-batch-02/README.md)，旧骨架结果见 [工程验收记录](docs/current/scaffold-verification.md)。以下命令均从仓库根目录执行。

```powershell
npm --prefix web ci
npm --prefix web run typecheck
npm --prefix web test
npm --prefix web run build
go build ./...
go test ./...
go vet ./...
```

Go 使用 pgx v5.11.0 连接 PostgreSQL，依赖版本及校验和保存在 `go.mod` 和 `go.sum`。前端使用已提交的 `web/package-lock.json` 安装；变更依赖时再更新锁文件。`validation/go.mod` 和 `third_party/go.mod` 分别隔离历史实验与独立上游源码，根目录 Go 命令不会编译或运行它们。

AgentTeams 本体位于 `third_party/AgentTeams/`，保留独立 Git 仓库且被父仓库忽略；来源、确定提交及重建方式见[上游源码说明](third_party/README.md)。目前仅完成源码克隆，没有业务或运行集成。

若本机报告 Git `dubious ownership` 或 Go `error obtaining VCS status`，先按[开发说明中的当前会话信任设置](docs/current/development-scaffold.md#本地启动与配置)处理，再运行上述命令；不需要改全局 Git 配置。

启动 Web（先完成前端构建）：

```powershell
go run ./cmd/repomesh-web
```

打开 <http://127.0.0.1:8080>。`GET /healthz` 返回 200，只表示 Web 进程存活；`GET /readyz` 固定返回 503，完整业务就绪条件尚未满足。未知 `/api` 路径返回 404；未配置认证时项目 API 返回 503。缺少前端构建文件或端口被占用时启动失败并报告原因；Ctrl+C 停止 Web。

前端独立开发（只启动本地 Vite）：

```powershell
npm --prefix web run dev
```

打开 <http://127.0.0.1:5173>。Vite 未配置 API 代理。认证集成使用 Go 同源服务的构建资源。

检查三个入口的版本：

```powershell
go run ./cmd/repomesh-web --version
go run ./cmd/repomesh-coordinator --version
go run ./cmd/repomesh-host-executor --version
```

`coordinator` 配置认证后运行账号核实、令牌刷新、仓库发现续扫与秘密清理／重包；未配置时退出 1。`host-executor` 仍报告 `not implemented` 并退出 1，没有执行监听、Docker 或 Python 启动功能。

## 数据库迁移与批次验证

设置本机开发库连接串后，使用 Web 二进制的独立数据库子命令。连接串可来自环境变量或子命令的 `--database-url`，环境变量不会写入帮助或错误输出。未启用认证时 Web 不连接数据库；提供 `REPOMESH_AUTH_CONFIG` 或 `--auth-config` 后，Web 和 coordinator 会连接并核查迁移，不自动迁移。

```powershell
$env:REPOMESH_DATABASE_URL = '<本机开发库连接串>'
go run ./cmd/repomesh-web db check
go run ./cmd/repomesh-web db migrate --timeout 30s
go run ./cmd/repomesh-web db check
```

直接运行二进制时，`check` 只有在迁移历史完全匹配时退出 0，缺少迁移或历史不匹配退出 1，参数错误退出 2。`go run` 还会报告子进程退出状态。当前第五条迁移增加模型供应商、保存回执、执行来源和默认 `pinned_version`；第四条增加项目、完整仓库范围、配置固定版本、操作回执与游标；前三条建立版本记录、认证秘密和账号／会话／发现表。部署执行来源只走 `repomesh-web sources import --file PATH` 与 `sources result --import-id UUID`，使用数据库部署身份，不走浏览器。迁移只支持前进，SQL 与历史记录同事务提交。具体命令、超时、失败恢复及配置范围见[数据库开发说明](docs/current/database-development.md)。

数据库批次验证需要 PowerShell 7 和 PostgreSQL 17，当前 B02 认证验证在 Linux 运行；Windows B01 历史证据对应当时的源码，不能替代当前认证平台验收。WSL 使用本页上方的 `/usr/lib/postgresql/17/bin`；下例为保留的 Windows 工具路径，本机下载目录位于被 Git 忽略的 `bin`。其他开发机可使用自己的安装目录。

```powershell
pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B00
pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B01 -PostgresBin ./bin/dev-postgres17/pgsql/bin
```

B01／B02 脚本创建独立临时数据库实例、运行全部工程检查及数据库和二进制验收，再停止并清理该实例。它拒绝把缺少或跳过的 PostgreSQL 测试标为通过。普通 `go test ./...` 在没有 `REPOMESH_TEST_DATABASE_URL` 时会明确跳过这些集成测试；该结果不能替代 B01 验收。B02 增加认证 race 与前端 API 测试，通过仅标记 LOCAL_VERIFIED，真实 GitHub 验收另列。每次脚本生成新的证据目录并拒绝覆盖。已有结果见[B01 记录](docs/development/2026-09-12-batch-01/README.md)。

## 认证配置

按[认证开发说明](docs/current/authentication-development.md)准备专用 GitHub App、固定 HTTPS 回调、独立秘密文件和数据库，再使用 [auth.example.json](configs/auth.example.json) 启动 Web 与 coordinator。程序不自动生成生产根，不支持任意 returnUrl。没有认证配置时 API 返回 503，页面提示无法确认，`/readyz` 仍为 503。

首次配置和真实验收按[GitHub App 操作手册](docs/current/b02-github-live-acceptance.md)执行，包含 App 设置、HTTPS 代理、配套包启动及自然到期刷新。真实验收发现的[UTC 时间输出](docs/development/2026-09-12-b026-utc-fix-01/README.md)及[同步回调 Cookie 竞争](docs/development/2026-09-12-b026-cookie-fix-01/README.md)均已完成本地修复和独立源码复核，完整 B02.6 验收仍待完成。

## 配置与配套构建

B03 后端检查可运行 `pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B03 -PostgresBin /usr/lib/postgresql/17/bin`。它使用独立 SCRAM 实例，包含 Go、真实事务、HTTP、进程重启和 race。项目管理代码已合入主目录，当前为 `INTEGRATED_LOCAL_VERIFIED`；真实 PostgreSQL 73 通过、0 跳过，前端 28/28、浏览器 25+1、Go/race、HTTP、实际进程恢复和配套发布均通过，[最终独立复核](docs/development/2026-09-12-b03-integration-01/FINAL-INDEPENDENT-REVIEW.md)确认两项 P1、一项 P2 闭环，无开放 P0/P1/P2。新包为 `dist/repomesh-0.3.0-b03-integrated-20260912-r1/`，businessReady=false；不是外部 GitHub、部署或整批业务 VERIFIED。B04 为 DESIGN_PREPARED_NOT_ADOPTED，本轮止于[交接](docs/development/2026-09-12-b04-handoff-01/HANDOFF.md)和[下会话 Prompt](docs/current/NEXT-TASK-B04-PROMPT.md)。历史 worktree 为 `LOCAL_VERIFIED`，证据位于 `/home/xubohan/projects/Repomesh_B03/docs/development/2026-09-12-b03-01/`，旧包位于 `/home/xubohan/projects/Repomesh_B03/dist/repomesh-0.3.0-b03-worktree-20260912-r1/`，均未复制到主目录。本轮集成记录见[集成证据](docs/development/2026-09-12-b03-integration-01/README.md)。下列 r3 保留为 B02 产物，不能验证新增项目功能；再次构建须使用不同版本标签。

[配置示例](configs/repomesh.env.example)列出 Web 实际消费的环境变量。程序不会自动加载 `.env`。命令行参数优先于环境变量，环境变量优先于默认值；资源路径相对于启动工作目录。

```powershell
go run ./cmd/repomesh-web --addr 127.0.0.1:8081 --assets web/dist
pwsh -NoProfile -File scripts/build.ps1 -Version 0.2.0-b026-cookie-20260912-r3
```

构建脚本从锁文件安装前端、检查类型、构建静态资源并输出三个同版本 Go 二进制。本次修复的配套构建输出到 `dist/repomesh-0.2.0-b026-cookie-20260912-r3/`，含静态资源、配置示例、启动说明及带 SHA-256 的 `release.json`。脚本拒绝覆盖已有同名包，重复构建须使用新的版本标签。原 `dist/repomesh-0.2.0-b02-local-20260912-r1/` 、`dist/repomesh-0.2.0-b026-utc-20260912-r2/` 及旧本地验收保留。构建使用当前 GOOS／GOARCH，默认本机目标；脚本不部署也不启动任何服务。

在仓库根目录启动本次 Linux 配套产物：

```powershell
./dist/repomesh-0.2.0-b026-cookie-20260912-r3/bin/repomesh-web --assets ./dist/repomesh-0.2.0-b026-cookie-20260912-r3/web/dist
```

发布时保持整个目录一起交付，三个入口和前端共用同一版本清单。B02 包含本地验证的认证及其持久状态，真实 App 集成和完整业务／运维验收仍待完成。

## 实施边界

PostgreSQL、认证、受限 GitHub 发现适配及项目管理已实现。项目可保存为待配置状态，默认配置为空时不伪造有效值；模型 Key 管理、配置来源管理、预算编辑、Issue、计划、调度、AgentTeams、运行待办和对象存储仍未接入。Graph 后续仍是后台进程内模块；ADR-0020 的 Python 仓库分析仅记录受控扩展边界；Skill 工程继续暂缓。后续业务目录、接口、数据库表及恢复算法按各批采用契约增加。

`validation/` 保存独立的历史实验和证据，不是产品代码，也不随产品发布。骨架构建通过不代表旧验证全部通过，更不等于业务或 AgentTeams 集成验收完成。
