# Model providers

Model providers lets a signed-in user save a vendor key into an isolated vault, close an empty slot, and recover the original save. The product does not send a model HTTP request in the adopted B04 scope.

## Sub-features

- `provider-open` opens `/settings/models`.
- `provider-save` submits `保存供应商`. The key field is cleared after send.
- `provider-validation` keeps the user on `/settings/models` for `422 VALIDATION_FAILED`.
- `provider-close` closes an empty slot so a late save cannot create a new key.

## How to get to it (user POV)

- From the workspace, choose `模型设置`.
- Open `/settings/models`.

## Driving it with Playwright and curl

Preconditions:

- Authenticated session and migrated database.
- No operator model API key is required. A fixture value is enough for save-shape proof.
- Do not send a real provider request.
- On the default local HTTP origin the signed-in recipes are `verified-unreachable`. Prerequisite: HTTPS origin in `auth.json` plus `__Host-` session cookie. Source: `web/src/ModelSettingsPage.tsx`, `internal/web/models.go`.

- **Unconfigured gate.** `helpers/drive-local-gates.sh` opens `/settings/models` on `http://127.0.0.1:<port>`. The page is the auth shell. `GET /api/model-providers` is 503 `AUTH_NOT_CONFIGURED`.
- **Open.** Muted header `模型设置`. Heading `模型连接`. Button `保存供应商` is visible.
- **Invalid save.** Enter `http://` as a key. Stay on `/settings/models`. Alert mentions the save was not accepted. Name and model remain. API key is empty.
- **Valid save.** `POST /api/model-provider-saves` then `GET` the same `saveId`. Close with `POST /api/model-provider-saves/{saveId}/close` when testing the empty-slot race.

## Gotchas

- A real vendor key is out of B04 authorization. Do not collect one for this feature.
- Two different S06 names exist. Vault-root S06 is a PostgreSQL case. Adoption text “不采用 S06” is a later repo-permission gate.
- Browser fixtures in `docs/development/2026-09-13-b04-validation-stay-01/` are the U04.2 stay-on-page proof.
