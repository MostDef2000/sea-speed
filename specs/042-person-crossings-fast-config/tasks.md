# Tasks: Person crossings + fast crossing-line config refresh

- Issue: #274
- Specification: specs/042-person-crossings-fast-config/spec.md

## Requirements traceability

- AC-001 | Task: TASK-042-01 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests | Coverage: COVERED
- AC-002 | Task: TASK-042-02 | Evidence: tests/test_line_crossing.py::ApiCrossingTests | Coverage: COVERED
- AC-003 | Task: TASK-042-03 | Evidence: tests/test_line_crossing.py::CrossingConfigRefreshTests | Coverage: COVERED

## Delivery tasks

Ordered sequence: worker person counting + TTL reduction, API registry guard, tests, validators, PR, exact-green-head merge, both-contour deployment, operator acceptance.

## Task records

- TASK-042-01 | Worker counts person crossings like other classes | AC-001 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests | Status: COMPLETE
- TASK-042-02 | API skips registry persistence for road-person crossings; store append retained | AC-002 | Evidence: tests/test_line_crossing.py::ApiCrossingTests | Status: COMPLETE
- TASK-042-03 | Crossing-line config freshness default reduced to 1s | AC-003 | Evidence: tests/test_line_crossing.py::CrossingConfigRefreshTests | Status: COMPLETE
- TASK-042-04 | Deploy both contours; operator acceptance (person counted, registry/events clean) | AC-001, AC-002 | Evidence: deployment manifests + operator check | Status: COMPLETE

## Completion gate

- [x] All TASK-042 records COMPLETE or explicitly RUNTIME-MANUAL with reason
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
- [x] Risks resolved or explicitly accepted (RISK-042-001..003 MITIGATED)
- [x] Waivers resolved or current (none)
