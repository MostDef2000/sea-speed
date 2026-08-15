# DR-004: Delivery Orchestrator convergence

Status: Accepted
Date: 2026-08-15
Issue: #174

## Context

Sea Speed accumulated an active Project Manager -> domain agents -> Review Gate -> Core Release orchestration model while later governance introduced Outcome Authorization, Connector-only lifecycle continuation and three explicit production contours. The old ownership model duplicated state and left active contracts/docs behind executable policy.

## Decision

Use one **Sea Speed Delivery Orchestrator** as the active lifecycle owner from Task Intake through terminal evidence.

- `contracts/branches/project-manager.md` remains a compatibility path for the Delivery Orchestrator.
- `docs/agents/PM_BOOTSTRAP.md` remains a compatibility path with a new canonical Delivery Orchestrator prompt.
- domain contracts and `core-release.md` are on-demand review lenses/checklists; they return findings without taking lifecycle ownership.
- new source work uses `OUTCOME APPROVED`; legacy source/merge phrases remain historical audit evidence only.
- active runtime delivery terminology is VPS, Ubuntu Worker/relay and Windows AI Worker.
- canonical server-pull / fastest-safe operator execution stays in `contracts/SEA_SPEED_DELIVERY_POLICY.md` rather than being duplicated in the orchestration compatibility contract.
- historical Issues, PRs and DR-001/002/003 are not rewritten. This record supersedes only their active orchestration interpretation where it conflicts with current governance.

## Consequences

New task state no longer emits mandatory `HANDOFF_VALIDATED` or `CORE_RELEASE_INTEGRATING` ownership transfers. Specialist review remains available without context loss. SDD/status drift is reconciled from durable evidence while original audit records remain intact.

## Runtime impact

CONTROL_PLANE only. No VPS, Ubuntu Worker/relay or Windows AI Worker production mutation is authorized or required by this decision.
