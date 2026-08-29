# Delivery Tasks: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Plan: `specs/074-water-detection-recall-evidence/plan.md`
- Issue: #346
- Original branch: `issue-346-water-recall-evidence`
- Original authorization: Task 3A `OUTCOME APPROVED` from exact protected main `739947c11471c746e74af0dfee4d9a5edd0d7bac`.
- Remediation branch: `issue-346-water-recall-ipc-remediation`
- Remediation PR: #358
- Remediation authorization: `OUTCOME APPROVED` from exact protected main `7b9902adca65d43151de629d15e526a5f79d3899` for scope `issue-346-task3a-ubuntu-diagnostic-ipc-remediation-v1`.
- Task 3B branch: `issue-346-water-recall-evidence-interpretation`
- Task 3B authorization: `OUTCOME APPROVED` from exact protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6` for scope `issue-346-task3b-water-recall-evidence-interpretation-v1`.
- Task 3B runtime contour: Ubuntu Worker READ-ONLY EVIDENCE REQUIRED; VPS NOT REQUIRED; deployment NOT REQUIRED.

## Delivery tasks

### Task 3A observability and Ubuntu IPC remediation

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
- [x] T014 Require exact remediation PR-head Repository validation and quality-integration green: exact head `dd341242e54f4e01382e2322e9571ec407cd295a`, PR Validation run `33251179588` PASS, quality-integration run `33251179586` PASS.
- [x] T015 Fresh-read main/head/scope/review state and merge only the exact green remediation head: PR #358 merged at expected head `dd341242e54f4e01382e2322e9571ec407cd295a` to protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- [x] T016 Require exact-main Repository validation and quality-integration green: runs `33251243227` and `33251243310` PASS.
- [x] T017 Deploy exact-main Ubuntu Worker through the protected zero-touch contour; deployment run `33251264466` PASS; Ubuntu REQUIRED/executed; VPS SKIPPED.
- [x] T018 Require AI self-test -> Worker started -> frame/state progression PASS and record exact deployment artifact/audit evidence: frames `17->33`, state posts `4->9`, AI inference successes `29->54`, `frame_and_state_progression=PASS`, artifact ID `9714438874`, evidence ZIP digest `sha256:66556adea96476163403a1440fd7bdb1aa3c24a07945dce02ab36699e708c1e5`.
- [x] T019 Explicitly defer representative vessel log sampling when deployment-time traffic/evidence was unavailable; accepted Worker remains instrumented for later read-only sampling.
- [x] T020 Keep threshold/class-map/ROI/tracker tuning blocked after Task 3A; no tuning was performed or authorized.

### Task 3B representative evidence interpretation

- [x] T021 Obtain fresh six-field Task 3B authorization from exact protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6` for SDD reconciliation plus bounded read-only diagnostic sampling.
- [x] T022 Reconcile spec/plan/tasks with completed Task 3A exact-head, merge, exact-main, deployment and runtime evidence; remove stale PENDING production state.
- [ ] T023 Collect a bounded representative sample of existing `WATER_RECALL_DIAGNOSTIC` records from `sea-speed-worker.service` while real Water vessel traffic is visible. Do not restart, redeploy or retune the Worker to obtain the sample.
- [ ] T024 Correlate accepted and visually missed/unstable vessel examples and classify observed loss across post-threshold detector visibility, class mapping, ROI-center filtering and tracker continuity.
- [ ] T025 Record a dominant evidence-supported loss stage, or explicitly record `INCONCLUSIVE` if the current post-threshold evidence cannot distinguish the cause.
- [ ] T026 If and only if T025 supports a behavioral change, present a new separate six-field tuning Scope. No tuning source mutation is permitted under Task 3B authorization.

## Requirements traceability

- AC-001 | Task: T001,T004,T010,T012 | Evidence: in-process equality test plus `test_child_side_channel_preserves_accepted_detection_semantics` | Coverage: COVERED
- AC-002 | Task: T001,T002,T004,T010 | Evidence: raw/class/track/ROI/final-acceptance fields and child post-threshold records | Coverage: COVERED
- AC-003 | Task: T002,T003,T004,T012 | Evidence: detector/ROI settings and secret-free child/parent assertions | Coverage: COVERED
- AC-004 | Task: T002,T003,T004,T011,T012 | Evidence: interval suppression, record cap, truncation flag and framed-response hard bound | Coverage: COVERED
- AC-005 | Task: T013 | Evidence: exact remediation base-to-head changed-file comparison and protected-path review | Coverage: COVERED
- AC-006 | Task: T014,T015,T016 | Evidence: exact-head runs `33251179588`/`33251179586`, expected-head merge #358, exact-main runs `33251243227`/`33251243310` | Coverage: COVERED
- AC-007 | Task: T017,T018,T019 | Evidence: deployment run `33251264466`, artifact `9714438874`, runtime progression PASS, explicit representative-sampling deferral | Coverage: COVERED for Task 3A
- AC-008 | Task: T005,T009,T020,T026 | Evidence: SDD and canonical #346 authorization boundaries keep recall tuning separately authorized | Coverage: COVERED
- AC-009 | Task: T010,T011,T012 | Evidence: `tests/test_water_recall_ubuntu_ipc.py` | Coverage: COVERED
- AC-010 | Task: T021,T022 | Evidence: SDD 074 reconciled to canonical Task 3A delivery evidence | Coverage: COVERED
- AC-011 | Task: T023,T024,T025 | Evidence: representative bounded production diagnostics plus durable stage interpretation or `INCONCLUSIVE` | Coverage: PENDING RUNTIME EVIDENCE

## Definition of Done

### Task 3A

- [x] Issue/spec/plan/tasks reflect implementation and production learning.
- [x] Exact changed-file scope verified.
- [x] Required deterministic remediation tests passed through authoritative CI.
- [x] Exact-head required checks green.
- [x] Exact-green-head merge complete.
- [x] Exact-main required checks green.
- [x] Ubuntu deployment state resolved with VPS skipped.
- [x] Runtime acceptance resolved with `frame_and_state_progression=PASS`.
- [x] Representative sampling deferral recorded without authorizing tuning.
- [x] Risks and waivers resolved or not required.

Task 3A source/deployment/runtime is COMPLETE at accepted production source `ea6f1e9d15252840d27721f004817ba35f11d0c6`.

### Task 3B

- [x] Fresh source authorization recorded.
- [x] SDD reconciliation implemented on a fresh branch from exact approved main.
- [ ] Documentation-only PR required checks green and exact-green-head merge complete.
- [ ] Representative bounded diagnostic sample collected.
- [ ] Dominant loss stage or `INCONCLUSIVE` recorded durably.
- [ ] Any later behavior tuning remains blocked behind a new Scope and fresh `OUTCOME APPROVED`.

## Completion gate

- [x] Task 3A requirements, delivery evidence and runtime acceptance are complete.
- [x] Task 3B source boundaries and interpretation rules are explicit.
- [ ] Task 3B SDD-only PR is merged after required checks.
- [ ] Task 3B representative production evidence has been interpreted.
- [ ] Issue #346 Task 3 final recall outcome is not complete until representative evidence supports either acceptance with no tuning or a separately authorized tuning delivery.

Current admissible runtime action after this SDD reconciliation is a bounded read-only observation of existing `WATER_RECALL_DIAGNOSTIC` records during representative vessel traffic. Absence of those lines from the prior deployment Actions log is not evidence of absence because that workflow did not export the Worker service journal.
