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

## How to get to it (user POV)

- Open `<origin>/login` on the configured HTTPS origin.
- Choose `使用 GitHub 登录`.
- On github.com, Cancel or Authorize. The account holder does this.
- Land on `/auth/result/{attemptId}`. Choose `查询本次授权结果` or `确认当前账号，继续`.
- From the workspace, choose `重新连接 GitHub` for reconnect.
- Choose `退出登录` to end the session.

## Driving it with Playwright and curl

Preconditions:

- Operator packet in the skill is in place. Secrets are files, not chat text.
- Web and coordinator share `REPOMESH_DATABASE_URL` and `REPOMESH_AUTH_CONFIG`.
- Doctor on the HTTPS origin reports live mode. `/api/session` is 401 `AUTHENTICATION_REQUIRED`.
- New evidence directory under `docs/development/`. Old LIVE folders stay untouched.
- Account A only.

- **Entry.** Open `/login`. Heading `开始使用 RepoMesh`. Click `使用 GitHub 登录`. Browser leaves for `https://github.com/login/oauth/authorize`.
- **Cancel.** Holder clicks Cancel. Callback 303 to `/auth/result/{id}` with no query. Attempt `cancelled/USER_CANCELLED`. `/api/session` still 401.
- **Authorize.** New login. Callback 303, attempt `confirmed`, `/api/session` 200 for account A. URL has no `code` or `state`.
- **Reconnect.** Click `重新连接同一账号`. Same `user.id`. Connection revision and `access_epoch` advance. Old generation revoked.
- **Refresh.** Keep the same connection until the natural window. Do not edit database expiry. Proof is two read-only connection snapshots plus a new discovery.
- **Logout.** `退出登录` returns 204. `/api/session` is 401. Workspace no longer lists repositories.

Record each LIVE id in the new template. Independent review is still required before B02 `VERIFIED`.

## Gotchas

- Vite and `http://127.0.0.1:8080` cannot prove `__Host-` cookies.
- Installation-complete on GitHub is not a RepoMesh login. Start from the product button.
- GitHub auto-consent can skip the Cancel page. Then `live-02` stays uncovered.
- First discovery 503 is `RESULT_UNCONFIRMED`. Re-read the same query. Do not swap in a fixture.
- `coverage=partial` is expected. An out-of-install private repo missing from the list is not a `denied` sample.
- Retained PASS for LIVE-01 through 04, 06, 07, 09, 10 does not reopen those items unless the operator asks.
- Restore leftovers from `second-account-02` need a separate authorized restore task.
