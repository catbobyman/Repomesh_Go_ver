# Projects

Projects lets the signed-in user save a pending-configuration project, list it, edit metadata, add repositories explicitly, and recover the original operation by key. It does not create Issues or start runs.

## Sub-features

- `project-list` opens `/projects` (`web/src/ProjectsPage.tsx`).
- `project-create` walks `/projects/new` through repository pick, details, and `查看保存摘要` (`web/src/CreateProjectPage.tsx`).
- `project-detail` opens `/projects/{id}` (`web/src/ProjectPage.tsx`).
- `project-settings` opens `/projects/{id}/settings` to edit metadata and add repositories (`web/src/ProjectSettingsPage.tsx`).
- `project-empty-catalog` saves a project when no model catalog exists.
- `project-recover` opens the original-operation page after a dropped response (`web/src/ProjectOperationPage.tsx`).

## How to get to it (user POV)

- From the workspace, choose `项目` or `新建项目`.
- Open `/projects` or `/projects/new`.
- From a project row, open the project, then settings.

## Driving it with Playwright and curl

Preconditions:

- Authenticated session.
- For HTTP-accurate local proof against real handlers and a GitHub test provider, the product B03 Playwright runner with `REPOMESH_B03_BROWSER_TEST=1` still exists. That runner is not this skill's launch model and is not github.com.
- On the default local HTTP origin the signed-in recipes are `verified-unreachable`. Prerequisite: HTTPS origin in `auth.json` plus `__Host-` session cookie. Source: `internal/web/projects.go`, `web/src/main.tsx`.

- **Unconfigured gate.** `helpers/drive-local-gates.sh` opens `/projects` and `/projects/new` on `http://127.0.0.1:<port>`. Both render the auth shell. `GET /api/projects` is 503 `AUTH_NOT_CONFIGURED`.
- **List.** Heading `项目`. Empty copy is `还没有项目` or a real list.
- **Create.** Button `新建项目`. Pick repositories with `#project-repository-search`. Choose `完成选择`. Fill 项目资料. Choose `查看保存摘要`, then the primary save. Result is 201 or idempotent 200, `canCreateIssue=false`.
- **Empty catalog.** Same create with no provider rows. Project stays 待配置.

## Gotchas

- Fixture GitHub is not B02 live.
- `PROJECT_UPDATE_NOT_ALLOWED` in the B03 browser script is a client fulfill. It is not a real server-role proof.
- Do not claim Issue or run success. Footer copy says those are unimplemented.
