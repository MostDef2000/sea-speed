# Implementation Plan: Water unified passage speed

- Specification: `specs/072-water-unified-passage-speed/spec.md`
- Issue: #346
- Branch: `issue-346-water-unified-passage-speed`
- Authorization base: Task 2 `OUTCOME APPROVED`; original base `50aec9a233b465f73993f92a69f8e9b22707a322`, resumed from accepted protected main `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5`.
- Scope: Ubuntu Worker REQUIRED, VPS NOT REQUIRED.

## Architecture

Before Task 2, Water had two speed ownership paths:

```text
Detection -> PassageEngine(two_gate) -> persisted passage
       \-> post-passage update_speed_lines_estimate -> live bbox speed
```

Task 2 changes this to one passage-owned state:

```text
Detection
  -> update_speed_lines_estimate
       -> fresh instantaneous calibrated evidence + provenance
  -> PassageEngine
       -> strict two_gate estimator
       -> passage-level calibrated evidence accumulator
       -> precedence: measured two_gate > measured calibrated fallback > gate lifecycle
  -> canonical passage speed copied back to detection
       -> Water live envelope
  -> same canonical passage object
       -> passage persistence
```

Per-track detection smoothing still produces fresh/held telemetry, but only `speed_sample_fresh=true` and finite positive `speed_instant_kmh` may enter passage evidence. Passage-level samples are bounded and therefore survive ByteTrack fragment churn without becoming unbounded trajectory storage.

## Decisions

- PassageEngine is the sole owner of published Water speed semantics.
- Preserve `TwoGateSpeedEstimator` and give any completed strict gate measurement precedence.
- Admit calibrated fallback only after the same default minimum fresh sample count used by detection-first speed (`DETECTION_SPEED_MIN_SAMPLES`, default 3).
- Use median of the recent bounded sample window; record samples used and min/avg/max in existing `measurement_meta`.
- Mark instantaneous evidence explicitly with `speed_sample_fresh` / `speed_instant_kmh`; held display values never count as new evidence.
- Store calibrated evidence on `_PassageState`, not `_track_states`, so stitched track fragments share the same measurement lifecycle.
- Remove the Water-only post-passage live overwrite; live envelopes use the canonical passage value copied onto detections.
- Do not modify API/frontend/Road/detector/tracker/ROI/topology.

## Affected contours

- Ubuntu Water Worker: REQUIRED (`worker/hls_motion_yolo_worker_events.py`, `worker/water_passage.py`).
- VPS: NOT REQUIRED; frontend and API remain zero-diff.
- Road Worker: source module is shared, but Road control flow and speed calculation branch remain unchanged; regression evidence required.
- Detection/tracking/ROI: protected / unchanged.
- Camera/HLS/MediaMTX/nginx/Auth/ZeroTier: protected / unchanged.

## Risk profile

- Risk profile: REQUIRED

Reason: Task 2 changes production Water speed-calculation ownership and persistence semantics. It intentionally changes when a passage becomes `measured`, so detection/tracking/calibration/speed impact is YES even though the calibrated formula itself is reused and API schema is unchanged. The change is bounded to Water passage semantics, deterministic tests, exact-source Worker rollout and rollback to `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5`.

## Test design

- TEST-072-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: fresh 10/12/14 samples yield measured 12.0 calibrated passage with min/avg/max metadata
- TEST-072-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: held `speed_sample_fresh=false` values leave sample count unchanged
- TEST-072-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: three fresh samples across track IDs 11/22/33 remain one stitched passage and measure successfully
- TEST-072-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: calibrated measured fallback is superseded by later A->B strict two-gate result
- TEST-072-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: finalize preserves calibrated measured value; two fresh samples finalize incomplete/null
- TEST-072-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: worker source contract verifies fresh telemetry precedes passage update, canonical speed maps back, legacy `_inst` overwrite absent
- TEST-072-007 | Covers: AC-007 | Level: regression | Priority: P0 | Evidence: existing Road/worker tests and exact changed-file review
- TEST-072-008 | Covers: AC-008 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, Ubuntu Worker deployment/runtime progression
- TEST-072-009 | Covers: AC-009 | Level: runtime-manual | Priority: P0 | Evidence: authenticated Water live measured speed and matching latest passage numeric speed

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Water had two independent speed owners in the same worker frame lifecycle; live detection speed could be measured after PassageEngine while the persisted passage remained incomplete.
- Production-learning adjacent-stage findings: API monotonic merge, Water frontend passage rendering, HLS/overlay sync and storage schema behave as designed; the contradiction originates in Worker ordering/ownership.
- TX-072-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no Task 2 source/runtime mutation admitted | Retry: repair authorization/contract evidence | Rollback: none | Evidence: Issue #346 Task 2 OUTCOME APPROVED plus Task 1 authenticated PASS
- TX-072-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production Worker remains prior accepted source | Retry: after exact-head and exact-main quality gates | Rollback: none | Evidence: protected main and quality checks
- TX-072-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate Worker must not be accepted | Retry: after bounded diagnosis | Rollback: exact previous accepted Worker lineage / source `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5` as repository baseline | Evidence: protected Ubuntu Worker deployment
- TX-072-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate remains non-terminal | Retry: verify after remediation/rollback | Rollback: restore previous Worker release if runtime progression degrades | Evidence: Worker deployment/runtime evidence and production passage observation
- TX-072-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded accepted | Retry: exact same verified source only | Rollback: restore prior release pointer/runtime | Evidence: runtime_verified deployment manifest/audit
- TX-072-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified Worker remains active; cleanup warning recorded | Retry: independently | Rollback: none for cleanup-only failure | Evidence: deployment cleanup output
- TX-072-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: Task 2 remains non-terminal | Retry: recollect exact evidence | Rollback: only if verification failed | Evidence: CI/deployment artifact/Issue checkpoint
- TX-072-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident stays open | Retry: after rollback diagnosis | Rollback: previous runtime-verified Water Worker release | Evidence: protected rollback audit if invoked

## Validation

- Validate SDD structure, Change Contract and risk applicability.
- Run deterministic `tests/test_water_passage.py` and `tests/test_worker_tracking_overlay.py`; full repository suite remains authoritative in CI.
- Verify exact diff contains only the two Worker files, approved tests and SDD 072.
- Require exact-head `Repository validation` and `quality-integration` green.
- Fresh-read base/head/scope/reviews and merge exact green head only.
- Require exact-main Quality green.
- Route deployment to Ubuntu Worker REQUIRED and VPS NOT REQUIRED.
- Require exact-source Worker runtime progression and no Road regression evidence.
- Require production observation tying a canonical live measured speed to numeric latest-passage persistence before Task 2 is terminal.

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #346 Task 2 addresses the observed live-speed/history contradiction after Task 1 acceptance.
- Specification impact: formalize one passage-owned speed lifecycle with calibrated fallback and strict-gate precedence.
- Plan impact: Worker-only mutation; API/frontend remain protected because they already represent persisted passage state correctly.
- Tasks impact: explicit fresh-sample provenance, passage-level aggregation, overwrite removal, deterministic precedence/finalization tests, Worker runtime acceptance.
- Authorization impact: no expansion beyond approved Task 2 scope.
- Follow-up: Task 3 recall remains separate and cannot start until Task 2 is accepted.

## Runtime feedback

- Accepted production baseline `e383c836253a8d9c3d824ed8f7c9cd8c1b6be1b5` has Water bbox synchronization PASS.
- Prior production evidence showed live numeric speed can coexist with passage `incomplete`; current source inspection reproduces that split through the post-passage `_inst` overwrite.
- Expected post-deploy evidence is Worker runtime progression plus a measured live speed whose corresponding persisted passage is numeric/measured under the same canonical passage lifecycle.