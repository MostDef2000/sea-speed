# Tasks: Road live metadata overlay (Stage 3) + detector frequency research kit (Stage 4 prep)

- Issue: #301
- Specification: specs/053-road-live-metadata-overlay/spec.md
- Plan: specs/053-road-live-metadata-overlay/plan.md

## Requirements traceability

- AC-001 | Task: TASK-053-01 | Evidence: test_worker_tracking_overlay + test_detection_runtime_optimization | Coverage: COVERED
- AC-002 | Task: TASK-053-01 | Evidence: test_frontend_contract | Coverage: COVERED
- AC-003 | Task: TASK-053-02 | Evidence: test_api_contract + test_telemetry_contract | Coverage: COVERED
- AC-004 | Task: TASK-053-04 | Evidence: test_detector_frequency_benchmark | Coverage: COVERED

## Delivery tasks

1. Worker immutable envelope + generation + publish path
2. API SSE bounded deque + internal ingest + validation
3. Frontend overlay canvas + SSE client + TTL/interpolation
4. Schema/validators + Stage4 research kit + exact-artifacts exposure
5. PR + merge + MIXED deploy + runtime acceptance

## Task records

- TASK-053-01 | Worker envelope + frontend overlay — live envelope, canvas TTL and content-box alignment | AC-001, AC-002 | Evidence: worker/hls_motion_yolo_worker_events.py, worker/ubuntu_worker_entrypoint.py, worker/detection_performance.py, frontend/sea-speed/road/index.html, tests/test_frontend_contract.py | Status: IN PROGRESS
- TASK-053-02 | API SSE transport — bounded deque and authenticated stream | AC-001, AC-003 | Evidence: api/app/main.py, schemas/telemetry.schema.json, tests/test_api_contract.py | Status: IN PROGRESS
- TASK-053-03 | Schema/observability compatibility — additive envelope and telemetry | AC-003 | Evidence: schemas/telemetry.schema.json, scripts/ci/validate_telemetry.py, tests/test_telemetry_contract.py | Status: IN PROGRESS
- TASK-053-04 | Stage4 research kit — matrix/schema/benchmark harness | AC-004 | Evidence: scripts/worker/benchmark_detector_frequency.py, scripts/worker/detector_frequency_matrix_v1.json, schemas/detector-frequency-benchmark.schema.json, tests/test_detector_frequency_benchmark.py | Status: IN PROGRESS
- TASK-053-05 | Validation + deploy + acceptance — validators, CI and MIXED runtime | AC-001, AC-002, AC-003, AC-004 | Evidence: validators, CI, manifests | Status: PENDING

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
- [ ] Deployment state resolved (VPS+Worker runtime_verified)
- [ ] Runtime acceptance resolved (overlay + research kit)
- [ ] Deferred work recorded (Stage4 production bump separate)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
