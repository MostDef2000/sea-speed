# Implementation Plan: Autonomous Production Execution by Standing Delegation

- Specification: specs/028-production-autonomous-execution/spec.md
- Issue: #229
- Status: Source implementation

## Architecture

The current comment-based authority path is replaced rather than layered. Source authorization remains `OUTCOME APPROVED`; production authority moves to independently administered trusted environment state. The repository defines a deterministic policy and evidence formats but cannot create an effective delegation through Issue/PR/comment/README/source text.

The trusted input is `vars.SEA_SPEED_PRODUCTION_DELEGATION_V1` resolved from the GitHub `production` environment. It contains the standing delegation object. `data/contracts/production-autonomy-policy-v1.json` is repository-owned constraint data. `production_policy.py` validates both and computes effective permissions as an intersection. `evaluate_production_policy.py` resolves exact merged release metadata through the GitHub API, never reads Issue comments for authority, and emits a typed allow/deny decision.

`deploy-runtime-autonomous.yml` listens only to successful `Quality integration gate` workflow runs for `push` on `main`, evaluates policy for the exact Quality head SHA, and routes required active contours when allowed. `deploy-vps.yml` and `deploy-ubuntu-worker.yml` independently re-evaluate the same trusted delegation with `--require-allow` before any SSH/runtime transport, preserving defense in depth against direct workflow dispatch.

New release provenance is `sea_speed_release_manifest_v3`; v1/v2 validators remain historical readers. Successful runtime workflows build a typed execution audit from the allow decision plus runtime-verified deployment manifest.

## Decisions

- D-001: Keep `OUTCOME APPROVED` unchanged as source-change authority; this task changes production runtime authority only.
- D-002: Treat all repository/Issue/PR/comment/README text as non-authoritative for production execution.
- D-003: Store effective standing delegation only in independently administered `production` environment state; repository source contains constraints and schemas, not effective authority.
- D-004: Use explicit intersection semantics so repository policy can narrow but never widen the trusted delegation.
- D-005: Limit standing production actions to `deploy` and `rollback`; IAM, secrets, environment/settings administration and arbitrary mutation remain outside authority.
- D-006: Trigger autonomous routing from successful exact-main Quality `workflow_run`, removing both three-line production approval and legacy `DEPLOY VPS` comment workflows.
- D-007: Re-evaluate policy inside each protected deploy workflow before transport, so manual workflow dispatch cannot bypass standing delegation.
- D-008: Introduce release manifest v3 rather than redefining v2; historical v1/v2 evidence remains semantically stable and readable.
- D-009: Emit typed execution audit only from allow decision plus runtime-verified deployment evidence.
- D-010: Keep this PR CONTROL_PLANE with no VPS/Ubuntu runtime deployment; activation requires one external environment-setting action after exact-main integration.

## Affected contours

- Source/control plane: REQUIRED — governance, release policy, workflow orchestration, schemas and tests change.
- VPS deployment for this PR: NOT REQUIRED.
- Ubuntu Worker/relay update for this PR: NOT REQUIRED.
- Production safety envelope for this PR: NOT REQUIRED because no runtime contour is changed by the PR itself.
- VPS execution capability for this PR: NOT APPLICABLE.
- Ubuntu worker execution capability for this PR: NOT APPLICABLE.
- Operator actions expected for this PR runtime delivery: 0.
- Post-merge activation: one independently administered trusted environment setting is required before autonomous runtime policy can allow a later runtime release.

## Validation

Pure unit tests cover standing-delegation parsing/validation, policy hash binding, intersection semantics, deny paths, decision ID tamper detection and unsupported actions. Architecture tests inspect workflow source to prove there is no active comment authority, old request paths are absent, exact-main Quality remains required, protected workflows re-evaluate policy before transport, and existing VPS/Ubuntu protected transaction markers remain.

Release tests validate v3 decision/delegation bindings and historical v1/v2 readability. `scripts/quality/validate_workflow_policy.py` enforces pinned actions, autonomous quality trigger, absence of obsolete comment-trigger workflows, policy-before-transport ordering and protected runtime markers.

Before PR creation, compare the exact branch diff with Issue #229 approved paths, verify no secret/runtime artifact, and synchronize the Change Contract. PR Validation and aggregate Quality must pass on one exact head. Merge uses fresh main/head/scope/review checks and expected-head protection when supported; exact-main Quality follows merge.

No production runtime mutation is part of this source PR. After source integration, trusted `production` environment state must be configured externally with an enabled delegation whose `policyHash` equals the merged repository policy hash and whose environment configuration does not impose a per-run reviewer prompt. The next ordinary runtime-impacting accepted release provides the end-to-end autonomous acceptance evidence.

## Risk profile

- Risk profile: REQUIRED

This change modifies the production authority boundary and release evidence schema. The principal risk is accidental self-authorization or a bypass around trusted delegation. The design counters this with independent trusted state, intersection semantics, duplicated policy checks before runtime transport, exact-main/Quality/provenance gates, removal of comment parsers and explicit deny tests.

- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: effective delegation comes only from independently administered production environment state; Issue/PR/comment/repository text is excluded from authority inputs | Validation: evaluator source assertions, absent legacy workflows/parsers, missing-delegation deny tests | Residual risk: an administrator of the trusted environment can intentionally change authority, which is the intended administrative root | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: effective permissions are intersection of trusted delegation and repo policy; protected workflows re-evaluate with `--require-allow` before transport | Validation: policy-widening test, direct-deploy workflow policy markers/order | Residual risk: a separately authorized source change could alter policy implementation; source `OUTCOME APPROVED` remains the human source boundary | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: fail closed until trusted delegation exists; exact-main Quality trigger plus existing per-contour rollback/runtime verification remain | Validation: no-delegation deny, workflow routing tests, existing runtime transaction tests | Residual risk: missing/misconfigured trusted delegation blocks production until administrator correction | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: release manifest v3 is additive; v1/v2 readers retained without rewriting persisted evidence | Validation: historical release/deployment tests | Residual risk: downstream consumers that assume only v2 must be updated to accept v3 before new production evidence is consumed | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002 | Level: unit | Priority: P0 | Evidence: valid standing delegation allows deploy; missing/mismatched/malformed inputs deny
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: repository `allowedActions` cannot widen trusted permissions; policy hash alone fails delegation validation
- TEST-003 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: evaluator source contains trusted environment variable input and contains no comment endpoint/magic authority parser
- TEST-004 | Covers: AC-005,AC-006,AC-007 | Level: integration | Priority: P0 | Evidence: workflow architecture tests and workflow-policy validator prove Quality workflow_run routing, policy-before-transport and absent legacy request paths
- TEST-005 | Covers: AC-008 | Level: unit | Priority: P0 | Evidence: v3 validator requires policy decision evidence/rejects productionAuthorization evidence; v1/v2 remain readable
- TEST-006 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: quality architecture tests preserve VPS privilege and Ubuntu target-transaction markers
- TEST-007 | Covers: AC-010,AC-011 | Level: integration | Priority: P0 | Evidence: exact authorized scope, PR Validation, aggregate Quality, expected-head merge and exact-main Quality
- TEST-008 | Covers: AC-012 | Level: integration | Priority: P1 | Evidence: canonical docs and DR-005 converge on standing-delegation trust model and one-time external administration
- TEST-009 | Covers: AC-013 | Level: runtime-manual | Priority: P0 | Evidence: administrator confirms trusted production environment standing delegation with exact merged policy hash and no per-run reviewer gate
- TEST-010 | Covers: AC-014 | Level: end-to-end | Priority: P0 | Evidence: later runtime-impacting exact release autonomously reaches policy allow, deployment runtime_verified and typed audit without per-release prompt

## Correct-course check

- Trigger: ARCHITECTURE_PIVOT
- Issue impact: Issue #229 defines a new production authority architecture while preserving the source authorization model and runtime safety gates.
- Specification impact: replaces per-release comment authority with independently administered standing delegation and typed policy decision/evidence.
- Plan impact: removes legacy request workflows/parsers, introduces Quality-triggered routing and duplicated pre-transport policy evaluation.
- Tasks impact: requires migration tests, historical-readability coverage, source integration, then one-time trusted environment administration and later end-to-end autonomous acceptance.
- Authorization impact: existing historical production approvals remain immutable evidence but no longer authorize new releases; no new per-release production authorization is part of the target model.
- Follow-up: after exact-main source integration configure trusted standing delegation once, then use the next applicable runtime release to prove autonomous production execution and audit.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no runtime workflow is routed when exact main Quality or trusted policy admission is absent | Retry: after exact main Quality succeeds and trusted delegation/policy inputs are valid | Rollback: not applicable before mutation | Evidence: workflow_run event fields, exact SHA, policy decision JSON
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: runtime hosts remain unchanged; direct protected workflow dispatch also stops before transport when policy denies | Retry: after policy/delegation mismatch is corrected without changing runtime state | Rollback: not applicable because policy and provenance checks precede transport | Evidence: protected workflow ordering, `--require-allow`, exact Quality/provenance output
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: only the already-existing repository-owned VPS or Ubuntu deployment transaction may have changed its contour; no new mutation primitive is introduced | Retry: per existing contour transaction after actual state is resolved | Rollback: existing exact previous release / target transaction rollback semantics | Evidence: existing `deploy/vps/deploy.sh` or Ubuntu `deploy-authorized.sh` runtime evidence
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate cannot be accepted without existing runtime health/product checks | Retry: after remediation under same source/runtime governance | Rollback: existing contour rollback remains authoritative | Evidence: deployment manifest checks and runtimeVerified state
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: accepted runtime state is not committed unless existing transaction verification succeeds | Retry: only after full verification | Rollback: exact previous accepted contour release | Evidence: deployment manifest `runtimeVerified=true`, `state=runtime_verified`, exact source
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime may remain accepted while cleanup is incomplete | Retry: existing safe housekeeping retry semantics | Rollback: no rollback solely for housekeeping failure | Evidence: existing per-contour cleanup output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: runtime may be healthy but autonomous acceptance is incomplete without policy decision, v3 release, deployment and typed audit evidence | Retry: rebuild/read evidence when deterministic identity remains provable; do not redeploy solely for missing presentation | Rollback: not applicable | Evidence: policy decision, release manifest v3, deployment manifest, execution audit, Issue evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: previous accepted contour release is restored or runtime remains unresolved/fail-closed | Retry: prohibited until actual state and standing policy decision are understood | Rollback: existing exact per-contour rollback target; no new rollback command channel | Evidence: existing rollback markers plus exact policy/source/deployment identity

## Runtime feedback

- The pre-change implementation couples durable production authority and execution intent to exact Issue-comment text and also retains a legacy `DEPLOY VPS` comment trigger.
- Current `main` was observed without branch protection during task intake, reinforcing that a source file is not a sufficient independent production authority root.
- Source implementation is intentionally fail closed until the trusted `production` environment delegation exists. That one-time environment administration is outside repository lifecycle writes and remains a protected human action.
