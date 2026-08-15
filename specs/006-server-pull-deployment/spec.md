# Feature Specification: Server-Pull Runtime Deployment Handoff

- Feature: 006-server-pull-deployment
- Issue: #135
- Status: Accepted / completed

## Product outcome

Normal VPS and Ubuntu Worker production handoff uses one short target-local bootstrap per deployment contour. Substantive deployment logic is reviewed in the repository at the exact approved/gated SHA rather than pasted as a large chat program or staged transiently on the operator laptop.

## User scenarios

1. Operator opens VPS shell and runs one short bootstrap selecting canonical repo + exact SHA + repo-owned entrypoint.
2. Operator independently opens Ubuntu Worker shell for its contour and runs its exact repo-owned operation.
3. Mixed work keeps independent failure domains and declared rollout order.
4. Missing safe entrypoint blocks production and returns to source lifecycle.
5. Control-laptop artifacts are explicit fallback only.

## Requirements

- canonical GitHub source is authoritative for substantive deployment logic;
- exact approved 40-char main SHA before runtime mutation;
- bootstrap is transport only, not deployment implementation;
- repo entrypoint owns applicable preflight/integrity/host/backup/mutation/health/evidence;
- secrets/protected input remain target-local/trusted UI;
- VPS and Ubuntu Worker remain independently executable contours;
- GitHub Actions may be an additional path, not the only normal path;
- fallback artifacts preserve exact provenance/integrity.

## Acceptance criteria

- Delivery Policy contains server-pull/one-command model.
- Delivery Orchestrator compatibility contract references that canonical policy without duplicating it.
- control-laptop staging is fallback-only.
- Issue #135 closed completed; no runtime deployment required for the contract-only feature.

## Runtime feedback

Runtime acceptance: NOT REQUIRED. The model is now canonical delivery policy and was later exercised by runtime tasks that added missing repo-owned operations when needed.
