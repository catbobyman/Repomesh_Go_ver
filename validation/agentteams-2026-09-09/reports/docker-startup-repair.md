# Docker Desktop 启动故障处理记录

日期：2026-09-09。状态：本次启动故障已修复并验证。

## 原始症状与复现

执行 `docker desktop start` 后，Docker Desktop 4.40.0 弹出 `An unexpected error occurred`。用户截图与本机后端日志一致：

```text
OTel manager: removing stale socket: remove <HOME>\AppData\Local\Docker\run\userAnalyticsOtlpHttp.sock: The file cannot be accessed by the system.
```

日志记录 2026-09-09T16:16:58Z 后端因此崩溃。`docker version --format '{{json .Server}}'` 返回 `null` 并提示 Linux Engine 命名管道不存在。

## 排查证据

- 故障套接字创建于 2026-09-06，长度 0，属性 `Archive, ReparsePoint`。
- `fsutil reparsepoint query` 直接失败，返回 Error 1920，同样为系统无法访问文件。
- 父目录 ACL 中当前用户、SYSTEM、Administrators 均有 FullControl。
- `run/` 目录只发现这一条套接字；未检查或修改 Docker 容器数据盘。

优先假设：残留套接字重解析状态异常；其次排查活动进程占用、目录权限。权限检查目前不支持父目录缺少权限的假设。

## 操作记录

1. “按进程路径筛选后强制结束进程＋删除套接字”的组合命令被自动审批策略拒绝，未执行。
2. 改为官方 `docker desktop stop`，日志确认收到 `/app/quit`，但进程持续存在。
3. 使用官方支持的 `docker desktop stop --force --timeout 20`，退出成功。再次检查后端进程已不存在。
4. 验证源、目标绝对路径均位于 `C:/Users/18092/AppData/Local/Docker` 后，将 `run` 改名为 `run-stale-20260909` 保留故障文件，创建新的空 `run`。未删除镜像、容器、卷、数据盘或其他旧目录。
5. `docker desktop start --timeout 60` 成功。新套接字创建时间为本次启动时间；引擎服务端返回 28.0.4、linux、overlay2，能够读取全部 28 个旧容器。
6. 使用本地 Alpine 镜像运行无网络、只读根文件系统、无额外能力的临时容器，退出成功且自动清除。

```powershell
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --name repomesh-docker-repair-smoke --label repomesh.validation=agentteams-2026-09-09 --entrypoint /bin/sh d529dd0c6e55 -c 'printf "DOCKER_REPAIR_SMOKE_OK\n"; uname -s'
```

结果：`DOCKER_REPAIR_SMOKE_OK`、`Linux`，退出码 0。随后查询没有遗留 smoke 容器。新启动时段的后端日志没有再次出现 `removing stale socket` 或 `backend crashed`。服务端版本原始证据见 [docker-server-after-repair.json](../evidence/docker-server-after-repair.json)。

## 验收标准

原始套接字错误不再阻断启动；Docker Engine API 正常返回服务端版本和容器列表；实际隔离测试容器成功退出。三项均通过。

现有证据支持“旧 run 目录中的套接字状态异常导致本次启动失败”，并证明更换该运行目录解除故障。尚未证明产生异常套接字的更深层原因或未来永不复发；未通过故意破坏套接字进行破坏性回归测试。
