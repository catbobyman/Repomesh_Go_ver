# 2026-09-14 Cloud VM B02.6 验证清单

本文件是这一轮真实验收的唯一进度表。每完成、阻塞或改判一项，先改这一页，再继续下一项。不要改写 `docs/development/2026-09-12-b026-*` 的旧证据。不要把本机观察写成施工计划 `VERIFIED`。

独立复核完成前，B02 保持 `IN_PROGRESS`。

## 退出条件

同时满足才停止本轮驱动。

- 下表「本轮」列里，账号 A 可做的 LIVE 项都是 `PASS`、`BLOCKED`、`DEFERRED_BY_USER` 或 `WAITING`。
- 每个 `PASS` 都有本目录证据，且证据与 `helpers/live-snapshot.sh` 的最近快照一致。
- `LIVE-09` 等到真实刷新窗口，不改库里的过期时间。
- `LIVE-10` 在 `LIVE-09` 之后做。在此之前不要点「退出登录」。
- 本轮不把 B02、B03、B04 标成整批 `VERIFIED`。

## 状态词

只使用这些值。`PASS` 只用于本 origin、本 App、本轮独立证据。旧 origin 的 PASS 不继承。

| 值 | 含义 |
| --- | --- |
| `PASS` | 本轮按手册判据成立，证据在本目录 |
| `FAIL` | 本轮做了，判据不成立 |
| `BLOCKED` | 缺条件，无法做完 |
| `NOT_RUN` | 还没做 |
| `DEFERRED_BY_USER` | 用户要求不做，不计 PASS |
| `OBSERVED_NOT_CLOSED` | 本轮看见了，尚未按手册收口或未独立复核 |
| `WAITING` | 在等真实时钟，禁止用改库代替 |

## 固定条件

| 项 | 值 |
| --- | --- |
| HTTPS origin | `https://127.0.0.1:18443/` |
| Web listen | `http://127.0.0.1:18080`。不要用地址栏打开它做 cookie 证明 |
| 环境默认 Web | `:8080`。不要动 |
| App | `RepoMesh-Cloud-Verify-1ef0`，ID `4940006`，安装 `161608372` |
| 安装内测试仓 | 稳定 ID `1367444901` |
| 账号 A | login `catbobyman`，展示名 `catmem`，GitHub ID `137759882` |
| 源码头 | 产品修复在 `cursor/fix-discovery-timeout-1ef0`，PR 6，头随提交前进 |
| 状态目录 | `/tmp/repomesh-verify-20260914T115738-48932` |
| 证据禁写 | 私仓名、cookie、OAuth code、PEM、数据库密码 |

## 下一项

**LIVE-04 第二次。** 会话刚在 17:21 UTC 由一次 login 重建。立刻点「重新连接 GitHub」。若出现「继续核查原授权尝试」，点「明确开始一次新的重连」，不要点「查询原授权尝试」。不要点「检查当前登录状态」。不要退出。30 分钟内必须完成，否则 idle 会话会再 401。

## B02.6 本轮 LIVE

| 顺序 | ID | 本轮 | 下一步 |
| --- | --- | --- | --- |
| 1 | LIVE-01 | `BLOCKED` | 匿名 session 401、healthz 200、readyz 503 已看到。证书是自签，Chrome 显示 Not secure。未达「浏览器信任证书」。 |
| 2 | LIVE-03 | `OBSERVED_NOT_CLOSED` | 持有人登录 confirmed，账号 A。未写入本目录正式表，无独立复核。不要重登冲掉会话。 |
| 3 | LIVE-06 | `OBSERVED_NOT_CLOSED` | 工作区画出 15 条。覆盖部分发现。安装内测试仓 App 能力已核实。未独立复核。列表已站住，可做 LIVE-04。 |
| 4 | LIVE-04 | `NOT_RUN` | 第一次失败。17:21:15 `POST /api/auth/github/reconnect` 401。工作区 SPA 仍显示已登录，但会话 idle 超过 30 分钟。随后 17:21:27 `POST /api/auth/github/login` 201，attempt 仍是 login，epoch 4→5。证据 `evidence/live-04-attempt1-proxy.txt` 与 `snapshots/after-live-04-attempt.json`。**现在立刻重试。** 必须出现 `purpose=reconnect` 的 confirmed 行。 |
| 5 | LIVE-08 | `OBSERVED_NOT_CLOSED` | 一页 15 条且 partial。YAML 未填安装外仓 ID。用户失权子项见 LIVE-08-USER-READ。LIVE-04 之后补 API 分页与安装外缺席。 |
| 6 | LIVE-07 | `NOT_RUN` | LIVE-04 与 LIVE-08 的 A 侧项之后做。把专用 App 权限降再恢复。不能用私仓缺席代替 denied。 |
| 7 | LIVE-02 | `NOT_RUN` | GitHub 可能自动同意，没有 Cancel 页就不能填 PASS。不要用当前已登录工作区去撞取消。 |
| 8 | LIVE-09 | `NOT_RUN` | LIVE-07 恢复后再重连一次，封存基线，等到自然窗口。期间禁止登录、重连、改安装权限。 |
| 9 | LIVE-10 | `NOT_RUN` | LIVE-09 之后。注销 204、session 401、列表清空。桌面与 390×844。 |
| — | LIVE-05 | `DEFERRED_BY_USER` | 不开账号 B。 |
| — | LIVE-08-USER-READ | `DEFERRED_BY_USER` | 不开账号 B。 |

## 计划口径（旧 origin，不继承）

施工计划与 HANDOFF 仍是 2026-09-13 的旧 App / `https://repomesh.bohanxu.me:8443`。本轮新 App 不能沿用那些 PASS。

| 范围 | 计划状态 | 本轮要不要做 |
| --- | --- | --- |
| B01 | `VERIFIED` | 不做 |
| B02 本地 B02.1–B02.5 | `LOCAL_VERIFIED` | 不做 |
| B02 整批 | `IN_PROGRESS`，外部 `PAUSED_BY_USER` | 本清单收口后仍要独立复核才能改计划 |
| B03 | `INTEGRATED_LOCAL_VERIFIED` | 不做。矩阵已齐，非整批 VERIFIED |
| B04 | `INTEGRATED_LOCAL_VERIFIED` | 不做。授权范围不发送模型请求 |
| 旧 LIVE-05 | 历史 `FAIL` | 延期 |
| 旧环境 6 步恢复 | `RESTORE_IN_PROGRESS` | 仅当 `run_scope` 为 `restore-leftovers` |

旧恢复 6 步仍未证明清理完。本轮默认不管它们。

## 维护规则

1. 做完一项立刻改本页「本轮」列，并在 [live-acceptance.md](live-acceptance.md) 写下观察。
2. 跑 `bash .cursor/skills/verify-repomesh/helpers/live-snapshot.sh docs/development/2026-09-14-b026-cloud-live-01/snapshots/<id>.json`。
3. 向 [decisions.tsv](decisions.tsv) 追加一行。
4. 再开始下一项。
5. 新 origin 或新 App 开新的 `docs/development/<日期>-b026-<主题>/`，不要覆盖本目录。
