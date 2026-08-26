# Tasks: Water overlay fallback fix

- Issue: #320
- Specification: specs/062-water-overlay-fallback-fix/spec.md
- Plan: specs/062-water-overlay-fallback-fix/plan.md

## Requirements traceability

- AC-001 | Task: TASK-062-01 | Evidence: frontend/sea-speed/index.html | Coverage: COVERED
- AC-002 | Task: TASK-062-01 | Evidence: frontend/sea-speed/index.html | Coverage: COVERED

## Delivery tasks

1. Frontend fallback fix for Water AI overlay

## Task records

- TASK-062-01 | Frontend Water fallback — expose HLS to window, fallback to latest live envelope, keep ROI valid | AC-001, AC-002 | Evidence: frontend/sea-speed/index.html | Status: PENDING

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
- [ ] Runtime acceptance resolved (Water AI visible, ROI tools)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (NOT REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
