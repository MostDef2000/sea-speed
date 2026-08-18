# Delivery Tasks: Water detection activation and registry cap

- Specification: specs/022-water-detection-registry-cap/spec.md
- Plan: specs/022-water-detection-registry-cap/plan.md
- Issue: #212
- Status: Implementing

## Delivery tasks

- T-001 [P0] Original `water-v1` default/profile activation source integration. COMPLETE through PR #213.
- T-002 [P0] Original newest-100 combined SQLite Objects Registry retention behavior and tests. COMPLETE through PR #213 and accepted VPS evidence.
- T-003 [P0] Original exact runtime `9e0cd96aa2f790f1ba806299c3dd4019e5572899` infrastructure/provenance rollout. COMPLETE as infrastructure evidence; later functional Water acceptance was invalidated by production regression.
- T-004 [P0] Production-learning SDD correction through PR #214. COMPLETE; current source/control-plane main at fresh authorization is `f3febcd6d9ae6a57e052f6b4a50bf3ec9f75fdf1`.
- T-005 [P0] Reopen Issue #212 and record real-vessel regression: moving in-ROI target with `MOTION idle`, `AI idle`, `DETECTIONS 0`, `TRACKS 0`. COMPLETE.
- T-006 [P0] Obtain fresh six-path source authorization for Water continuous detection remediation. COMPLETE: Issue #212 comment `5323802105` records exact scope and `OUTCOME APPROVED`.
- T-007 [P0] Add profile-aware detection admission: Water runs YOLO on every sampled ROI-bounded frame and bypasses motion-box filtering; Road preserves motion gate/filter. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-008 [P0] Change Water event admission to one successful event per tracked `vessel` without speed readiness, while preserving Road speed/event readiness logic. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-009 [P0] Add deterministic focused Water/Road regression tests and analytics-profile protection assertions. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-010 [P0] Reconcile spec/plan/tasks to production regression, source authorization, Ubuntu-only runtime contour, risk/test design and transaction audit. IN PROGRESS.
- T-011 [P0] Verify exact six-path diff against authorization base; ensure no protected model/ROI/API/deploy/frontend path changed. PENDING.
- T-012 [P0] Open canonical PR with valid Change Contract declaring `Production impact: UBUNTU_WORKER`, Ubuntu deployment REQUIRED, VPS NOT REQUIRED, Risk profile REQUIRED and source authorization `OUTCOME APPROVED`. PENDING.
- T-013 [P0] Reach exact-head PR Validation and aggregate Quality; automatically remediate any in-scope deterministic defect without widening scope. PENDING.
- T-014 [P0] Re-check current main, exact head, six-path scope and review state; merge only the exact green head; require exact-main post-merge Quality. PENDING.
- T-015 [P0] Persist source integration evidence and compute the new exact merged executable release. PENDING.
- T-016 [P0] Obtain a fresh exact-SHA production safety envelope before any Ubuntu mutation. PENDING HUMAN DECISION AFTER SOURCE MERGE.
- T-017 [P0] After production authorization, deploy the exact Ubuntu release while preserving Road desired state and prove exact model/profile/source/runtime identity plus sustained Water 5-FPS inference health. PENDING RUNTIME.
- T-018 [P0] Require a naturally occurring moving vessel inside Water ROI to produce non-zero `DETECTIONS`/`TRACKS` and one new `vessel` event without synthetic production evidence. PENDING RUNTIME.
- T-019 [P0] Persist final sanitized source/runtime/functional acceptance evidence to Issue #212 and close only when all mandatory gates pass. PENDING.

## Requirements traceability

- AC-001 | Task: T-007,T-009 | Evidence: `tests/test_water_detection_pipeline.py` Water no-motion inference regression | Coverage: COVERED
- AC-002 | Task: T-007,T-009 | Evidence: `tests/test_water_detection_pipeline.py` verifies no Water motion-filter call and retained ROI filter | Coverage: COVERED
- AC-003 | Task: T-007,T-013 | Evidence: existing `tests/test_worker_roi_pipeline.py` plus exact-head CI | Coverage: COVERED
- AC-004 | Task: T-007,T-009 | Evidence: focused Road motion inactive/active policy regression | Coverage: COVERED
- AC-005 | Task: T-008,T-009 | Evidence: tracked Water vessel event-candidate regression without speed readiness | Coverage: COVERED
- AC-006 | Task: T-008,T-009 | Evidence: posted-track dedupe and non-null track-ID regressions | Coverage: COVERED
- AC-007 | Task: T-009,T-013 | Evidence: `tests/test_analytics_profiles.py` plus exact-head CI | Coverage: COVERED
- AC-008 | Task: T-002,T-013 | Evidence: unchanged existing `tests/test_api_contract.py` registry/API contract suite | Coverage: COVERED
- AC-009 | Task: T-011,T-012,T-013 | Evidence: Connector exact compare, PR Validation and aggregate Quality | Coverage: COVERED
- AC-010 | Task: T-014,T-015 | Evidence: expected-head merge and exact-main post-merge Quality | Coverage: COVERED
- AC-011 | Task: T-016,T-017 | Evidence: exact-SHA Ubuntu deployment, model/profile/service/frame/AI/GPU and Road-state evidence | Coverage: RUNTIME-MANUAL | Reason: production GPU/service/runtime state requires separately authorized live Ubuntu evidence
- AC-012 | Task: T-018,T-019 | Evidence: real naturally occurring vessel detection/track/event evidence recorded in Issue #212 | Coverage: RUNTIME-MANUAL | Reason: physical scene occurrence and production event transport cannot be proven by hosted CI

## Definition of Done

- [x] Issue/spec/plan/tasks current — regression, authorization and source design are reconciled on the task branch; final CI/merge/runtime evidence remains pending.
- [ ] Exact changed-file scope verified — must confirm exactly six authorized paths on final PR head.
- [ ] Required tests and evidence complete — source regressions are authored; CI and production natural-vessel evidence remain.
- [ ] Required CI green — exact-head PR Validation/Quality and exact-main post-merge Quality remain.
- [ ] Exact-green-head merge complete — task branch is not yet merged.
- [ ] Deployment state resolved — future exact merged Ubuntu release is not production-authorized or deployed.
- [ ] Runtime acceptance resolved — sustained continuous inference and real-vessel event acceptance remain.
- [x] Deferred work recorded — protected model parameters, ROI editor, camera/media topology, API/schema and retention redesign are explicitly out of scope.
- [ ] Risks resolved or explicitly accepted — source mitigations are defined; GPU duty-cycle risk remains open until runtime acceptance.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the exact six-path source diff passes PR Validation and aggregate Quality on one exact head, merges with expected-head protection, receives exact-main post-merge Quality, a fresh production safety envelope authorizes that exact executable SHA, Ubuntu deployment/verification preserves Road desired state and sustained Water inference health, and a real naturally occurring vessel inside ROI produces non-zero detections/tracks plus one persisted `vessel` event without synthetic production evidence. Issue #212 must contain the final sanitized evidence before closure.
