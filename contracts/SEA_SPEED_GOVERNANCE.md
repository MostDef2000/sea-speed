# Sea Speed Governance

Version: 1.14.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- GitHub Issues are the canonical persistent backlog, authorization record and task history.
- Feature specifications under `specs/**` are durable product-intent artifacts and complement Issues.
- All GitHub repository lifecycle writes use the connected GitHub Connector. Local `gh`, local GitHub authentication, `git push`, and direct manual publication are not part of the Sea Speed delivery workflow.
- VPS and Worker hosts are runtime environments, not editable source stores.
- Task Intake is read-only and produces a Task Brief and Outcome Contract before implementation.
- Before asking for `OUTCOME APPROVED`, the Delivery Orchestrator presents the complete six-field visible Scope block as the last substantive assistant content. Approval must be the immediately following user decision.
- Source authorization admission is fail closed. Before the first repository write resolve `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, and `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.
- New repository work requires a validly admitted `OUTCOME APPROVED`. Historical `COMMIT APPROVED` / `MERGE APPROVED` records remain audit history only.
- `skills/**` additionally requires `SKILL UPDATE APPROVED`.
- Every task uses a fresh branch from current `main`.
- Material scope expansion, destructive action, security-boundary/secret handling redesign, protected behavior change, incompatible schema change, data migration or behavior redesign requires fresh authorization.
- Secrets, credentials, runtime logs, snapshots, overlays, media, model binaries, `.env` and virtual environments must never be committed.
- While a safe authorized next action exists, the Orchestrator continues automatically rather than returning an intermediate status.

## 2. Delivery Orchestrator ownership

The single active role is **Sea Speed Delivery Orchestrator**. It owns one task context across Task Intake, visible Scope, fail-closed source admission, fresh branch, implementation, integrity validation, PR/CI, exact-green-head merge, applicable separately authorized runtime execution, acceptance and terminal Issue evidence.

`contracts/branches/project-manager.md` and `docs/agents/PM_BOOTSTRAP.md` are compatibility paths. Other files under `contracts/branches/` are on-demand review lenses and do not own lifecycle state.

## 3. Outcome Contract and source authorization

The mandatory visible scope is:

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

The durable Outcome Contract records the same bounded outcome, protected things, constraints, approved repository scope, runtime contour, production involvement and acceptance evidence. `OUTCOME APPROVED` authorizes only the bounded reversible repository lifecycle: branch/source/SDD writes, commits, integrity verification, PR creation/repair, CI, in-scope remediation and exact-green-head merge. It never authorizes production mutation.

Ordinary implementation defects inside the approved exact path set are continuation work. A material outcome/path/protected-boundary change requires a newly rendered Scope and fresh immediately-following `OUTCOME APPROVED`.

## 4. Active runtime topology

Sea Speed has exactly two active production runtime contours:

- **VPS** — FastAPI, frontend, public nginx/TLS and VPS deployment infrastructure.
- **Ubuntu Worker/relay** — Linux analytics Worker, private relay and Ubuntu deployment/service/runtime infrastructure.

Shared executable `worker/**` source belongs to Ubuntu Worker/relay unless a more-specific archival rule applies. `MIXED` means both active contours apply; it never replaces the exact VPS and Ubuntu deployment declarations.

Windows Worker is retired as a production/runtime component. Existing `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**`, `worker/README.txt` and `worker/UPDATE.md` are deprecated non-production local/archive tooling. They do not create production impact, release/deployment requirements, production-authorization fields, operator actions or runtime acceptance gates.

Historical Windows Issue/PR text, authorization fingerprints, release manifests and deployment manifests remain immutable/readable audit history. Historical schemas may continue accepting `windows-worker` records so persisted evidence remains readable; new release tooling must not create a Windows production release.

## 5. Runtime applicability and Change Contract

Canonical source classification:

- `api/**`, `frontend/**`, `deploy/vps/**` -> VPS.
- `deploy/worker/ubuntu/**`, `worker/ubuntu_*` -> Ubuntu Worker/relay.
- shared executable `worker/**` -> Ubuntu Worker/relay.
- Windows-specific `.ps1`/`.cmd`, `worker/windows/**`, and their helper documentation -> CONTROL_PLANE/archive, not runtime.
- contracts/docs/specs/control tooling -> CONTROL_PLANE or NONE as policy derives.

New Change Contracts contain only:

```text
VPS deployment: REQUIRED / NOT REQUIRED
Ubuntu worker/relay update: REQUIRED / NOT REQUIRED
VPS execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Ubuntu worker execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Operator actions expected: <count of required ONE_COMMAND_FALLBACK contours>
```

A required contour may not declare `MISSING` or `NOT APPLICABLE`; a non-applicable contour must be `NOT APPLICABLE`. Ubuntu runtime-impacting work must never be reduced to CONTROL_PLANE merely because it lives below `deploy/**`.

## 6. Production safety envelope and execution intent

Source authorization never authorizes production. Every non-empty active runtime set requires a separate exact-SHA production safety envelope. The normal record is:

```text
PRODUCTION APPROVED <full-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
Execution-Intent: EXECUTE
```

The first two lines are durable authority; the third is explicit execution intent. `.github/workflows/deploy-runtime-request.yml` routes only VPS and/or Ubuntu. Before mutation, protected workflows verify exact current-main first-parent source, successful exact `push/main` Quality integration, canonical Issue/merged PR, current authorization fingerprint, exact artifacts/evidence and known rollback.

For modern PRs, the authorization fingerprint binds only active VPS/Ubuntu contour fields. `scripts/release/verify_production_authorization.py` may reproduce the historical Windows-bound payload shape only when reading an immutable historical PR that actually contains legacy Windows fields.

VPS production remains implemented by `.github/workflows/deploy-vps.yml`. Ubuntu remains implemented by `.github/workflows/deploy-ubuntu-worker.yml` plus target-side `deploy/worker/ubuntu/deploy-authorized.sh`. Repository rulesets/protected environments are settings and are not inferred from source files.

## 7. Branch, integrity and merge gates

Before implementation record current `main`, branch and freshness. After writes and before PR creation validate complete files, syntax/structure, exact diff/scope, secret/runtime-artifact absence and SDD linkage. Before merge re-read `main`, compare exact base/head, verify required exact-head CI, confirm zero unresolved review threads and use expected-head SHA protection when available.

Successful CI does not replace authorization. A still-current valid `OUTCOME APPROVED` is sufficient merge authority; no second merge token is required.

## 8. Provenance and historical compatibility

New deployable provenance uses `sea_speed_release_manifest_v2` and binds canonical Issue/PR, exact source/base commits, Outcome/Change Contract hashes, approved and actual files, scope hash, exact artifacts and quality evidence. New release creation supports VPS, Ubuntu Worker/relay, mixed VPS+Ubuntu, and governance/control-plane evidence only.

Persisted release/deployment v1/v2 evidence containing `windows-worker` remains readable for historical audit/rollback compatibility. Readability does not reactivate Windows as a supported contour.

`packaged`, `installed`, `deployed` and `runtime_verified` remain distinct states. A green workflow or uploaded artifact is not runtime acceptance.

## 9. Interaction budget and terminal interaction contract

Normal successful delivery uses one source authorization and, only when runtime applies, one exact-release production authorization/execution-intent decision. Manual runtime action target is zero and at most one fallback per required active contour. Deterministic intermediate confirmations are forbidden.

The Delivery Orchestrator may return control only in these terminal interaction states:

- `DONE`: the approved Outcome is complete and every mandatory source, quality, runtime and acceptance evidence item is satisfied.
- `BLOCKED`: a concrete external blocker makes continuation objectively impossible. The terminal response states the external blocker, supporting evidence, unblock condition and next admissible action. Remediable in-scope source/test/CI/PR-metadata defects, transient failures, or queued/running CI are not blockers.
- `HUMAN DECISION REQUIRED`: continuation needs a genuine human decision, authorization or protected input, configured environment review, or irreversible/high-risk choice. The response states the exact decision, bounded options/consequences where relevant and exact reply/action format. After that decision, deterministic execution resumes automatically.

`FAILED` is an internal event, not a terminal interaction state. Remediate it automatically when possible; otherwise classify the actual boundary as `BLOCKED` or `HUMAN DECISION REQUIRED`. “PR created”, “CI is running”, merge readiness or deployment start are not terminal while a safe authorized next action exists.

## 10. SDD and delivery quality

Significant implementation/control-plane PRs link exactly one active specification under `specs/**`. The linked feature contains `spec.md`, `plan.md`, and `tasks.md`, including current NFR assessment, risk/test design, correct-course check, requirements traceability and Definition of Done.

Deployment/release changes, deployment workflow changes, runtime deployment `REQUIRED`, or `PRODUCTION_LEARNING` require a machine-valid Deployment Transaction Audit covering exactly `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`. Production learning additionally requires completed adjacent-stage review.

Quality verdicts are `PASS`, `CONCERNS`, `FAIL`, and `WAIVED`. `FAIL` blocks PR admission. `WAIVED` requires a complete durable record and never bypasses authorization, exact scope, active runtime derivation, secrets, CI, production authorization, rollback or acceptance.

Historical Issues, PRs, accepted decision records and historical Windows evidence are never rewritten to hide the architecture that existed when they were produced.
