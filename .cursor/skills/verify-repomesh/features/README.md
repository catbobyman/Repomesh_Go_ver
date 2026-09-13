# RepoMesh verification map

This directory is the maintained source for verifying user-facing RepoMesh behavior. Read this index before driving the app. Use the matching feature file as the recipe.

## Baseline preconditions

- Unconfigured UI proofs use an isolated Web on `127.0.0.1:18080` started by `helpers/launch-unconfigured.sh`.
- Live GitHub proofs use the operator packet in the skill, a configured HTTPS origin, and a coordinator you started.
- Run `helpers/doctor.sh` first. Refuse a process you did not start.
- Never drive Vite `http://127.0.0.1:5173` for API or auth claims.
- Never paste secrets into evidence.

## Driving conventions

- Start every recipe from its listed preconditions.
- Click by accessible name. The product UI is Chinese.
- Treat helper invocations as literal.
- Restore fixture data after a mutation. Keep proof artifacts.

## Proof and skip reporting

- Capture the user action and the resulting state.
- UI proof includes a screenshot or the HTML heading plus the matching API body.
- Mutation proof includes a second read.
- Record the feature ID and entry point in `proof.json`.
- Report an unreachable path with the unmet precondition. Do not mark it verified through a different path.

## Feature entry contract

Each feature file starts with an H1 and one paragraph. It then uses exactly these four H2 sections.

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with Playwright and curl`
4. `Gotchas`

## Features

- [Unconfigured login](./unconfigured-login.md) is the isolated no-App UI. This is the default skill proof.
- [Live GitHub auth](./live-github-auth.md) is B02.6 on a real App and HTTPS origin.
- [Repository discovery](./repository-discovery.md) is the signed-in workspace list.
- [Projects](./projects.md) is create, list, and original-operation recovery.
- [Model providers](./model-providers.md) is save and close of a provider. No real model HTTP.
