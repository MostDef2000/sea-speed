# Spec: AI overlay — remove per-class crossing lines, keep CROSSINGS only

- Issue: #289
- Status: ACTIVE
- Runtime contour: Ubuntu Worker/relay

## Product outcome

AI overlay image rendered by worker (both water `/sea-speed/` and road `/sea-speed/road/`) must show only the aggregate crossing counter line `CROSSINGS -> X <- Y` and the yellow crossing line itself. Per-class lines (`car: N`, `person: N`, `truck: N`, etc.) previously drawn below the aggregate line on the bottom-right must be removed. Full per-class breakdown remains only in the `Crossing counter` panel (`#cxSummary` table) and `crossings/summary` API, not in the overlay.

## User scenarios

- Operator enables crossing line on water, sees yellow line and `CROSSINGS -> 5 <- 3` on AI frame; no `car: 7` etc. below it. Same on road.
- Operator opens `Crossing counter` details — there the table still lists `car`, `person`, `truck` with `→ / ← / total`.
- After deploy, both contours share same single-line overlay.

## Requirements

- R1: `draw_overlay(..., crossing_summary)` when `line_enabled` draws yellow line between the two points and exactly one text line `CROSSINGS -> {ltr} <- {rtl}` on bottom-right; no per-class lines.
- R2: Yellow crossing line rendering unchanged (color `(0,255,255)`, thickness 2, `LINE_AA`, only when `line_enabled` and `len(line)==2`).
- R3: Counting and persistence unchanged: `update_crossing_counts`, `crossing_overlay_summary`, `_crossings_by_class`, `crossings/summary`, `crossings` POST remain intact.
- R4: No API/frontend/deploy contract change; only `worker/hls_motion_yolo_worker_events.py` overlay text block changes.

## NFR assessment

- NFR-048-001 | Area: correctness | Target: overlay never shows per-class text, single CROSSINGS line always present when line enabled | Validation: unit test mocking cv2 and inspecting putText calls | Evidence: tests/test_overlay_crossing.py | Status: PASS
- NFR-048-002 | Area: reliability | Target: no regression in crossing counting or line rendering | Validation: existing worker tests + overlay test with yellow line | Evidence: tests/test_overlay_crossing.py + discover | Status: PASS
- NFR-048-003 | Area: performance | Target: overlay render time not increased (single line vs N lines) | Validation: code review | Evidence: single putText vs loop | Status: PASS

## Acceptance criteria

- AC-001: AI overlay with `line_enabled=true, ltr=3, rtl=2, by_class={car:{...}}` renders `CROSSINGS -> 3 <- 2` and does NOT render `car:`
- AC-002: Same overlay still draws yellow line between the two points (cv2.line called with correct color)
- AC-003: `crossing_overlay_summary` still returns `by_class` correctly (no data loss)
- AC-004: Only `worker/hls_motion_yolo_worker_events.py` changed (plus SDD); no frontend/api change
- AC-005: Existing unit suite 516+ tests still green

## Runtime feedback

To be recorded after Ubuntu Worker deployment acceptance.
