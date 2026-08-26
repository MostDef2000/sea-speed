# Tasks: Water overlay tools fix — restore AI overlay and ROI/speed/crossing editing

- Issue: #318
- Specification: specs/061-water-overlay-tools-fix/spec.md
- Plan: specs/061-water-overlay-tools-fix/plan.md

## Requirements traceability

- AC-001 | Task: TASK-061-01 | Evidence: frontend/sea-speed/index.html, tests/test_frontend_contract.py, tests/test_road_overlay_sync.py | Coverage: COVERED
- AC-002 | Task: TASK-061-01 | Evidence: frontend/sea-speed/index.html, tests/test_frontend_contract.py | Coverage: COVERED
- AC-003 | Task: TASK-061-01 | Evidence: frontend/sea-speed/index.html | Coverage: COVERED

## Delivery tasks

1. Frontend opacity/display fix for Water AI overlay and ROI/speed/crossing tools
2. Validators + PR + CI + VPS deploy + visual acceptance

## Task records

- TASK-061-01 | Frontend Water tools restore — opacity handling, contentRect via waterMainVideo/ROI, lag median, hi passages stable | AC-001, AC-002, AC-003 | Evidence: frontend/sea-speed/index.html | Status: PENDING
- TASK-061-02 | Validation + VPS deploy + acceptance — validators, CI, VPS runtime_verified | AC-001..AC-003 | Evidence: scripts/ci/validate_*.py, deployment manifests | Status: PENDING

## Completion gate

- [ ] All tasks COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] VPS runtime_verified

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS runtime_verified)
- [ ] Runtime acceptance resolved (Water AI + ROI/Speed/Crossing)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (NOT REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
