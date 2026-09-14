# Live GitHub auth

Live GitHub auth lets account A start login from RepoMesh, finish or cancel on github.com, return to `/auth/result/{attemptId}`, and hold a session cookie. This is construction batch B02.6. Local `LOCAL_VERIFIED` and fixture browsers do not satisfy it.

## Sub-features

- `live-01` trusted HTTPS, login entry, anonymous session 401, healthz 200, readyz 503.
- `live-02` GitHub Cancel yields `cancelled/USER_CANCELLED` and no session.
- `live-03` authorize yields `confirmed`, expected account, no code or state in the URL.
- `live-04` same-account reconnect updates connection revision and revokes the old browser session.
- `live-06` installed private repo is `userParticipation=allowed` and `appCapability=allowed`.
- `live-07` reduced App permission is `denied` with a real reason, then restored `allowed`.
- `live-08-partial` cursor pages stay `coverage=partial`. Out-of-install private absence is not `denied`.
- `live-09` natural refresh with no new login or reconnect.
- `live-10` post-refresh discovery, logout 204, session 401, desktop and 390×844.

`live-05` and `live-08-user-read` stay `DEFERRED_BY_USER`. Do not start a second GitHub account.

On a local HTTP origin these cookie and callback items are `verified-unreachable`. Prerequisite: `auth.json` `origin` is exact HTTPS, `callbackUrl` matches, the holder opens that HTTPS origin, and `__Host-repomesh-session` is accepted with Secure. `internal/access/deployment.go` rejects a non-HTTPS origin. `internal/web/auth.go` always sets Secure on `__Host-` cookies.

## How to get to it (user POV)

- Fill `config.yaml` with `run_scope: account-a-live` and the live fields. Helpers still listen on `http://127.0.0.1:<port>`.
- Open `/login` on the HTTPS origin written in `auth.json`, not on the local HTTP listen address, when proving cookie acceptance.
- Choose `使用 GitHub 登录`.
- On github.com, Cancel or Authorize. The account holder does this.
- Land on `/auth/result/{attemptId}`. Choose `查询本次授权结果` or `确认当前账号，继续`.
- From the workspace, choose `重新连接 GitHub` for reconnect.
- Choose `退出登录` to end the session.

## Driving it with Playwright and curl

Preconditions:

- Operator yaml and host packet are in place. Secrets are files, not chat text.
- Web and coordinator share the database URL from yaml and `REPOMESH_AUTH_CONFIG`.
- `helpers/launch.sh` and `helpers/doctor.sh` use the local listen origin. Doctor live mode is `/api/session` 401 `AUTHENTICATION_REQUIRED` on that local HTTP process.
- Browser proof uses the HTTPS origin from `auth.json`. If that origin is missing, stop and record `verified-unreachable`.
- New evidence directory under `docs/development/`. Old LIVE folders stay untouched.
- Account A only.

- **Local probes only.** `GET http://127.0.0.1:<port>/api/session` may be 401 after a configured launch. That is not login proof.
- **Entry.** Open `/login` on the HTTPS origin. Heading `开始使用 RepoMesh`. Click `使用 GitHub 登录`. Browser leaves for `https://github.com/login/oauth/authorize`.
- **Cancel.** Holder clicks Cancel. Callback 303 to `/auth/result/{id}` with no query. Attempt `cancelled/USER_CANCELLED`. `/api/session` still 401.
- **Authorize.** New login. Callback 303, attempt `confirmed`, `/api/session` 200 for account A. URL has no `code` or `state`.
- **Reconnect.** Click `重新连接同一账号`. Same `user.id`. Connection revision and `access_epoch` advance. Old generation revoked.
- **Refresh.** Keep the same connection until the natural window. Do not edit database expiry. Proof is two read-only connection snapshots plus a new discovery.
- **Logout.** `退出登录` returns 204. `/api/session` is 401. Workspace no longer lists repositories.

Record each LIVE id in the new template. Independent review is still required before B02 `VERIFIED`.

## Gotchas

- Vite and `http://127.0.0.1:<port>` cannot prove `__Host-` cookies. Do not claim live login from the skill's default local origin.
- Product `auth.json` origin must be `https`. HTTP there fails open in `OpenRuntime`.
- Installation-complete on GitHub is not a RepoMesh login. Start from the product button.
- GitHub auto-consent can skip the Cancel page. Then `live-02` stays uncovered.
- First discovery 503 is `RESULT_UNCONFIRMED`. Re-read the same query. Do not swap in a fixture.
- `coverage=partial` is expected. An out-of-install private repo missing from the list is not a `denied` sample.
- Retained PASS for LIVE-01 through 04, 06, 07, 09, 10 does not reopen those items unless the operator asks. That sentence applies only to the origin and App that produced the PASS. A new HTTPS origin or App starts at [the current checklist](../../../docs/development/2026-09-14-b026-cloud-live-01/CHECKLIST.md).
- Restore leftovers from `second-account-02` need `run_scope: restore-leftovers` and the leftover confirmation flags.
- Update the current checklist after every LIVE item. Snapshot with `helpers/live-snapshot.sh`. Do not mark B02 `VERIFIED` from this file.
