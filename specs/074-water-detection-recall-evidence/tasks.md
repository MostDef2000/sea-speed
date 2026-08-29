# Delivery Tasks: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Plan: `specs/074-water-detection-recall-evidence/plan.md`
- Issue: #346
- Original branch: `issue-346-water-recall-evidence`
- Original authorization: Task 3A `OUTCOME APPROVED` from exact protected main `739947c11471c746e74af0dfee4d9a5edd0d7bac`.
- Remediation branch: `issue-346-water-recall-ipc-remediation`
- Remediation PR: #358
- Remediation Change Contract: canonical PR schema bound to #358 before authoritative CI.
- Remediation authorization: `OUTCOME APPROVED` from exact protected main `7b9902adca65d43151de629d15e526a5f79d3899` for scope `issue-346-task3a-ubuntu-diagnostic-ipc-remediation-v1`.
- Runtime contour: Ubuntu Worker REQUIRED; VPS NOT REQUIRED.

## Delivery tasks

- [x] T001 Add an optional detector diagnostics sink that records post-threshold model class/confidence/bbox/track/class-map evidence without changing returned detections.
- [x] T002 Add bounded Water-only structured diagnostics with existing ROI-center relation and actual post-ROI acceptance outcome.
- [x] T003 Keep diagnostics secret-free and bounded by default interval, record cap and no additional inference pass.
- [x] T004 Add deterministic tests for decision equivalence, stage fields, rate limiting, truncation and secret exclusion.
- [x] T005 Record the post-threshold observability limitation so below-threshold misses are not misclassified as evidence.
- [x] T006 First 3A source passed exact-head/exact-main gates and merged as PR #353.
- [x] T007 Record failed Ubuntu rollout evidence: candidate `7b9902ad...` failed runtime progression twice and automatically restored `739947c...`.
- [x] T008 Identify production root cause: Ubuntu monkey-patch rejected `diagnostics=` and child IPC discarded class-map rejects.
- [x] T009 Obtain fresh bounded remediation authorization for Ubuntu child/parent IPC paths.
- [x] T010 Serialize accepted detections plus diagnostic records from the same single child `model.track()` result without changing accepted detection fields/values.
- [x] T011 Make the Ubuntu parent supervisor and monkey-patched detector accept an optional diagnostic sink while preserving two-argument callers and the 4 MiB response bound.
- [x] T012 Add deterministic remediation tests for accepted-output equality, diagnostic-only rejects, one inference call, sink compatibility, boundedness and secret exclusion.
- [x] T013 Verify exact remediation changed-file scope and SDD/Change Contract admission; base-to-head review contains only six authorized paths.
- [ ] T014 Require exact remediation PR-head Repository validation and quality-integration green.
- [ ] T015 Fresh-read main/head/scope/review state and merge only the exact green remediation head.
- [ ] T016 Require exact-main Repository validation and quality-integration green.
- [ ] T017 Deploy exact-main Ubuntu Worker through the protected zero-touch contour; VPS must skip.
- [ ] T018 Require AI self-test -> Worker started -> frame/state progression PASS and record exact deployment artifact/audit evidence.
- [ ] T019 Explicitly defer representative vessel log sampling if traffic is unavailable.
- [ ] T020 Keep later threshold/class-map/ROI/tracker tuning blocked until evidence is reviewed under a new bounded authorization.

## Requirements traceability

- AC-001 | Task: T001,T004,T010,T012 | Evidence: in-process equality test plus `test_child_side_channel_preserves_accepted_detection_semantics` | Coverage: COVERED
- AC-002 | Task: T001,T002,T004,T010 | Evidence: raw/class/track/ROI/final-acceptance fields and child post-threshold records | Coverage: COVERED
- AC-003 | Task: T002,T003,T004,T012 | Evidence: detector/ROI settings and secret-free child/parent assertions | Coverage: COVERED
- AC-004 | Task: T002,T003,T004,T011,T012 | Evidence: interval suppression, record cap, truncation flag and framed-response hard bound | Coverage: COVERED
- AC-005 | Task: T013 | Evidence: exact remediation base-to-head changed-file comparison and protected-path review | Coverage: COVERED
- AC-006 | Task: T014,T015,T016 | Evidence: exact-head and exact-main GitHub required checks plus expected-head merge | Coverage: COVERED
- AC-007 | Task: T017,T018,T019 | Evidence: protected Ubuntu Worker exact-main deployment manifest/artifact/audit and runtime progression PASS; representative traffic sample may be deferred | Coverage: RUNTIME-MANUAL | Reason: representative vessel traffic is time-dependent and may be unavailable during deployment, while exact runtime progression is machine-verifiable.
- AC-008 | Task: T005,T009,T020 | Evidence: SDD boundaries and canonical #346 checkpoints keep recall tuning separately authorized | Coverage: COVERED
- AC-009 | Task: T010,T011,T012 | Evidence: `tests/test_water_recall_ubuntu_ipc.py` | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current for remediation implementation
- [x] Exact changed-file scope verified
- [x] Required deterministic remediation tests authored
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head remediation merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the remediation design.
- [ ] Required CI is green.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [ ] Applicable deployment/runtime acceptance is complete.
- [x] Runtime learning and deferred work are written back to the feature artifacts.

Task 3A can reach source/deployment completion without representative-vessel sampling when traffic is unavailable, provided the remediation exact Worker release reaches the protected runtime progression gate. That deferral does not authorize any recall tuning; Task 3 evidence interpretation and behavior changes remain a separately authorized follow-up.
