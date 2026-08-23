# Feature Specification: Road event hygiene + person detection

- Feature: 039-road-event-hygiene-person-detection
- Issue: #263
- Status: Source implementation

Runtime contour: MIXED (Ubuntu Worker/relay + VPS)

## Product outcome

Road events are published only for identified tracks, removing the
non-deduplicable None-track event stream observed at ~36% of production
volume. Person detection is enabled on the road profile: persons are visible
in the live overlay and state counters, but no person event is ever emitted
and no person object is ever persisted into any registry.

## User scenarios

1. A vehicle crosses the road ROI; its track is identified and one event is
   posted for that track (existing per-track dedup preserved).
2. A detection without a track id is speed-ready: it is drawn on the live
   overlay and counted in state, but no event is posted.
3. A pedestrian walks through the road frame: they appear in the overlay and
   in `detections`/`tracks` state counters; no person event is emitted and no
   person row appears in any registry or event feed.

## Requirements

- R1: The road event worker MUST NOT post an analytics event whose best
  detection has `track_id is None`.
- R2: The worker MUST NOT post an event whose canonical `object_type` is
  `person` on the road profile.
- R3: `analytics_profiles.road-v1.class_map` MUST include `"person": "person"`
  so the detector feeds tracking/overlay/state for persons.
- R4: The API (`post_analytics_event`) MUST skip persistence and event-log
  insertion for road-domain events whose canonical object type is `person`,
  returning a normal ok response so legacy workers cannot pollute storage.
- R5: Detection/tracking/calibration/speed formulas MUST remain unchanged;
  only publication gating and profile class composition change.

## NFR assessment

- NFR-039-001 | Area: PERF | Target: gates add O(1) checks per frame batch; no new loops or IO | Validation: code review of diff; existing worker tests green | Evidence: PR #263 exact diff | Status: PASS
- NFR-039-002 | Area: REL | Target: API person guard never breaks the worker POST contract (ok response, no persistence) | Validation: unit test posts a person event and asserts ok:true with empty persistence | Evidence: tests/test_road_event_hygiene.py | Status: PASS
- NFR-039-003 | Area: COMPAT | Target: water contour untouched; non-person road events unchanged | Validation: full unittest discovery green including water suites | Evidence: local discovery run log | Status: PASS
- NFR-039-004 | Area: SEC | Target: no new endpoints, auth unchanged, no secrets | Validation: diff review | Evidence: PR #263 exact diff review | Status: PASS

## Acceptance criteria

- AC-001: Worker does not post an event when best detection has
  `track_id is None`; posting resumes for identified tracks.
- AC-002: Worker does not post an event when canonical object type is person.
- AC-003: road-v1 class_map contains person -> person mapping.
- AC-004: API skips persistence and event-log insertion for road person
  events and returns ok.
- AC-005: Non-person road events persist exactly as before (regression).
- AC-006: Water passage path unaffected (regression).
- AC-007: Full local unittest suite passes.
- AC-008: Both required CI checks pass on exact PR head.
- AC-009: Post-deploy runtime verification: worker journal shows no person
  events; road event rate reduced vs baseline (~36% None-track share gone);
  persons visible in overlay/state counters.
- AC-010: Change Contract matches final diff exactly.

## Runtime feedback

None yet; record production observations after deployment.
