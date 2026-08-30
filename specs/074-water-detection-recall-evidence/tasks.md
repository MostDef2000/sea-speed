# Delivery Tasks: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Plan: `specs/074-water-detection-recall-evidence/plan.md`
- Issue: #346
- Task 3A remediation PR: #358
- Task 3B reconciliation PR: #359
- Task 3C branch: `issue-346-water-low-confidence-recall`
- Task 3C authorization: `OUTCOME APPROVED` from exact protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad` for scope `issue-346-task3c-water-low-confidence-recall-tuning-v1`.

## Delivery tasks

### Task 3A observability and Ubuntu IPC remediation

- [x] T001 Add optional post-threshold Water detector diagnostics without changing accepted detections.
- [x] T002 Record class/confidence/bbox/track/class-map/ROI/final-acceptance evidence.
- [x] T003 Keep diagnostics secret-free, bounded and single-pass.
- [x] T004 Add deterministic decision-equivalence and boundedness tests.
- [x] T005 Record that diagnostics cannot observe candidates below configured `model.track(..., conf=...)` threshold.
- [x] T006 Merge initial Task 3A source as PR #353.
- [x] T007 Record failed first Ubuntu rollout and automatic restoration.
- [x] T008 Identify Ubuntu monkey-patch/IPC root cause.
- [x] T009 Obtain fresh remediation authorization.
- [x] T010 Carry accepted detections plus diagnostics through the same single Ubuntu child inference result.
- [x] T011 Preserve two-argument callers and the 4 MiB IPC bound.
- [x] T012 Add Ubuntu IPC remediation tests.
- [x] T013 Verify exact remediation changed-file scope.
- [x] T014 Exact remediation head `dd341242e54f4e01382e2322e9571ec407cd295a`: PR Validation `33251179588` PASS; quality-integration `33251179586` PASS.
- [x] T015 Merge exact green remediation head through PR #358 to protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- [x] T016 Exact-main Repository validation `33251243227` PASS and quality-integration `33251243310` PASS.
- [x] T017 Protected Ubuntu deployment run `33251264466` PASS; Ubuntu REQUIRED/executed; VPS SKIPPED.
- [x] T018 Runtime progression PASS: frames `17->33`, state posts `4->9`, AI inference successes `29->54`; artifact ID `9714438874`.
- [x] T019 Defer representative vessel sampling until traffic is available.
- [x] T020 Keep threshold/class-map/ROI/tracker tuning blocked until evidence review.

### Task 3B representative evidence interpretation

- [x] T021 Obtain fresh Task 3B six-field authorization from exact protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- [x] T022 Reconcile SDD 074 with completed Task 3A delivery/runtime evidence.
- [x] T022A Normalize PR #359 Change Contract metadata after validation-only failures; no production behavior widened.
- [x] T023 Merge SDD reconciliation PR #359 to protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad`; exact-main Repository validation `33255091247` PASS and quality-integration `33255091254` PASS.
- [x] T024 Collect bounded representative Worker journal evidence temporally overlapping real vessel passages.
- [x] T025 Classify a healthy passage: `P-20260829T231340-5d4b1ffb` had `boat` confidence about `0.82`, class-map accepted, ROI accepted and stable `track_id=4183`.
- [x] T026 Classify an unstable passage: `P-20260829T232107-c5dcf174` had intermittent detections including confidence `0.1781`, bbox `20x8`, class-map/ROI accepted, `track_id=null`, plus surrounding zero-detection runs.
- [x] T027 Record dominant stage `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; record `TRACKER_NON_ASSIGNMENT` as secondary consequence; do not blame class-map or ROI.
- [x] T028 Present a separate Task 3C six-field tuning Scope and receive fresh literal `OUTCOME APPROVED` before source mutation.

### Task 3C Water-only low-confidence recall tuning

- [x] T029 Record Task 3C source authorization receipt on exact protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad` with `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.
- [x] T030 Create fresh branch `issue-346-water-low-confidence-recall` from the exact authorization base.
- [x] T031 Change only `water-v1.confidence` from `0.15` to `0.10`; keep `road-v1.confidence` at `0.15`.
- [x] T032 Update analytics profile tests to assert Water `0.10`, Road `0.15`, while retaining model/imgsz/tracker/sample/class-map contracts.
- [x] T033 Reconcile SDD 074 with Task 3B evidence verdict and Task 3C one-variable experiment.
- [ ] T034 Verify exact base-to-head diff contains only the five authorized repository paths.
- [ ] T035 Open one bounded PR with a complete Change Contract and Ubuntu Worker production impact declared.
- [ ] T036 Require exact-head `Repository validation` PASS.
- [ ] T037 Require exact-head `quality-integration` PASS.
- [ ] T038 Perform fresh merge probe: protected main, exact green head, exact diff, review threads and authorization assumptions.
- [ ] T039 Merge only the exact green head.
- [ ] T040 Require exact-main `Repository validation` PASS and `quality-integration` PASS.
- [ ] T041 Deploy exact main through the protected Ubuntu Worker contour; VPS MUST be skipped.
- [ ] T042 Require Worker readiness/frame/state/inference progression gates PASS on deployed exact main.
- [ ] T043 Collect representative post-deploy Water evidence for small/distant vessels and false-positive behavior.
- [ ] T044 PASS if continuity improves without materially uncontrolled false positives; otherwise FAIL and restore Water confidence to `0.15`.
- [ ] T045 Keep tracker/imgsz/ROI/class-map/model/speed/API/frontend/Road tuning outside Task 3C; any different behavior change requires a new six-field Scope and fresh `OUTCOME APPROVED`.

## Requirements traceability

- AC-001 | Task: T031,T032 | Evidence: `tests/test_analytics_profiles.py` | Coverage: IMPLEMENTED / PENDING CI
- AC-002 | Task: T034 | Evidence: exact base-to-head compare | Coverage: PENDING
- AC-003 | Task: T034 | Evidence: protected-path diff review | Coverage: PENDING
- AC-004 | Task: T036,T037 | Evidence: exact-head Actions runs | Coverage: PENDING
- AC-005 | Task: T038,T039 | Evidence: fresh merge probe and expected-head merge | Coverage: PENDING
- AC-006 | Task: T040 | Evidence: exact-main required Actions runs | Coverage: PENDING
- AC-007 | Task: T041,T042 | Evidence: protected Ubuntu deployment/runtime gate | Coverage: PENDING
- AC-008 | Task: T043,T044 | Evidence: representative post-deploy vessel continuity | Coverage: PENDING RUNTIME
- AC-009 | Task: T043,T044 | Evidence: representative false-positive review | Coverage: PENDING RUNTIME
- AC-010 | Task: T031,T032,T034 | Evidence: Road profile remains `0.15`, no Road source changes | Coverage: IMPLEMENTED / PENDING CI
- AC-011 | Task: T045 | Evidence: exact scope and canonical checkpoints | Coverage: ENFORCED

## Definition of Done

### Task 3A

- [x] Observability source and Ubuntu IPC remediation merged.
- [x] Exact-head/exact-main quality gates passed.
- [x] Protected Ubuntu deployment and runtime progression passed.

### Task 3B

- [x] SDD reconciliation merged.
- [x] Representative production evidence collected.
- [x] Dominant loss stage recorded as detector visibility instability.
- [x] Fresh separate tuning authorization obtained before behavior change.

### Task 3C

- [x] Fresh authorization recorded.
- [x] Water-only threshold implementation and profile test update completed on a fresh branch.
- [ ] Exact diff verified and bounded PR opened.
- [ ] Exact-head required checks green.
- [ ] Exact-green-head merge complete.
- [ ] Exact-main required checks green.
- [ ] Protected Ubuntu deployment/runtime gates green.
- [ ] Representative production acceptance PASS, or controlled rollback to Water `0.15` completed after FAIL.

## Completion gate

Issue #346 Task 3 is not complete until Task 3C production acceptance establishes that the lower Water threshold improves small/distant vessel continuity without materially uncontrolled false positives, or the experiment is rolled back and a newly authorized next direction is chosen.
