# DR-001: Two-runtime delivery model

Status: Accepted
Date: 2026-07-12

## Decision

Treat VPS deployment and Windows worker update as independent release contours coordinated by one Project Manager and one task runtime.

## Scope

Applies to release classification, CI, merge, deployment evidence, rollback and final user handoff.

## Context

Sea Speed is not a single deployable artifact. The VPS hosts API, storage and frontend, while the Windows laptop runs the AI worker and retains local secrets, model files, virtual environment and runtime output.

## Consequences

- Merge into `main` does not imply either runtime has been updated.
- API/frontend changes normally require VPS deployment.
- Worker changes normally require a Windows worker update.
- Mixed or schema-changing work may require both contours and an explicit rollout order.
- Governance-only changes require neither runtime release.
- Final status must report VPS and worker states separately.
- Rollback evidence is required for every applicable contour.

## Related contracts

- `contracts/SEA_SPEED_GOVERNANCE.md`
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`
- `contracts/runtime/RELEASE_READINESS_GATE.md`
- `contracts/branches/project-manager.md`
- `contracts/branches/core-release.md`