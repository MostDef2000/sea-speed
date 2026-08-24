# Tasks: Road overlay consistency, UI fit and FPS evidence

- Issue: #296
- Specification: specs/051-road-overlay-consistency/spec.md
- Plan: specs/051-road-overlay-consistency/plan.md

## Requirements traceability

- AC-001 | Task: TASK-051-01 | Evidence: test_roi_normalization ROAD norm + legacy fallback + test_frontend_contract speed lines | Coverage: COVERED
- AC-002 | Task: TASK-051-01 | Evidence: test_frontend_contract frameMeta resolution + state fields 1920x1080 | Coverage: COVERED
- AC-003 | Task: TASK-051-01 | Evidence: test_detection_runtime_optimization atomic queue + test_line_crossing overlay sync | Coverage: COVERED
- AC-004 | Task: TASK-051-01 | Evidence: test_frontend_contract layout stage fit no bands | Coverage: COVERED
- AC-005 | Task: TASK-051-02 | Evidence: test_ubuntu_worker_observability + api contract effective_fps | Coverage: COVERED
- AC-006 | Task: TASK-051-02 | Evidence: discover + validators + MIXED manifest | Coverage: COVERED

## Delivery tasks

Ordered sequence: frontend ROAD speed lines norm fix + labels, resolution badge, stage fit, API atomic overlay + state fields, worker snapshot reuse + bytes queue, telemetry exposure, tests, validators, PR, MIXED deploy, visual acceptance.

## Task records

- TASK-051-01 | Road ROAD restoration & sync — frontend normalized A/B + labels, resolution display, stage fit + preload, api atomic replace, worker single snapshot + immutable bytes, fps fields | AC-001, AC-002, AC-003, AC-004 | Evidence: git diff + frontend/road + api/main + worker/hls + ubuntu_entrypoint | Status: PENDING
- TASK-051-02 | Validation & deploy — SDD validators, file-scope, full unittest, PR, exact-green-head merge, MIXED runtime_verified, visual Road check | AC-005, AC-006 | Evidence: CI + manifest + visual | Status: PENDING

## Completion gate

- [ ] All TASK-051 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green before merge
- [ ] Exact-main Quality green
- [ ] MIXED deployment runtime_verified (VPS+Worker)
- [ ] Visual Road acceptance (A/B, resolution, sync, fit, FPS)

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Worker runtime_verified)
- [ ] Runtime acceptance resolved (Road visual)
- [ ] Deferred work recorded (telemetry trend optional)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none)
