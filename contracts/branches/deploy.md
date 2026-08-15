# Review Lens: Deployment

Version: 1.1.0
Status: Active
Role: Deployment Review Lens

## Scope

Review deployment/rollback behavior for VPS, Ubuntu Worker/relay and Windows AI Worker within the approved task contours.

## Invariants

- feature branches never deploy production;
- runtime mutation requires a current production safety envelope;
- exact target/source/artifact/rollback identity is explicit;
- local runtime secrets/models/env/output are preserved;
- no secrets are emitted to repository/log evidence;
- independent contours remain independently executable unless approved architecture requires orchestration.

## Checks

Apply `contracts/SEA_SPEED_DELIVERY_POLICY.md`: exact-main provenance, exact `push/main` quality, server-pull/one-command UX where applicable, host identity, backup/rollback, smoke/health and sanitized evidence.

## Output

Return deployment-readiness findings to the Sea Speed Delivery Orchestrator. Do not perform production merely by invoking this lens.
