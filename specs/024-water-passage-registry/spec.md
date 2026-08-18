# Feature Specification: Water Passage Architecture

- Feature: 024-water-passage-registry
- Issue: #218
- Status: Correct-course remediation
- Owner outcome: Make a physical vessel passage the primary Water record, keep test data bounded, make speed measurement replaceable without redesigning storage or UI, and restore the protected Sea Speed entrypoint from the observed HTTP 500 before mixed-contour runtime acceptance.

## Product outcome

Water analytics creates one bounded `passage_id` for one observed physical vessel pass. ByteTrack `track_id` remains a short-lived tracking implementation detail; short, spatially plausible tracker-ID interruptions may be stitched into the same active passage. The passage carries a nullable future `vessel_id`, but cross-passage visual ReID is deferred.

Speed is a passage property behind a pluggable `SpeedEstimator` boundary. The first strategy is `two_gate`, which consumes bounded in-memory observations and reports `speed_status`, optional `speed_kmh`, `speed_method`, optional direction and compact measurement metadata. A passage may be persisted while speed is still null and later update the same record to a measured result. Accuracy optimization is not an acceptance target in this Outcome.

The VPS stores Water passages in a dedicated bounded SQLite table separate from the existing newest-100 Objects Registry. At most 300 passage rows and 300 passage snapshots are retained. Raw per-frame trajectory observations are never persisted; they exist only in a bounded Worker RAM ring buffer.

Runtime feedback after the first source merge exposed a release-blocking pre-existing failure: the protected `https://mostdef.ru/sea-speed/` entrypoint was observed returning HTTP 500. The canonical Auth v1 deploy transaction previously deadlocked on that condition because public frontend smoke ran before Auth reconciliation, while the privileged reconciliation path required an already healthy protected baseline. This Outcome therefore includes a narrowly bounded recovery path for exactly that fail-closed HTTP 500 state before any Water source mutation on the VPS. It does not authorize an auth bypass or generic nginx/root repair mechanism.

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

### Scenario 6 - existing protected HTTP 500 does not deadlock deployment
Given the anonymous protected Operator entrypoint returns exactly HTTP 500 while exact release/helper admission passes, VPS deployment attempts only the bounded Auth v1 recovery transaction before live API/frontend/current-release mutation. Recovery must restore the protected entrypoint to an auth-gated `302`, `401` or `403`; any different failure remains fail-closed and prevents Water source mutation.

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
- FR-017: With Auth v1 required, VPS deployment MUST distinguish an already healthy anonymous protected response (`302|401|403`) from the specifically recoverable HTTP 500 state before any live Water source/service/current-release mutation. HTTP 200, 5xx other than the explicitly admitted 500, transport failure or any other status MUST fail closed.
- FR-018: The restricted root helper MAY relax the existing healthy-baseline requirement only after the exact protected-baseline check fails with the explicit `/sea-speed/ ... HTTP 500` marker. It MUST then use the same exact source-managed cutover renderer and fixed private topology; failed activation MUST restore the exact pre-recovery nginx file bytes and validate nginx syntax/service health. Arbitrary nginx paths, arbitrary commands and auth bypass remain forbidden.
- FR-019: Successful pre-source recovery MUST re-read the protected entrypoint and observe `302|401|403` before normal VPS source deployment continues. Ubuntu Worker rollout MUST remain blocked until the VPS protected entrypoint, API/UI and passage boundary pass acceptance.

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
- AC-013: Exact PR diff is a subset of the currently authorized sixteen-path union recorded on Issue #218 and passes PR Validation plus aggregate Quality on one exact head; expected-head merge is followed by exact-main Quality.
- AC-014: After separate exact-SHA production authorization, VPS-first/Ubuntu-second acceptance observes a naturally occurring vessel as one passage with one retained snapshot and a passage speed lifecycle. Numerical speed accuracy is not a release criterion for this architectural Outcome.
- AC-015: Transaction tests reproduce protected `/sea-speed/` HTTP 500 and prove bounded recovery completes before live API/frontend/current-release mutation, after which deployment proceeds normally.
- AC-016: Recovery unit/transaction tests prove non-500 baseline failures do not enter the recovery path and failed recovery activation invokes exact-baseline rollback; production acceptance proves `https://mostdef.ru/sea-speed/` no longer returns 500 and remains auth-gated.

## NFR assessment

- NFR-001 | Area: DATA_SAFETY | Target: Water test storage remains bounded at 300 passage rows/300 passage snapshots and existing Objects Registry remains 100 | Validation: deterministic SQLite/media retention tests | Evidence: `tests/test_water_passage.py`, `tests/test_api_contract.py` | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: tracker-ID churn within a bounded plausible gap does not automatically duplicate one physical pass | Validation: deterministic stitch/new-pass tests plus natural-vessel runtime evidence | Evidence: `tests/test_water_passage.py`, Issue #218 | Status: CONCERNS
- NFR-003 | Area: EXTENSIBILITY | Target: passage persistence/UI remain stable when speed estimator implementation changes | Validation: pluggable fake-estimator contract test | Evidence: `tests/test_water_passage.py` | Status: PASS
- NFR-004 | Area: BACKWARD_COMPATIBILITY | Target: Road event path and Water protected model/profile/inference settings remain unchanged | Validation: existing regression suites and exact diff review | Evidence: `tests/test_water_detection_pipeline.py`, `tests/test_analytics_profiles.py` | Status: PASS
- NFR-005 | Area: OPERABILITY | Target: mixed-contour rollout is fail-closed and ordered VPS before Worker | Validation: Change Contract, exact artifacts, production safety envelope and runtime acceptance | Evidence: PR/Quality/Issue #218 | Status: CONCERNS
- NFR-006 | Area: SECURITY_RELIABILITY | Target: pre-existing protected HTTP 500 is recoverable without auth bypass, arbitrary root execution or Water source mutation before recovery | Validation: privileged-helper recovery unit tests, VPS deployment transaction tests, exact runtime HTTP/auth evidence | Evidence: `tests/test_vps_deploy_transaction.py`, Issue #218 | Status: CONCERNS

## Runtime feedback

- #212 established continuous Water inference and proved a real tracked vessel event on exact Worker release `a43ad7bec5bbcd80887bad842ab28c20b135381a`.
- Live UI then exposed that a first Water event can be persisted before speed becomes available, while ByteTrack identity is too short-lived to represent the longer-lived business concept of a vessel passage.
- The approved architectural correction makes passage identity and speed lifecycle explicit while preserving current detector/tracker settings and deferring permanent visual vessel ReID.
- Initial Water Passage source authorization is durably recorded on Issue #218 comments `5325409717` and `5325529286`.
- PR #219 merged that architecture to main `e814d32f9b743d674ce87556313e264debd0bc14` with exact-main Quality success.
- Before production mutation, the operator reported `https://mostdef.ru/sea-speed/` returning HTTP 500. Source analysis identified a recovery deadlock between pre-reconcile frontend smoke and the healthy-baseline-only privileged Auth reconciliation path; root-cause evidence is Issue #218 comment `5327488945`.
- The complete recovery Scope then received a fresh exact `OUTCOME APPROVED`; durable authorization is Issue #218 comment `5327660150`. Production remains separately unauthorized until this remediation is merged and a fresh exact-main fingerprint is approved.
