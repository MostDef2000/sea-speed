# Tasks: Registry image zoom and live stream fullscreen

- Issue: #287
- Specification: specs/047-registry-live-fullscreen/spec.md
- Plan: specs/047-registry-live-fullscreen/plan.md

## Requirements traceability

- AC-001 | Task: TASK-047-01 | Evidence: manual overlay test (registry card) | Coverage: RUNTIME-MANUAL | Reason: browser DOM overlay
- AC-002 | Task: TASK-047-01 | Evidence: manual overlay test (detail) | Coverage: RUNTIME-MANUAL | Reason: browser DOM overlay
- AC-003 | Task: TASK-047-02 | Evidence: manual water fullscreen test | Coverage: RUNTIME-MANUAL | Reason: HLS video fullscreen requires browser
- AC-004 | Task: TASK-047-03 | Evidence: manual road fullscreen test | Coverage: RUNTIME-MANUAL | Reason: HLS video fullscreen requires browser
- AC-005 | Task: TASK-047-01, TASK-047-02, TASK-047-03 | Evidence: Esc/backdrop/× checks | Coverage: RUNTIME-MANUAL | Reason: keyboard/backdrop requires browser
- AC-006 | Task: TASK-047-01 | Evidence: git diff --stat (3 files) | Coverage: COVERED

## Delivery tasks

Ordered sequence: registry zoom overlay, water live fullscreen, road live fullscreen, validators/PR/merge/deploy.

## Task records

- TASK-047-01 | Registry image zoom overlay — add #imageZoomOverlay + handlers to `frontend/sea-speed/objects/index.html` | AC-001, AC-002, AC-005, AC-006 | Evidence: DOM smoke + validate_change_contract | Status: COMPLETE
- TASK-047-02 | Water live fullscreen — add ⛶ button + #liveFullscreenOverlay moving #video to `frontend/sea-speed/index.html` | AC-003, AC-005 | Evidence: manual smoke | Status: COMPLETE
- TASK-047-03 | Road live fullscreen — same for `frontend/sea-speed/road/index.html` (#livePreviewFrame) | AC-004, AC-005 | Evidence: manual smoke | Status: COMPLETE
- TASK-047-04 | Validation & deploy — SDD validators, file-scope check, PR, exact-green-head merge, VPS runtime_verified, operator acceptance | AC-006 | Evidence: CI + manifest + mostdef.ru check | Status: PENDING

## Completion gate

- [x] All TASK-047 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green before merge
- [ ] VPS runtime_verified after merge
- [ ] Operator acceptance: zoom + both fullscreen overlays verified

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified (3 frontend files)
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (VPS runtime_verified)
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (NOT REQUIRED)
- [ ] Waivers resolved or current (none)
