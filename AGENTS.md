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
11. Feed production acceptance, regressions and architectural learning back into linked feature artifacts when they change accepted behavior or design. Historical Issues/PRs/decision records remain immutable audit evidence.
12. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
13. Production deployment and worker installation are separate protected operations. They require the evidence defined by the delivery policy and a separate production safety-envelope authorization; source Outcome Authorization alone never authorizes production mutation.

## Production runtime contours and admission

Sea Speed has three explicit production runtime contours: **VPS**, **Ubuntu Worker/relay**, and **Windows AI Worker**. A source change may affect one contour or a mixed set. Ubuntu production-impact paths must never be reduced to CONTROL_PLANE merely because they live below `deploy/**`; shared Worker source that affects more than one runtime must declare the exact applicable deployment fields.

Every runtime-impacting change requires a production safety envelope. VPS production dispatch remains manual and protected by the `production` environment. Before SSH configuration it must reject anything except an already-lowercase full SHA on current `main` first-parent history, require a successful aggregate quality workflow run produced by `push` on `main` for that exact SHA, resolve the canonical Issue through the applicable merged PR, and verify durable exact-SHA production authorization from an authorized actor. Production authorization is stale when its bound Outcome Contract, runtime contours, security impact, deployment target, rollback target, Issue, PR, or source SHA changes.

New deployable provenance uses release manifest v2. It distinguishes the approved Change Contract file set from the actual Git diff and binds canonical Issue/PR, Outcome and Change Contract hashes, artifacts, and quality/exact-artifact evidence. Persisted v1 release/deployment evidence remains readable for rollback compatibility.

The aggregate `quality-integration` workflow executes SDD validation for significant PRs. This is a repository delivery gate; do not infer GitHub branch-protection settings from the workflow itself.

Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`. `PLAN READY` may be used before repository writes when an implementation plan awaits authorization.
