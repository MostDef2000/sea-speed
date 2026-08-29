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

## Single-HLS refinement tasks

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

- AC-001 | Tasks: T101,T107 | Evidence: one `waterMainVideo`, no `id="video"`/`stream-probe` | Coverage: COVERED
- AC-002 | Tasks: T102,T107 | Evidence: one `new Hls(` and sole attach target | Coverage: COVERED
- AC-003 | Tasks: T103,T107 | Evidence: Water video event/watchdog contract markers | Coverage: COVERED
- AC-004 | Tasks: T104,T105,T110 | Evidence: worker inactive clear/gating + runtime continuity | Coverage: RUNTIME-MANUAL
- AC-005 | Tasks: T106,T107 | Evidence: healthy playback guard and cached fallback URL | Coverage: COVERED
- AC-006 | Tasks: T102,T105,T107,T108 | Evidence: unchanged live-sync algorithm markers, exact changed-file review, full CI | Coverage: COVERED
- AC-007 | Tasks: T107,T108 | Evidence: existing dashboard/layout/mobile/Road contracts remain green | Coverage: COVERED
- AC-008 | Tasks: T108,T109,T110 | Evidence: exact-head CI, merge, exact-main Quality, VPS runtime_verified and authenticated continuity | Coverage: RUNTIME-MANUAL

## Definition of Done

- Issue #326 contains the fresh single-HLS authorization receipt/checkpoints.
- SDD 069 reflects the admitted lifecycle refinement and separate #335 follow-up.
- Exact diff contains only `frontend/sea-speed/index.html`, `tests/test_frontend_contract.py`, and SDD 069 `spec.md` / `plan.md` / `tasks.md`.
- Water page has one HLS media element/player; hidden legacy consumer is absent.
- Worker OFF clears AI overlay without interrupting video; Worker ON resumes overlay without media reconnect.
- Healthy HLS does not trigger periodic annotated snapshot downloads.
- Existing layout, editor controls, crossings/passages, Road protection and live-sync timing markers remain green.
- Required Repository validation / quality-integration green on exact PR head and exact main.
- VPS exact release reaches runtime_verified; Ubuntu Worker deployment remains not required.
- Authenticated production continuity check records Worker OFF→ON→OFF with uninterrupted advancing Water video before terminal DONE.

## Completion gate

No source/CI intermediate state is completion. Delivery completes only after exact-green merge, exact-main Quality, protected VPS deployment and authenticated single-player continuity evidence are durable in #326.
