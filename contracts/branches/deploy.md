# Branch Contract: Deploy

Version: 1.0.0
Status: Active
Role: Deployment Agent

## Scope

- VPS service layout, Nginx and systemd;
- exact-commit deployment;
- health checks and rollback;
- Windows worker package/update flow.

## Invariants

- Do not change worker, API, frontend or governance behavior unless explicitly approved.
- Never expose secrets in repository, logs or output.
- Feature branches must not deploy production.
- Every deployment must identify target, commit, backup/rollback target and acceptance checks.
- Preserve local worker `.env`, model, `.venv`, output and runtime data.

## Validation

Validate configuration syntax where possible, deployment ordering, health probes, rollback path and target isolation.

## Handoff

Report deployed target, commit/version, health evidence, rollback target, changed infrastructure files and remaining user action.