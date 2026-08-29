# Delivery Tasks: Road operator Water-interface parity

- Specification: `specs/070-road-water-interface-parity/spec.md`
- Issue: #343
- PR: pending
- Branch: `issue-343-road-water-interface-parity`
- Scope identity: `issue-343-road-water-interface-parity-v1`

## Delivery tasks

- T001 — Replace Road header/workspace composition with the accepted Water single-row/two-column hierarchy while retaining Road navigation/session/status semantics.
- T002 — Remove the separate Road clean-live card and second HLS consumer; retain exactly one `<video id="roadMainVideo">`.
- T003 — Bind the single Road Hls.js lifecycle, playback watchdog and recovery to `roadMainVideo` while preserving preview start/stop API and retry constants.
- T004 — Decouple Road Worker Start/Stop from media lifecycle; inactive worker clears Road AI live buffer/canvas and active worker resumes only fresh metadata.
- T005 — Bound Road `last_overlay_url` to unhealthy-playback fallback and stop regular overlay JPEG refresh while HLS advances.
- T006 — Move existing Road ROI, speed-lines, crossing-line, calibration and diagnostics into one default-collapsed under-camera control area.
- T007 — Add independent Road crossing-statistics and latest-events right-rail cards from existing Road state/events data and Road-scoped registry navigation.
- T008 — Update frontend structural contracts for Road Water-parity/single-HLS behavior while preserving endpoint/control/auth/live-sync invariants.
- T009 — Run exact-scope/SDD/Change Contract validation and required PR CI; remediate only within the five admitted paths.
- T010 — Merge exact green head, require exact-main Quality, deploy VPS exact-main and record authenticated desktop/mobile + Road Worker OFF->ON->OFF continuity acceptance; Ubuntu Worker source deployment remains NOT REQUIRED.

## Requirements traceability

- AC-001 | Task: T001,T006,T007,T008 | Evidence: Road Water-parity data-layout and control/card markers | Coverage: COVERED
- AC-002 | Task: T002,T008 | Evidence: one `roadMainVideo`, no clean-live/cleanPreviewVideo/Чистый поток | Coverage: COVERED
- AC-003 | Task: T003,T008 | Evidence: one `new Hls(`, sole attach target and Road video watchdog markers | Coverage: COVERED
- AC-004 | Task: T004,T010 | Evidence: worker inactive clear/gating plus production continuity observation | Coverage: RUNTIME-MANUAL | Reason: authenticated video continuity and visual overlay behavior require production browser observation.
- AC-005 | Task: T005,T008 | Evidence: healthy playback guard and cached fallback URL | Coverage: COVERED
- AC-006 | Task: T003,T004,T008,T009 | Evidence: fixed Road endpoints, unchanged protected contours and full Quality | Coverage: COVERED
- AC-007 | Task: T006,T008 | Evidence: default-closed under-camera details and all editor control IDs | Coverage: COVERED
- AC-008 | Task: T007,T008 | Evidence: independent crossing/events cards and Road registry links | Coverage: COVERED
- AC-009 | Task: T009,T010 | Evidence: exact-head CI, exact-main Quality, VPS runtime_verified and authenticated acceptance | Coverage: RUNTIME-MANUAL | Reason: final protected deployment and authenticated Road continuity/visual inspection are runtime gates.

## Definition of Done

- Issue/spec/plan/tasks current — #343 and SDD 070 reflect authorized Road parity.
- Exact changed-file scope verified — only five admitted paths differ from authorization base.
- Required tests/evidence complete — frontend/repository contracts plus authenticated runtime evidence.
- Required CI green — exact PR head Repository validation and quality-integration, then exact-main Quality.
- Exact-green-head merge complete — only after fresh base/head/scope/review verification.
- Deployment state resolved — VPS exact-main runtime verified or explicitly rolled back; Ubuntu Worker deployment not required.
- Runtime acceptance resolved — authenticated Road desktop/mobile parity and Worker OFF->ON->OFF continuity recorded before terminal DONE.
- Protected contours unchanged — Water/API/worker/live-sync/media topology remain zero-diff.
- Risks resolved or explicitly accepted — runtime continuity/usability concerns resolved by production acceptance.
- Waivers resolved or current — no waiver expected; any waiver must satisfy Change Contract policy.

## Completion gate

No source/CI intermediate state is completion. Delivery completes only after exact-green merge, exact-main Quality, protected VPS deployment and authenticated Road parity/single-player continuity evidence are durable in #343.
