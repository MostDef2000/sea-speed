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
3. **Before asking the operator to send `OUTCOME APPROVED`, always show a visible Scope block in the conversation.** That block must state the product outcome, exact repository path set, protected/out-of-scope boundaries, runtime/production impact, and acceptance evidence. A bare approval prompt such as “send `OUTCOME APPROVED`” without the immediately preceding scope is forbidden. If re-authorization is required because scope or protected boundaries changed, show the updated scope first and only then request the fresh approval.
4. New repository work requires `OUTCOME APPROVED` recorded after the displayed Implementation Scope Check. Historical `COMMIT APPROVED` / `MERGE APPROVED` evidence remains audit history but is not a valid source-authorization model for a new Change Contract.
5. `OUTCOME APPROVED` authorizes the bounded, reversible repository lifecycle for the approved outcome: branch creation, source/SDD writes, commits, integrity checks, PR creation and metadata repair, in-scope CI remediation, and merge of the exact green head when all merge gates remain satisfied. It does not authorize production mutation. Ordinary defects discovered inside the already approved path set do not consume another source-approval interaction; only material outcome/scope/protected-boundary expansion does.
6. For significant implementation/control-plane work, create or update the linked feature specification, plan and tasks in `specs/**`; do not leave accepted product or architecture decisions only in chat, Issue comments or code.
7. Use one fresh branch and one bounded pull request for one canonical task.
8. Stop and obtain fresh authorization before material product-scope expansion, destructive action, secrets/security-boundary changes, protected behavior changes, schema incompatibility, data migration, behavior redesign, or edits under `skills/**`.
9. Keep the PR Change Contract synchronized with the exact Git diff and the derived production-impact class. Significant PRs must also link the active specification with `- Specification: specs/<feature>/spec.md`. Runtime-impacting Change Contracts also declare a machine-readable execution capability for every contour and an expected operator-action count; a required contour may not declare `MISSING`.
10. Merge requires successful required CI, a fresh head/base check, exact changed-file scope, no unresolved review threads, and an expected-head guard when supported. A still-valid `OUTCOME APPROVED` is sufficient merge authorization.
11. Do not treat merge, packaging, deployment, installation, or runtime acceptance as equivalent states.
12. Feed production acceptance, regressions and architectural learning back into linked feature artifacts when they change accepted behavior or design. After a production failure, audit the full deployment transaction and adjacent stages before the next source fix/retry; do not stop analysis at the last visible failing line.
13. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
14. Production deployment and worker installation are separate protected operations. They require the evidence defined by the delivery policy and a separate production safety-envelope authorization; source Outcome Authorization alone never authorizes production mutation.
15. Normal successful delivery has a two-intent interaction budget: one `OUTCOME APPROVED`, then one exact-release production authorization carrying explicit execution intent. Deterministic internal transitions must not be surfaced as extra confirmation prompts when repository-owned automation can guard them safely.

## Production runtime contours and admission

Sea Speed has three explicit production runtime contours: **VPS**, **Ubuntu Worker/relay**, and **Windows AI Worker**. A source change may affect one contour or a mixed set. Ubuntu production-impact paths must never be reduced to CONTROL_PLANE merely because they live below `deploy/**`; shared Worker source that affects more than one runtime must declare the exact applicable deployment fields.

Every runtime-impacting change requires a production safety envelope. The normal authorize-and-execute record is the exact three-line canonical Issue comment:

```text
PRODUCTION APPROVED <exact-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
Execution-Intent: EXECUTE
```

The first two lines are durable production authority. The third line is explicit execution intent. Omitting the third line remains authorize-only and must not trigger runtime mutation. `.github/workflows/deploy-runtime-request.yml` parses/re-verifies this record and routes only the exact runtime contours declared by the merged Change Contract. Legacy `DEPLOY VPS <sha>` remains a compatible VPS execution-request path; it does not replace production authorization.

For Ubuntu Worker/relay, `.github/workflows/deploy-ubuntu-worker.yml` is the protected reusable orchestration path and `deploy/worker/ubuntu/deploy-authorized.sh` is the repository-owned target transaction. If a separately provisioned restricted production transport is available, the workflow may execute zero-touch. If it is not available, the workflow produces one exact operator bootstrap that stages the authorized SHA and hands off to the repository entrypoint; preparation and activation must not be exposed as separate confirmations.

Before any protected workflow configures SSH or otherwise crosses the runtime boundary it must reject anything except an already-lowercase full SHA on current `main` first-parent history, require a successful aggregate quality workflow run produced by `push` on `main` for that exact SHA, resolve the canonical Issue through the applicable merged PR, and verify durable exact-SHA production authorization from an authorized actor. Production authorization is stale when its bound Outcome Contract, runtime contours, security impact, deployment target, rollback target, Issue, PR, or source SHA changes.

New deployable provenance uses release manifest v2. It distinguishes the approved Change Contract file set from the actual Git diff and binds canonical Issue/PR, Outcome and Change Contract hashes, artifacts, and quality/exact-artifact evidence. Persisted v1 release/deployment evidence remains readable for rollback compatibility.

The aggregate `quality-integration` workflow executes SDD validation for significant PRs. This is a repository delivery gate; do not infer GitHub branch-protection settings from the workflow itself.

## Interaction budget

For a normal task, expose no more human checkpoints than the protected decisions actually require:

```text
Source authorization: 1
Production authorization + execution intent: 1 per exact release
Manual runtime commands: 0 target; <=1 fallback per required contour
Intermediate deterministic confirmations: FORBIDDEN
```

The source-authorization interaction itself has a mandatory presentation order: **Scope first, approval second**. The scope must be visible to the operator before the approval token is requested; the approval token must never be requested as a standalone prompt with the scope only implicit in prior internal reasoning.

Additional user interaction is justified only by a material scope/protected-boundary change, a new exact SHA after source remediation, secret/password/sudo/TOTP entry, irreversible/high-risk decision, configured environment reviewer, or evidence that cannot safely be collected by repository automation. A completed preparation stage is not by itself a reason to ask for permission to activate when the same authorized transaction can guard activation and rollback.

## Delivery quality layer

For every linked significant PR, the active SDD also carries the bounded delivery-quality artifacts enforced by `scripts/ci/validate_sdd.py`: NFR assessment in `spec.md`; risk profile, risk-based test design and correct-course check in `plan.md`; requirements traceability and Definition of Done in `tasks.md`.

Deployment/release changes, deployment workflow changes, Change Contracts with any runtime deployment `REQUIRED`, and `PRODUCTION_LEARNING` additionally require a machine-valid `Deployment transaction audit` in the linked plan. It covers admission, pre-mutation, mutation, verification, state commit, housekeeping, evidence and rollback. A production learning also requires a completed adjacent-stage review, concrete root cause and concrete neighboring-stage findings. Minimal source diff does not mean minimal analysis.

The PR Change Contract declares `Risk profile: REQUIRED|NOT REQUIRED` and a quality verdict. Full risk profiling is required when the change has a security-boundary impact, API/event/state/storage schema impact, destructive/data-migration impact, `MIXED` runtime impact, or an explicitly declared other high-risk trigger. Low-risk work may explicitly declare `NOT REQUIRED`.

Quality verdicts are `PASS`, `CONCERNS`, `FAIL`, and `WAIVED`. `FAIL` blocks PR admission. `WAIVED` requires a durable finding, owner, expiry/review date, compensating controls and remediation target. A waiver is advisory quality disposition only: it never bypasses source authorization, exact scope, runtime-contour, secret, CI, production-authorization, rollback or other hard gates.

Historical SDD directories are not mass-rewritten solely to adopt this layer. When an older feature becomes active significant work again, its linked SDD must be brought to the current quality format inside that task's approved scope.

Valid terminal execution states are `COMPLETE`, `BLOCKED`, and `FAILED`. `PLAN READY` may be used before repository writes when an implementation plan awaits authorization.
