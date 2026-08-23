# Tasks: Registry hygiene — reject objects without photo

- Issue: #283
- Specification: specs/045-no-photo-registry-guard/spec.md
- Plan: specs/045-no-photo-registry-guard/plan.md

## Requirements traceability

- AC-001 | Task: TASK-045-01 | Evidence: tests/test_api_contract.py::NoPhotoGuardTests | Coverage: COVERED
- AC-002 | Task: TASK-045-02 | Evidence: tests/test_api_contract.py::NoPhotoGuardTests + passage guard | Coverage: COVERED
- AC-003 | Task: TASK-045-01 | Evidence: tests/test_api_contract.py::NoPhotoGuardTests | Coverage: COVERED
- AC-004 | Task: TASK-045-03 | Evidence: worker source pins + unit test | Coverage: COVERED
- AC-005 | Task: TASK-045-04 | Evidence: operator verification post-deploy | Coverage: RUNTIME-MANUAL | Reason: requires live VPS check for both domains
- AC-006 | Task: TASK-045-01 | Evidence: tests/test_api_contract.py::NoPhotoGuardTests (prune test) | Coverage: COVERED

## Delivery tasks

Ordered sequence: API low-level guards + cleanup, endpoint 422 guards, worker snapshot-write guard, tests/validators, PR, exact-green-head merge, MIXED deployment, runtime acceptance (road + water).

## Task records

- TASK-045-01 | API persist guards + prune_snapshotless_objects helper and startup call | AC-001, AC-003, AC-006 | Evidence: persist guards + cleanup test | Status: COMPLETE
- TASK-045-02 | API endpoint 422 for events and passages without snapshot | AC-001, AC-002 | Evidence: endpoint validation test | Status: COMPLETE
- TASK-045-03 | Worker hardening — snapshot write check before POST | AC-004 | Evidence: worker source pins | Status: COMPLETE
- TASK-045-04 | Validation and deploy — discovery green, validators PASS, PR, merges, manifests | AC-005 | Evidence: CI + manifests + operator check | Status: PENDING

## Completion gate

- [x] All TASK-045 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green on both required checks before merge
- [ ] Both contours runtime_verified; operator acceptance confirms zero missing photos (road + water)

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted (RISK-045-001..003 MITIGATED)
- [x] Waivers resolved or current (none)
