# Delivery Tasks: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Plan: `specs/074-water-detection-recall-evidence/plan.md`
- Issue: #346
- Task 3A remediation PR: #358
- Task 3B reconciliation PR: #359
- Task 3C PR: #360
- Task 3C1 PR: #361
- Task 3C1 branch: `issue-346-task3c1-water-confidence-reconcile`
- Task 3C1 authorization: `OUTCOME APPROVED` from exact protected main `cf85d610311e2a0d9100b0851b20aed99f7aa9c3` for scope `issue-346-task3c1-ubuntu-water-confidence-reconciliation-v1`.

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
- [x] T025 Classify healthy passage `P-20260829T231340-5d4b1ffb`: `boat` confidence about `0.82`, class-map accepted, ROI accepted, stable `track_id=4183`.
- [x] T026 Classify unstable passage `P-20260829T232107-c5dcf174`: intermittent detections including confidence `0.1781`, bbox `20x8`, class-map/ROI accepted, `track_id=null`, plus surrounding zero-detection runs.
- [x] T027 Record dominant stage `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; record `TRACKER_NON_ASSIGNMENT` as secondary consequence; do not blame class-map or ROI.
- [x] T028 Present a separate Task 3C six-field tuning Scope and receive fresh literal `OUTCOME APPROVED` before source mutation.

### Task 3C Water-only low-confidence recall tuning

- [x] T029 Record Task 3C source authorization receipt on exact protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad` with `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`.
- [x] T030 Create fresh branch `issue-346-water-low-confidence-recall` from the exact authorization base.
- [x] T031 Change only canonical `water-v1.confidence` from `0.15` to `0.10`; keep `road-v1.confidence` at `0.15`.
- [x] T032 Update analytics profile tests to assert Water `0.10`, Road `0.15`, while retaining model/imgsz/tracker/sample/class-map contracts.
- [x] T033 Reconcile SDD 074 with Task 3B evidence verdict and Task 3C one-variable experiment.
- [x] T034 Verify exact base-to-head diff after CI remediation contains only the six authorized repository paths.
- [x] T035 Open one bounded PR #360 with a complete Change Contract and Ubuntu Worker production impact declared.
- [x] T035A Record first exact-head CI blocker: PR Validation `33284886697` and Quality `33284886705` failed only because `tests/test_frame_quality.py` still asserted Water confidence `0.15`; Change Contract, SDD and other shown independent quality domains passed.
- [x] T035B Obtain fresh literal `OUTCOME APPROVED` for remediation scope `issue-346-task3c-frame-quality-contract-remediation-v1`, adding only `tests/test_frame_quality.py` and authorizing no additional production behavior.
- [x] T035C Reconcile frame-quality detector invariants to Water confidence `0.10`, Road confidence `0.15`, and unchanged `image_size=960` for both profiles.
- [x] T035D Record metadata sequencing failure on runs `33285212866`/`33285212862`; create a fresh authoritative PR event without changing production behavior.
- [x] T036 Exact-head `Repository validation` run `33285244727` PASS.
- [x] T037 Exact-head `quality-integration` run `33285244723` PASS.
- [x] T038 Fresh merge probe confirmed protected main unchanged, exact six-file authorized diff, zero review threads and exact-green head `d804f89e...`.
- [x] T039 Merge exact green PR #360 to protected main `cf85d610311e2a0d9100b0851b20aed99f7aa9c3`.
- [x] T040 Exact-main `Repository validation` run `33285295734` PASS and `quality-integration` run `33285295735` PASS.
- [x] T041 Autonomous protected deployment run `33285316835` PASS; Ubuntu Worker executed and VPS application contour skipped.
- [x] T042 Worker readiness/frame/state/inference progression PASS on deployed exact main.
- [x] T043A Collect first post-deploy diagnostic evidence: runtime still reported `confidence_threshold=0.15`, exposing that the intended `0.10` experiment was not active.
- [ ] T043 Collect representative post-deploy Water evidence only after runtime threshold is proven `0.10`, including small/distant-vessel continuity and false-positive behavior.
- [ ] T044 PASS if continuity improves without materially uncontrolled false positives; otherwise FAIL and restore Water confidence to `0.15`.
- [x] T045 Keep tracker/imgsz/ROI/class-map/model/speed/API/frontend/Road tuning outside Task 3C; any different behavior change requires a new six-field Scope and fresh `OUTCOME APPROVED`.

### Task 3C1 Ubuntu Water confidence reconciliation

- [x] T046 Identify source-confirmed production contradiction: canonical `water-v1=0.10` but `configure-analytics-profiles.py` forced Water `worker.env` to `0.15`.
- [x] T047 Present fresh six-field Task 3C1 scope and receive literal `OUTCOME APPROVED` against protected main `cf85d610311e2a0d9100b0851b20aed99f7aa9c3`.
- [x] T048 Record generation 25 source authorization with `VISIBLE_SCOPE_PRESENTED=YES`, `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`, `SOURCE_AUTHORIZATION_ADMISSION=OPEN`; record that the branch ref was created before durable receipt but before any file mutation.
- [x] T049 Change protected Ubuntu Water reconciliation only from `YOLO_CONFIDENCE=0.15` to `0.10`; retain Road `0.15` and image size `960`.
- [x] T050 Extend the existing reconciler execution test to assert resulting Water `worker.env` is `water-v1`, confidence `0.10`, imgsz `960`, and Road env is `road-v1`, confidence `0.15`, imgsz `960`.
- [x] T051 Reconcile SDD 074 with completed Task 3C delivery, the production config contradiction and Task 3C1 acceptance gates.
- [x] T052 Verify exact base-to-head diff contains only the five Task 3C1 authorized paths; behind=0.
- [x] T053 Open one bounded Task 3C1 remediation PR #361 with complete Change Contract and Ubuntu Worker impact declared.
- [x] T053A Normalize SDD schema-only CI findings on PR #361: NFR pending statuses use `CONCERNS`, the production-learning transaction audit includes all eight stages, and canonical Definition of Done marker vocabulary is present; no production behavior changed.
- [ ] T054 Require exact-head `Repository validation` PASS and `quality-integration` PASS.
- [ ] T055 Perform fresh merge probe and merge only the exact green Task 3C1 head.
- [ ] T056 Require exact-main `Repository validation` PASS and `quality-integration` PASS.
- [ ] T057 Require repository-owned autonomous Ubuntu deployment PASS with VPS application contour skipped and Road desired state preserved.
- [ ] T058 Collect first post-deploy Water diagnostic and require `confidence_threshold=0.10` before resuming T043/T044 representative acceptance.

## Requirements traceability

- AC-001 | Task: T031,T032,T050 | Evidence: canonical and resulting-env Water `0.10` / Road `0.15` assertions | Coverage: COVERED
- AC-002 | Task: T052 | Evidence: exact connector base-to-head compare contains only five Task 3C1 authorized paths | Coverage: COVERED
- AC-003 | Task: T052,T045 | Evidence: exact protected-path diff review and tuning exclusions | Coverage: COVERED
- AC-004 | Task: T054 | Evidence: exact-head required Actions runs | Coverage: COVERED
- AC-005 | Task: T055 | Evidence: fresh main/head/diff/review probe and expected-head merge | Coverage: COVERED
- AC-006 | Task: T056 | Evidence: exact-main required Actions runs | Coverage: COVERED
- AC-007 | Task: T057 | Evidence: protected Ubuntu deployment and runtime progression audit | Coverage: COVERED
- AC-008 | Task: T043,T044 | Evidence: representative post-`0.10` vessel detection/track continuity | Coverage: RUNTIME-MANUAL | Reason: requires real small/distant vessel traffic after confirmed runtime threshold
- AC-009 | Task: T043,T044 | Evidence: representative post-`0.10` false-positive visual/diagnostic review | Coverage: RUNTIME-MANUAL | Reason: false-positive acceptability requires representative production traffic
- AC-010 | Task: T031,T032,T049,T050 | Evidence: Road remains `0.15` in canonical profile and resulting protected env | Coverage: COVERED
- AC-011 | Task: T045,T052 | Evidence: Task 3C1 scope and exact changed-file enforcement | Coverage: COVERED
- AC-012 | Task: T049,T050 | Evidence: executed reconciler writes Water `0.10`/960 and Road `0.15`/960 | Coverage: COVERED
- AC-013 | Task: T058 | Evidence: post-deploy `WATER_RECALL_DIAGNOSTIC.detector.confidence_threshold` equals `0.10` | Coverage: RUNTIME-MANUAL | Reason: requires exact deployed production runtime evidence

## Definition of Done

- [x] Issue/spec/plan/tasks current through Task 3C1 source admission, production-learning root cause and SDD schema remediation.
- [x] Exact changed-file scope verified against the five Task 3C1 authorized paths.
- [ ] Required tests and evidence complete after exact-head CI, exact-main CI, protected Ubuntu deployment and runtime threshold proof.
- [ ] Required CI green on the final exact PR head and exact merged main.
- [ ] Exact-green-head merge complete for Task 3C1 PR #361.
- [ ] Deployment state resolved with protected Ubuntu deployment complete and VPS application contour skipped.
- [ ] Runtime acceptance resolved after Water threshold `0.10` is proven and representative recall/false-positive evidence is evaluated, or controlled rollback is completed.
- [x] Deferred work recorded: any tracker/imgsz/ROI/class-map tuning requires a new scope; insufficient traffic remains explicit evidence deferral.
- [x] Risks resolved or explicitly accepted through one-variable scope, configuration-convergence regression coverage, protected deployment and rollback `0.10 -> 0.15`.
- [x] Waivers resolved or current: no waiver is requested.

## Completion gate

Issue #346 Task 3 is not complete until protected runtime is proven to use the intended Water threshold `0.10` and representative production acceptance establishes improved small/distant vessel continuity without materially uncontrolled false positives, or the experiment is rolled back and a newly authorized next direction is chosen.
