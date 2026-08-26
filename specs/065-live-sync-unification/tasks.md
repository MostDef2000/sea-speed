# Tasks: Unify live-sync overlay and passage engine for Road and Water

- Issue: #327
- Specification: specs/065-live-sync-unification/spec.md
- Plan: specs/065-live-sync-unification/plan.md

## Requirements traceability

- AC-001 | Task: TASK-065-01 | Evidence: frontend/sea-speed/live-sync.js + both index.html + tests/test_live_overlay_sync.py | Coverage: COVERED
- AC-002 | Task: TASK-065-02 | Evidence: worker/water_passage.py + tests/test_water_passage.py | Coverage: COVERED
- AC-003 | Task: TASK-065-02 | Evidence: worker/water_passage.py + tests/test_water_passage.py (Road param) | Coverage: COVERED
- AC-004 | Task: TASK-065-02 | Evidence: tests/test_water_passage.py | Coverage: COVERED
- AC-005 | Task: TASK-065-02 | Evidence: existing PassageEngineTests | Coverage: COVERED
- AC-006 | Task: TASK-065-03 | Evidence: MIXED deployment manifests + execution audit | Coverage: RUNTIME-MANUAL | Reason: protected hardware MIXED deploy

## Delivery tasks

1. Frontend shared live-sync.js + wire both pages
2. Worker generic PassageEngine (alias, reuse for Road)
3. Tests + validators + PR + CI + MIXED deploy + visual acceptance

## Task records

- TASK-065-01 | Frontend deduplication — create live-sync.js, update Water + Road index.html to include it, keep per-page config minimal | AC-001 | Evidence: frontend/sea-speed/live-sync.js, both index.html, sync tests | Status: COMPLETE
- TASK-065-02 | Worker unification — expose PassageEngine alias, instantiate for Water and for Road speed-line path | AC-002, AC-003, AC-004, AC-005 | Evidence: worker/water_passage.py, worker/hls_motion_yolo_worker_events.py, tests/test_water_passage.py | Status: COMPLETE
- TASK-065-03 | Validation + MIXED deploy + acceptance — validators, CI, MIXED runtime | AC-001..AC-006 | Evidence: scripts/ci/validate_*.py, deployment manifests | Status: RUNTIME-MANUAL

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
- [ ] Runtime acceptance resolved (both contours live-sync + passage stitching)
- [ ] Deferred work recorded (none beyond alias preservation)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
