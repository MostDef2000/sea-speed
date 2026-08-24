# Tasks: Stage 3 clean-overlay — hide baked boxes, live canvas only

- Issue: #305
- Specification: specs/055-road-clean-overlay/spec.md
- Plan: specs/055-road-clean-overlay/plan.md

## Requirements traceability

- AC-001 | Task: TASK-055-01 | Evidence: test_worker_tracking_overlay | Coverage: COVERED
- AC-002 | Task: TASK-055-02 | Evidence: test_frontend_contract | Coverage: COVERED
- AC-003 | Task: TASK-055-03 | Evidence: test_telemetry_contract | Coverage: COVERED

## Delivery tasks

1. Worker clean overlay — no AI boxes baked for Road.
2. Frontend hide overlayImg when live present, draw liveOverlayCanvas only.
3. Fallback clean overlay until first live, no duplicate boxes.
4. PR + exact-green merge + MIXED deploy + visual clean check.

## Task records

- TASK-055-01 | Worker clean overlay — Road JPEG without AI boxes/IDs/speeds | AC-001 | Evidence: worker/hls_motion_yolo_worker_events.py | Status: IN PROGRESS
- TASK-055-02 | Frontend live canvas as sole box source — hide overlayImg when live, content-box ±1px, TTL | AC-002 | Evidence: frontend/sea-speed/road/index.html | Status: IN PROGRESS
- TASK-055-03 | Backward compatibility and Water no-regression — events/ROI preserved | AC-003 | Evidence: tests/test_worker_tracking_overlay, tests/test_telemetry_contract | Status: IN PROGRESS
- TASK-055-04 | Validation and MIXED deploy — validators, CI, manifests, visual | AC-001, AC-002, AC-003 | Evidence: validators, CI, manifests | Status: PENDING

## Completion gate

- [ ] All TASK-055 records COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] MIXED runtime_verified

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Worker runtime_verified)
- [ ] Runtime acceptance resolved (clean overlay visual)
- [ ] Deferred work recorded (Stage4 frequency separate)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
