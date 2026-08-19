# Delivery Tasks: Autonomous Production Execution by Standing Delegation

- Specification: specs/028-production-autonomous-execution/spec.md
- Issue: #229
- Status: Source implementation

## Delivery tasks

- T-001 [x] Recover exact `main`, canonical governance, existing comment authority path and release evidence coupling; present complete visible Scope and receive immediately following `OUTCOME APPROVED`.
- T-002 [x] Create canonical Issue #229 and fresh branch from exact approved base through GitHub Connector.
- T-003 [x] Add pure standing-delegation policy primitives with deterministic policy hash, permission intersection, allow/deny decision and tamper-bound decision ID.
- T-004 [x] Add exact merged-release evaluator that reads trusted environment delegation, derives runtime contours from the exact first-parent source diff, cross-checks mutable PR metadata, binds Issue/PR/Outcome/Change Contract identity, and does not read Issue comments as authority.
- T-005 [x] Add autonomous successful-current-main-Quality router with stale-run suppression and require protected VPS/Ubuntu workflows to independently re-evaluate policy before runtime transport.
- T-006 [x] Remove active three-line/legacy comment request workflows, parsers, verifier and actor policy.
- T-007 [x] Add release manifest v3 and typed execution-audit evidence while retaining historical v1/v2/deployment readability.
- T-008 [x] Add/replace policy, workflow, release and architecture tests for self-authorization resistance, source-derived contours, stale-run suppression, fail-closed delegation, protected runtime invariants and historical compatibility.
- T-009 [x] Complete canonical docs, DR-005 and SDD convergence for the standing-delegation trust boundary and one-time environment administration.
- T-010 [ ] Run exact integrity/scope checks; ensure all changed paths are within Issue #229 Scope and no secret/runtime artifacts exist.
- T-011 [ ] Open linked PR with exact Change Contract, Risk profile REQUIRED, Quality verdict CONCERNS with the bounded post-merge activation finding, and full deployment transaction audit linkage.
- T-012 [ ] Require PR Validation and aggregate Quality on one exact head; remediate only within approved scope.
- T-013 [ ] Refresh current main/head/scope/reviews, merge exact green head with expected-head protection, and require exact-main Quality.
- T-014 [ ] Persist source-integration evidence to Issue #229 and resolve this control-plane PR runtime fields as NOT REQUIRED.
- T-015 [ ] Human administrator configures trusted `production` environment standing delegation using the exact merged repository policy hash and removes any per-run reviewer prompt while keeping environment-setting administration outside agent authority.
- T-016 [ ] On the next ordinary runtime-impacting accepted release, verify automatic current-main Quality policy allow -> applicable protected deployment -> runtime_verified -> typed execution audit without any per-release production approval prompt.
- T-017 [ ] Persist activation/end-to-end evidence and close Issue #229 only after standing delegation and one successful autonomous runtime release are proven.

## Requirements traceability

- AC-001 | Task: T-003,T-008 | Evidence: valid standing delegation allow + deterministic decision-ID validation | Coverage: COVERED
- AC-002 | Task: T-003,T-008 | Evidence: missing/mismatched/invalid/out-of-scope deny tests | Coverage: COVERED
- AC-003 | Task: T-003,T-008 | Evidence: trusted-permission intersection and policy-hash-not-authority tests | Coverage: COVERED
- AC-004 | Task: T-004,T-008 | Evidence: evaluator source has no comments endpoint/magic authority parser and exact source diff determines runtime contours | Coverage: COVERED
- AC-005 | Task: T-005,T-006,T-008 | Evidence: workflow-run current-main Quality router, stale-run suppression and absent legacy magic/comment triggers | Coverage: COVERED
- AC-006 | Task: T-005,T-008 | Evidence: both protected deploy workflows invoke `--require-allow` before transport | Coverage: COVERED
- AC-007 | Task: T-006,T-008 | Evidence: legacy workflow/parser/verifier/policy paths absent | Coverage: COVERED
- AC-008 | Task: T-007,T-008 | Evidence: v3 policy binding and historical v1/v2 tests | Coverage: COVERED
- AC-009 | Task: T-005,T-008 | Evidence: VPS privilege boundary and Ubuntu target transaction architecture assertions | Coverage: COVERED
- AC-010 | Task: T-010,T-011 | Evidence: exact GitHub compare scope and secret/runtime-artifact checks | Coverage: COVERED
- AC-011 | Task: T-012,T-013 | Evidence: exact-head PR Validation/Quality, expected-head merge, exact-main Quality | Coverage: COVERED
- AC-012 | Task: T-009 | Evidence: canonical docs, DR-005 and SDD | Coverage: COVERED
- AC-013 | Task: T-015 | Evidence: trusted environment delegation administration with exact merged policy hash/no per-run reviewer prompt | Coverage: RUNTIME-MANUAL | Reason: environment settings are deliberately outside agent/repository authority
- AC-014 | Task: T-016,T-017 | Evidence: later runtime release autonomously produces allow decision, runtime_verified deployment and typed audit without per-release prompt | Coverage: RUNTIME-MANUAL | Reason: requires a later production-impacting release after one-time standing delegation activation

## Definition of Done

- [ ] Issue/spec/plan/tasks current — source design is current; final CI/merge/activation evidence remains to be fed back.
- [ ] Exact changed-file scope verified — branch diff must be an exact subset of Issue #229 approved paths and match PR Change Contract.
- [ ] Required tests and evidence complete — source tests plus post-merge standing-delegation activation and first autonomous runtime release are required.
- [ ] Required CI green — exact PR head and exact-main Quality remain required.
- [ ] Exact-green-head merge complete — pending PR lifecycle.
- [x] Deployment state resolved — this source PR is CONTROL_PLANE and requires no VPS/Ubuntu runtime deployment.
- [ ] Runtime acceptance resolved — standing delegation activation and first autonomous runtime release remain external/runtime evidence.
- [x] Deferred work recorded — unrelated product behavior, IAM/secrets administration and historical evidence rewriting are outside scope.
- [x] Risks resolved or explicitly accepted — security/operations/data risks are bounded by independent trusted state, fail-closed policy and historical-readability tests.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until Issue #229 source changes are integrated with exact PR Validation, aggregate Quality and exact-main Quality; the trusted `production` environment contains a valid enabled standing delegation bound to the merged repository policy hash without a per-run reviewer approval; and a subsequent ordinary runtime-impacting release proves automatic `merge -> current-main Quality -> policy allow -> deploy -> runtime_verified -> typed audit` without `PRODUCTION APPROVED`, `Execution-Intent`, `DEPLOY VPS` or another per-release production prompt.
