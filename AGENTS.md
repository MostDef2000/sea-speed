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
3. Before asking the operator to send `OUTCOME APPROVED`, always show a visible Scope block in the conversation. It states product outcome, exact repository path set, protected/out-of-scope boundaries, runtime/production impact, and acceptance evidence. The Scope block is the last substantive assistant content before the approval request, and the valid approval arrives in the immediately following user turn.
4. Treat source authorization admission as fail closed. Before the first repository write resolve `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`. Missing, stale, incomplete, or non-adjacent scope evidence leaves admission blocked.
5. New repository work requires `OUTCOME APPROVED` recorded after the displayed Implementation Scope Check. Historical `COMMIT APPROVED` / `MERGE APPROVED` evidence remains audit history only.
6. `OUTCOME APPROVED` authorizes the bounded reversible repository lifecycle for the approved outcome: branch creation, source/SDD writes, commits, integrity checks, PR creation and metadata repair, in-scope CI remediation, and merge of the exact green head when all merge gates remain satisfied. It does not authorize production mutation.
7. Significant implementation/control-plane work creates or updates linked `spec.md`, `plan.md`, and `tasks.md` under `specs/**`.
8. Use one fresh branch and one bounded pull request for one canonical task.
9. Obtain fresh authorization before material product-scope expansion, destructive action, secret/security-boundary change, protected behavior change, schema incompatibility, data migration, behavior redesign, or edits under `skills/**`.
10. Keep the PR Change Contract synchronized with the exact Git diff and derived production-impact class. Significant PRs link the active specification. Runtime-impacting Change Contracts declare execution capability for every active runtime contour and an exact operator-action count; a required contour may not declare `MISSING`.
11. Merge requires successful required CI, fresh head/base check, exact changed-file scope, no unresolved review threads, and an expected-head guard when supported. A still-valid `OUTCOME APPROVED` is sufficient merge authorization.
12. Merge, packaging, deployment, installation and runtime acceptance are distinct states.
13. Feed production acceptance, regressions and architecture learning back into linked feature artifacts. After a production failure audit the full deployment transaction and adjacent stages before retry.
14. Never commit secrets, local runtime data, private media, model binaries, `.env`, virtual environments, snapshots, overlays, logs, or generated output.
15. Production deployment and Worker installation are protected operations requiring a separate exact-SHA production safety envelope; source authorization alone never authorizes runtime mutation.
16. Normal successful delivery has a two-intent interaction budget: one `OUTCOME APPROVED`, then one exact-release production authorization carrying explicit execution intent.
17. Never return control merely because a deterministic internal stage completed or failed. While a safe authorized next action exists, continue automatically until the terminal interaction contract is satisfied.
18. Tool routing is deny by default. A tool, connector, service, CLI, side-channel, publication path or runtime mutation path is permitted only when the Tool Routing Allowlist explicitly lists it for the current task class; availability alone never grants permission.

## Production runtime contours and admission

Sea Speed has exactly two active production runtime contours: **VPS** and **Ubuntu Worker/relay**. Shared executable `worker/**` source belongs to the Ubuntu Worker runtime unless a more-specific non-runtime archival rule applies. A change that affects both VPS and Ubuntu is summarized as `MIXED`, while the exact two deployment fields remain authoritative.

Windows Worker is retired as a production/runtime component. Existing `worker/*.cmd`, `worker/*.ps1`, `worker/windows/**`, `worker/README.txt`, and `worker/UPDATE.md` are deprecated local/archive tooling only. They do not create a runtime contour, release requirement, deployment action, production authorization field, or acceptance gate. Historical Issues, PRs, authorization fingerprints, release manifests and deployment manifests that contain Windows evidence remain immutable/readable audit history and are not rewritten.

Every active runtime-impacting change requires a production safety envelope. The normal authorize-and-execute record is the exact three-line canonical Issue comment:

```text
PRODUCTION APPROVED <exact-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
Execution-Intent: EXECUTE
```

The first two lines are durable production authority. The third line is explicit execution intent. Omitting the third line remains authorize-only and must not trigger runtime mutation. `.github/workflows/deploy-runtime-request.yml` parses/re-verifies this record and routes only VPS and/or Ubuntu according to the exact merged Change Contract. Legacy `DEPLOY VPS <sha>` remains a compatible VPS execution-request path; it does not replace production authorization.

For Ubuntu Worker/relay, `.github/workflows/deploy-ubuntu-worker.yml` is the protected reusable orchestration path and `deploy/worker/ubuntu/deploy-authorized.sh` is the repository-owned target transaction. If separately provisioned restricted production transport is unavailable, the workflow may produce one exact operator bootstrap that stages the authorized SHA and hands off to the repository entrypoint.

Before protected workflows cross a runtime boundary they reject anything except an already-lowercase full SHA on current `main` first-parent history, require successful aggregate quality from `push` on `main` for that exact SHA, resolve the canonical Issue through the applicable merged PR, and verify durable exact-SHA production authorization from an authorized actor. Production authorization is stale when its bound Outcome Contract, active runtime contours, security impact, deployment target, rollback target, Issue, PR, or source SHA changes.

New deployable provenance uses release manifest v2. It binds canonical Issue/PR, Outcome and Change Contract hashes, approved versus actual files, artifacts and quality/exact-artifact evidence. New release creation supports active components only; persisted historical release/deployment evidence, including Windows records, remains readable for rollback/audit compatibility.

The aggregate `quality-integration` workflow executes SDD validation for significant PRs. Workflow presence does not prove GitHub branch-protection settings.

## Tool Routing Allowlist — DENY BY DEFAULT

This allowlist is closed. For Sea Speed development, CI, release, deployment, diagnostics and evidence collection, anything not explicitly permitted below is forbidden. Installed or connected capability is not authorization. Fallbacks are valid only for the exact task row that declares them and never generalize by analogy.

If the primary route is unavailable and the row has no allowed fallback, or the allowed fallback cannot complete safely, do not discover another connector/service/CLI. Return `HUMAN DECISION REQUIRED` with the exact missing capability.

| Task class | Allowed primary route | Allowed fallback |
|---|---|---|
| GitHub repository lifecycle: repo/Issue/PR/comments/branches/source publication/merge | GitHub Connector | NONE |
| CI status/jobs/logs/artifacts | GitHub Connector | One bounded read-only GitHub API/PowerShell command to the operator only when the exact Connector endpoint is unavailable |
| Patch/build/test/hash/static analysis | Ephemeral local tooling/container | User checkout when required for preparation/validation; never publication or production mutation |
| Public `mostdef.ru` / Sea Speed HTTP verification | Read-only HTTP/web | One bounded read-only `curl`/PowerShell command to the operator |
| External technical documentation | Read-only web using primary/official sources only | NONE |
| User-provided logs/screenshots/config/files | Read the provided material directly | NONE |
| Production authorization | Exact three-line canonical Issue record through GitHub Connector | NONE |
| VPS deployment | GitHub Actions -> `.github/workflows/deploy-vps.yml` | Only a repository-owned VPS action explicitly exposed by the canonical deployment path |
| Ubuntu deployment | GitHub Actions -> `.github/workflows/deploy-ubuntu-worker.yml` -> `deploy/worker/ubuntu/deploy-authorized.sh` | Only the repository-owned sudo/root bootstrap explicitly emitted by the canonical path |
| VPS/Ubuntu runtime diagnostics | Repository-owned diagnostic/deployment tooling | One bounded read-only command to the operator on the corresponding host |
| Password/sudo/TOTP/SSH trust/credentials/tokens | Operator enters locally into the intended prompt/secret store | NONE; protected values never enter chat or Git |

Explicit forbidden implicit fallbacks include Gmail, Calendar, Drive, Notion, `gh`, local GitHub authentication, assistant-side `git push`, manual GitHub web publication, ad-hoc SSH/shell exploration, direct database mutation, cloud-console mutation, and every other unlisted connector/plugin/service.

Local ephemeral tooling is computation only. It may prepare or validate bytes but never becomes the repository publication control plane or a production mutation authority.

A future need for an unlisted tool or service requires a new visible Scope and source authorization that changes the allowlist; a one-off conversational convenience does not silently amend it.

## Interaction budget

For a normal task:

```text
Scope presentation: mandatory immediately preceding assistant turn
Source authorization: 1
Production authorization + execution intent: 1 per exact release
Manual runtime commands: 0 target; <=1 fallback per required active contour
Intermediate deterministic confirmations: FORBIDDEN
```

Additional user interaction is justified only by a material scope/protected-boundary change, a new exact SHA after source remediation, secret/password/sudo/TOTP entry, irreversible/high-risk decision, configured environment reviewer, or evidence that repository automation cannot safely collect.

## Terminal interaction contract

The Delivery Orchestrator may return control only in exactly one terminal interaction state:

- `DONE`: the approved Outcome is complete and all mandatory source, quality, runtime and acceptance evidence is satisfied.
- `BLOCKED`: continuation is objectively impossible because of a concrete external blocker outside the Orchestrator's authorized deterministic control. The response identifies the external blocker, supporting evidence, unblock condition, and next admissible action. An in-scope source defect, test failure, CI failure, PR metadata defect or transient deterministic failure that can be remediated is not `BLOCKED`.
- `HUMAN DECISION REQUIRED`: continuation requires a genuine human decision, authorization or protected input, configured environment review, or irreversible/high-risk choice. The response states the exact decision, bounded alternatives/consequences when relevant, and the exact reply/action format. After the decision the Orchestrator resumes deterministic execution automatically.

`FAILED` is an event, not a terminal interaction state. Remediate it automatically when possible; otherwise classify the actual boundary as `BLOCKED` or `HUMAN DECISION REQUIRED`. Progress-only states such as “PR created”, “CI is running”, queued/running CI, merge readiness or deployment start are not terminal while a safe authorized next action exists.

## Delivery quality layer

For every linked significant PR, the active SDD carries NFR assessment in `spec.md`; risk profile, risk-based test design and correct-course check in `plan.md`; acceptance traceability and Definition of Done in `tasks.md`.

Deployment/release changes, deployment workflow changes, Change Contracts with any runtime deployment `REQUIRED`, and `PRODUCTION_LEARNING` additionally require a machine-valid Deployment Transaction Audit covering admission, pre-mutation, mutation, verification, state commit, housekeeping, evidence and rollback. Production learning also requires completed adjacent-stage review and concrete root cause/findings.

The PR Change Contract declares `Risk profile: REQUIRED|NOT REQUIRED` and a quality verdict. Full risk profiling is required for security-boundary impact, API/event/state/storage schema impact, destructive/data migration, `MIXED` runtime impact, or another explicit high-risk trigger.

Quality verdicts are `PASS`, `CONCERNS`, `FAIL`, and `WAIVED`. `FAIL` blocks PR admission. `WAIVED` requires a complete durable record and never bypasses source authorization, exact scope, active runtime contour derivation, secret, CI, production authorization, rollback or acceptance gates.

Only `DONE`, `BLOCKED`, and `HUMAN DECISION REQUIRED` are valid terminal interaction states. `PLAN READY` may be used only as a non-terminal planning label before repository writes when implementation awaits authorization.
