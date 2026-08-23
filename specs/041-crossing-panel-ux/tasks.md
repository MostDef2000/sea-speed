# Tasks: Crossing panel UX refinements

- Issue: #271
- Specification: specs/041-crossing-panel-ux/spec.md

## Requirements traceability

- AC-001 | Task: TASK-041-01 | Evidence: tests/test_line_crossing.py::CrossingPanelUiTests | Coverage: COVERED
- AC-002 | Task: TASK-041-02 | Evidence: tests/test_line_crossing.py::CrossingPanelUiTests | Coverage: COVERED
- AC-003 | Task: TASK-041-02 | Evidence: tests/test_line_crossing.py::CrossingPanelUiTests | Coverage: COVERED

## Delivery tasks

Ordered sequence: panel script changes on both pages, UI-contract tests, validators, PR, exact-green-head merge, VPS contour deployment, operator UI acceptance.

## Task records

- TASK-041-01 | Delete-line action clears and persists disabled empty state | AC-001 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-041-02 | Dynamic enable/disable toggle with guard for missing line | AC-002, AC-003 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-041-03 | Deploy VPS contour; operator UI acceptance | AC-001, AC-002 | Evidence: deployment manifest + operator check | Status: COMPLETE

## Completion gate

- [x] All TASK-041 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green on both required checks before merge
- [ ] VPS runtime_verified; operator UI acceptance confirmed

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted (RISK-041-001..002 MITIGATED)
- [x] Waivers resolved or current (none)
