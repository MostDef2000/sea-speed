# Tasks: Crossing daily sync (VLZ midnight), full-class overlay, registry speed row and crossings period layer

- Issue: #278
- Specification: specs/044-crossing-daily-sync-registry-layer/spec.md

## Requirements traceability

- AC-001 | Task: TASK-044-01 | Evidence: RegistrySpeedRowTests | Coverage: COVERED
- AC-002 | Task: TASK-044-02 | Evidence: OverlayAllClassesTests | Coverage: COVERED
- AC-003 | Task: TASK-044-03 | Evidence: tests/test_line_crossing.py::VlzDailyResetTests | Coverage: COVERED
- AC-004 | Task: TASK-044-04 | Evidence: panel script source pins | Coverage: COVERED
- AC-005 | Task: TASK-044-05 | Evidence: SummaryDateRangeTests + layer pins | Coverage: COVERED

## Delivery tasks

Ordered sequence: worker reset + overlay, API date windows, frontend sync + registry layer, tests, validators, PR, exact-green-head merge, both-contour deployment, operator acceptance.

## Task records

- TASK-044-01 | Registry card description shows speed row | AC-001 | Evidence: RegistrySpeedRowTests | Status: COMPLETE
- TASK-044-02 | Overlay counter renders all counted classes | AC-002 | Evidence: OverlayAllClassesTests | Status: COMPLETE
- TASK-044-03 | VLZ-midnight daily reset preserving pending posts | AC-003 | Evidence: VlzDailyResetTests | Status: COMPLETE
- TASK-044-04 | Panel headline/table synced via state.crossings | AC-004 | Evidence: panel source pins | Status: COMPLETE
- TASK-044-05 | Summary date_from/date_to windows + registry crossings layer | AC-005 | Evidence: SummaryDateRangeTests + layer pins | Status: COMPLETE
- TASK-044-06 | Deploy both contours; operator acceptance of all five items | AC-001..AC-005 | Evidence: deployment manifests + operator check | Status: COMPLETE

## Completion gate

- [x] All TASK-044 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green on both required checks before merge
- [ ] Both contours runtime_verified; operator acceptance confirmed

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted (RISK-044-001..003 MITIGATED)
- [x] Waivers resolved or current (none)
