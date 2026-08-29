# Implementation Plan: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Issue: #346
- Status: Active
- Branch: `issue-346-water-recall-evidence`
- Authorization base: `739947c11471c746e74af0dfee4d9a5edd0d7bac`
- Scope: Ubuntu Worker REQUIRED; VPS NOT REQUIRED; observability-only, no detection decision change.

## Architecture

The current Water decision path stays authoritative:

```text
ROI mask before inference
  -> model.track(... conf=current threshold, tracker=current tracker)
  -> profile class mapping (`boat` -> `vessel`)
  -> bbox-center ROI post-filter
  -> Water passage/live processing
```

Task 3A adds a side-channel that observes the same in-memory results without feeding back into the decision path:

```text
model.track result
  -> optional diagnostic record
       model_class/confidence/bbox size/track assignment/class mapping
  -> existing accepted detection list (unchanged)
       -> existing ROI filter (unchanged)
  -> bounded diagnostic enrichment
       existing ROI-center predicate + final acceptance outcome
  -> one secret-free JSON log line per bounded interval
```

The diagnostic term `post_threshold_raw` is deliberately precise: Ultralytics has already applied the configured `conf` threshold inside the existing `model.track` call. This stage does not run shadow inference at a lower threshold because a second inference/tracker pass could change GPU load or persistent tracker state. If daytime evidence cannot explain misses, a separate authorized experiment is required.

## Decisions

### D-074-001 - Optional detector diagnostic sink

- Decision: extend `detect_vehicles` with an optional list sink that records model outputs while returning the same accepted detections.
- Reason: exposes class/confidence/bbox/track evidence with no second inference and no API/schema change.
- Alternatives rejected: a second low-confidence `model.predict/track` pass, because it changes runtime cost and could perturb persistent tracking; publishing diagnostics through the API, because Task 3A does not authorize API/storage changes.

### D-074-002 - Reuse the existing ROI predicate

- Decision: compute diagnostic ROI relation with `detection_inside_road_roi(..., roi_points)` and derive final acceptance from the actual post-filter list.
- Reason: diagnostics must describe current semantics rather than implement a parallel approximation.
- Alternatives rejected: geometric IoU/intersection diagnostics as the acceptance predicate, because production currently filters by bbox center and changing that belongs to later evidence-based tuning.

### D-074-003 - Bounded local structured logging

- Decision: emit `WATER_RECALL_DIAGNOSTIC <compact-json>` at most once per configurable interval, default 10 seconds, and cap records per emission, default 12 and hard-capped at 50.
- Reason: evidence is retrievable from Worker runtime logs without increasing API/storage surface or unbounded log volume.
- Alternatives rejected: per-frame logging and image/crop persistence because both are unnecessarily expensive and increase data exposure.

## Affected contours

- Repository: `worker/hls_motion_yolo_worker_events.py`, `tests/test_worker_tracking_overlay.py`, SDD 074.
- VPS: NONE / deployment NOT REQUIRED.
- Ubuntu worker/relay: REQUIRED exact-main release because Worker source changes.
- Windows worker/AI: NONE.
- Public interfaces: NONE; no API/event/state/storage schema changes.
- Road: shared source file is touched, but Road calls `detect_vehicles` without diagnostics and decision flow is unchanged.

## Validation

- Static/CI: SDD validation, Change Contract validation, Python syntax, existing repository behavioral suite, exact diff review.
- Integration: detector-output equality with/without diagnostics; bounded structured payload test; existing Water speed and Road worker regressions.
- Runtime acceptance: protected exact-main Ubuntu Worker installation/activation and deployment manifest PASS. Real-vessel diagnostic sampling may remain deferred while no representative traffic exists.

## Risk profile

- Risk profile: NOT REQUIRED

Task 3A does not change security boundaries, schemas/migrations, destructive behavior, detector/tracker/ROI decisions, calibration/speed formulas or mixed runtime topology. The only production behavior added is bounded Worker logging. Operational overhead is controlled by one emission per 10 seconds by default, capped records and no additional inference pass; exact-source rollback remains available.

## Test design

- TEST-074-001 | Covers: AC-001,NFR-001 | Level: unit | Priority: P0 | Evidence: `tests/test_worker_tracking_overlay.py::test_recall_diagnostics_sink_does_not_change_detector_result`
- TEST-074-002 | Covers: AC-002,AC-003,NFR-003,NFR-004 | Level: unit | Priority: P0 | Evidence: `tests/test_worker_tracking_overlay.py::test_water_recall_diagnostics_are_bounded_and_stage_explicit`
- TEST-074-003 | Covers: AC-004,NFR-002 | Level: unit | Priority: P0 | Evidence: bounded interval/truncation assertions plus source review confirming a single existing `model.track` call
- TEST-074-004 | Covers: AC-005,AC-008 | Level: integration | Priority: P0 | Evidence: exact base-to-head changed-file comparison and protected-path review
- TEST-074-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact-head PR Validation/quality-integration and exact-main push checks
- TEST-074-006 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: protected Ubuntu Worker deployment manifest, exact release artifact and execution audit
- TEST-074-007 | Covers: daytime evidence collection | Level: runtime-manual | Priority: P1 | Evidence: representative `WATER_RECALL_DIAGNOSTIC` log samples when vessel traffic is available; explicitly deferrable in Task 3A

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #346 Task 3 is split into evidence-only Task 3A before any recall tuning because production showed missed/unstable Water vessels.
- Specification impact: diagnostic evidence is now an explicit prerequisite to selecting a recall change.
- Plan impact: add only bounded Worker observability; keep detector/tracker/ROI behavior protected.
- Tasks impact: instrument, prove decision equivalence, deploy, then defer representative sampling if traffic is unavailable.
- Authorization impact: no expansion beyond approved Task 3A; tuning still requires later authorization.
- Follow-up: use daytime evidence to decide whether the minimal later change concerns class mapping, ROI processing/filtering, resolution/confidence or tracker configuration.

## Deployment transaction audit

- TX-074-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current production Worker unchanged | Retry: after authorization/contract evidence is corrected | Rollback: NOT REQUIRED because mutation has not started | Evidence: #346 Task 3A `OUTCOME APPROVED` and exact base
- TX-074-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: current production Worker unchanged | Retry: after exact-head/exact-main gates are green | Rollback: NOT REQUIRED because mutation has not started | Evidence: protected main and Quality evidence
- TX-074-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate release must not be accepted on deployment failure | Retry: protected exact-source deploy after bounded diagnosis | Rollback: previous runtime-verified Ubuntu Worker release | Evidence: Ubuntu deployment protocol
- TX-074-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate remains non-terminal if manifest/source verification fails | Retry: after remediation or rollback | Rollback: previous accepted Worker release | Evidence: deployment manifest and exact artifact identity
- TX-074-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded accepted | Retry: exact same verified source only | Rollback: restore prior release pointer/runtime | Evidence: accepted deployment manifest/audit
- TX-074-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime state preserved | Retry: independently | Rollback: NOT REQUIRED solely for housekeeping failure | Evidence: cleanup warning if any
- TX-074-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed instrumentation remains valid while representative vessel evidence is deferred | Retry: collect logs when traffic exists | Rollback: only if runtime verification or boundedness fails | Evidence: exact deployment evidence plus later diagnostic sample
- TX-074-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open until previous Worker release is verified | Retry: protected rollback after diagnosis | Rollback: previous accepted Ubuntu Worker release | Evidence: rollback manifest/audit if invoked

- Adjacent-stage review: COMPLETE
- Production-learning root cause: current Water runtime exposes only accepted detections, so a missed vessel cannot be attributed to model output/class mapping/ROI/tracker stage from existing production state.
- Production-learning adjacent-stage findings: Task 1 overlay sync is accepted; Task 2 canonical speed source/deployment is complete with daytime speed acceptance deferred; API/frontend do not need diagnostic schema changes; current ROI pre-mask and center filter remain intentionally unchanged pending evidence.

## Rollout and rollback

- Rollout: exact-head PR gates -> fresh merge probe -> exact-green-head merge -> exact-main Repository/Quality -> protected Ubuntu Worker exact-main deployment; VPS skipped. Representative vessel log sampling may occur later without a new deployment.
- Rollback: protected rollback to the previous runtime-verified Ubuntu Worker release if diagnostics cause unexpected Worker instability or operational overhead; no data migration is involved.

## Runtime feedback

- Actual architecture after acceptance: PENDING exact-main Ubuntu Worker deployment.
- Differences from plan: NONE YET.
- Deferred cleanup: representative Water vessel diagnostic samples are intentionally deferred until traffic exists; no threshold/class/ROI/tracker tuning is admitted by that deferral.
