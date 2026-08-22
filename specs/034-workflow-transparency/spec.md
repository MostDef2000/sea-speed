# Spec 034 — Workflow Transparency Refactor

## Outcome
Make CI/CD workflows transparent and DRY — shared verify-exact-release composite action, remove duplication, disable legacy workflows, add overview doc. No runtime change.

## NFR Assessment
- Security: NONE — no secret or production credential change
- Reliability: PASS — same verification logic, now shared
- Performance: NONE
- Observability: PASS — overview doc improves transparency

## Changed files
- `.github/actions/verify-exact-release/action.yml` (new)
- `.github/workflows/deploy-vps.yml` (edit)
- `.github/workflows/deploy-ubuntu-worker.yml` (edit)
- `docs/WORKFLOW_OVERVIEW.md` (new)

## Out of scope
- Runtime VPS/Ubuntu deploy logic, secrets, production delegation, branch protection, api/frontend/worker.

## Acceptance
- `validate_workflow_policy` PASS, `validate_repo` PASS, 428 tests PASS, Actions shows 6 active workflows, Deploy workflows use shared action.
