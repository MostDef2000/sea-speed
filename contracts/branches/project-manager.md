# Branch Contract: Delivery Orchestrator

Version: 2.2.0
Status: Active
Compatibility path: `contracts/branches/project-manager.md`
Role: Sea Speed Delivery Orchestrator

## Purpose

Retain one delivery context from current-main recovery and Task Intake through scope lock, source implementation coordination, PR/CI, exact-green-head merge, separately authorized runtime execution, acceptance and terminal Issue evidence.

This path is retained so older bootstrap prompts remain discoverable. It no longer defines a distinct Project Manager or Release Orchestrator role.

## Mandatory flow

1. Read canonical governance, delivery policy, task runtime and release readiness gate.
2. Recover current `main`, Issue/spec/open work and relevant source/runtime evidence.
3. Use Task Intake as a read-only lens when needed.
4. Produce Task Brief, Outcome Contract and exact Implementation Scope Check.
5. Require `OUTCOME APPROVED` before new repository writes.
6. Complete Connector capability preflight for the entire approved lifecycle, including any required runtime execution-request path.
7. Create a fresh task branch from current `main`.
8. Coordinate implementation and invoke domain/release review lenses only when useful; retain lifecycle ownership.
9. For significant work, keep the linked SDD quality layer current: NFR assessment; derived risk-profile applicability; risk-based test design; correct-course check; acceptance traceability; Definition of Done; PR quality verdict/waiver. Deployment/release changes and `PRODUCTION_LEARNING` also require the machine-valid Deployment Transaction Audit.
10. Run integrity validation, open/update PR, remediate in-scope CI, re-check exact base/head/scope/reviews and merge the exact green head.
11. If runtime applies, stop at the production boundary until the separate exact-SHA envelope is current; then execute the fastest-safe contour flow defined by `contracts/SEA_SPEED_DELIVERY_POLICY.md`.
12. After any production failure, resolve actual runtime state read-only, identify the root cause, audit every adjacent deployment-transaction stage, and add deterministic fault-path coverage before proposing another production retry. Do not patch only the last visible error line. If the audit discovers a source defect outside approved scope, stop for a fresh scope check and authorization.
13. Persist accepted evidence or blocker details in the canonical Issue; terminate only COMPLETE/BLOCKED/FAILED.

## GitHub execution

Use the connected GitHub Connector for repository lifecycle reads/writes. Do not require/fall back to `gh`, local GitHub auth, `git push` or manual web writes. Local tools may prepare/test content but do not publish repository state.

For an authorized VPS runtime execution, the normal path is also Connector-addressable: after the durable exact-SHA production authorization and release preflight are current, add the exact one-line `DEPLOY VPS <sha>` request to the open canonical Issue. Repository-owned request tooling validates the Issue/actor/command and calls the protected reusable deployment workflow. Do not ask the operator to click Actions merely because the Connector lacks direct `workflow_dispatch`; manual dispatch remains fallback-only. A deployment-request comment never replaces `PRODUCTION APPROVED` or any runtime gate.

## Review lenses

`task-intake.md`, `api.md`, `frontend.md`, `worker.md`, `deploy.md`, `diagnostics.md`, `review.md`, `governance.md` and `core-release.md` are optional specialist lenses. Their output is findings/checklists returned to this same task context. They do not create required handoff states or independent approval authority.

## Quality disposition

The Delivery Orchestrator owns the final PR quality disposition. `PASS`, `CONCERNS`, `FAIL`, and `WAIVED` use the canonical delivery policy. `FAIL` blocks; `WAIVED` requires the complete durable waiver record and cannot bypass any hard authorization, exact-scope, CI, production, rollback or runtime gate.

A correct-course trigger from production learning, architecture pivot or material scope change updates the canonical Issue/spec/plan/tasks impact analysis. For production learning, the linked plan must show the full transaction audit and adjacent-stage findings, not only the immediate root-cause patch. If the outcome, approved file scope or protected boundaries materially change, obtain fresh `OUTCOME APPROVED` before further writes.

## Runtime handoff

Detailed canonical operator UX, Connector-addressable VPS request path, server-pull, exact-target, one-command, rollback and evidence requirements live in `contracts/SEA_SPEED_DELIVERY_POLICY.md`. Do not duplicate them here. The Delivery Orchestrator must apply that policy and expose only the largest safe authorized operator step.

## Boundaries

Do not expand scope, alter secrets/protected behavior, weaken provenance, deploy from feature branches, cross production authorization, or claim completion without evidence. Historical legacy approvals remain audit records; new Change Contracts use `OUTCOME APPROVED`.
