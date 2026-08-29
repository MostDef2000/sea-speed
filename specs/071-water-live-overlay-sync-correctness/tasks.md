# Delivery Tasks: Water live overlay sync correctness

- Specification: `specs/071-water-live-overlay-sync-correctness/spec.md`
- Issue: #346
- PR: #348 (initial implementation); #349 (runtime-acceptance remediation).
- Branch: `issue-346-water-sync-runtime-fix`
- Scope identity: `issue-346-water-live-overlay-sync-task1-v1`
- Change Contract local checks: PASS — remediation remains within admitted Water frontend/test/SDD paths; worker/API/Road/speed/detection/media topology remain protected.
- Existing regression alignment: `tests/test_water_overlay_sync.py` and `tests/test_water_live_sync_guard.py` cover the approved frontend/live-sync semantics.

## Delivery tasks

- T001 — Tighten Water `renderForVideoFrame()` so unresolved HLS media time clears the AI canvas instead of drawing arrival-order metadata.
- T002 — Preserve valid same-generation bracket interpolation and explicitly bound closest-earlier fallback to no more than 2000 ms behind compensated media time.
- T003 — Remove unconditional newest-buffer drawing from the Water no-bracket path; stale/future/unmatched metadata must clear the canvas.
- T004 — Add deterministic Water frontend contract coverage and update the existing Water sync regression for unresolved media time, bounded earlier metadata, future-only metadata and absence of newest-buffer fallback.
- T005 — Keep one-HLS Water lifecycle, metadata-only Worker control and protected Road/worker/API/speed/detection/media topology unchanged.
- T006 — Run SDD/Change Contract/repository validation and exact-head CI; remediate only within admitted Task 1 paths.
- T007 — Merge exact green head, require exact-main Quality, deploy VPS exact-main and record authenticated Water moving-vessel sync acceptance; Ubuntu Worker source deployment remains NOT REQUIRED.
- T008 — Runtime-acceptance remediation: do not reject the entire live buffer merely because the newest Worker envelope is more than 6000 ms ahead of the HLS media time. HLS may legitimately trail Worker live-edge while an older envelope in the bounded buffer still matches the displayed media frame. Let bracket/closest-earlier selection decide; never restore latest-buffer fallback.
- T009 — Add deterministic fault-path coverage proving a valid historical bracket remains eligible when the newest envelope is >6s ahead, then repeat exact-head/main/VPS/runtime acceptance gates.

## Requirements traceability

- AC-001 | Task: T001,T004 | Evidence: `raw==null` clears overlay and latest-buffer draw is absent | Coverage: COVERED
- AC-002 | Task: T002,T004 | Evidence: `LIVE_NEAR_MAX_AGE_MS=2000` plus bounded closest-earlier capture-time guard and legacy sync regression | Coverage: COVERED
- AC-003 | Task: T003,T004 | Evidence: no unconditional newest-buffer fallback; >2s stale and future-only tests clear | Coverage: COVERED
- AC-004 | Task: T002,T005,T008,T009 | Evidence: `bracketForMedia()` remains authoritative even when newest Worker metadata is ahead of current HLS media time | Coverage: COVERED
- AC-005 | Task: T005,T007 | Evidence: existing one-HLS/worker lifecycle contracts plus production continuity | Coverage: RUNTIME-MANUAL | Reason: authenticated HLS/overlay continuity requires production browser observation.
- AC-006 | Task: T005,T006 | Evidence: exact changed-file review and full Quality | Coverage: COVERED
- AC-007 | Task: T006,T007,T009 | Evidence: exact-head CI, exact-main Quality and VPS runtime_verified | Coverage: COVERED
- AC-008 | Task: T007,T009 | Evidence: authenticated production moving-vessel observation | Coverage: RUNTIME-MANUAL | Reason: visual alignment against real moving vessels requires the authenticated production stream.

## Production learning / runtime feedback

Initial Task 1 release `50aec9a233b465f73993f92a69f8e9b22707a322` reached `runtime_verified`, but authenticated visual acceptance failed. Production showed `AI active`, `DETECTIONS 1`, `TRACKS 1` while no bbox was rendered. The failure was traced to the frontend-only 6000 ms newest-envelope freshness guard executing before temporal bracket lookup. Normal HLS playback can trail the Worker live edge by more than that threshold while the bounded buffer still contains metadata matching the displayed frame. This is an acceptance defect, not detector failure. Remediation removes only that blanket guard; stale/future/unmatched no-bracket behavior remains fail-closed.

## Definition of Done

- Issue/spec/plan/tasks current — #346 Task 1 and SDD 071 reflect the authorized sync-only scope and runtime remediation.
- Exact changed-file scope verified — Water frontend, corresponding Water sync tests and SDD 071 only; all protected runtime/source contours remain unchanged.
- Required tests and evidence complete — deterministic sync guard contracts include the >6s-newest/valid-historical-bracket fault path.
- Required CI green — exact PR head Repository validation and quality-integration, then exact-main Quality.
- Exact-green-head merge complete — only after fresh base/head/scope/review verification.
- Deployment state resolved — VPS exact-main runtime verified or explicitly rolled back; Ubuntu Worker deployment not required.
- Runtime acceptance resolved — authenticated Water observation records aligned bbox when valid metadata exists and no displaced latest-envelope fallback.
- Protected contours unchanged — Road, worker, API, detection/tracking, speed/passages and media topology remain zero-diff.
- Deferred work recorded — #346 Task 2 speed semantics and Task 3 detector/tracker recall remain separate future deliveries.
- Risks resolved or explicitly accepted — fail-closed matching remains; valid buffered metadata is no longer rejected solely by distance from newest Worker envelope.
- Waivers resolved or current — no waiver expected; any waiver must satisfy Change Contract policy.

## Completion gate

Task 1 is complete only after exact-green merge, exact-main Quality, protected VPS deployment and authenticated production evidence that a positive Water detection can render a temporally matched bbox while unmatched metadata still does not produce a displaced bbox.
