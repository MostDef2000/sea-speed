# Delivery Tasks: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Plan: `specs/074-water-detection-recall-evidence/plan.md`
- Issue: #346
- Branch: `issue-346-water-recall-evidence`
- Authorization: Task 3A `OUTCOME APPROVED` from exact protected main `739947c11471c746e74af0dfee4d9a5edd0d7bac`.
- Runtime contour: Ubuntu Worker REQUIRED; VPS NOT REQUIRED.

## Delivery tasks

- [x] T001 Add an optional detector diagnostics sink that records post-threshold model class/confidence/bbox/track/class-map evidence without changing returned detections.
- [x] T002 Add bounded Water-only structured diagnostics with existing ROI-center relation and actual post-ROI acceptance outcome.
- [x] T003 Keep diagnostics secret-free and bounded by default interval, record cap and no additional inference pass.
- [x] T004 Add deterministic tests for decision equivalence, stage fields, rate limiting, truncation and secret exclusion.
- [x] T005 Record the post-threshold observability limitation so below-threshold misses are not misclassified as evidence.
- [ ] T006 Verify exact changed-file scope and SDD/Change Contract admission.
- [ ] T007 Require exact PR-head Repository validation and quality-integration green.
- [ ] T008 Fresh-read main/head/scope/review state and merge only the exact green head.
- [ ] T009 Require exact-main Repository validation and quality-integration green.
- [ ] T010 Deploy exact-main Ubuntu Worker through the protected zero-touch contour; VPS must skip.
- [ ] T011 Record deployment/runtime evidence and explicitly defer representative vessel log sampling if traffic is unavailable.
- [ ] T012 Keep later threshold/class-map/ROI/tracker tuning blocked until evidence is reviewed under a new bounded authorization.

## Requirements traceability

- AC-001 | Task: T001,T004 | Evidence: `test_recall_diagnostics_sink_does_not_change_detector_result` | Coverage: COVERED
- AC-002 | Task: T001,T002,T004 | Evidence: `test_water_recall_diagnostics_are_bounded_and_stage_explicit` verifies raw/class/track/ROI/final-acceptance fields | Coverage: COVERED
- AC-003 | Task: T002,T003,T004 | Evidence: structured payload test verifies detector/ROI settings and secret-free allowlisted fields | Coverage: COVERED
- AC-004 | Task: T002,T003,T004 | Evidence: interval suppression, record cap and truncation flag assertions | Coverage: COVERED
- AC-005 | Task: T006 | Evidence: exact base-to-head changed-file comparison and protected-path review | Coverage: COVERED
- AC-006 | Task: T007,T008,T009 | Evidence: exact-head and exact-main GitHub required checks plus expected-head merge | Coverage: COVERED
- AC-007 | Task: T010,T011 | Evidence: protected Ubuntu Worker exact-main deployment manifest/artifact/audit; representative traffic sample may be deferred | Coverage: RUNTIME-MANUAL | Reason: exact release can be installed while operator desired state is stopped and no vessel traffic is available
- AC-008 | Task: T005,T012 | Evidence: SDD boundaries, exact diff and canonical #346 checkpoint keep later recall tuning separately authorized | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the implemented behavior.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [ ] Applicable deployment/runtime acceptance is complete, or explicitly NOT REQUIRED.
- [x] Runtime learning and deferred work are written back to the feature artifacts or recorded as approved follow-up.

Task 3A can reach source/deployment completion without representative-vessel sampling when traffic is unavailable, provided the exact Worker release is accepted and the deferral is durable. That deferral does not authorize any recall tuning; Task 3 evidence interpretation and behavior changes remain a separately authorized follow-up.
