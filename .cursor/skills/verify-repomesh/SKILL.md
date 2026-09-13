---
name: verify-repomesh
description: Drive the RepoMesh web UI (login, workspace, projects, model settings) the way a user does. Use when proving a page, HTTP contract, or B02 live GitHub acceptance against a real process, not when only running go test.
---

# Verify RepoMesh

Primary surface is the Go-served React UI. Users open pages in a browser. The same origin exposes `/api/*`. Companion processes are `repomesh-coordinator` (required for live GitHub) and `repomesh-host-executor` (unimplemented, exit 1). Vite `5173` is frontend-only and has no API proxy. Do not use it for auth proof.

This skill is for the next agent. Read the feature map before driving. Drive every listed entry point for the feature you claim, or report the unmet precondition.

## Operator packet for B02 live

B02 live is GitHub App login, reconnect, discovery, and natural refresh. It is not a model-provider test. Do not ask for a model API key.

The operator must place secrets on the Linux host that runs Web and coordinator. The operator must not paste secret bodies into chat, evidence JSON, or this repo.

**Tell the agent these non-secret facts.**

- Fixed HTTPS origin, including port if not 443. Example shape `https://repomesh.example.com`.
- Absolute path to `auth.json` on the server. Path only.
- Whether the existing wrap root and existing PostgreSQL must be reused. Reuse if that database already has auth rows.
- GitHub login of account A. Current handover says future live work uses only A.
- Whether this run is A-only re-proof of retained LIVE items, restore of the paused second-account leftovers, or both.
- Confirmation that the account holder will click GitHub Authorize, Cancel, App permission, and install UI. Agents must not complete those GitHub pages for the holder.
- Dedicated acceptance PostgreSQL connection available as `REPOMESH_DATABASE_URL` in the process environment, not typed into a command line if avoidable.
- One installed private repository the A account can read, plus one A-readable repository left outside the App install if LIVE-08 pagination or out-of-install absence is in scope. Give stable numeric IDs if needed. Do not put private repo names in evidence.

**Place on the Linux host. Never paste the bodies.**

| File | Role | Constraints |
| --- | --- | --- |
| `auth.json` | Non-secret App IDs, origin, callback, secret paths | Copy from `configs/auth.example.json`. Unknown fields rejected. |
| client secret file | GitHub App OAuth client secret | Regular file, `0600`, not a symlink, ≤64 KiB. |
| App RSA PEM | GitHub App private key | Same file rules. PKCS#1 or PKCS#8, ≥2048 bits. |
| wrap root | Envelope-encryption root | Raw 32 random bytes, not hex text. Do not regenerate a same-id root over an existing database. |
| TLS cert and key, or a reverse proxy | Browser-trusted HTTPS | `__Host-` cookies require Secure. HTTP origins cannot prove live login. |

`callbackUrl` must equal `<origin>/api/auth/github/callback` character for character.

**Do not provide.**

- Model vendor API keys, billing keys, or B04/B05 test permits.
- Account B, collaborator invites, or a second-account plan. `LIVE-05` and `LIVE-08-USER-READ` are `DEFERRED_BY_USER`.
- Docker socket, AgentTeams credentials, or host-executor setup.
- Cookie values, OAuth `code`/`state`, PEM text, wrap-root bytes, database passwords, or raw HAR.

**Optional restore packet.** Only if the operator authorizes cleanup of `docs/development/2026-09-12-b026-second-account-02/`. Confirm in GitHub UI, then tell the agent only booleans and IDs.

- App visibility is private again.
- Installation `161284386` is gone.
- Collaborator and pending invite on the A-owned fixture repo are gone.
- B OAuth grant for the App is revoked.
- A installation `161172403` still selects only repository `1367444901` with Metadata read, Contents write, Pull requests write.
- Account A cannot see repository `1368000734`.

Historical origin `https://repomesh.bohanxu.me:8443` and old PIDs are record-time facts. Do not reuse them without a fresh doctor.

## Launch

Work from the repository root on Linux. Auth secret files are Linux-only.

Unconfigured UI, isolated from the default `:8080` session:

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%S)-$$"
export REPOMESH_VERIFY_RUN="$RUN_ID"
export REPOMESH_VERIFY_STATE="/tmp/repomesh-verify-$RUN_ID"
export REPOMESH_VERIFY_EVIDENCE="$PWD/.cursor/skills/verify-repomesh/evidence/$RUN_ID"
export REPOMESH_VERIFY_ADDR="127.0.0.1:18080"
bash .cursor/skills/verify-repomesh/helpers/launch-unconfigured.sh
```

Ready when the helper prints `ready origin=http://127.0.0.1:18080` and `GET /healthz` is 200. Log line on stderr is `web listening` with `address=127.0.0.1:18080` and `authentication_configured=false`.

Live GitHub is a different launch. The operator must already have placed the packet above.

```bash
export REPOMESH_DATABASE_URL="$(cat "${REPOMESH_DEV_PG_ROOT:-$HOME/repomesh-pg}/connection-url.txt")"
export REPOMESH_AUTH_CONFIG="/absolute/path/to/auth.json"
go run ./cmd/repomesh-web db check
go run ./cmd/repomesh-web db migrate --timeout 30s
npm --prefix web ci
npm --prefix web run build
go run ./cmd/repomesh-web --addr 127.0.0.1:8080 --assets ./web/dist
```

Second terminal, same two environment variables:

```bash
go run ./cmd/repomesh-coordinator
```

Open `/login` on the configured HTTPS origin, not `http://127.0.0.1:8080`. Ready when `/healthz` is 200, `/readyz` is 503, `/api/session` is 401 with `AUTHENTICATION_REQUIRED`, and coordinator stays up. `/api/session` 503 with `AUTH_NOT_CONFIGURED` means this process has no App config. Stop. That is not a live run.

Teardown uses the cleanup helper for unconfigured runs. For live `go run` processes, send SIGTERM to the PIDs you started. Do not `pkill` by name.

## Doctor

```bash
bash .cursor/skills/verify-repomesh/helpers/doctor.sh
```

Uses `REPOMESH_VERIFY_ORIGIN` or the origin recorded in `REPOMESH_VERIFY_STATE/origin`. Pass when the process is listening, `/healthz` is 200 with `businessReady=false`, `/readyz` is 503, and session matches the expected mode.

- Unconfigured. `/api/session` is 503 `AUTH_NOT_CONFIGURED`. State file `mode=unconfigured`.
- Live. `/api/session` is 401 `AUTHENTICATION_REQUIRED`. Coordinator must still be running if you started it.

Refuse to drive a shared instance you did not start. Default environment Web on `:8080` may already exist. Unconfigured verification uses `:18080` unless the operator names another free port.

## Drive

Prefer Playwright role clicks, matching `docs/development/2026-09-12-batch-02/browser-check.mjs`. Stable handles are Chinese accessible names, not coordinates.

| Control | Handle |
| --- | --- |
| Unconfigured login heading | `暂时无法确认登录状态` |
| Unconfigured retry | button `检查当前登录状态` |
| Live login | button `使用 GitHub 登录` |
| Live reconnect | button `重新连接同一账号` |
| Query prior attempt | button `查询原授权尝试` or `查询本次授权结果` |
| Return to workspace | button `稍后处理，返回工作区` |
| Sign out | button `退出登录` or `退出当前账号` |
| Projects | button `项目` and heading `项目` |
| New project | button `新建项目` |
| Model settings | button `模型设置` |
| Save provider | button `保存供应商` |

Unconfigured recipe lives in `features/unconfigured-login.md`. Helper:

```bash
bash .cursor/skills/verify-repomesh/helpers/drive-unconfigured-login.sh
```

Live GitHub recipe lives in `features/live-github-auth.md`. Copy `docs/development/2026-09-12-b02-external-preparation/live-acceptance-template.md` into a new `docs/development/<date>-b026-<topic>/` directory. Do not overwrite old LIVE evidence.

Local batch script is not a user-path proof:

```bash
pwsh -NoProfile -File scripts/verify-batch.ps1 -Batch B02 -PostgresBin /usr/lib/postgresql/17/bin
```

That emits `LOCAL_VERIFIED` only. Fixture browsers in `browser-check.mjs` isolate the external system with `page.route`. Live GitHub must hit `github.com` and `api.github.com` for real.

## Evidence

Store proof under `$REPOMESH_VERIFY_EVIDENCE`. Cleanup must not delete that directory.

Required for a user-path claim:

- HTTP status and error `code` for `/healthz`, `/readyz`, `/api/session`, and the feature's write or query.
- Screenshot or ARIA-equivalent of the page after the user action, with the RepoMesh heading visible.
- For mutations, a second read of the same resource or a read-only database snapshot. No secrets in the snapshot.
- Feature id and entry point recorded in `proof.json`.

Forbidden in evidence: Cookie values, `authorizationUrl`, OAuth `code`/`state`, CSRF tokens, PEM, wrap-root bytes, API keys, database URLs with passwords, raw HAR.

`/readyz` 503 and `businessReady=false` are expected. They are not failures.

## Cleanup

```bash
bash .cursor/skills/verify-repomesh/helpers/cleanup.sh
```

Kills only the PID in `$REPOMESH_VERIFY_STATE/web.pid`. Removes the state directory. Leaves `$REPOMESH_VERIFY_EVIDENCE` in place.

## Helpers

All helpers are `bash` scripts in `.cursor/skills/verify-repomesh/helpers/`. Invoke them from the repository root with the environment variables in Launch.

- `launch-unconfigured.sh` builds `web/dist` if `index.html` is missing, starts Web with `--auth-config=`, writes origin and pid.
- `doctor.sh` is read-only.
- `drive-unconfigured-login.sh` exercises `/login` on the unconfigured process and writes `proof.json` plus response bodies.
- `cleanup.sh` tears down that process.

## Feature map

`.cursor/skills/verify-repomesh/features/README.md`
