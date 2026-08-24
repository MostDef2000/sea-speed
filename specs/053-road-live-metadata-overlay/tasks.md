# Tasks: Road live metadata overlay (Stage 3) + detector frequency research kit (Stage 4 prep)

- Issue: #301
- Specification: specs/053-road-live-metadata-overlay/spec.md
- Plan: specs/053-road-live-metadata-overlay/plan.md

## Requirements traceability

- R1 | TASK-053-01 | test_worker_tracking_overlay + test_detection_runtime_optimization | COVERED
- R2 | TASK-053-02 | test_api_contract | COVERED
- R3 | TASK-053-01 | test_frontend_contract | COVERED
- R4 | TASK-053-03 | test_telemetry_contract + telemetry.schema | COVERED
- R5 | TASK-053-04 | test_detector_frequency_benchmark | COVERED

## Delivery tasks

1. Worker immutable envelope + generation + publish path
2. API SSE bounded deque + internal ingest + validation
3. Frontend overlay canvas + SSE client + TTL/interpolation
4. Schema/validators + Stage4 research kit + exact-artifacts exposure
5. PR + merge + MIXED deploy + runtime acceptance

## Task records

- TASK-053-01 | Worker envelope + frontend overlay | R1,R3 | Evidence: worker/hls_motion_yolo_worker_events.py, worker/ubuntu_worker_entrypoint.py, worker/detection_performance.py, frontend/sea-speed/road/index.html, tests/test_frontend_contract.py | Status: IN PROGRESS
- TASK-053-02 | API SSE transport | R2 | Evidence: api/app/main.py, schemas/telemetry.schema.json, tests/test_api_contract.py | Status: IN PROGRESS
- TASK-053-03 | Schema/observability compatibility | R4 | Evidence: schemas/telemetry.schema.json, scripts/ci/validate_telemetry.py, tests/test_telemetry_contract.py | Status: IN PROGRESS
- TASK-053-04 | Stage4 research kit | R5 | Evidence: scripts/worker/benchmark_detector_frequency.py, scripts/worker/detector_frequency_matrix_v1.json, schemas/detector-frequency-benchmark.schema.json, scripts/quality/build_exact_artifacts.py, tests/test_detector_frequency_benchmark.py | Status: IN PROGRESS
- TASK-053-05 | Validation + deploy + acceptance | All | Evidence: validators, CI, manifests | Status: PENDING

## Completion gate

- [ ] All tasks COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] MIXED runtime_verified

## Definition of Done

- [ ] Spec/plan/tasks current
- [ ] Scope verified
- [ ] Tests + validators PASS
- [ ] PR exact-green-head merged
- [ ] MIXED deployed and accepted
