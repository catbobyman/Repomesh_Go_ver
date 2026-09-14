# Unconfigured login

Unconfigured login shows that Web can serve the login shell when no GitHub App file is loaded. The user sees that login is not currently confirmable. The GitHub button is absent. APIs answer `AUTH_NOT_CONFIGURED`.

## Sub-features

- `unconfigured-open` opens `/login` on the isolated origin.
- `unconfigured-session` reads `/api/session` as 503 `AUTH_NOT_CONFIGURED`.
- `unconfigured-retry` clicks `检查当前登录状态` and stays on the same shell.

## How to get to it (user POV)

- Open `http://127.0.0.1:18080/login` after `helpers/launch.sh` with `run_scope: unconfigured-only`. Use the yaml port if it is not 18080.
- Open `/` or `/projects` on that origin. Unauthenticated routes render the same auth shell.

## Driving it with Playwright and curl

Preconditions:

- `helpers/doctor.sh` reports `mode=unconfigured` on the local origin from yaml.
- Origin is the value in `$REPOMESH_VERIFY_STATE/origin`, a loopback HTTP URL.
- No `REPOMESH_AUTH_CONFIG` is set for this process.

- **Open login.** Go to `/login`. Heading `暂时无法确认登录状态` is visible. Button `使用 GitHub 登录` count is 0. Button `检查当前登录状态` is visible.
- **Read session.** `GET /api/session` is 503. Body code is `AUTH_NOT_CONFIGURED`.
- **Read probes.** `GET /healthz` is 200 and `businessReady` is false. `GET /readyz` is 503.
- **Retry.** Click `检查当前登录状态`. The heading stays `暂时无法确认登录状态`.
- **Helper.** `bash .cursor/skills/verify-repomesh/helpers/drive-unconfigured-login.sh`. Exit 0 writes `$REPOMESH_VERIFY_EVIDENCE/proof.json`.

## Gotchas

- A configured process on `:8080` is a different instance. Do not doctor that port for this feature.
- `/api/session` 401 means auth is configured. Stop. This feature is unconfigured only.
- Fixture `browser-check.mjs` later stubs `/api/**`. That stub is not this recipe.
- Do not open `https://repomesh.example.com` for this proof. The skill origin is local HTTP.
