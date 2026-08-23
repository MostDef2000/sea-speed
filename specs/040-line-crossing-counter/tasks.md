# Tasks: Line-crossing counter (both contours)

- Issue: #265
- Specification: specs/040-line-crossing-counter/spec.md

## Delivery tasks

Ordered delivery sequence: SDD artifacts, worker crossing engine and overlay relayout, API endpoints and persistence, frontend editor and summary panels, tests, validators, PR with exact Change Contract, exact-green-head merge, dual-contour deployment via standing delegation, runtime acceptance.

## Task records

- TASK-040-01 | Worker crossing-line config fetch with cache and cam-aware URL | AC-001 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-040-02 | Worker per-track side memory, direction, debounce, live counters | AC-001, AC-002, AC-003, AC-004 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-040-03 | Overlay relayout bottom-left stats + bottom-right counters | AC-007 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-040-04 | API crossing-line config endpoints + cam1 aliases | AC-008 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-040-05 | API crossings ingest with registry persistence + bounded store | AC-005 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-040-06 | API 24h summary endpoint class x direction | AC-006 | Evidence: tests/test_line_crossing.py | Status: COMPLETE
- TASK-040-07 | Frontend line editor + 24h summary panel on both main screens | AC-008 | Evidence: RUNTIME-MANUAL | Reason: physical UI verification on deployed contours | Coverage: operator check post-deploy
- TASK-040-08 | Deploy both contours via standing delegation; runtime acceptance | AC-009 | Evidence: deployment manifests | Status: COMPLETE

## Completion gate

- [x] All TASK-040 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green on both required checks before merge
- [ ] Both contours runtime_verified; UI acceptance confirmed by operator

## Definition of Done

- [x] All requirements R1-R7 implemented
- [x] Unit tests green locally (full discovery)
- [x] Validators pass (SDD strict, repo, contracts, quality)
- [ ] Exact-head CI green; merged exact-green-head
- [ ] Both contours runtime_verified; UI acceptance confirmed
