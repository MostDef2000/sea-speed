# Delivery Tasks: Reciprocal Water/Road navigation toggle

- Specification: specs/021-water-road-reciprocal-nav/spec.md
- Issue: #209
- Status: Implementing

## Delivery tasks

- T-001 [x] Update `frontend/sea-speed/index.html` so Water shows one highlighted `Дорога` link to `/sea-speed/road/` beside `Камеры`.
- T-002 [x] Update `frontend/sea-speed/road/index.html` so Road shows one highlighted `Вода` link to `/sea-speed/` beside `Камеры`.
- T-003 [x] Extend `tests/test_frontend_contract.py` with exact reciprocal navigation assertions while preserving existing authenticated navigation/runtime contracts.
- T-004 [x] Add the mandatory `specs/021-water-road-reciprocal-nav/{spec,plan,tasks}.md` delivery-quality layer after CI exposed significant-frontend SDD linkage.
- T-005 [x] Synchronize `tests/test_analytics_profiles.py` so Water/Objects/Cameras retain Road navigation while the Road page asserts reciprocal `Вода` navigation to `/sea-speed/`; preserve all private-source, M2M and bounded Road-control assertions.
- T-006 [ ] Verify the final diff is exactly the seven authorized paths and is ahead-only from the authorization base/current `main`.
- T-007 [ ] Require linked SDD validation, PR Validation and aggregate Quality integration to pass on the same exact final PR head.
- T-008 [ ] Refresh `main`, PR head, changed-file scope, reviews and review threads; merge PR #210 only with expected-head protection.
- T-009 [ ] Require post-merge Quality to pass on the exact resulting `main` SHA and persist source-integration evidence to Issue #209.
- T-010 [ ] Obtain a separate exact-SHA production authorization with fingerprint and `Execution-Intent: EXECUTE`; do not infer production authority from `OUTCOME APPROVED`.
- T-011 [ ] Execute VPS-only Connector deployment for the exact authorized merged SHA; require exact release/deployment evidence and no Ubuntu Worker/relay update.
- T-012 [ ] Complete authenticated browser smoke: Water shows highlighted `Дорога`, Road shows highlighted `Вода`, both directions navigate correctly, and the protected session remains usable.
- T-013 [ ] Persist final runtime/browser evidence and close Issue #209 only after all source, deployment and runtime acceptance gates pass.

## Requirements traceability

- AC-001 | Task: T-001,T-002,T-003,T-005 | Evidence: tests/test_frontend_contract.py reciprocal Water/Road navigation contract plus synchronized tests/test_analytics_profiles.py navigation regression | Coverage: COVERED
- AC-002 | Task: T-003,T-005,T-007 | Evidence: existing frontend authenticated navigation/runtime contract, analytics-profile protected-source/M2M/control regression and exact-head repository behavioral tests | Coverage: COVERED
- AC-003 | Task: T-004,T-006,T-007,T-008,T-009 | Evidence: exact seven-path compare, linked SDD validation, PR Validation, aggregate Quality, expected-head merge and post-merge main Quality | Coverage: COVERED
- AC-004 | Task: T-010,T-011,T-012,T-013 | Evidence: Issue #209 production authorization, exact VPS deployment manifest and authenticated Water↔Road browser smoke | Coverage: RUNTIME-MANUAL | Reason: protected production session behavior and deployed exact-release navigation must be observed in the live VPS contour

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Completion gate

The issue remains open until the exact seven-path source change is green and merged, post-merge Quality passes, separate exact-SHA production authorization is recorded, VPS-only Connector deployment is accepted, and authenticated browser smoke proves the reciprocal Water↔Road navigation in production. Source merge alone is not `COMPLETE`.
