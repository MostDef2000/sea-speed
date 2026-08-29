# Delivery Tasks: Water media-time provenance

- Specification: `specs/073-water-media-time-provenance/spec.md`
- Issue: #346
- Branch: `issue-346-water-media-time-provenance`
- Authorization: Task 1B `OUTCOME APPROVED` at base `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e`.
- Actual implementation contour: VPS-only, narrowed from the approved MIXED ceiling after proving Worker mutation unnecessary.
- Change Contract risk profile: NOT REQUIRED for the derived VPS-only impact; the SDD keeps explicit production-learning risks as engineering evidence, not as a policy high-risk trigger.

## Delivery tasks

- T001 — Add Water-only live-edge latency resolver to shared `live-sync.js`, preferring hls.js latency and falling back to native seekable-edge latency.
- T002 — Project Water playback latency onto the newest Worker capture timestamp and use that relative target for same-generation bracket selection.
- T003 — Preserve Road absolute-media-time behavior and all existing bracket gap/generation constraints.
- T004 — Ensure absent/invalid absolute Water media time can reach the relative selector without fabricating an absolute timestamp; fail closed if no relative target can be resolved.
- T005 — Preserve no-unconditional-latest behavior and existing bounded stale/future safeguards.
- T006 — Add deterministic Water tests for relative target selection, arbitrary Worker/browser clock offset invariance and invalid-latency fail-closed behavior.
- T007 — Verify exact diff contains no Worker, Road page, API, detector/tracker, ROI, speed/passage or topology changes.
- T008 — Run SDD/Change Contract validation, exact-head Repository validation and quality-integration.
- T009 — Fresh-read base/head/scope/reviews and merge exact green head; require exact-main Quality.
- T010 — Deploy exact-main VPS only, obtain runtime_verified evidence and authenticated production moving-vessel acceptance.

## Requirements traceability

- AC-001 | Tasks: T001,T002,T006 | Evidence: 500ms live latency selects 10.0/10.2 bracket at 10.1 target | Coverage: COVERED.
- AC-002 | Tasks: T002,T006 | Evidence: fixed Worker clock offset leaves selected IDs/fraction unchanged | Coverage: COVERED.
- AC-003 | Tasks: T001,T004,T006 | Evidence: unavailable/invalid/>30s latency yields no relative target | Coverage: COVERED.
- AC-004 | Tasks: T004,T006 | Evidence: Water video media-time compatibility probe reaches selector while non-finite absolute time is rejected as a target | Coverage: COVERED.
- AC-005 | Tasks: T005,T006 | Evidence: no latest-buffer draw and bounded closest-earlier source contract | Coverage: COVERED.
- AC-006 | Tasks: T003,T007 | Evidence: Road page zero-diff + existing regression suite | Coverage: COVERED.
- AC-007 | Tasks: T008,T009,T010 | Evidence: exact-head/main CI and protected runtime evidence | Coverage: DELIVERY.
- AC-008 | Task: T010 | Evidence: authenticated production observation with positive Water detections/tracks and visible aligned bbox | Coverage: RUNTIME-MANUAL.

## Definition of Done

- #346 and SDD 073 identify the refined cross-clock root cause and relative-timeline design.
- Exact changed-file scope is limited to `frontend/sea-speed/live-sync.js`, approved Water sync tests and SDD 073.
- Water Worker source and Ubuntu runtime remain zero-diff; actual deployment is VPS-only.
- Deterministic tests cover relative target, clock-offset invariance, invalid latency and preservation of fail-closed latest/stale rules.
- Exact PR head Repository validation and quality-integration are green.
- Exact green head is merged after fresh merge probe; exact-main Quality is green.
- Protected VPS exact-main is runtime_verified or rolled back explicitly.
- Authenticated production acceptance shows bbox when `AI active` and detections/tracks are positive, with bbox following the corresponding vessel rather than being absent or displaced.
- Task 2 unified speed semantics remains sequenced after Task 1 terminal acceptance.

## Completion gate

Task 1B is complete only when source/CI/deployment are exact-green and authenticated production observation confirms positive Water detections can render an aligned bbox while unresolved metadata remains fail-closed.
