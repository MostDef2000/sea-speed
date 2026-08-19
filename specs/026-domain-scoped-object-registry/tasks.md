# Delivery Tasks: Domain-scoped Object Registry

- Specification: specs/026-domain-scoped-object-registry/spec.md
- Issue: #223
- Status: Source implementation

## Delivery tasks

- T-001 [x] Implement shared Objects-page scope resolution for explicit `?scope=water|road`, same-origin Road referrer inference when scope is absent, and Water default otherwise.
- T-002 [x] Lock every Objects list request to the resolved `camera_id/domain` pair and prevent ordinary form interaction from crossing the active domain.
- T-003 [x] Preserve scope across Reset/reload/direct scoped links while retaining search/date/speed/status filters, pagination and object detail behavior.
- T-004 [x] Preserve the generic `/sea-speed/api/objects` backend, SQLite schema, newest-100 Objects retention, newest-300 Water Passage retention and PATCH/DELETE/session behavior unchanged.
- T-005 [x] Add focused `tests/test_frontend_contract.py` coverage for Water/Road scope resolution, canonicalization, scope locking and Reset behavior.
- T-006 [x] Keep Water/Road operator page bytes unchanged because their existing common Objects links are sufficient for contextual resolution.
- T-007 [x] Correct the linked SDD triplet from conflicting branch-only prefix `025` to unique `026` under fresh exact Outcome approval.
- T-008 [x] Align the PR Change Contract to the exact five-file VPS-only diff and complete the mandatory SDD quality structure.
- T-009 [ ] Require PR Validation and aggregate Quality to succeed on the same exact final head.
- T-010 [ ] Refresh current main, exact head, changed-file scope and review state; merge PR #224 only with expected-head protection.
- T-011 [ ] Require exact-main Quality on the merge commit and persist source-integration evidence on Issue #223.
- T-012 [ ] Obtain separate exact-SHA VPS production authorization before any runtime mutation.
- T-013 [ ] Execute the canonical VPS deployment transaction for the authorized exact merge SHA and require accepted deployment evidence/rollback identity.
- T-014 [ ] Complete authenticated browser acceptance: Water registry shows only `cam1/water`, Road registry shows only `road1/road`, scope survives Reset/reload, and ordinary filters/pagination/edit/delete remain usable.
- T-015 [ ] Persist final deployment/browser evidence and close Issue #223 only after every applicable source and runtime gate passes.

## Requirements traceability

- AC-001 | Task: T-001,T-005,T-006 | Evidence: frontend contract assertions for contextual Water/Road resolution and unchanged common operator links | Coverage: COVERED
- AC-002 | Task: T-002,T-005 | Evidence: frontend contract assertions that every list request forces the resolved `camera_id` and `domain` | Coverage: COVERED
- AC-003 | Task: T-003,T-005 | Evidence: frontend contract assertions that Reset reapplies the active domain scope | Coverage: COVERED
- AC-004 | Task: T-002,T-003,T-005 | Evidence: locked camera/domain controls plus retained ordinary filter/pagination controls in the shared Objects page | Coverage: COVERED
- AC-005 | Task: T-001,T-003,T-005 | Evidence: explicit URL canonicalization and reload/direct-link scope assertions | Coverage: COVERED
- AC-006 | Task: T-003,T-004,T-005 | Evidence: existing PATCH/DELETE/detail/session frontend contract remains present and backend path is absent from diff | Coverage: COVERED
- AC-007 | Task: T-007,T-008,T-009 | Evidence: exact five-file authorized-subset diff, Change Contract/SDD validation, PR Validation and aggregate Quality | Coverage: COVERED
- AC-008 | Task: T-010,T-011 | Evidence: expected-head merge followed by exact-main Quality and Issue #223 source-integration record | Coverage: COVERED
- AC-009 | Task: T-012,T-013,T-014,T-015 | Evidence: exact-SHA production authorization, accepted VPS deployment manifest and authenticated Water/Road browser smoke | Coverage: RUNTIME-MANUAL | Reason: deployed protected-session behavior and domain-specific production data presentation require live VPS/browser evidence after separate production authorization

## Definition of Done

- [ ] Issue/spec/plan/tasks current — linked `026` SDD is current on the PR branch; merge/post-merge evidence remains pending.
- [x] Exact changed-file scope verified — GitHub changed-file inspection shows exactly the five intended frontend/test/`026` SDD paths and no protected backend/worker/camera/auth paths.
- [ ] Required tests and evidence complete — exact-head CI, exact-main Quality and runtime browser evidence remain pending.
- [ ] Required CI green — PR Validation and aggregate Quality must pass on one exact final head, then exact-main Quality must pass after merge.
- [ ] Exact-green-head merge complete — PR #224 remains open until same-head CI is green and merge gate is refreshed.
- [ ] Deployment state resolved — source approval does not authorize deployment; exact-SHA VPS production authorization and canonical deployment remain pending.
- [ ] Runtime acceptance resolved — authenticated Water/Road registry smoke remains pending after deployment.
- [x] Deferred work recorded — Camera/H264 recovery, persistent ReID/AIS and all non-registry product changes remain outside Issue #223.
- [x] Risks resolved or explicitly accepted — Risk profile is NOT REQUIRED; runtime risk is bounded by exact-SHA authorization, canonical VPS transaction and rollback evidence.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the final exact five-file PR head passes PR Validation and aggregate Quality, PR #224 merges with expected-head protection, exact-main Quality succeeds, Issue #223 contains source-integration evidence, a separate exact-SHA VPS production authorization exists, the canonical VPS deployment transaction is accepted with rollback identity, authenticated browser acceptance proves Water-only and Road-only registries with scope persistence and preserved ordinary operations, and terminal sanitized evidence is recorded.
