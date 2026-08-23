# Tasks: Detection runtime optimization — FP16, 10-15 FPS, telemetry, motion gate

- Issue: #291
- Specification: specs/049-detection-runtime-optimization/spec.md
- Plan: specs/049-detection-runtime-optimization/plan.md

## Requirements traceability

- AC-001 | Task: TASK-049-01 | Evidence: `test_frame_quality` + `configure-analytics-profiles` HD assertion | Coverage: COVERED
- AC-002 | Task: TASK-049-01, TASK-049-02 | Evidence: `detection_performance` benchmark helper + telemetry | Coverage: COVERED
- AC-003 | Task: TASK-049-01 | Evidence: `test_detection_runtime_optimization` FP16 parity | Coverage: COVERED
- AC-004 | Task: TASK-049-01 | Evidence: `test_detection_runtime_optimization` class-filter parity | Coverage: COVERED
- AC-005 | Task: TASK-049-01 | Evidence: `test_detection_runtime_optimization` motion gate modes | Coverage: COVERED
- AC-006 | Task: TASK-049-01 | Evidence: `detection_performance` stage timing test | Coverage: COVERED
- AC-007 | Task: TASK-049-02 | Evidence: discover green + validators | Coverage: COVERED
- AC-008 | Task: TASK-049-02 | Evidence: CI + deployment manifest runtime_verified | Coverage: COVERED

## Delivery tasks

Ordered sequence: HD guarantee + motion allowlist, bounded queue + decoupled publishing, telemetry module, FP16/class-filter/ByteTrack wiring, unit/tests, benchmark docs, validators, PR, exact-green-head merge, Ubuntu deploy Water+Road, runtime acceptance, security follow-up.

## Task records

- TASK-049-01 | Worker pipeline optimization — analytics_profiles (FPS 10, HD, FP16/class knobs), ubuntu_worker_entrypoint bounded latest-frame + background publish, ubuntu_ai_inference_worker FP16/class filter, hls_motion_yolo_worker_events motion modes + telemetry integration, new worker/detection_performance.py, deploy configure-analytics-profiles HD fix + observed-runner forward, road env example | AC-001, AC-002, AC-003, AC-004, AC-005, AC-006 | Evidence: git diff + `test_detection_runtime_optimization.py` + `test_frame_quality.py` | Status: COMPLETE
- TASK-049-02 | Validation & deploy — SDD validators, file-scope re-check, full unittest, PR, exact-green-head merge, exact-main Quality, policy ALLOW, Ubuntu runtime_verified both profiles, manual benchmark + token rotation follow-up issue | AC-007, AC-008 | Evidence: CI + manifest + telemetry sample + benchmark notes | Status: PENDING

## Completion gate

- [ ] All TASK-049 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green before merge
- [ ] Exact-main Quality green
- [ ] Ubuntu Worker runtime_verified (Water + Road) after merge
- [ ] Operator acceptance: benchmark shows ≥2× effective FPS or hardware ceiling, stale 0, HD 1920×1080, FP16 parity

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete (including parity)
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (Ubuntu runtime_verified)
- [ ] Runtime acceptance resolved (benchmark + telemetry)
- [ ] Deferred work recorded (token rotation follow-up, dataset for tiling/model retrain)
- [ ] Risks resolved or explicitly accepted (REQUIRED profile documented)
- [ ] Waivers resolved or current (none, CONCERNS not WAIVED for deployment gates)
