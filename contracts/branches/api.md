# Branch Contract: API

Version: 1.0.0
Status: Active
Role: VPS FastAPI Agent

## Scope

- state and events endpoints;
- ROI and speed configuration endpoints;
- media references and storage access;
- API health checks.

## Invariants

- Do not change worker, frontend, deploy or governance files unless explicitly approved.
- API, event, state and storage schema changes require explicit approval and rollout compatibility notes.
- Do not commit secrets or production runtime data.
- Preserve backward compatibility unless an approved migration states otherwise.

## Validation

Run Python syntax/import checks where available, validate affected routes, storage behavior, authentication boundaries and health response.

## Handoff

Report branch, commit, changed files, checks, schema impact, deploy requirement, rollback target and compatibility matrix.