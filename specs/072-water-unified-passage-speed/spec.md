# Feature Specification: Water unified passage speed

- Feature: 072-water-unified-passage-speed
- Issue: #346
- Status: ACTIVE
- Owner outcome: Water live speed and `Последние проходы` expose one canonical passage measurement state instead of independent speed estimators producing contradictory results.
- Authorization: Task 2 `OUTCOME APPROVED`; original authorization base `50aec9a233b465f73993f92a69f8e9b22707a322`, implementation resumes after Task 1 acceptance from protected main `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5` without scope expansion.

## Product outcome

For each Water vessel passage, `WaterPassageEngine` owns the published speed lifecycle. Fresh calibrated detection telemetry is admitted as passage evidence and survives ByteTrack fragment changes because it is stored in passage state rather than per-track state. Three valid fresh samples are sufficient for a calibrated fallback measurement using the median of the configured recent sample window. A completed strict `two_gate` measurement has higher precedence and replaces the calibrated fallback. Water live detections receive their speed back from the canonical passage state, and the same passage object is posted to persistent history.

## User scenarios

### Scenario 1 - calibrated speed completes before both gates

Given a tracked vessel has not completed both strict speed gates but has at least three fresh calibrated speed samples, the passage becomes `speed_status=measured`, `speed_method=detection_first_calibrated`, and live bbox plus persisted passage expose the same numeric speed.

### Scenario 2 - strict gate completes later

Given a passage already has a calibrated fallback measurement, when the same passage subsequently completes A->B or B->A strict gate measurement, `two_gate` becomes canonical and has precedence over the fallback.

### Scenario 3 - ByteTrack fragment churn

Given one physical vessel is stitched across multiple track IDs, calibrated samples accumulated before and after the fragment change belong to the same passage and may complete one canonical measurement.

### Scenario 4 - held display value

Given per-track speed smoothing is temporarily holding an earlier display value without a new physical sample, that held value may remain UI telemetry but MUST NOT increase passage evidence or satisfy the canonical minimum-sample gate.

### Scenario 5 - incomplete measurement

Given a passage ends with fewer than the required fresh calibrated samples and without a strict two-gate result, it completes with `speed_status=incomplete` and no numeric speed.

### Scenario 6 - Road

Road speed estimation, event semantics and worker control flow remain unchanged.

## Requirements

- R1: Water passage state MUST be the single owner of the speed value published both to Water live envelopes and passage persistence.
- R2: Fresh `detection_first_calibrated` evidence MUST be computed before `PassageEngine.update` and carried as explicit provenance, not by overwriting `det["speed_kmh"]` after passage evaluation.
- R3: Only fresh valid instantaneous calibrated samples count toward passage measurement; held/stale display samples MUST NOT increment evidence.
- R4: Default calibrated minimum sample count MUST remain aligned with `DETECTION_SPEED_MIN_SAMPLES` (3) and smoothing with `DETECTION_SPEED_SMOOTH_SAMPLES` (5).
- R5: Calibrated passage measurement MUST use the median of the recent bounded sample window and retain sample count plus min/avg/max measurement metadata.
- R6: Calibrated evidence MUST be bounded in memory and survive ByteTrack fragment stitching inside the same passage.
- R7: A strict `two_gate` measured result MUST have precedence over a calibrated fallback result.
- R8: Finalization MUST preserve an already measured calibrated fallback when no strict gate result exists; insufficient calibrated evidence MUST finalize as `incomplete` with null speed.
- R9: Existing API/storage fields (`speed_status`, `speed_kmh`, `speed_method`, `measurement_meta`) MUST be reused without schema change.
- R10: Road runtime and speed semantics MUST remain unchanged.
- R11: No detector, model class, confidence, ByteTrack, ROI, camera/HLS, MediaMTX, nginx/Auth/ZeroTier or frontend behavior change is allowed in Task 2.

## Acceptance criteria

- AC-001: Three fresh calibrated samples 10/12/14 km/h on one passage produce measured calibrated speed 12.0 km/h and metadata containing sample count plus min/avg/max.
- AC-002: Replayed/held speed telemetry with `speed_sample_fresh=false` does not increment canonical passage sample count.
- AC-003: Fresh calibrated samples accumulated across stitched track IDs complete one measured passage.
- AC-004: A passage measured by calibrated fallback switches to `speed_method=two_gate` when the strict second gate completes.
- AC-005: Finalizing a calibrated measured passage preserves its numeric measured speed; finalizing fewer than three fresh samples yields `incomplete` and null speed.
- AC-006: Water worker source computes calibrated telemetry before `passage_engine.update`, maps passage speed back onto detections, and contains no independent post-passage live speed overwrite.
- AC-007: Road worker semantics and source paths outside the approved Task 2 files remain unchanged.
- AC-008: exact-head Repository validation + quality-integration, exact-green-head merge, exact-main Quality and required Ubuntu Worker deployment/runtime progression pass.
- AC-009: Production observation confirms that when Water live bbox shows a canonical measured speed, the corresponding latest passage persists a numeric speed rather than `не измерена`.

## NFR assessment

- NFR-072-001 | Area: CORRECTNESS | Target: one canonical Water speed state for live and persistence | Validation: passage unit tests plus worker source-order contract | Evidence: Task 2 tests and production passage observation | Status: CONCERNS
- NFR-072-002 | Area: SAFETY | Target: held/stale values cannot falsely complete measurement and strict two-gate retains precedence | Validation: deterministic tests | Evidence: AC-002 and AC-004 | Status: PASS
- NFR-072-003 | Area: BOUNDEDNESS | Target: passage calibrated sample history remains bounded | Validation: bounded deque configuration and tests/inspection | Evidence: `calibrated_max_samples` state | Status: PASS
- NFR-072-004 | Area: COMPATIBILITY | Target: API schema and Road semantics unchanged | Validation: exact diff and regression suite | Evidence: no `api/**` or Road file diff | Status: PASS
- NFR-072-005 | Area: SECURITY | Target: no auth/network/topology changes | Validation: exact changed-file scope | Evidence: Worker/tests/SDD-only diff | Status: PASS

## Production learning

Production demonstrated the contradiction that motivated Task 2: Water live bbox could display a calibrated numeric speed while the corresponding passage remained strict-gate `incomplete`, causing `Последние проходы` to show `не измерена`. Source inspection proved this was not an API merge defect. The Worker evaluated `PassageEngine` first, then independently overwrote each Water detection with `update_speed_lines_estimate` before publishing the live envelope.

## Runtime feedback

- Task 1/1B completed first and authenticated production acceptance passed on exact main `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5`.
- Water overlay synchronization is therefore a protected accepted baseline for Task 2 and is not modified here.
- Expected Task 2 post-deploy evidence is a Water Worker exact-source runtime progression plus a vessel for which canonical measured speed is visible live and the corresponding latest passage contains the same measurement lifecycle rather than `incomplete`.