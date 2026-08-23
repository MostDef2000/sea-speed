# Tasks: Crossing speed in registry + top-5 overlay counter classes

- Issue: #276
- Specification: specs/043-crossing-speed-overlay-top5/spec.md

## Requirements traceability

- AC-001 | Task: TASK-043-01 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests | Coverage: COVERED
- AC-002 | Task: TASK-043-02 | Evidence: tests/test_line_crossing.py::ApiCrossingTests | Coverage: COVERED
- AC-003 | Task: TASK-043-03 | Evidence: OverlayLayoutTests source pin | Coverage: COVERED

## Delivery tasks

Ordered sequence: worker payload + overlay limit, API persistence, tests, validators, PR, exact-green-head merge, both-contour deployment, operator acceptance.

## Task records

- TASK-043-01 | Crossing payload carries det speed_kmh | AC-001 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests | Status: COMPLETE
- TASK-043-02 | Ingest persists speed_kmh into registry record and store | AC-002 | Evidence: tests/test_line_crossing.py::ApiCrossingTests | Status: COMPLETE
- TASK-043-03 | Overlay counter renders top-5 classes | AC-003 | Evidence: OverlayLayoutTests source pin | Status: COMPLETE
- TASK-043-04 | Deploy both contours; operator acceptance (registry speeds, person on overlay) | AC-001, AC-002 | Evidence: deployment manifests + operator check | Status: COMPLETE

## Completion gate

- [x] All TASK-043 records COMPLETE or explicitly RUNTIME-MANUAL with reason
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
- [x] Risks resolved or explicitly accepted (RISK-043-001..002 MITIGATED)
- [x] Waivers resolved or current (none)
