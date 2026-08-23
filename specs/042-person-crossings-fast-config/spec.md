# Spec: Person crossings + fast crossing-line config refresh

- Issue: #274
- Status: ACTIVE
- Runtime contour: MIXED

## Product outcome

Line counters count persons: live overlay counters and the 24h summary include the person class via canonical /crossings ingest, while the objects registry and latest-events feed remain person-free (API structural guard skips persist_object_event for road-domain person crossings). The phantom yellow-line trail after line deletion/move is reduced by lowering the worker crossing-line config freshness window from 5s to 1s.

## User scenarios

- A person walks across the counting line: the directional counter and by-class summary increment; no registry row and no event-feed entry appears.
- Operator deletes or moves the line: the worker overlay stops drawing the old position within about one second (plus inherent stream latency).

## Runtime feedback

- Worker refreshes crossing-line config every 1 second by default (env-overridable).
- Summary panels reflect person crossings through the existing 15-second polling.

## Requirements

- R1: update_crossing_counts counts person detections like any other class.
- R2: post_analytics_crossing skips persist_object_event when domain=road and object_type=person, while still appending to the bounded crossings store.
- R3: CROSSING_LINE_REFRESH_SEC default is 1.0 seconds.

## NFR assessment

- NFR-042-001 | Area: correctness | Target: registry and event feed remain person-free on road | Validation: unit test asserts persist spy not called for road-person | Evidence: tests/test_line_crossing.py::ApiCrossingTests | Status: PASS
- NFR-042-002 | Area: performance | Target: config refresh at 1s adds negligible API load (two workers polling) | Validation: endpoint is a file read; existing rate envelope | Evidence: code review + runtime observation | Status: PASS
- NFR-042-003 | Area: compatibility | Target: water contour unaffected; non-person crossings unchanged | Validation: regression tests green | Evidence: full unittest discovery | Status: PASS

## Acceptance criteria

- AC-001: Person crossing increments directional/by-class counters in the worker.
- AC-002: Road person crossing ingest returns ok, appends the store, and creates no objects-registry row.
- AC-003: Crossing-line config freshness default equals 1 second.
