# Delivery Tasks: Domain-scoped Object Registry

- Specification: specs/026-domain-scoped-object-registry/spec.md
- Issue: #223
- Status: Production-learning delivery correction

## Delivery tasks

- T-001 [x] Implement shared Objects-page scope resolution for explicit `?scope=water|road`, same-origin Road referrer inference when scope is absent, and Water default otherwise.
- T-002 [x] Lock every Objects list request to the resolved `camera_id/domain` pair and prevent ordinary form interaction from crossing the active domain.
- T-003 [x] Preserve scope across Reset/reload/direct scoped links while retaining search/date/speed/status filters, pagination and object detail behavior.
- T-004 [x] Preserve the generic `/sea-speed/api/objects` backend, SQLite schema, newest-100 Objects retention, newest-300 Water Passage retention and PATCH/DELETE/session behavior unchanged.
- T-005 [x] Add focused `tests/test_frontend_contract.py` coverage for Water/Road scope resolution, canonicalization, scope locking and Reset behavior.
- T-006 [x] Keep Water/Road operator page bytes unchanged because their existing common Objects links are sufficient for contextual resolution.
- T-007 [x] Correct the linked SDD triplet from conflicting branch-only prefix `025` to unique `026` under fresh exact Outcome approval.
- T-008 [x] Align PR #224 Change Contract to the exact five-file VPS-only diff and complete the mandatory SDD quality structure.
- T-009 [x] PR #224 exact-head PR Validation and aggregate Quality succeeded on final head `ec45f90d4611e1dbddcda66db1da354a529dfa58`.
- T-010 [x] Refresh merge gate and merge PR #224 with expected-head protection.
- T-011 [x] Exact-main Quality succeeded on merge commit `0af31b5e2516fb0d529228a51025693e7a932779`; source-integration evidence is durable on Issue #223.
- T-012 [x] Obtain exact-SHA VPS production authorization for `0af31b5e2516fb0d529228a51025693e7a932779` with execution intent.
- T-013 [ ] Execute the canonical VPS deployment transaction for the authorized exact product SHA and require accepted deployment evidence/rollback identity; first attempt run `32219455747` failed closed before acceptance because the protected privilege bundle source SHA was stale.
- T-014 [ ] Complete authenticated browser acceptance: Water registry shows only `cam1/water`, Road registry shows only `road1/road`, scope survives Reset/reload, and ordinary filters/pagination/edit/delete remain usable.
- T-015 [ ] Persist final deployment/browser evidence and close Issue #223 only after every applicable source and runtime gate passes.
- T-016 [x] Classify run `32219455747` as `PRODUCTION_LEARNING`: authorization, Quality, provenance and transport passed; protected privilege-bundle exact-source precondition failed before candidate acceptance.
- T-017 [x] Obtain fresh `OUTCOME APPROVED` for the exact three-path corrective SDD Scope without changing product bytes, runtime target, authorization-bound Issue/PR fields or Ubuntu Worker state.
- T-018 [x] Record effective VPS capability `ONE_COMMAND_FALLBACK`, operator actions expected `1`, root cause, adjacent-stage findings and full eight-stage Deployment Transaction Audit in the `026` SDD triplet.
- T-019 [ ] Require corrective PR changed-file set to be exactly the three approved SDD paths, derived Production impact `NONE`, and pass PR Validation plus aggregate Quality on the same exact head.
- T-020 [ ] Refresh current `main`, corrective head, exact changed-file scope and review state; merge only with expected-head protection, then require exact-main Quality on corrective merge SHA.
- T-021 [ ] Perform the one repository-owned protected-boundary refresh on the VPS for exact product target `0af31b5e2516fb0d529228a51025693e7a932779` and record its exact-target/fixed-topology PASS markers.
- T-022 [ ] Retry failed VPS deployment job `95967126921` in run `32219455747`; require accepted `runtime_verified` evidence for the original authorized product target and confirm Ubuntu contour remains skipped.

## Requirements traceability

- AC-001 | Task: T-001,T-005,T-006 | Evidence: frontend contract assertions for contextual Water/Road resolution and unchanged common operator links | Coverage: COVERED
- AC-002 | Task: T-002,T-005 | Evidence: frontend contract assertions that every list request forces the resolved `camera_id` and `domain` | Coverage: COVERED
- AC-003 | Task: T-003,T-005 | Evidence: frontend contract assertions that Reset reapplies the active domain scope | Coverage: COVERED
- AC-004 | Task: T-002,T-003,T-005 | Evidence: locked camera/domain controls plus retained ordinary filter/pagination controls in the shared Objects page | Coverage: COVERED
- AC-005 | Task: T-001,T-003,T-005 | Evidence: explicit URL canonicalization and reload/direct-link scope assertions | Coverage: COVERED
- AC-006 | Task: T-003,T-004,T-005 | Evidence: existing PATCH/DELETE/detail/session frontend contract remains present and backend path is absent from original product diff | Coverage: COVERED
- AC-007 | Task: T-007,T-008,T-009 | Evidence: exact five-file authorized-subset product diff, PR Validation and aggregate Quality on PR #224 | Coverage: COVERED
- AC-008 | Task: T-010,T-011 | Evidence: expected-head PR #224 merge followed by exact-main Quality and Issue #223 source-integration record | Coverage: COVERED
- AC-009 | Task: T-013,T-014,T-015,T-022 | Evidence: accepted VPS deployment manifest and authenticated Water/Road browser smoke | Coverage: RUNTIME-MANUAL | Reason: protected production session and domain-specific live data presentation require runtime evidence
- AC-010 | Task: T-016,T-017,T-018,T-019,T-020 | Evidence: exact three-path production-learning corrective diff, complete SDD audit, exact-head PR Validation + aggregate Quality, expected-head merge and exact-main Quality | Coverage: COVERED
- AC-011 | Task: T-021 | Evidence: repository-owned protected-boundary refresh emits exact-target PASS and fixed privilege-topology markers | Coverage: RUNTIME-MANUAL | Reason: protected VPS boundary state exists only on the production host
- AC-012 | Task: T-022 | Evidence: retried VPS job `95967126921` reaches accepted `runtime_verified` for exact product target while Ubuntu contour remains skipped | Coverage: RUNTIME-MANUAL | Reason: deployment manifest and contour routing are production runtime evidence

## Definition of Done

- [x] Issue/spec/plan/tasks current — product source integration, production authorization and production-learning correction are represented in the linked `026` SDD; corrective CI/merge evidence remains pending.
- [ ] Exact changed-file scope verified — corrective PR must show exactly the three approved `026` SDD paths.
- [ ] Required tests and evidence complete — corrective exact-head CI, exact-main Quality, protected-boundary refresh, accepted VPS deployment and browser acceptance remain pending.
- [ ] Required CI green — corrective PR Validation and aggregate Quality must pass on one exact head, followed by exact-main Quality after merge.
- [ ] Exact-green-head merge complete — corrective PR remains unmerged until fresh main/head/scope/review gate is clean.
- [ ] Deployment state resolved — current authorized product target has not yet reached accepted `runtime_verified`; first attempt failed closed before acceptance.
- [ ] Runtime acceptance resolved — authenticated Water/Road registry smoke remains pending after accepted deployment.
- [x] Deferred work recorded — Camera/H264 recovery, persistent ReID/AIS and all non-registry product changes remain outside Issue #223.
- [x] Risks resolved or explicitly accepted — corrective source Risk profile is NOT REQUIRED; runtime risk is bounded by fail-closed exact-source boundary, one repository-owned operator action, canonical retry and rollback evidence.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until the exact three-path production-learning corrective PR passes PR Validation and aggregate Quality on one exact head, merges with expected-head protection, exact-main Quality succeeds on the corrective merge, the one protected-boundary refresh reports exact-target PASS, failed VPS job `95967126921` is retried for original authorized product target `0af31b5e2516fb0d529228a51025693e7a932779` and reaches accepted `runtime_verified`, Ubuntu remains skipped, authenticated browser acceptance proves Water-only and Road-only registries with scope persistence and preserved ordinary operations, and terminal sanitized evidence is recorded on Issue #223.
