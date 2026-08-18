# Feature Specification: Water Passage Architecture

- Feature: 024-water-passage-registry
- Issue: #218
- Status: Implementing
- Owner outcome: Make a physical vessel passage the primary Water record, keep test data bounded, and make speed measurement replaceable without redesigning storage or UI.

## Product outcome

Water analytics creates one bounded `passage_id` for one observed physical vessel pass. ByteTrack `track_id` remains a short-lived tracking implementation detail; short, spatially plausible tracker-ID interruptions may be stitched into the same active passage. The passage carries a nullable future `vessel_id`, but cross-passage visual ReID is deferred.

Speed is a passage property behind a pluggable `SpeedEstimator` boundary. The first strategy is `two_gate`, which consumes bounded in-memory observations and reports `speed_status`, optional `speed_kmh`, `speed_method`, optional direction and compact measurement metadata. A passage may be persisted while speed is still null and later update the same record to a measured result. Accuracy optimization is not an acceptance target in this Outcome.

The VPS stores Water passages in a dedicated bounded SQLite table separate from the existing newest-100 Objects Registry. At most 300 passage rows and 300 passage snapshots are retained. Raw per-frame trajectory observations are never persisted; they exist only in a bounded Worker RAM ring buffer.

## User scenarios

### Scenario 1 - tracker interruption does not automatically create another physical pass
Given one vessel remains spatially close and the ByteTrack ID changes within the configured stitch window, the Water engine rebinds the new track fragment to the existing passage.

### Scenario 2 - a later pass remains distinct
Given a new track appears after the stitch window or outside the stitch distance, it receives a new `passage_id` even if the class is also `vessel`.

### Scenario 3 - speed can arrive after the passage record exists
Given a passage is already visible, it may show `speed_status=measuring` and `speed_kmh=null`; when the selected strategy produces a result, the same `passage_id` is updated rather than duplicated.

### Scenario 4 - speed implementation can evolve
Given a future trajectory, calibrated-plane or AIS-assisted estimator implements the same strategy boundary, passage persistence and UI contracts do not require redesign.

### Scenario 5 - test storage remains bounded
Given repeated passages and snapshot replacements, SQLite retains no more than 300 Water passages and media retains no more than one current snapshot per retained passage. Oldest completed passages are pruned before active passages.

## Requirements

- FR-001: Water MUST continue using the protected `water-v1` detector/profile behavior established by #212; Road `road-v1` behavior MUST remain unchanged.
- FR-002: Each active physical Water pass MUST have one `passage_id` independent from ByteTrack `track_id`.
- FR-003: A short tracker-ID interruption MAY stitch to an active passage only within configured time and pixel-distance bounds; the active-passage set itself MUST be bounded.
- FR-004: Active passage observation history MUST use a fixed-size in-memory ring buffer and MUST NOT create per-frame SQLite rows.
- FR-005: Passage speed MUST be exposed through a strategy boundary returning `speed_status`, nullable `speed_kmh`, `speed_method`, nullable `direction` and bounded `measurement_meta`.
- FR-006: `two_gate` MUST be the first strategy and MUST support both A→B and B→A order using the configured gate distance and observation timestamps.
- FR-007: A passage that has not completed the configured measurement MUST retain `speed_kmh=null`; finalization MAY mark its speed status `incomplete`.
- FR-008: The Worker MUST select one best vessel snapshot candidate for a passage and MUST replace rather than accumulate local/remote snapshots for that passage.
- FR-009: VPS passage persistence MUST be idempotent by `passage_id`; later updates MUST modify the same row.
- FR-010: Persistent Water passage storage MUST be capped at 300 rows. When pruning is required, oldest `completed` rows MUST be removed deterministically before active rows; admission MUST fail closed rather than delete active rows merely to satisfy the cap.
- FR-011: Snapshot media belonging to pruned passages MUST be removed; snapshot replacement for the same retained passage MUST use one stable media object.
- FR-012: The existing combined Objects Registry MUST remain capped at 100 rows and its existing schema/retention contract MUST not be redefined by this feature.
- FR-013: Water operator UI MUST render passage identity and lifecycle, including measuring/null speed and later measured speed/direction on the same passage card.
- FR-014: `worker/water_passage.py` MUST be included in exact Ubuntu Worker and edge artifacts so runtime imports cannot be omitted by packaging.
- FR-015: `vessel_id` MAY be present as nullable structural metadata only; automated persistent visual identity matching is out of scope.
- FR-016: Production rollout MUST require a new exact-SHA production authorization and MUST deploy VPS before Ubuntu Worker because the new Worker consumer depends on the new passage API.

## Acceptance criteria

- AC-001: Deterministic test proves a short ByteTrack split produces one passage with multiple track fragments.
- AC-002: Deterministic test proves a later/out-of-bound track produces a different `passage_id`.
- AC-003: Deterministic test proves bounded observation history never exceeds the configured ring-buffer size.
- AC-004: Strategy-boundary test proves a non-`two_gate` test estimator can populate the same passage contract without persistence changes.
- AC-005: `two_gate` tests prove A→B and B→A produce positive measured speed and direction; incomplete measurement keeps speed null.
- AC-006: Snapshot tests prove first candidate is retained and replacement requires a materially better candidate without producing a second retained media object.
- AC-007: API tests prove two writes for one `passage_id` keep one row and later speed/status values replace earlier measuring/null values.
- AC-008: API retention tests prove the passage table remains <=300, deterministic oldest-completed pruning removes orphan media, and active-only overflow fails closed.
- AC-009: Static storage test proves no persistent per-frame passage-observation table is introduced.
- AC-010: Existing Water continuous-detection and Road regression contracts remain green, including protected detector/profile values.
- AC-011: Frontend contract renders `/api/cam1/passages`, `passage_id`, lifecycle, direction and measured/null speed.
- AC-012: Exact artifact contract includes `worker/water_passage.py` in Ubuntu Worker and edge payloads.
- AC-013: Exact PR diff is a subset of the eleven authorized paths and passes PR Validation plus aggregate Quality on one exact head; expected-head merge is followed by exact-main Quality.
- AC-014: After separate exact-SHA production authorization, VPS-first/Ubuntu-second acceptance observes a naturally occurring vessel as one passage with one retained snapshot and a passage speed lifecycle. Numerical speed accuracy is not a release criterion for this architectural Outcome.

## NFR assessment

- NFR-001 | Area: DATA_SAFETY | Target: Water test storage remains bounded at 300 passage rows/300 passage snapshots and existing Objects Registry remains 100 | Validation: deterministic SQLite/media retention tests | Evidence: `tests/test_water_passage.py`, `tests/test_api_contract.py` | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: tracker-ID churn within a bounded plausible gap does not automatically duplicate one physical pass | Validation: deterministic stitch/new-pass tests plus natural-vessel runtime evidence | Evidence: `tests/test_water_passage.py`, Issue #218 | Status: CONCERNS
- NFR-003 | Area: EXTENSIBILITY | Target: passage persistence/UI remain stable when speed estimator implementation changes | Validation: pluggable fake-estimator contract test | Evidence: `tests/test_water_passage.py` | Status: PASS
- NFR-004 | Area: BACKWARD_COMPATIBILITY | Target: Road event path and Water protected model/profile/inference settings remain unchanged | Validation: existing regression suites and exact diff review | Evidence: `tests/test_water_detection_pipeline.py`, `tests/test_analytics_profiles.py` | Status: PASS
- NFR-005 | Area: OPERABILITY | Target: mixed-contour rollout is fail-closed and ordered VPS before Worker | Validation: Change Contract, exact artifacts, production safety envelope and runtime acceptance | Evidence: PR/Quality/Issue #218 | Status: CONCERNS

## Runtime feedback

- #212 established continuous Water inference and proved a real tracked vessel event on exact Worker release `a43ad7bec5bbcd80887bad842ab28c20b135381a`.
- Live UI then exposed that a first Water event can be persisted before speed becomes available, while ByteTrack identity is too short-lived to represent the longer-lived business concept of a vessel passage.
- The approved architectural correction makes passage identity and speed lifecycle explicit while preserving current detector/tracker settings and deferring permanent visual vessel ReID.
- Final source authorization is durably recorded on Issue #218 comment `5325409717` against main `a2b27333d38ab6b430c51e814256535ca878b3fb`.
