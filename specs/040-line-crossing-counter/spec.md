# Spec: Line-crossing counter (both contours)

- Issue: #265
- Status: ACTIVE
- Runtime contour: MIXED

## Product outcome

Virtual counting lines for water cam1 and road road1. Objects crossing the line are counted per direction (left-to-right, right-to-left) and grouped by class. Crossings persist into the objects registry per domain registry logic. Both AI detection main screens show a 24h summary. Overlay relayout: white stats block moves to bottom-left; new live crossing counters block overlays bottom-right.

## User scenarios

- Operator draws a counting line on the road AI screen; vehicles crossing it increment directional counters visible as the bottom-right overlay block and in the 24h summary panel.
- Operator draws a counting line on the water AI screen; vessels crossing it are counted the same way and stored into the objects registry.
- Reviewer opens either main screen and reads the 24h class-by-direction summary without any manual queries.

## Runtime feedback

- Worker overlay reflects live crossing counters within one state interval once the line is enabled.
- Summary endpoint aggregates persisted crossings over the requested window and both pages refresh it every 15 seconds.
- Registry rows appear immediately after each counted crossing via the existing persistence path.

## Requirements

- R1: Per-camera crossing line config (`enabled`, `line` of exactly 2 points) served by the API and fetched by the worker with short-TTL caching (speed-lines pattern).
- R2: Worker detects line crossings from tracked centroids with per-track side memory, direction derived from horizontal motion across the line, debounced so one track cannot double-count within a cooldown window.
- R3: Road-domain person detections do not produce crossings or registry rows (consistent with the event publication gate); water unaffected.
- R4: Each counted crossing is posted to the API, persisted into the objects registry via `persist_object_event` (domain-aware), and appended to a bounded per-camera crossings store.
- R5: API exposes `GET/POST /api/analytics/{camera_id}/crossing-line` (+ cam1 aliases), `POST .../crossings` ingest, and `GET .../crossings/summary?hours=24` aggregating class x direction totals.
- R6: Both main screens render an editable counting line (canvas editor) and a 24h summary panel (class x direction table).
- R7: Overlay relayout in the worker: existing white stats block renders bottom-left; new live crossing-counters block renders bottom-right.

## NFR assessment

- NFR-040-001 | Area: performance | Target: crossing detection adds <5 ms per frame at 704x576 | Validation: unit timing not required; pure arithmetic per track | Evidence: tests/test_line_crossing.py | Status: PASS
- NFR-040-002 | Area: reliability | Target: no double count on centroid wobble around the line | Validation: synthetic wobble test with cooldown assertion | Evidence: tests/test_line_crossing.py | Status: PASS
- NFR-040-003 | Area: storage | Target: crossings store bounded (cap 5000 entries per camera) | Validation: cap enforced on append | Evidence: tests/test_line_crossing.py | Status: PASS
- NFR-040-004 | Area: compatibility | Target: state/event/passage contracts unchanged; new endpoints additive | Validation: existing suites stay green | Evidence: local unittest discovery | Status: PASS

## Acceptance criteria

- AC-001: Crossing counted left-to-right for a track moving across the line rightward | Evidence: RUNTIME-MANUAL + TESTS | Coverage: tests/test_line_crossing.py
- AC-002: Crossing counted right-to-left for the reverse motion | Evidence: RUNTIME-MANUAL + TESTS | Coverage: tests/test_line_crossing.py
- AC-003: Wobble around the line does not inflate counts beyond debounce rules | Evidence: TESTS | Coverage: tests/test_line_crossing.py
- AC-004: Road person detections produce no crossing counts or registry rows | Evidence: TESTS | Coverage: tests/test_line_crossing.py
- AC-005: Crossing persists as an objects-registry row with domain-aware identity | Evidence: TESTS | Coverage: tests/test_line_crossing.py
- AC-006: 24h summary aggregates class x direction within the window | Evidence: TESTS | Coverage: tests/test_line_crossing.py
- AC-007: Stats block renders bottom-left; counters block bottom-right | Evidence: TESTS | Coverage: tests/test_line_crossing.py
- AC-008: Line editable in UI on both pages; config round-trips through API | Evidence: RUNTIME-MANUAL | Reason: physical camera UI verification | Coverage: tasks.md
- AC-009: Both deployed contours runtime_verified with exact source | Evidence: CI | Coverage: deployment manifests
