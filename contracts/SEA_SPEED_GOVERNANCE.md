# Sea Speed Governance

Version: 1.12.0
Status: Active
Source of truth: GitHub `main`

## 1. Core rules

- `main` is the only long-term source of truth.
- GitHub Issues are the canonical persistent backlog, authorization record and task history. Chat context may assist execution but must not replace durable Issue state for implementation work.
- Feature specifications under `specs/**` are durable product-intent artifacts. They complement Issues and do not replace governance contracts.
- All GitHub repository lifecycle writes use the connected GitHub Connector. GitHub CLI `gh`, local GitHub authentication, `git push`, and direct local publication are not part of the Sea Speed delivery workflow.
- VPS and worker hosts are runtime environments, not editable source stores.
- Task Intake is read-only and produces a canonical Task Brief plus an Outcome Contract before implementation.
- Before asking the operator to issue `OUTCOME APPROVED`, the Delivery Orchestrator MUST first present a visible Scope block containing the product outcome, exact repository paths, protected/out-of-scope boundaries, runtime/production impact and acceptance evidence. The Scope block MUST be the last substantive assistant content before the approval request, and the approval MUST be supplied in the immediately following user turn. A bare approval prompt without that displayed scope is not valid Task Intake completion.
- Source authorization admission is fail closed. A new or fresh `OUTCOME APPROVED` presented without the immediately preceding complete six-field Scope block is invalid for source execution even if an older scope exists elsewhere in the conversation. In that case the Orchestrator MUST perform no branch/source write, return to `DISCUSSION`, present the full Scope again, and request a new approval.
- Before the first repository write, source admission MUST resolve both `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`.
- New repository work requires `OUTCOME APPROVED` issued after the displayed Implementation Scope Check and valid admission sequence. Historical `COMMIT APPROVED` / `MERGE APPROVED` records remain valid audit evidence for the tasks that used them, but are not accepted as the source-authorization declaration of a new pull request.
- Changes under `skills/**` additionally require `SKILL UPDATE APPROVED`.
- Every task uses a fresh branch created from current `main`.
- Material product-scope expansion, destructive action, secret use/security-boundary change, protected behavior change, schema incompatibility, data migration, or behavior redesign requires fresh authorization.
- Secrets, credentials, runtime logs, snapshots, overlays, videos, model binaries, `.env`, and local virtual environments must never be committed.

## 2. Delivery Orchestrator ownership

The single active delivery role is **Sea Speed Delivery Orchestrator**. It owns one task context across:

```text
read-only Task Intake
-> Outcome Contract / visible Implementation Scope Check
-> fail-closed source authorization admission
-> capability preflight
-> fresh branch
-> implementation coordination
-> integrity verification
-> pull request
-> CI and in-scope remediation
-> exact-green-head merge
-> applicable release readiness
-> separately authorized production execution
-> runtime acceptance
-> terminal Issue evidence
```

`contracts/branches/project-manager.md` is retained as a compatibility path for this role. `docs/agents/PM_BOOTSTRAP.md` is likewise a compatibility entrypoint. Files under `contracts/branches/` and `contracts/branches/core-release.md` are on-demand review lenses/checklists. They may contribute specialized findings, but they do not own separate branch/PR/merge state and do not require a handoff that discards the Delivery Orchestrator context.

## 3. Outcome Contract and source authorization

Before source authorization, the Delivery Orchestrator records a concise Outcome Contract in the canonical Issue or equivalent durable task record and presents the same bounded scope visibly to the operator before requesting approval:

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

The visible Scope block is mandatory immediately before the authorization request. The Orchestrator MUST NOT request `OUTCOME APPROVED` by itself, MUST NOT rely on unshown internal reasoning as the scope, MUST NOT ask the operator to infer the approved paths from prior discussion, and MUST NOT treat a non-adjacent earlier Scope block as sufficient admission evidence. The complete Scope block must be the final substantive assistant block before the approval request; the next user decision supplies the token.

A source approval sequence is invalid when any of the following is true: the immediately preceding assistant turn has no Scope block; any of the six fields is missing or materially ambiguous; the scope shown is stale relative to the requested outcome; substantive assistant content intervenes after the Scope block in a way that changes or obscures what is being approved; or the approval token is being reused for a materially revised scope. Invalid approval leaves the task in `DISCUSSION`; branch creation and source writes are prohibited until the Orchestrator re-renders the complete current Scope and obtains a fresh immediately-following approval.

If a re-authorization trigger changes the outcome, path set, runtime contour or protected boundary, the updated Scope block MUST be shown before requesting a fresh `OUTCOME APPROVED` and the same adjacency rule applies.

The durable Outcome Contract remains:

```text
Outcome Contract
- Product outcome:
- Protected things that must not change:
- Main constraints:
- Approved repository scope:
- Runtime contour:
- Production involved: YES/NO
- Acceptance evidence:
```

`OUTCOME APPROVED` authorizes the complete bounded, reversible repository lifecycle needed to deliver that Outcome Contract only after fail-closed source admission succeeds:

```text
fresh branch
-> source/SDD writes
-> commits
-> integrity verification
-> pull request
-> PR metadata correction
-> CI validation
-> in-scope CI remediation
-> exact-green-head merge
```

The authorization remains current while the canonical Issue/product outcome, approved file scope, runtime contours and protected boundaries remain unchanged and all merge gates are satisfied. Ordinary defects and CI findings that can be corrected entirely inside that authorized path set are continuation work, not a new approval event. A material change to outcome, approved paths or protected/security semantics requires fresh authorization.

## 4. Controlled delivery, interaction budget and capability preflight

After valid source authorization, the Delivery Orchestrator continues through every deterministic safe repository transition without another routine approval prompt. Do not stop at commit, PR, CI, merge, package creation, deployment preparation, deployment start or process start when the next transition is already authorized and technically guarded.

The normal interaction budget is:

```text
scope presentation: mandatory immediately preceding assistant turn
source intent: one OUTCOME APPROVED after that Scope block
production intent: one exact-release authorization carrying Execution-Intent: EXECUTE
manual runtime action: zero target; at most one fallback action per required contour
intermediate deterministic confirmations: none
```

Extra interaction is allowed only for a material reauthorization trigger, a new exact release SHA after source remediation, protected secret/password/sudo/TOTP entry, irreversible/high-risk decision, configured environment reviewer, or evidence that automation cannot safely collect.

Before the first repository write verify that the complete approved lifecycle is feasible through the GitHub Connector and repository-owned execution paths and verify source authorization admission itself: `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, current Scope matches the durable Outcome Contract, and the supplied `OUTCOME APPROVED` applies to that exact scope. Any `NO`, unknown, stale, or ambiguous value blocks implementation. After admission succeeds, required files must be readable/writable; Issue/branch/commit/PR/CI/review/merge operations must be available; the complete mandatory scope must be deliverable; and applicable runtime execution, rollback and acceptance paths must be known. Missing `gh`, local Git credentials or a local remote is not a blocker.

Every runtime-impacting Change Contract declares the execution capability for VPS, Ubuntu Worker/relay and Windows AI Worker using `CONNECTOR`, `ONE_COMMAND_FALLBACK`, `MISSING`, or `NOT APPLICABLE`, plus the exact number of operator actions expected after production intent. A contour marked `REQUIRED` may not be admitted with `MISSING` or `NOT APPLICABLE`. The operator-action count equals the number of required `ONE_COMMAND_FALLBACK` contours.

If a mandatory Connector operation is unavailable but a repository-owned one-command runtime fallback exists, the task may continue with that declared fallback. If no safe execution path exists for a required contour, stop `BLOCKED` before partial delivery.

## 5. Branch and merge policy

Before implementation record current `main`, task branch, branch head and freshness. Before merge re-read current `main`, compare exact base/head scope, verify required exact-head checks, confirm zero unresolved review threads, and use expected-head-SHA protection when supported.

Successful CI is necessary but does not replace authorization. For new tasks a still-current, validly admitted `OUTCOME APPROVED` is the merge authorization; no second merge phrase is required. Historical tasks that used legacy tokens remain historical and are not reinterpreted.

## 6. Domain and runtime boundaries

- `worker/**`: Worker runtime source; specific path rules determine Ubuntu Worker/relay, Windows AI Worker, or shared/mixed applicability.
- `api/**`: VPS FastAPI backend.
- `frontend/**`: operator UI.
- `deploy/vps/**`: VPS deployment/service/health/rollback infrastructure.
- `deploy/worker/ubuntu/**`: Ubuntu Worker/relay deployment/service/health/rollback infrastructure.
- `schemas/**`: release, deployment and telemetry contracts.
- `contracts/**`, `docs/**`, `specs/**`, `.specify/**`, `skills/**`: governance, SDD and documentation.

The explicit production runtime contours are **VPS**, **Ubuntu Worker/relay**, and **Windows AI Worker**. `MIXED` summarizes two or more applicable contours but never replaces the exact per-contour deployment declarations. Ubuntu-only production-impact source must never become CONTROL_PLANE solely because it is under `deploy/**`.

Domain review lenses inspect only the approved task scope. Cross-domain changes remain explicit in the Outcome Contract; invoking a lens does not create new authorization.

## 7. Protected behavior and re-authorization triggers

Fresh authorization is mandatory before material outcome/scope expansion; destructive or irreversible work outside the Outcome Contract; secret disclosure/use outside an already approved protected runtime mechanism; security-boundary weakening or credential-handling redesign; protected camera/runtime behavior change; incompatible API/state/storage/session schema change; data migration; detection/tracking/scoring/speed/calibration or event-semantics redesign; deployment-target redesign; or unauthorized `skills/**` edits.

Before requesting that fresh authorization, the Delivery Orchestrator must present the updated visible Scope block that caused the re-authorization boundary. The updated Scope must immediately precede the approval request and the fresh approval must be the next user decision; otherwise the re-authorization is not admitted for source execution.

Ordinary bug fixes, test corrections, PR metadata repair and CI remediation that remain inside the Outcome Contract do not require re-authorization.

## 8. Provenance and runtime identity

Applicable delivery work uses `schemas/release-manifest.schema.json`, `schemas/deployment-manifest.schema.json`, and `schemas/telemetry.schema.json`. New deployable provenance is `sea_speed_release_manifest_v2`: canonical Issue/merged PR, exact source/base commits, Outcome/Change Contract hashes, approved and actual file sets, scope hash, exact artifacts and evidence bindings. Persisted v1 evidence remains readable for rollback compatibility.

`packaged`, `installed`, `deployed` and `runtime_verified` are distinct states. A green workflow, uploaded package or running process does not prove runtime acceptance.

## 9. Integrity and evidence gates

After writes and before PR creation fetch complete written files, validate syntax/structure, compare branch to current `main`, prove changed paths remain inside the approved scope, and check for secrets/runtime artifacts. The task evidence must retain that source admission was opened only after `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`. Failed checks return to in-scope implementation.

Post-release review follows `docs/evidence/POST_RELEASE_REVIEW.md` and ends in `accepted`, `regressed`, or `insufficient_evidence`. A regression requires a linked Issue and rollback decision unless the exact rollback condition was already included in the active production envelope.

Valid terminal task states are only `COMPLETE`, `BLOCKED`, and `FAILED`.

## 10. Spec-Driven Development

Significant implementation/control-plane PRs declare exactly one active specification using `- Specification: specs/<feature>/spec.md`. The feature directory contains at least `spec.md`, `plan.md`, and `tasks.md`; `scripts/ci/validate_sdd.py` enforces repository structure and PR linkage.

The canonical feature identifier is the full directory name, such as `002-sdd-adoption`. Numeric prefixes are sequencing aids, not identifiers. The historical pair `002-camera-preview-gallery` / `002-sdd-adoption` is grandfathered audit history and must not be renamed solely for cleanup. New duplicate numeric prefixes are prohibited by CI.

Historical Issues, PRs and accepted decision records remain audit history. Runtime evidence may supersede obsolete assumptions in active specs/plans/tasks, but historical records are not rewritten to hide earlier decisions.

## 11. Executable Change Contract

Every implementation PR keeps the machine-readable Change Contract from `.github/pull_request_template.md`; path policy lives in `data/contracts/change-control-policy-v1.json` and validation in `scripts/ci/validate_change_contract.py`.

A new Change Contract must declare `Source authorization: OUTCOME APPROVED`, one canonical Issue, the exact changed-file set, derived production impact, exact VPS/Ubuntu/Windows applicability, production safety-envelope applicability, per-contour execution capability, expected operator-action count, compatibility/rollout/rollback/evidence declarations, and `NO` material scope/protected-boundary drift since authorization. Significant PRs also link their specification.

Historical legacy authorization text remains readable in old audit records but is not admitted as a new PR source authorization.

## 12. Production safety envelope and durable execution intent

Source authorization never authorizes production mutation.

A separate `PRODUCTION APPROVED <full-sha>` envelope may authorize bounded execution for one canonical task and exact runtime contour set, including declared deployment, necessary normal restart/reload, bounded health/smoke checks and an explicitly declared safe rollback condition/target.

The source-controlled authorized actor set and exact approval/fingerprint format are defined by `data/contracts/production-authorization-policy-v1.json`. Durable authorization binds canonical Issue, applicable merged PR, exact source SHA, Outcome Contract, runtime contours, security impact, deployment target and rollback semantics. Any material change makes it stale; missing/ambiguous GitHub evidence fails closed.

Production authorization and execution intent remain distinct semantics but may be expressed in one durable Issue comment:

```text
PRODUCTION APPROVED <full-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
Execution-Intent: EXECUTE
```

The first two exact lines provide authority. The third exact line provides execution intent. A two-line approval remains authorize-only. `.github/workflows/deploy-runtime-request.yml` may react only to the exact three-line form, must independently re-run `verify_production_authorization.py --require-execution-intent`, and may route only the exact required contours from the applicable merged Change Contract.

For VPS production, `.github/workflows/deploy-vps.yml` remains the single protected implementation. For Ubuntu Worker/relay, `.github/workflows/deploy-ubuntu-worker.yml` is the reusable protected orchestrator and `deploy/worker/ubuntu/deploy-authorized.sh` owns the target-side admission/preparation/activation/verification/evidence/rollback transaction. A separately provisioned restricted transport may enable zero-touch Ubuntu execution; absent that protected bootstrap, the declared fallback is one operator action that stages exact main and hands off to the repository-owned launcher. This governance change does not itself authorize secrets, sudoers changes, public runners or privilege expansion.

Repository rulesets, branch protection, required approvals and protected environments are GitHub settings, not facts proved by source installation. They may be reported as enforced only after independent settings verification.

## 13. Delivery quality layer

For a linked significant PR, the active SDD carries the delivery-quality model in the same canonical feature directory rather than a separate BMAD or quality document tree:

- `spec.md`: measurable NFR assessment and evidence status;
- `plan.md`: compact risk profile when required, risk-based test design, and correct-course impact check;
- `tasks.md`: acceptance-criterion traceability and terminal Definition of Done;
- PR Change Contract: derived risk-profile applicability and advisory quality verdict/waiver record.

A full risk profile is mandatory when any of the following applies: non-`NONE` security impact; non-`NONE` API/event/state/storage schema impact; destructive/data migration; `MIXED` runtime impact; or an explicitly declared other high-risk trigger. Otherwise the Change Contract may declare `Risk profile: NOT REQUIRED`.

NFR results use only `PASS`, `CONCERNS`, `FAIL`, or `NOT APPLICABLE`; an unknown/unmeasurable target cannot be represented as `PASS`. Test design classifies evidence as `unit`, `integration`, `end-to-end`, or `runtime-manual`, prioritized `P0` through `P3`. Every `AC-*` in the linked spec must map to a delivery task and test/evidence record or a justified runtime-manual evidence path.

PR quality verdicts use `PASS`, `CONCERNS`, `FAIL`, or `WAIVED`. `FAIL` blocks admission. `WAIVED` requires durable reason, owner, review/expiry date, compensating controls and follow-up/remediation target. No quality waiver can override Outcome Authorization, exact scope, protected-boundary reauthorization, deployment contour derivation, secrets rules, required CI, production authorization, rollback requirements, or other hard gates.

Historical SDD remains readable without mass retrofit. When historical feature work becomes an active significant PR again, the quality layer is added to that linked feature inside the newly approved scope. Production learning, architecture pivot or material scope change invokes the correct-course check; any resulting material outcome/scope/protected-boundary change still follows normal reauthorization rules.
