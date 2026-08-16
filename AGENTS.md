# Sea Speed Agent Entry Point

Status: Active

This file is the concise adapter for coding agents. The canonical rules remain:

- `contracts/SEA_SPEED_GOVERNANCE.md`;
- `contracts/SEA_SPEED_DELIVERY_POLICY.md`;
- `contracts/runtime/SEA_SPEED_TASK_RUNTIME.md`;
- `contracts/runtime/RELEASE_READINESS_GATE.md`.

The canonical SDD entry points are:

- `.specify/memory/constitution.md` for Sea Speed SDD principles;
- `specs/README.md` for the feature-artifact model;
- `specs/<feature>/spec.md` for product intent;
- `specs/<feature>/plan.md` for architecture and decisions;
- `specs/<feature>/tasks.md` for bounded execution.

## Canonical delivery role

The active orchestration role is **Sea Speed Delivery Orchestrator**. It retains one task context from read-only Task Intake through scope lock, implementation coordination, integrity validation, pull request, CI, exact-green-head merge, and every separately authorized runtime contour required for acceptance.

`contracts/branches/project-manager.md` and `docs/agents/PM_BOOTSTRAP.md` are retained compatibility paths. Their active meaning is Delivery Orchestrator, not a separate Project Manager role. Domain files under `contracts/branches/` and `core-release.md` are on-demand review lenses/checklists; they do not create mandatory autonomous-agent handoffs or a second release orchestrator.

## Mandatory operating rules

1. Treat GitHub `main` as the only long-term source of truth.
2. Start implementation from a canonical Issue and an explicit Outcome Contract / Implementation Scope Check.
3. New repository work requires `OUTCOME APPROVED` recorded after the Implementation Scope Check. Historical `COMMIT APPROVED` / `MERGE APPROVED` evidence remains audit history but is not a valid source-authorization model for a new Change Contract.
4. `OUTCOME APPROVED` authorizes the bounded, reversible repository lifecycle for the approved outcome: branch creation, source/SDD writes, commits, integrity checks, PR creation and metadata repair, in-scope CI remediation, and merge of the exact green head when all merge gates remain satisfied. It does not authorize production mutation.
5. For significant implementation/control-plane work, create or update the linked feature specification, plan and tasks in `specs/**`; do not leave accepted product or architecture decisions only in chat, Issue comments or code.
6. Use one fresh branch and one bounded pull request for one canonical task.
7. Stop and obtain fresh authorization before material product-scope expansion, destructive action, secrets/security-boundary changes, protected behavior changes, schema incompatibility, data migration, behavior redesign, or edits under `skills/**`.
8. Keep the PR Change Contract synchronized with the exact Git diff and the derived production-impact class. Significant PRs must also link the active specification with `- Specification: specs/<feature>/spec.md`.
9. Merge requires successful required CI, a fresh head/base check, exact changed-file scope, no unresolved review threads, and an expected-head guard when supported. A still-valid `OUTCOME APPROVED` is sufficient merge authorization.
10. Do not treat merge, packaging, deployment, installation, or runtime acceptance as equivalent states.
11. Feed production acceptance, regressions and architectural learning back into linked feature artifacts when they change accepted behavior or design. After a production failure, audit the full deployment transaction and adjacent stages before the next source fix/retry; do not stop analysis at the last visible failing line.
12. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
13. Production deployment and worker installation are separate protected operations. They require the evidence defined by the delivery policy and a separate production safety-envelope authorization; source Outcome Authorization alone never authorizes production mutation.

## Production runtime contours and admission

Sea Speed has three explicit production runtime contours: **VPS**, **Ubuntu Worker/relay**, and **Windows AI Worker**. A source change may affect one contour or a mixed set. Ubuntu production-impact paths must never be reduced to CONTROL_PLANE merely because they live below `deploy/**`; shared Worker source that affects more than one runtime must declare the exact applicable deployment fields.

Every runtime-impacting change requires a production safety envelope. For VPS, the normal Delivery Orchestrator execution request is a connected-GitHub-Connector comment `DEPLOY VPS <exact-lowercase-sha>` on the open canonical Issue after the durable production authorization is current. The request workflow delegates to the same protected reusable `Deploy VPS` implementation; manual `workflow_dispatch` remains an emergency/operator fallback, not the normal orchestration path. The request comment never replaces production authorization.

Before SSH configuration the protected VPS workflow must reject anything except an already-lowercase full SHA on current `main` first-parent history, require a successful aggregate quality workflow run produced by `push` on `main` for that exact SHA, resolve the canonical Issue through the applicable merged PR, and verify durable exact-SHA production authorization from an authorized actor. Production authorization is stale when its bound Outcome Contract, runtime contours, security impact, deployment target, rollback target, Issue, PR, or source SHA changes.

New deployable provenance uses release manifest v2. It distinguishes the approved Change Contract file set from the actual Git diff and binds canonical Issue/PR, Outcome and Change Contract hashes, artifacts, and quality/exact-artifact evidence. Persisted v1 release/deployment evidence remains readable for rollback compatibility.

The aggregate `quality-integration` workflow executes SDD validation for significant PRs. This is a repository delivery gate; do not infer GitHub branch-protection settings from the workflow itself.

## Delivery quality layer

For every linked significant PR, the active SDD also carries the bounded delivery-quality artifacts enforced by `scripts/ci/validate_sdd.py`: NFR assessment in `spec.md`; risk profile, risk-based test design and correct-course check in `plan.md`; requirements traceability and Definition of Done in `tasks.md`.

Deployment/release changes, deployment workflow changes, Change Contracts with any runtime deployment `REQUIRED`, and `PRODUCTION_LEARNING` additionally require a machine-valid `Deployment transaction audit` in the linked plan. It covers admission, pre-mutation, mutation, verification, state commit, housekeeping, evidence and rollback. A production learning also requires a completed adjacent-stage review, concrete root cause and concrete neighboring-stage findings. Minimal source diff does not mean minimal analysis.

The PR Change Contract declares `Risk profile: REQUIRED|NOT REQUIRED` and a quality verdict. Full risk profiling is required when the change has a security-boundary impact, API/event/state/storage schema impact, destructive/data-migration impact, `MIXED` runtime impact, or an explicitly declared other high-risk trigger. Low-risk work may explicitly declare `NOT REQUIRED`.

Quality verdicts are `PASS`, `CONCERNS`, `FAIL`, and `WAIVED`. `FAIL` blocks PR admission. `WAIVED` requires a durable finding, owner, expiry/review date, compensating controls and remediation target. A waiver is advisory quality disposition only: it never bypasses source authorization, exact scope, runtime-contour, secret, CI, production-authorization, rollback or other hard gates.

Historical SDD directories are not mass-rewritten solely to adopt this layer. When an older feature becomes active significant work again, its linked SDD must be brought to the current quality format inside that task's approved scope.

Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`. `PLAN READY` may be used before repository writes when an implementation plan awaits authorization.
