# Delivery Tasks: Water live overlay sync correctness

- Specification: `specs/071-water-live-overlay-sync-correctness/spec.md`
- Issue: #346
- PR: #348
- Branch: `issue-346-water-sync`
- Scope identity: `issue-346-water-live-overlay-sync-task1-v1`
- Change Contract local checks: PASS — exact five-path scope and bounded Water frontend diff verified before PR validation.

## Delivery tasks

- T001 — Tighten Water `renderForVideoFrame()` so unresolved HLS media time clears the AI canvas instead of drawing arrival-order metadata.
- T002 — Preserve valid same-generation bracket interpolation and explicitly bound closest-earlier fallback to no more than 2000 ms behind compensated media time.
- T003 — Remove unconditional newest-buffer drawing from the Water no-bracket path; stale/future/unmatched metadata must clear the canvas.
- T004 — Add deterministic Water frontend contract coverage for unresolved media time, bounded earlier metadata and absence of newest-buffer fallback.
- T005 — Keep one-HLS Water lifecycle, metadata-only Worker control and protected Road/worker/API/speed/detection/media topology unchanged.
- T006 — Run SDD/Change Contract/repository validation and exact-head CI; remediate only within admitted Task 1 paths.
- T007 — Merge exact green head, require exact-main Quality, deploy VPS exact-main and record authenticated Water moving-vessel sync acceptance; Ubuntu Worker source deployment remains NOT REQUIRED.

## Requirements traceability

- AC-001 | Task: T001,T004 | Evidence: `raw==null` clears overlay and latest-buffer draw is absent | Coverage: COVERED
- AC-002 | Task: T002,T004 | Evidence: `LIVE_NEAR_MAX_AGE_MS=2000` plus bounded closest-earlier capture-time guard | Coverage: COVERED
- AC-003 | Task: T003,T004 | Evidence: no unconditional newest-buffer fallback and explicit `clearLive()` no-match path | Coverage: COVERED
- AC-004 | Task: T002,T005 | Evidence: `bracketForMedia()` and interpolation remain present | Coverage: COVERED
- AC-005 | Task: T005,T007 | Evidence: existing one-HLS/worker lifecycle contracts plus production continuity | Coverage: RUNTIME-MANUAL | Reason: authenticated HLS/overlay continuity requires production browser observation.
- AC-006 | Task: T005,T006 | Evidence: exact changed-file review and full Quality | Coverage: COVERED
- AC-007 | Task: T006,T007 | Evidence: exact-head CI, exact-main Quality and VPS runtime_verified | Coverage: COVERED
- AC-008 | Task: T007 | Evidence: authenticated production moving-vessel observation | Coverage: RUNTIME-MANUAL | Reason: visual alignment against real moving vessels requires the authenticated production stream.

## Definition of Done

- Issue/spec/plan/tasks current — #346 Task 1 and SDD 071 reflect the authorized sync-only scope.
- Exact changed-file scope verified — only Water frontend, Water sync contract test and three SDD 071 files differ from authorization base.
- Required tests and evidence complete — deterministic sync guard contract plus existing frontend/repository contracts and runtime evidence.
- Required CI green — exact PR head Repository validation and quality-integration, then exact-main Quality.
- Exact-green-head merge complete — only after fresh base/head/scope/review verification.
- Deployment state resolved — VPS exact-main runtime verified or explicitly rolled back; Ubuntu Worker deployment not required.
- Runtime acceptance resolved — authenticated Water observation records aligned-box-or-no-box behavior before Task 1 terminal DONE.
- Protected contours unchanged — Road, worker, API, detection/tracking, speed/passages and media topology remain zero-diff.
- Deferred work recorded — #346 Task 2 speed semantics and Task 3 detector/tracker recall remain separate future deliveries.
- Risks resolved or explicitly accepted — conservative no-box fallback is the intended reliability posture.
- Waivers resolved or current — no waiver expected; any waiver must satisfy Change Contract policy.

## Completion gate

Task 1 is complete only after exact-green merge, exact-main Quality, protected VPS deployment and authenticated production evidence that unmatched metadata no longer produces a displaced Water bbox.
