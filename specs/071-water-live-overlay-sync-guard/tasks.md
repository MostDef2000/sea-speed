# Delivery Tasks: Water live overlay sync guard

- Specification: `specs/071-water-live-overlay-sync-guard/spec.md`
- Issue: #346
- PR: #347
- Branch: `issue-346-water-live-sync`
- Scope identity: `issue-346-task1-water-live-overlay-sync-v1`

## Delivery tasks

- T001 — Make Water live renderer fail closed when HLS media time is unavailable: clear AI canvas instead of drawing the latest buffered envelope.
- T002 — Remove the unmatched-latest fallback from Water no-bracket rendering; retain only closest-earlier metadata within the existing 2000 ms tolerance.
- T003 — Preserve timestamp bracketing, <=500 ms interpolation, lag compensation and generation/frame ordering without changing the shared live-sync module.
- T004 — Preserve one continuous `waterMainVideo` HLS lifecycle and metadata-only Water Worker OFF/ON behavior.
- T005 — Add deterministic frontend contracts for raw-null and no-bracket fail-closed behavior plus existing single-HLS invariants.
- T006 — Run exact-scope/SDD/Change Contract validation and required PR CI; remediate only inside the authorized Task 1 paths.
- T007 — Merge exact green head, require exact-main Quality, deploy VPS exact-main, and record authenticated Water visual acceptance; Ubuntu Worker source deployment remains NOT REQUIRED.

## Requirements traceability

- AC-001 | Task: T001,T005 | Evidence: raw-null branch contains `clearLive()` and no latest-buffer draw | Coverage: COVERED
- AC-002 | Task: T002,T005 | Evidence: closest-earlier <=2000 ms guard and clear fallback | Coverage: COVERED
- AC-003 | Task: T002,T005 | Evidence: unmatched `liveBuffer[liveBuffer.length-1]` rendering absent from Water render path | Coverage: COVERED
- AC-004 | Task: T003,T005 | Evidence: bracket/interpolation/maxGap/lag markers remain | Coverage: COVERED
- AC-005 | Task: T004,T005,T007 | Evidence: one HLS constructor/media target and Worker overlay clear semantics; production continuity observation | Coverage: RUNTIME-MANUAL | Reason: authenticated video continuity and visible canvas behavior require production browser observation.
- AC-006 | Task: T006 | Evidence: exact changed-file review and full Quality | Coverage: COVERED
- AC-007 | Task: T006,T007 | Evidence: exact-head CI, exact-main Quality, VPS runtime_verified and authenticated visual acceptance | Coverage: RUNTIME-MANUAL | Reason: final protected deployment and moving-vessel visual inspection are runtime gates.

## Definition of Done

- Issue/spec/plan/tasks current — #346 and SDD 071 reflect the authorized Task 1 boundary.
- Exact changed-file scope verified — only Water frontend, Task 1 test and SDD 071 files differ from authorization base.
- Required tests and evidence complete — fail-closed renderer contracts and repository Quality pass.
- Required CI green — exact PR head Repository validation and quality-integration, then exact-main Quality.
- Exact-green-head merge complete — only after fresh base/head/scope/review verification.
- Deployment state resolved — VPS exact-main runtime verified or explicitly rolled back; Ubuntu Worker deployment not required.
- Runtime acceptance resolved — authenticated Water observation confirms unmatched metadata yields no bbox rather than a displaced bbox while HLS remains continuous.
- Protected contours unchanged — worker/API/Road/shared-live-sync/detection/speed/passage/media topology remain zero-diff.
- Deferred work recorded — Task 2 unified speed semantics and Task 3 vessel detection/tracking recall remain pending in #346.
- Risks resolved or explicitly accepted — temporary box absence during metadata gaps is accepted over knowingly misplaced boxes.
- Waivers resolved or current — no waiver expected; any waiver must satisfy Change Contract policy.

## Completion gate

Task 1 completes only after exact-green merge, exact-main Quality, protected VPS deployment and authenticated Water sync acceptance are durable in #346. #346 remains open for Task 2 and Task 3 after Task 1 completion.
