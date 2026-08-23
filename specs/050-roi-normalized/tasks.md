# Tasks: Normalized ROI model 0..1 for HD 1920 and future 4K

- Issue: #294
- Specification: specs/050-roi-normalized/spec.md
- Plan: specs/050-roi-normalized/plan.md

## Requirements traceability

- AC-001 | Task: TASK-050-01 | Evidence: test_roi_normalization legacy 704 migration | Coverage: COVERED
- AC-002 | Task: TASK-050-01 | Evidence: test_roi_normalization normalized roundtrip | Coverage: COVERED
- AC-003 | Task: TASK-050-01 | Evidence: deploy migration + api read migration | Coverage: COVERED
- AC-004 | Task: TASK-050-01 | Evidence: frontend code 1920/1080 + normalize | Coverage: COVERED
- AC-005 | Task: TASK-050-01 | Evidence: worker scaled mask center test | Coverage: COVERED
- AC-006 | Task: TASK-050-02 | Evidence: discover + validators + MIXED manifest | Coverage: COVERED

## Delivery tasks

Ordered sequence: api normalization + migration, worker scale-on-read, frontend normalization, VPS migration hook, tests, validators, PR, MIXED deploy MIXED runtime_verified.

## Task records

- TASK-050-01 | Normalized ROI implementation — api/app/main.py dual-schema + reference, worker/hls scale + speed/crossing, frontend/index normalize 16/9, deploy/vps migrate | AC-001, AC-002, AC-003, AC-004, AC-005 | Evidence: git diff + test_roi_normalization.py | Status: COMPLETE
- TASK-050-02 | Validation & deploy — SDD validators, file-scope, full unittest, PR, exact-green-head merge, MIXED runtime_verified water+road, visual ROI check | AC-006 | Evidence: CI + manifest + screenshots | Status: PENDING

## Completion gate

- [ ] All TASK-050 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green before merge
- [ ] Exact-main Quality green
- [ ] MIXED deployment runtime_verified (VPS+Worker)
- [ ] Visual ROI acceptance water+road

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified and matches Change Contract
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS+Worker runtime_verified)
- [ ] Runtime acceptance resolved (ROI visual)
- [ ] Deferred work recorded (future 4K automatic)
- [ ] Risks resolved or explicitly accepted (REQUIRED documented)
- [ ] Waivers resolved or current (none)
