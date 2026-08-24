# Tasks: ROI persistence and measured fresh-frame detection cadence

- Issue: #299
- Specification: specs/052-roi-persistence-detection-cadence/spec.md
- Plan: specs/052-roi-persistence-detection-cadence/plan.md

## Requirements traceability

- AC-001 | Task: TASK-052-01 | Evidence: test_frontend_contract + test_api_contract draft/persisted/verified save | Coverage: PENDING
- AC-002 | Task: TASK-052-01 | Evidence: test_frontend_contract + test_api_contract reload after restart/reload | Coverage: PENDING
- AC-003 | Task: TASK-052-01 | Evidence: test_roi_normalization + test_api_contract malformed vs absent | Coverage: PENDING
- AC-004 | Task: TASK-052-02 | Evidence: test_vps_deploy_transaction executed migration | Coverage: PENDING
- AC-005 | Task: TASK-052-02 | Evidence: worker poll / reload integration test + runtime check | Coverage: PENDING
- AC-006 | Task: TASK-052-03 | Evidence: test_detection_runtime_optimization complete-frame latest slot | Coverage: PENDING
- AC-007 | Task: TASK-052-04 | Evidence: test_detection_runtime_optimization + test_ubuntu_worker_observability + test_telemetry_contract | Coverage: PENDING
- AC-008 | Task: TASK-052-04 | Evidence: test_detection_runtime_optimization + test_worker_tracking_overlay critical-path | Coverage: PENDING
- AC-009 | Task: TASK-052-03 | Evidence: test_analytics_profiles + test_ubuntu_worker_ai_supervision independent Road cadence | Coverage: PENDING
- AC-010 | Task: TASK-052-05 | Evidence: protected-runtime benchmark report | Coverage: PENDING
- AC-011 | Task: TASK-052-05 | Evidence: full validations + MIXED manifests + health checks | Coverage: PENDING

## Delivery tasks

Ordered lifecycle:

1. Frontend Road ROI draft/persisted/error behavior and independent config loading.
2. API persistence and error-distinguishing read path.
3. VPS migration execution fix and atomic semantics.
4. Worker frame transport + cadence configuration independence.
5. Worker telemetry + critical-path decoupling.
6. Telemetry/health/profile schema exposure.
7. Regression/contract tests and validators.
8. PR + exact-green-head merge + exact-main Quality.
9. MIXED deployment + runtime ROI + benchmark evidence.

## Task records

- TASK-052-01 | Road ROI persistence surface — draft vs persisted vs error UI, POST→GET verified save, independent ROI load | AC-001, AC-002, AC-003 | Evidence: frontend/sea-speed/road/index.html, api/app/main.py, tests/test_frontend_contract.py, tests/test_api_contract.py, tests/test_roi_normalization.py | Status: PENDING
- TASK-052-02 | ROI durable storage and deployment correctness — atomic write/migration against production data directory, per-file semantics | AC-004, AC-005 | Evidence: deploy/vps/deploy.sh, tests/test_vps_deploy_transaction.py, worker/hls_motion_yolo_worker_events.py, deploy/worker/ubuntu/configure-analytics-profiles.py | Status: PENDING
- TASK-052-03 | Fresh-frame transport and cadence ownership — verified complete-frame latest slot without partial drain; Road cadence not silently inherited from Water | AC-006, AC-009 | Evidence: worker/ubuntu_worker_entrypoint.py, worker/ubuntu_ai_inference_worker.py, worker/analytics_profiles.py, deploy/worker/ubuntu/configure-analytics-profiles.py, tests/test_detection_runtime_optimization.py, tests/test_analytics_profiles.py | Status: PENDING
- TASK-052-04 | Measured pipeline and non-blocking publish — split decoded/inferred/published FPS without double counting, stage timing, queue isolation while preserving snapshot consistency | AC-007, AC-008 | Evidence: worker/detection_performance.py, worker/hls_motion_yolo_worker_events.py, worker/ubuntu_worker_entrypoint.py, schemas/telemetry.schema.json, tests/test_detection_runtime_optimization.py, tests/test_ubuntu_worker_observability.py, tests/test_telemetry_contract.py, tests/test_worker_tracking_overlay.py | Status: PENDING
- TASK-052-05 | Validation and runtime benchmark — validators, full suite, exact-green-head merge, exact-main Quality, MIXED deploy, ROI + cadence runtime acceptance and protected 5/10/15 benchmark | AC-010, AC-011 | Evidence: specs/052/*, manifests, health, benchmark report | Status: PENDING

## Completion gate

- [ ] All TASK-052 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green before merge
- [ ] Exact-main Quality green
- [ ] MIXED deployment runtime_verified (VPS+Worker)
- [ ] ROI persistence + fresh-frame runtime acceptance resolved

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Worker runtime_verified)
- [ ] Runtime acceptance resolved (ROI + cadence/freshness)
- [ ] Deferred work recorded (stage 3 metadata overlay is post-scope target)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
