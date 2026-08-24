# Tasks: Stage 3 visual finish — live canvas rendering from SSE

- Issue: #303
- Specification: specs/054-road-live-overlay-render/spec.md
- Plan: specs/054-road-live-overlay-render/plan.md

## Requirements traceability

- AC-001 | Task: TASK-054-01 | Evidence: test_worker_tracking_overlay | Coverage: COVERED
- AC-002 | Task: TASK-054-02 | Evidence: test_frontend_contract | Coverage: COVERED
- AC-003 | Task: TASK-054-03 | Evidence: test_telemetry_contract | Coverage: COVERED

## Delivery tasks

1. Worker live envelope publish path (immutable normalized, generation, observed_mono, crossings).
2. API SSE bounded deque and stream (validate, no disk, reconnect).
3. Frontend liveOverlayCanvas rendering (content-box, interpolation, TTL, generation).
4. PR + exact-green merge + MIXED deploy + manual visual acceptance.

## Task records

- TASK-054-01 | Worker live envelope publish — immutable normalized envelope with generation/observed_mono and bounded queue | AC-001 | Evidence: worker/hls_motion_yolo_worker_events.py, worker/ubuntu_worker_entrypoint.py | Status: IN PROGRESS
- TASK-054-02 | API live SSE — bounded deque 120, validate, stream with no disk amplification | AC-001 | Evidence: api/app/main.py | Status: IN PROGRESS
- TASK-054-03 | Frontend live canvas — content-box ±1px, interpolation at display cadence, TTL 1s discard | AC-002 | Evidence: frontend/sea-speed/road/index.html | Status: IN PROGRESS
- TASK-054-04 | Validation and MIXED deploy — validators, CI, manifests, runtime visual | AC-001, AC-002, AC-003 | Evidence: validators, CI, manifests | Status: PENDING

## Completion gate

- [ ] All TASK-054 records COMPLETE or RUNTIME-MANUAL
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
- [ ] Runtime acceptance resolved (live overlay visual)
- [ ] Deferred work recorded (Stage4 frequency separate)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
