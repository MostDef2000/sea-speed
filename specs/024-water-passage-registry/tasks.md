# Delivery Tasks: Water Passage Architecture

- Specification: specs/024-water-passage-registry/spec.md
- Plan: specs/024-water-passage-registry/plan.md
- Issue: #218
- Status: Implementing

## Delivery tasks

- T-001 [P0] Record final eleven-path source authorization after packaging dependency and pluggable-speed architecture refinement. COMPLETE: Issue #218 comment `5325409717`.
- T-002 [P0] Add pure bounded `worker/water_passage.py` with passage identity, short split stitching, active caps, RAM ring buffers and pluggable speed estimator boundary. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-003 [P0] Implement `two_gate` as first speed strategy with A→B/B→A and incomplete/null speed semantics. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-004 [P0] Integrate Water Worker passage transport, best vessel crop, transition-only/idempotent posting and passage labels while preserving Road event path and protected Water inference settings. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-005 [P0] Add dedicated VPS `water_passages` SQLite persistence, idempotent upsert, 300-row completed-first retention, orphan snapshot cleanup and `/api/cam1/passages`. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-006 [P0] Change Water operator recent-history view to passage lifecycle cards with passage ID, measuring/measured speed and direction. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-007 [P0] Include `worker/water_passage.py` in Ubuntu Worker and edge exact artifact allowlists. IMPLEMENTED ON TASK BRANCH; CI PENDING.
- T-008 [P0] Add deterministic passage/strategy/retention/frontend/artifact tests and keep existing Water/Road/API regression suites intact. TASK-BRANCH FOCUSED RESULT: 14/14 PASS; CI PENDING.
- T-009 [P0] Commit only authorized source/SDD paths, verify exact diff against authorization base, and open canonical PR with valid MIXED Change Contract. PENDING.
- T-010 [P0] Reach exact-head PR Validation and aggregate Quality; remediate only in-scope deterministic defects. PENDING.
- T-011 [P0] Re-check base/head/scope/reviews and merge only the exact green head; require exact-main post-merge Quality. PENDING.
- T-012 [P0] Persist merged source/release evidence and compute exact mixed-contour production fingerprint. PENDING.
- T-013 [P0] Obtain fresh exact-SHA production safety envelope with execution intent before any VPS/Ubuntu mutation. PENDING HUMAN DECISION AFTER SOURCE MERGE.
- T-014 [P0] After authorization, deploy VPS first and prove passage API/UI/SQLite/media retention health. PENDING RUNTIME.
- T-015 [P0] Deploy exact Ubuntu Worker second, preserving Road desired state, and prove source/service/frame/AI progression plus passage transport. PENDING RUNTIME.
- T-016 [P0] Observe a naturally occurring vessel as one passage with one retained snapshot and speed lifecycle; numerical speed accuracy is not required. PENDING RUNTIME.
- T-017 [P0] Persist final sanitized evidence to #218 and close only when all mandatory source and runtime gates pass. PENDING.

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
- AC-010 | Task: T-004,T-010 | Evidence: existing Water/Road/profile/ROI aggregate suites | Coverage: CI-PENDING
- AC-011 | Task: T-006,T-008 | Evidence: frontend passage lifecycle contract test | Coverage: COVERED
- AC-012 | Task: T-007,T-008 | Evidence: exact artifact allowlist contract test | Coverage: COVERED
- AC-013 | Task: T-009,T-010,T-011 | Evidence: Connector exact diff, PR Validation, aggregate Quality, expected-head merge and exact-main Quality | Coverage: PENDING
- AC-014 | Task: T-013,T-014,T-015,T-016,T-017 | Evidence: separately authorized VPS-first/Ubuntu-second natural-vessel acceptance | Coverage: RUNTIME-MANUAL | Reason: live camera/GPU/production persistence cannot be proven by hosted CI

## Definition of Done

- [x] Issue/spec/plan/tasks current — final scope, architecture, retention, risk/test design and rollout order are represented.
- [ ] Exact changed-file scope verified — final GitHub branch/PR diff must remain within the eleven authorized paths.
- [ ] Required tests and evidence complete — local focused 14/14 pass; aggregate repository CI and production evidence remain.
- [ ] Required CI green — exact-head PR Validation/Quality and exact-main Quality remain pending.
- [ ] Exact-green-head merge complete — task branch is not yet merged.
- [ ] Deployment state resolved — mixed exact release is not production-authorized or deployed.
- [ ] Runtime acceptance resolved — VPS passage boundary and natural-vessel Worker passage lifecycle remain pending.
- [x] Deferred work recorded — visual ReID, AIS, homography/calibrated trajectory speed and numeric accuracy tuning are separate future Outcomes.
- [ ] Risks resolved or explicitly accepted — test-stage ReID/accuracy residuals are accepted; mixed runtime/data risks require CI/runtime evidence.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the exact authorized source diff passes PR Validation and aggregate Quality on one exact head, merges with expected-head protection, receives exact-main Quality, a fresh exact-SHA production envelope authorizes the mixed release, VPS is deployed/verified before Ubuntu, Ubuntu exact runtime preserves Road desired state and advances Water inference, and one naturally occurring vessel is represented by one retained passage/snapshot with a valid speed lifecycle. Numerical speed accuracy is explicitly not a completion criterion for this architectural Outcome.
