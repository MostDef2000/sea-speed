# Tasks: Water fast vessel tracking + live overlay sync alignment

- Issue: #324
- Specification: specs/064-water-fast-vessel-overlay-sync/spec.md
- Plan: specs/064-water-fast-vessel-overlay-sync/plan.md

## Requirements traceability

- AC-001 | Task: TASK-064-01 | Evidence: tests/test_water_passage.py::FastVesselStitchTests | Coverage: COVERED
- AC-002 | Task: TASK-064-01 | Evidence: tests/test_water_passage.py::FastVesselStitchTests | Coverage: COVERED
- AC-003 | Task: TASK-064-01 | Evidence: existing PassageEngineTests unchanged | Coverage: COVERED
- AC-004 | Task: TASK-064-02 | Evidence: tests/test_water_overlay_sync.py | Coverage: COVERED
- AC-005 | Task: TASK-064-03 | Evidence: MIXED deployment manifests + execution audit | Coverage: RUNTIME-MANUAL | Reason: protected hardware runtime acceptance

## Delivery tasks

1. Worker velocity-aware stitching + frontend Water overlay fallback
2. Sync-math and stitching unit tests
3. Validators + PR + CI + MIXED deploy + visual acceptance

## Task records

- TASK-064-01 | Worker velocity-aware stitch — predicted anchor, capped dynamic radius, claim safety; slow behavior preserved | AC-001, AC-002, AC-003 | Evidence: worker/water_passage.py, tests/test_water_passage.py | Status: PENDING
- TASK-064-02 | Frontend Water overlay alignment — lag clamp 1200ms, closest-earlier fallback within 2s | AC-004 | Evidence: frontend/sea-speed/index.html, tests/test_water_overlay_sync.py | Status: PENDING
- TASK-064-03 | Validation + MIXED deploy + acceptance — validators, CI, MIXED runtime, jet ski visual check | AC-001..AC-005 | Evidence: scripts/ci/validate_*.py, deployment manifests | Status: PENDING

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
- [ ] Runtime acceptance resolved (fast vessel passage + overlay alignment)
- [ ] Deferred work recorded (ByteTrack yaml tuning deferred)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
