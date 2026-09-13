# Repository discovery

Repository discovery is the signed-in home page. The user sees the current account, GitHub connection status, and repositories whose user-read qualification has been verified. App work capability is a separate pill.

## Sub-features

- `home-account` shows `session.user.displayName` and connection status.
- `home-list` lists verified-readable repositories with App capability pills.
- `home-search` filters the current discovery result.
- `home-pages` walks `下一页` and `上一页` while `coverage` stays honest.
- `home-refresh` clicks `重新发现`.

## How to get to it (user POV)

- After a confirmed login, open `/` or choose `稍后处理，返回工作区`.
- Choose brand `RepoMesh` from an inner page.

## Driving it with Playwright and curl

Preconditions:

- Live session cookie is present. `/api/session` is 200.
- Doctor is live mode.

- **Open home.** Heading `仓库与账号连接`. Pill `已登录` is visible.
- **List.** `GET /api/repositories` returns items and `coverage`. End page is `partial` unless the product later changes that rule.
- **Search.** Fill `#repository-search` and submit `搜索`. Names in the list match the query or the empty copy appears.
- **Reconnect entry.** Button `重新连接 GitHub` goes to `/login` in reconnect mode.

## Gotchas

- Unconfigured Web never reaches this page.
- Names appear only after user-read verification. Unconfirmed selections hide names.
- A 60 second user-read cache is real. Immediate recheck after a GitHub permission change is not a new observation.
- Do not record repository names of private fixtures in shared evidence. Stable IDs are enough.
