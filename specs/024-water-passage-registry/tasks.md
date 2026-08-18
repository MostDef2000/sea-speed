# Delivery Tasks: Water Passage Architecture

- Specification: specs/024-water-passage-registry/spec.md
- Plan: specs/024-water-passage-registry/plan.md
- Issue: #218
- Status: Correct-course remediation

## Delivery tasks

- T-001 [P0] Record initial passage source authorization and later bounded Auth 500 recovery expansion. COMPLETE: initial comments `5325409717` / `5325529286`; recovery expansion comment `5327660150`.
- T-002 [P0] Add pure bounded `worker/water_passage.py` with passage identity, short split stitching, active caps, RAM ring buffers and pluggable speed estimator boundary. COMPLETE IN PR #219.
- T-003 [P0] Implement `two_gate` as first speed strategy with A→B/B→A and incomplete/null speed semantics. COMPLETE IN PR #219.
- T-004 [P0] Integrate Water Worker passage transport, best vessel crop, transition-only/idempotent posting and passage labels while preserving Road event path and protected Water inference settings. COMPLETE IN PR #219.
- T-005 [P0] Add dedicated VPS `water_passages` SQLite persistence, idempotent upsert, 300-row completed-first retention, orphan snapshot cleanup and `/api/cam1/passages`. COMPLETE IN PR #219.
- T-006 [P0] Change Water operator recent-history view to passage lifecycle cards with passage ID, measuring/measured speed and direction. COMPLETE IN PR #219.
- T-007 [P0] Include `worker/water_passage.py` in Ubuntu Worker and edge exact artifact allowlists. COMPLETE IN PR #219.
- T-008 [P0] Add deterministic passage/strategy/retention/frontend/artifact tests and keep existing Water/Road/API regression suites intact. COMPLETE IN PR #219; exact-head and exact-main Quality passed.
- T-009 [P0] Merge the initial Water Passage architecture with exact-head protection and record exact-main Quality. COMPLETE: PR #219 -> `e814d32f9b743d674ce87556313e264debd0bc14`.
- T-010 [P0] Treat operator-observed `https://mostdef.ru/sea-speed/` HTTP 500 as release-blocking production feedback and perform adjacent-stage correct-course analysis. COMPLETE: root-cause comment `5327488945`.
- T-011 [P0] Add pre-source VPS protected-entrypoint gate: healthy `302|401|403` continues, exact HTTP 500 enters bounded privileged recovery, all other statuses fail closed. IMPLEMENTED ON `agent/water-passage-auth-recovery`; CI PENDING.
- T-012 [P0] Extend restricted helper reconciliation so only the explicit protected-baseline `/sea-speed/ ... HTTP 500` failure may retry the exact source-managed cutover without the healthy-baseline prerequisite. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-013 [P0] On failed recovery activation, restore exact pre-recovery nginx bytes from bounded roots and prove nginx syntax/service health; retain no arbitrary root command/path input. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-014 [P0] Add helper unit tests and VPS transaction tests proving recovery happens before live Water source mutation, non-500 failures do not recover, and failed recovery requires rollback. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-015 [P0] Synchronize SDD risk/test/transaction/correct-course evidence with the observed HTTP 500 and expanded authorization. COMPLETE ON TASK BRANCH.
- T-016 [P0] Open a canonical remediation PR with exact changed-file subset inside the current sixteen-path authorization union and valid MIXED Change Contract. PENDING.
- T-017 [P0] Reach exact-head PR Validation and aggregate Quality; remediate only authorized deterministic defects. PENDING.
- T-018 [P0] Re-check base/head/scope/reviews and merge only the exact green remediation head; require exact-main post-merge Quality. PENDING.
- T-019 [P0] Compute the new exact mixed-contour production fingerprint; the prior `e814d32...` fingerprint is stale because the authorized source outcome changed. PENDING.
- T-020 [P0] Obtain fresh exact-SHA production safety envelope with `Execution-Intent: EXECUTE` before any recovery/deployment mutation. PENDING HUMAN DECISION AFTER REMEDIATION MERGE.
- T-021 [P0] Satisfy the existing exact privileged-helper bundle/bootstrap admission for the new remediation SHA if required by the target; this is a protected runtime checkpoint, not an auth bypass. PENDING RUNTIME.
- T-022 [P0] Execute VPS first: if `/sea-speed/` is still HTTP 500, prove bounded pre-source recovery restores `302|401|403`; then deploy exact VPS passage API/UI/storage and verify source identity/retention. PENDING RUNTIME.
- T-023 [P0] Deploy exact Ubuntu Worker second, preserving Road desired state, and prove source/service/frame/AI progression plus passage transport. PENDING RUNTIME.
- T-024 [P0] Observe a naturally occurring vessel as one passage with one retained snapshot and speed lifecycle; numerical speed accuracy is not required. PENDING RUNTIME.
- T-025 [P0] Persist final sanitized recovery/deployment/passage evidence to #218 and close only when all mandatory gates pass. PENDING.

## Requirements traceability

- AC-001 | Task: T-002,T-008 | Evidence: short ByteTrack split stitching test | Coverage: COVERED
- AC-002 | Task: T-002,T-008 | Evidence: distinct later/out-of-bound pass test | Coverage: COVERED
- AC-003 | Task: T-002,T-008 | Evidence: bounded RAM deque test | Coverage: COVERED
- AC-004 | Task: T-002,T-003,T-008 | Evidence: injected alternate estimator contract test | Coverage: COVERED
- AC-005 | Task: T-003,T-008 | Evidence: two-gate bidirectional/incomplete tests | Coverage: COVERED
- AC-006 | Task: T-004,T-008 | Evidence: best snapshot replacement test and stable snapshot path design | Coverage: COVERED
- AC-007 | Task: T-005,T-008 | Evidence: SQLite upsert-in-place test | Coverage: COVERED
- AC-008 | Task: T-005,T-008 | Evidence: retention/media cleanup and active-overflow fail-closed tests | Coverage: COVERED
- AC-009 | Task: T-005,T-008 | Evidence: static no-persistent-observation-table assertion | Coverage: COVERED
- AC-010 | Task: T-004,T-008,T-017 | Evidence: Water/Road/profile/ROI aggregate suites | Coverage: COVERED
- AC-011 | Task: T-006,T-008 | Evidence: frontend passage lifecycle contract test | Coverage: COVERED
- AC-012 | Task: T-007,T-008 | Evidence: exact artifact allowlist contract test | Coverage: COVERED
- AC-013 | Task: T-016,T-017,T-018 | Evidence: Connector exact diff, PR Validation, aggregate Quality, expected-head merge and exact-main Quality | Coverage: COVERED
- AC-014 | Task: T-020,T-022,T-023,T-024,T-025 | Evidence: separately authorized VPS-first/Ubuntu-second natural-vessel acceptance | Coverage: RUNTIME-MANUAL | Reason: live camera/GPU/production persistence cannot be proven by hosted CI
- AC-015 | Task: T-011,T-012,T-014,T-022 | Evidence: simulated and production pre-source HTTP 500 recovery | Coverage: COVERED
- AC-016 | Task: T-012,T-013,T-014,T-022 | Evidence: exact-marker fallback test, non-500 rejection, recovery rollback test and production auth-gated HTTP evidence | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — passage architecture plus HTTP 500 correct-course recovery, risks, tests and rollout are represented.
- [ ] Exact changed-file scope verified — remediation PR must remain within current Issue #218 authorization union.
- [ ] Required tests and evidence complete — initial passage CI passed; recovery helper/transaction and full aggregate CI remain pending.
- [ ] Required CI green — remediation exact-head PR Validation/Quality and new exact-main Quality remain pending.
- [ ] Exact-green-head remediation merge complete.
- [ ] Deployment state resolved — no new production mutation is authorized after the recovery scope change.
- [ ] Protected `/sea-speed/` recovery acceptance resolved — HTTP 500 must be absent and anonymous access must remain auth-gated.
- [ ] Runtime passage acceptance resolved — VPS passage boundary and natural-vessel Ubuntu passage lifecycle remain pending.
- [x] Deferred work recorded — visual ReID, AIS, homography/calibrated trajectory speed and numeric accuracy tuning are separate future Outcomes.
- [ ] Risks resolved or explicitly accepted — test-stage ReID/accuracy residuals accepted; Auth recovery, mixed runtime and production evidence remain open.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until the remediation source diff passes exact-head PR Validation and aggregate Quality, merges with expected-head protection, receives exact-main Quality, a fresh exact-SHA production envelope authorizes runtime execution, the protected `/sea-speed/` endpoint is restored from HTTP 500 to an Authentik-gated response without bypass, VPS passage API/UI/storage are verified before Ubuntu, Ubuntu exact runtime preserves Road desired state and advances Water inference, and one naturally occurring vessel is represented by one retained passage/snapshot with a valid speed lifecycle. Numerical speed accuracy remains explicitly outside the completion criterion.
