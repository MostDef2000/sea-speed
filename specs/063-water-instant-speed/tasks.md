# Tasks: Water instant speed — per-pixel median on full track + average between lines

- Issue: #322
- Specification: specs/063-water-instant-speed/spec.md
- Plan: specs/063-water-instant-speed/plan.md

## Requirements traceability

- AC-001 | Task: TASK-063-01 | Evidence: tests/test_worker_tracking_overlay.py, tests/test_road_overlay_sync.py | Coverage: COVERED
- AC-002 | Task: TASK-063-02 | Evidence: tests/test_worker_tracking_overlay.py | Coverage: COVERED
- AC-003 | Task: TASK-063-01 | Evidence: tests/test_road_overlay_sync.py | Coverage: COVERED

## Delivery tasks

1. Worker Water per-pixel median live + passage average
2. API passage average storage + tests
3. Validators + PR + CI + MIXED deploy + visual acceptance

## Task records

- TASK-063-01 | Worker Water per-pixel median live — bottom_center progress_m inst median last 5 on every frame, live v2 | AC-001, AC-003 | Evidence: worker/hls_motion_yolo_worker_events.py, worker/water_passage.py | Status: PENDING
- TASK-063-02 | API passage average — store avg/min/max between lines as summary | AC-002 | Evidence: api/app/main.py, schemas/telemetry.schema.json | Status: PENDING
- TASK-063-03 | Validation + MIXED deploy + acceptance — validators, CI, MIXED runtime | AC-001..AC-003 | Evidence: scripts/ci/validate_*.py, deployment manifests | Status: PENDING

## Completion gate

- [ ] All tasks COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] MIXED runtime_verified

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Ubuntu runtime_verified)
- [ ] Runtime acceptance resolved (Water per-pixel live + passage average)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
