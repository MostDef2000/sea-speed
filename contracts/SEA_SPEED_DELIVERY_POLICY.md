# Sea Speed Delivery Policy

Version: 1.16.0
Status: Active

## 1. Purpose

Define quality admission, release provenance, runtime applicability, production authorization, operator execution and completion evidence for the two active production contours: **VPS** and **Ubuntu Worker/relay**.

Windows Worker is retired as a production/runtime component. Historical documents and tests may use the former name **Windows AI Worker**; that name is retained only for historical compatibility and does not identify an active contour. Historical Windows evidence remains readable audit history; deprecated Windows scripts are non-production local/archive tooling.

## 2. Applicability

| Changed paths | VPS | Ubuntu Worker/relay |
|---|---:|---:|
| `api/**`, `frontend/**`, `deploy/vps/**` | YES | NO unless compatibility requires |
| `deploy/worker/ubuntu/**`, `worker/ubuntu_*` | NO | YES |
| shared executable `worker/**` | NO | YES |
| API contract plus shared Worker consumer | YES | YES |
| contracts/docs/specs/control tooling | NO | NO |
| `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**`, Windows helper docs | NO | NO |

`MIXED` means both active contours apply; it never replaces exact VPS/Ubuntu declarations. Ubuntu-only runtime source must not be reduced to CONTROL_PLANE by a generic `deploy/**` rule.

Windows `.cmd`/`.ps1` assets may remain portable/local tooling, but they are not a production target, release contour, deployment requirement, production-authorization field or runtime acceptance gate.

## 3. Source admission and continuation

New tasks use `OUTCOME APPROVED` only after the complete visible Scope block immediately precedes the approval. Before the first repository write resolve `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, and `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.

PR admission requires an exact Change Contract, exact changed-file match, valid SDD linkage for significant work, required CI and unchanged protected boundaries. Merge additionally requires fresh base/head comparison, zero unresolved review threads and expected-head protection when supported.

After valid `OUTCOME APPROVED`, ordinary implementation defects, tests, CI remediation and PR metadata corrections inside the approved exact path set continue automatically. A deterministic stage such as PR created, queued/running CI, merge readiness or packaging is not a terminal handoff while a safe authorized next action remains.

## 4. Release identity

Every new deployable release uses `sea_speed_release_manifest_v2` and binds canonical Issue, merged PR, exact source/base commits, Outcome/Change Contract hashes, approved and actual files, deterministic scope hash, component, exact artifact digest/size and quality/exact-artifact evidence.

New release creation supports active components only: `vps`, `ubuntu-worker`, `mixed`, and `governance`. Existing schemas/validators may continue reading historical `windows-worker` manifests. Historical readability does not authorize a new Windows release.

Deployment manifest v1 remains backward-readable for persisted VPS, Ubuntu and historical Windows evidence. New runtime delivery is VPS/Ubuntu only.

## 5. Production authorization and execution intent

Source authorization never authorizes runtime mutation. Runtime change requires durable exact-SHA authorization on the canonical Issue:

```text
PRODUCTION APPROVED <full-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
Execution-Intent: EXECUTE
```

The first two lines provide authority; the third provides execution intent. The fingerprint binds Issue, merged PR, exact source, Outcome Contract, exact active runtime contour set, security impact, deployment target and rollback semantics.

Modern PR fingerprints contain only VPS/Ubuntu contour fields. To preserve immutable audit history, `scripts/release/verify_production_authorization.py` reproduces the legacy Windows field in the payload only when the historical PR body itself contains that legacy field.

Before mutation prove exact lowercase SHA, current-main first-parent ancestry, successful exact `push/main` Quality integration, one applicable merged PR, current durable fingerprint, explicit execution intent, valid exact artifacts/release/quality evidence and known rollback target.

`.github/workflows/deploy-runtime-request.yml` routes only VPS and/or Ubuntu according to the exact merged Change Contract. It contains no runtime SSH/mutation logic itself.

## 6. Runtime execution capability

Every runtime-impacting Change Contract declares only these active fields:

```text
VPS deployment: REQUIRED / NOT REQUIRED
Ubuntu worker/relay update: REQUIRED / NOT REQUIRED
VPS execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Ubuntu worker execution capability: CONNECTOR / ONE_COMMAND_FALLBACK / MISSING / NOT APPLICABLE
Operator actions expected: <integer>
```

A required contour cannot use `MISSING` or `NOT APPLICABLE`; a non-required contour must use `NOT APPLICABLE`. `Operator actions expected` equals the number of required active contours using `ONE_COMMAND_FALLBACK`.

## 7. Mixed-contour rollout

When both active contours apply, declare compatibility, schema/migration requirements, rollout order, acceptance and rollback order. VPS and Ubuntu Worker/relay remain independent failure domains unless an approved architecture explicitly couples them.

## 8. Canonical operator execution context

Current non-secret operator targets, subject to runtime verification:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

Credentials, keys, passwords, TOTP and populated environment values remain local/trusted and never enter chat or Git.

## 9. Repository-owned server-pull model

The default interactive VPS/Ubuntu fallback is target-local server-pull of the exact authorized SHA, then handoff to a repository-owned entrypoint that owns admission, preparation, mutation, verification, evidence and rollback. Substantive deployment logic must not be embedded in ad hoc operator commands.

## 10. Operator interaction budget

Normal successful task:

```text
OUTCOME APPROVED: 1
PRODUCTION APPROVED + Authorization-Fingerprint + Execution-Intent: 1 per exact release
manual runtime command: 0 target, <=1 fallback per required active contour
intermediate deterministic confirmation prompts: 0
```

Extra interaction is reserved for material reauthorization, a new exact source SHA, password/sudo/TOTP/secret entry, host trust, configured environment reviewer, irreversible/high-risk decision or evidence unavailable to safe automation.

## 11. VPS execution and evidence

`.github/workflows/deploy-vps.yml` remains the single protected VPS implementation. It performs exact-main, quality, authorization, artifact/release and rollback admission before SSH. VPS completion requires exact deployed source, health/smoke evidence, applicable product/security checks and a known rollback target.

## 12. Ubuntu Worker/relay execution and evidence

`.github/workflows/deploy-ubuntu-worker.yml` is the protected reusable Ubuntu orchestrator. `deploy/worker/ubuntu/deploy-authorized.sh` owns the target-side exact deployment transaction. Restricted zero-touch transport is `CONNECTOR` only when independently provisioned; otherwise the truthful capability is `ONE_COMMAND_FALLBACK` and one repository-owned bootstrap is exposed.

Ubuntu completion requires exact source/runtime identity, protected-local-state preservation, valid deployment evidence, service state and applicable advancing freshness/frame/AI/relay evidence. Hosted CI alone does not prove physical NVIDIA/camera runtime.

## 13. Retired Windows tooling and historical evidence

Windows Worker has no active runtime completion gate. The legacy Windows packaging workflow named `package-worker` is removed and must remain absent. Exact edge artifacts must not contain `.cmd`, `.ps1` or `worker/windows/**` content. New release tooling must reject `windows-worker` as a new component.

Persisted Windows release/deployment manifests and immutable historical Issue/PR/fingerprint evidence remain readable and are not rewritten. Deprecated Windows scripts may stay in the repository as non-production local/archive tooling so generic cross-platform Python compatibility is not conflated with a supported Windows deployment target.

## 14. Media and security boundaries

The active media mode remains `mvp_v1`; `edge_v2` is a separate protected migration. Runtime identity fields do not redefine detection/tracking/calibration/speed/event formulas.

## 15. Completion and terminal interaction

Merge is not release. Release is not deployment. Deployment is not acceptance.

The Delivery Orchestrator may return control only in one terminal interaction state:

- `DONE`: all mandatory evidence for the approved Outcome is satisfied.
- `BLOCKED`: a concrete external blocker makes continuation objectively impossible. The response records the external blocker, supporting evidence, unblock condition and next admissible action. A remediable in-scope source/test/CI/PR-metadata failure, transient failure or queued/running CI is not `BLOCKED`.
- `HUMAN DECISION REQUIRED`: continuation requires a genuine human decision, authorization or protected input, configured environment review, or irreversible/high-risk choice. The response gives the exact decision, bounded options/consequences when relevant and exact reply/action format. Deterministic execution resumes after the decision.

`FAILED` is an internal event, not a terminal interaction state. Remediate it automatically where possible; otherwise classify the real boundary as `BLOCKED` or `HUMAN DECISION REQUIRED`.

## 16. Delivery quality admission

A linked significant PR is quality-enabled only when its SDD includes current NFR assessment, risk/test design, correct-course check, traceability and Definition of Done, and the Change Contract declares the derived Risk profile plus quality verdict.

Full risk profiling is required for security impact, API/event/state/storage schema impact, destructive/data migration, `MIXED` runtime or another explicit high-risk trigger. `FAIL` blocks. `WAIVED` requires a complete durable waiver and never bypasses hard authorization/scope/CI/production/rollback gates.

Production-equivalent deterministic deployment tests should execute the real transaction entrypoint with isolated fake external/runtime boundaries when executable ordering/rollback semantics are in scope.

## 17. Deployment transaction audit

For linked significant work, `scripts/ci/validate_sdd.py` requires a Deployment Transaction Audit when a changed path is under `deploy/**` or `scripts/release/**`, a deployment workflow changes, any runtime deployment field is `REQUIRED`, or the correct-course trigger is `PRODUCTION_LEARNING`.

The audit covers exactly `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`, with mutation possibility, failure disposition, state after failure, safe retry, rollback semantics and evidence. Production learning additionally requires completed adjacent-stage review and concrete root cause/findings.
