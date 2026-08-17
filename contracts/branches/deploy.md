# Review Lens: Deployment

Version: 1.2.0
Status: Active
Role: Deployment Review Lens

## Scope

Review deployment/rollback behavior for the two active production contours: VPS and Ubuntu Worker/relay. Return findings to the Sea Speed Delivery Orchestrator.

## Invariants

- feature branches never deploy production;
- runtime mutation requires a current production safety envelope;
- exact target/source/artifact/rollback identity is explicit;
- local runtime secrets/models/env/output are preserved;
- no secrets are emitted to repository/log evidence;
- active contours remain independently executable unless approved architecture requires orchestration;
- retired Windows local/archive tooling is never treated as a production deployment target.

## Checks

Apply `contracts/SEA_SPEED_DELIVERY_POLICY.md`: exact-main provenance, exact `push/main` quality, server-pull/one-command UX where applicable, host identity, backup/rollback, smoke/health and sanitized evidence. Historical Windows deployment manifests may be read for audit/rollback history but do not create a new execution path.

## Output

Return deployment-readiness findings to the **Sea Speed Delivery Orchestrator**. Do not perform production merely by invoking this lens.
