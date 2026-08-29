# Delivery Tasks: Water media-time provenance

- Specification: `specs/073-water-media-time-provenance/spec.md`
- Issue: #346
- Branch: `issue-346-water-media-time-provenance`
- Authorization: Task 1B `OUTCOME APPROVED` at base `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e`.
- Actual implementation contour: VPS-only, narrowed from the approved MIXED ceiling after proving Worker mutation unnecessary.
- Change Contract risk profile: NOT REQUIRED for the derived VPS-only impact; production-learning concerns remain covered by deterministic tests, transaction audit, rollback and runtime acceptance.

## Delivery tasks

- T001 — Add Water-only live-edge latency resolver to shared `live-sync.js`, preferring hls.js latency and falling back to native seekable-edge latency.
- T002 — Project Water playback latency onto the newest Worker capture timestamp and use that relative target for same-generation bracket selection.
- T003 — Preserve Road absolute-media-time behavior and all existing bracket gap/generation constraints.
- T004 — Ensure absent/invalid absolute Water media time can reach the relative selector without fabricating a usable absolute timestamp; fail closed if no relative target can be resolved.
- T005 — Preserve no-unconditional-latest behavior and existing bounded stale/future safeguards.
- T006 — Add deterministic Water tests for relative target selection, arbitrary Worker/browser clock offset invariance and invalid-latency fail-closed behavior.
- T007 — Verify exact diff contains no Worker, Road page, API, detector/tracker, ROI, speed/passage or topology changes.
- T008 — Run SDD/Change Contract validation, exact-head Repository validation and quality-integration.
- T009 — Fresh-read base/head/scope/reviews and merge exact green head; require exact-main Quality.
- T010 — Deploy exact-main VPS only, obtain runtime_verified evidence and authenticated production moving-vessel acceptance.

## Requirements traceability

- AC-001 | Task: T001,T002,T006 | Evidence: 500ms live latency selects 10.0/10.2 bracket at 10.1 target | Coverage: COVERED
- AC-002 | Task: T002,T006 | Evidence: fixed Worker clock offset leaves selected IDs and interpolation fraction unchanged | Coverage: COVERED
- AC-003 | Task: T001,T004,T006 | Evidence: unavailable, negative or greater-than-30s latency yields no relative target | Coverage: COVERED
- AC-004 | Task: T004,T006 | Evidence: Water video media-time compatibility probe reaches selector while non-finite absolute time is rejected as a target | Coverage: COVERED
- AC-005 | Task: T005,T006 | Evidence: no latest-buffer draw and bounded closest-earlier source contract remain | Coverage: COVERED
- AC-006 | Task: T003,T007 | Evidence: Road page zero-diff plus existing Road/live-sync regression suite | Coverage: COVERED
- AC-007 | Task: T008,T009,T010 | Evidence: exact-head and exact-main CI plus protected VPS runtime evidence | Coverage: COVERED
- AC-008 | Task: T010 | Evidence: authenticated production observation with positive Water detections/tracks and visible aligned bbox | Coverage: RUNTIME-MANUAL | Reason: alignment against a real moving vessel requires authenticated production video observation

## Definition of Done

- Issue/spec/plan/tasks current — #346 and SDD 073 reflect the refined cross-clock root cause and the authorized Task 1B outcome.
- Exact changed-file scope verified — only `frontend/sea-speed/live-sync.js`, approved Water sync tests and SDD 073; Worker, Road page, API and protected analytics/topology contours remain zero-diff.
- Required tests and evidence complete — deterministic relative target, clock-offset invariance, invalid latency, fail-closed fallback and compatibility regressions are green.
- Required CI green — exact PR head Repository validation and quality-integration succeed.
- Exact-green-head merge complete — merge occurs only after fresh base/head/scope/review verification.
- Deployment state resolved — protected VPS exact-main is runtime_verified or an explicit rollback is recorded; Ubuntu Worker deployment is not required.
- Runtime acceptance resolved — authenticated production Water observation confirms positive detections render an aligned moving bbox and no-match cases remain fail-closed.
- Deferred work recorded — Task 2 unified speed semantics and Task 3 detector/tracker recall remain separate sequenced work in #346.
- Risks resolved or explicitly accepted — production-learning concerns are bounded by Water-only mapping, deterministic coverage, fail-closed behavior, rollback and runtime acceptance.
- Waivers resolved or current — no waiver is expected; any future waiver must satisfy repository Change Contract policy.

## Completion gate

Task 1B is complete only when source/CI/deployment are exact-green and authenticated production observation confirms positive Water detections can render an aligned bbox while unresolved metadata remains fail-closed.
