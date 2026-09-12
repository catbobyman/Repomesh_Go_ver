# RepoMesh

多仓库协作产品的工程骨架。当前包含 React／TypeScript／Vite 页面、同一 Go 工程的三个入口，以及 PostgreSQL 连接、显式迁移和版本核查。登录、项目业务及 AgentTeams 集成尚未实现。现行产品决定见 [文档导航](docs/README.md)，工程职责及扩展边界见 [开发说明](docs/current/development-scaffold.md)。

## Codex 项目插件

本仓库通过项目级配置启用 pstack 0.9.28，包含 54 个开发辅助技能。在本项目的 Codex 任务中选择 `pstack:poteto-mode` 使用；安装范围、固定来源及 Windows 限制见[插件说明](.agents/plugins/README.md)。这是开发工具配置，不改变产品 Skill 模块暂缓的决定。

## 开发与检查

正式业务开发前先读[开发前阅读与行动指南](docs/current/DEVELOPMENT-START.md)，按[分批施工 TODO plan](docs/current/IMPLEMENTATION-PLAN.md)查看范围、依赖和验证结果。旧交接、协作日志和被替代原型已移入[历史归档](docs/archive/2026-09-12-development-preparation/README.md)。

要求 Go 1.26 或以上、Node.js 22.12 或以上、npm；配套打包脚本使用 PowerShell 7（`pwsh`）。本轮实际工具版本与检查结果见 [工程验收记录](docs/current/scaffold-verification.md)。以下命令均从仓库根目录执行。

```powershell
npm --prefix web ci
npm --prefix web run typecheck
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

打开 <http://127.0.0.1:8080>。`GET /healthz` 返回 200，只表示 Web 进程存活；`GET /readyz` 固定返回 503，表示业务未实现。未知 `/api` 路径返回 404。缺少前端构建文件或端口被占用时启动失败并报告原因；Ctrl+C 停止 Web。

前端独立开发（只启动本地 Vite）：

```powershell
npm --prefix web run dev
```

打开 <http://127.0.0.1:5173>。当前页面不请求业务 API，不显示实时状态，也不触发任何外部实例。

检查三个入口的版本：

```powershell
go run ./cmd/repomesh-web --version
go run ./cmd/repomesh-coordinator --version
go run ./cmd/repomesh-host-executor --version
```

`coordinator` 和 `host-executor` 不带 `--version` 时打印 `not implemented` 并以 1 退出，这是当前骨架的预期行为；没有后台任务循环、执行监听、Docker 操作或 Python 启动功能。

## 数据库迁移与批次验证

设置本机开发库连接串后，使用 Web 二进制的独立数据库子命令。连接串可来自环境变量或子命令的 `--database-url`，环境变量不会写入帮助或错误输出。普通 Web 启动不读取数据库配置，也不自动迁移。

```powershell
$env:REPOMESH_DATABASE_URL = '<本机开发库连接串>'
go run ./cmd/repomesh-web db check
go run ./cmd/repomesh-web db migrate --timeout 30s
go run ./cmd/repomesh-web db check
```

直接运行二进制时，`check` 只有在迁移历史完全匹配时退出 0，缺少迁移或历史不匹配退出 1，参数错误退出 2。`go run` 还会报告子进程退出状态。首条迁移只建立迁移记录表，尚无业务表。迁移只支持前进，SQL 与历史记录同事务提交。具体命令、超时、失败恢复及配置范围见[数据库开发说明](docs/current/database-development.md)。

数据库批次验证需要 PowerShell 7 和 PostgreSQL 17 的 Windows 二进制。本机本轮下载目录已位于被 Git 忽略的 `bin`，其他开发机可使用自己的安装目录。

```powershell
pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B00
pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B01 -PostgresBin ./bin/dev-postgres17/pgsql/bin
```

B01 脚本创建独立临时数据库实例、运行全部工程检查及数据库和二进制验收，再停止并清理该实例。它拒绝把缺少或跳过的 PostgreSQL 测试标为通过。普通 `go test ./...` 在没有 `REPOMESH_TEST_DATABASE_URL` 时会明确跳过这些集成测试；该结果不能替代 B01 验收。每次脚本生成新的证据目录并拒绝覆盖。已有结果见[B01 记录](docs/development/2026-09-12-batch-01/README.md)。

## 配置与配套构建

[配置示例](configs/repomesh.env.example)列出 Web 实际消费的环境变量。程序不会自动加载 `.env`。命令行参数优先于环境变量，环境变量优先于默认值；资源路径相对于启动工作目录。

```powershell
go run ./cmd/repomesh-web --addr 127.0.0.1:8081 --assets web/dist
pwsh -NoProfile -File scripts/build.ps1 -Version 0.1.0-scaffold-final
```

构建脚本从锁文件安装前端、检查类型、构建静态资源并输出三个同版本 Go 二进制。当前验收产物位于 `dist/repomesh-0.1.0-scaffold-final/`，含静态资源、配置示例、启动说明及带 SHA-256 的 `release.json`。已有同名输出目录会拒绝覆盖；重复构建时使用新的版本标签。此前本轮检查产生的其他 `dist/repomesh-*` 包不属于最终验收包。构建使用当前 GOOS／GOARCH，默认本机目标；脚本不部署也不启动任何服务。

在仓库根目录启动 Windows 配套产物：

```powershell
./dist/repomesh-0.1.0-scaffold-final/bin/repomesh-web.exe --assets ./dist/repomesh-0.1.0-scaffold-final/web/dist
```

发布时保持整个目录一起交付，三个入口和前端共用同一版本清单。目前只适于本地骨架检查，认证、权限、持久化及完整运维流程尚未实现。

## 实施边界

PostgreSQL 连接与迁移工具已实现。Issue、计划、调度、权限、GitHub、AgentTeams、业务持久化、持久队列和对象存储均未接入。Graph 后续仍是后台进程内模块；ADR-0020 的 Python 仓库分析仅记录受控扩展边界；Skill 工程继续暂缓。未预建这些业务目录、接口、数据库表、MCP Schema 或恢复算法。

`validation/` 保存独立的历史实验和证据，不是产品代码，也不随产品发布。骨架构建通过不代表旧验证全部通过，更不等于业务或 AgentTeams 集成验收完成。
