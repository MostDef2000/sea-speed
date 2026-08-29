# Delivery Tasks: Water operator dashboard redesign

- Specification: `specs/069-water-operator-redesign/spec.md`
- Issue: #326
- PR: #342
- Branch: `issue-326-water-single-hls`
- Scope identity: `issue-326-water-single-hls-v2`
- PR quality preflight: Change Contract admitted with `Quality verdict: CONCERNS` while exact-head CI and authenticated runtime continuity evidence remain pending.

## Completed redesign baseline

- T001 — Approved Water desktop/mobile dashboard composition delivered.
- T002 — Crossing editor and statistics separated.
- T003 — Direct Water crossing-history navigation delivered.
- T004 — Independent three-record Water passages card delivered.
- T005 — Dashboard/registry contracts delivered.
- T006 — Original redesign CI/merge/deployment completed.
- T007 — `Разметка и калибровка` made collapsible and default-closed; deployed and accepted.

## Delivery tasks

- T101 — Remove hidden legacy `video#video.stream-probe`; retain exactly one Water `<video id="waterMainVideo">`.
- T102 — Collapse dual Hls.js lifecycle into one Hls instance attached to `waterMainVideo`; retain existing retry/recovery constants.
- T103 — Rebind playback watchdog, progress and media/network recovery event handling to `waterMainVideo`.
- T104 — Decouple Worker Start/Stop from media lifecycle: stopped worker clears AI buffer/canvas; active worker resumes fresh live metadata without HLS reconnect.
- T105 — Gate SSE/poll/render paths against inactive worker so stale live envelopes cannot repopulate the overlay after stop.
- T106 — Stop periodic `last_overlay_url` image refresh while HLS advances; use changed-URL snapshot only as unhealthy-playback fallback.
- T107 — Update frontend structural contracts for one video/one HLS, worker overlay clearing and bounded fallback behavior while preserving layout/Road/live-sync markers.
- T108 — Run exact-scope/SDD/Change Contract validation and required PR CI; remediate only within the five admitted paths.
- T109 — Merge exact green head after fresh main/head/scope/review probe; require exact-main Quality.
- T110 — Deploy VPS exact-main through protected standing delegation and record authenticated Worker OFF→ON→OFF continuity acceptance; Ubuntu Worker source deployment remains NOT REQUIRED.

## Requirements traceability

- AC-001 | Task: T101,T107 | Evidence: one `waterMainVideo`, no `id="video"`/`stream-probe` | Coverage: COVERED
- AC-002 | Task: T102,T107 | Evidence: one `new Hls(` and sole attach target | Coverage: COVERED
- AC-003 | Task: T103,T107 | Evidence: Water video event/watchdog contract markers | Coverage: COVERED
- AC-004 | Task: T104,T105,T110 | Evidence: worker inactive clear/gating plus production continuity observation | Coverage: RUNTIME-MANUAL | Reason: browser-authenticated continuity and visual overlay behavior cannot be proven by repository CI alone.
- AC-005 | Task: T106,T107 | Evidence: healthy playback guard and cached fallback URL | Coverage: COVERED
- AC-006 | Task: T102,T105,T107,T108 | Evidence: unchanged live-sync algorithm markers, exact changed-file review and full CI | Coverage: COVERED
- AC-007 | Task: T107,T108 | Evidence: existing dashboard/layout/mobile/Road contracts remain green | Coverage: COVERED
- AC-008 | Task: T108,T109,T110 | Evidence: exact-head CI, merge, exact-main Quality, VPS runtime_verified and authenticated continuity | Coverage: RUNTIME-MANUAL | Reason: final protected production deployment and authenticated Water continuity are runtime gates outside static CI.

## Definition of Done

- Issue/spec/plan/tasks current — #326 and SDD 069 reflect the single-HLS refinement authorization and implementation.
- Exact changed-file scope verified — diff remains limited to the five admitted paths.
- Required tests and evidence complete — frontend/repository contracts and runtime continuity evidence must be complete before terminal DONE.
- Required CI green — exact PR head Repository validation and quality-integration, followed by exact-main Quality.
- Exact-green-head merge complete — PR #342 may merge only after fresh base/head/scope/review verification.
- Deployment state resolved — VPS exact-main runtime is either verified or explicitly rolled back; Ubuntu Worker deployment is not required.
- Runtime acceptance resolved — authenticated Worker OFF→ON→OFF continuity is recorded before terminal DONE.
- Deferred work recorded — VPS CPU/transcoding topology remains separate Issue #335.
- Risks resolved or explicitly accepted — no full risk profile is required; runtime continuity concern must be resolved by production acceptance.
- Waivers resolved or current — no waiver is currently required; any future waiver must satisfy the Change Contract.

## Completion gate

No source/CI intermediate state is completion. Delivery completes only after exact-green merge, exact-main Quality, protected VPS deployment and authenticated single-player continuity evidence are durable in #326.
