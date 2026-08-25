# Tasks: Road overlay polish — lag compensation, clean preview restore, stable crossings

- Issue: #314
- Specification: specs/059-road-overlay-polish/spec.md
- Plan: specs/059-road-overlay-polish/plan.md

## Requirements traceability

- AC-001 | Task: TASK-059-01 | Evidence: tests/test_road_overlay_sync.py | Coverage: COVERED
- AC-002 | Task: TASK-059-02 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- AC-003 | Task: TASK-059-03 | Evidence: tests/test_road_overlay_sync.py, tests/test_frontend_contract.py | Coverage: COVERED

## Delivery tasks

1. Frontend lag compensation + stable crossings
2. Frontend clean preview restore
3. Tests + validators + PR + CI + VPS deploy + visual acceptance

## Task records

- TASK-059-01 | Frontend lag compensation + stable crossings — median delta 0..600ms, bracket-only, hi-crossings stable | AC-001, AC-003 | Evidence: frontend/sea-speed/road/index.html, tests/test_road_overlay_sync.py | Status: PENDING
- TASK-059-02 | Clean preview restore — duplicate Hls.js 1.5.7 for cleanPreviewVideo, same hls_url | AC-002 | Evidence: frontend/sea-speed/road/index.html, tests/test_frontend_contract.py | Status: PENDING
- TASK-059-03 | Validation + VPS deploy + acceptance — validators, CI, VPS runtime_verified | AC-001..AC-003 | Evidence: scripts/ci/validate_*.py, tests/test_*.py, deployment manifests | Status: PENDING

## Completion gate

- [ ] All tasks COMPLETE or RUNTIME-MANUAL
- [ ] Exact-head CI green
- [ ] Exact-main Quality green
- [ ] VPS runtime_verified

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS runtime_verified)
- [ ] Runtime acceptance resolved (lag-compensated sync + clean preview + stable crossings)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none expected)
