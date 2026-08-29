# Implementation Plan: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Issue: #346
- Status: Active
- Original branch: `issue-346-water-recall-evidence`
- Original authorization base: `739947c11471c746e74af0dfee4d9a5edd0d7bac`
- Remediation branch: `issue-346-water-recall-ipc-remediation`
- Remediation authorization base: `7b9902adca65d43151de629d15e526a5f79d3899`
- Scope: Ubuntu Worker REQUIRED; VPS NOT REQUIRED; observability-only, no detection decision change.

## Architecture

The Water decision path remains authoritative:

```text
ROI mask before inference
  -> one model.track(... conf=current threshold, tracker=current tracker)
  -> profile class mapping (`boat` -> `vessel`)
  -> bbox-center ROI post-filter
  -> Water passage/live processing
```

Task 3A adds a decision-neutral side-channel. On the direct/in-process path the detector produces both accepted detections and diagnostic records from the same result. Production Ubuntu uses an isolated child and therefore carries the same split through its existing bounded framed IPC:

```text
Ubuntu parent supervisor
  -> frame request
  -> Ubuntu AI child
       -> one model.track result
       -> serialize accepted detections (unchanged)
       -> serialize post-threshold diagnostic records
  <- bounded framed {detections, diagnostics}
  -> optional diagnostic sink
  -> existing accepted detection list
       -> existing ROI filter
  -> bounded diagnostic enrichment
       existing ROI-center predicate + final acceptance outcome
  -> one secret-free WATER_RECALL_DIAGNOSTIC line per bounded interval
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

### D-074-004 - Carry diagnostics through the existing Ubuntu inference IPC

- Decision: the Ubuntu AI child serializes two logical outputs from the same single `model.track()` result: the exact pre-existing accepted detection list and a separate diagnostic list. The parent validates both in the existing <=4 MiB framed response and forwards diagnostics only when an optional sink is supplied.
- Reason: production executes inference in `ubuntu_ai_inference_worker.py`; the original 3A implementation only instrumented the in-process detector and its monkey-patch call signature was incompatible with the new keyword argument.
- Alternatives rejected: suppressing the diagnostics keyword on Ubuntu, because class-map rejects would remain invisible; running another inference pass, because it changes runtime behavior; changing deployment/runtime verifier scripts, because the failure is source-path compatibility, not deployment infrastructure.

## Affected contours

- Repository original 3A: `worker/hls_motion_yolo_worker_events.py`, `tests/test_worker_tracking_overlay.py`, SDD 074.
- Repository remediation: `worker/ubuntu_worker_entrypoint.py`, `worker/ubuntu_ai_inference_worker.py`, `tests/test_water_recall_ubuntu_ipc.py`, and SDD 074. `worker/hls_motion_yolo_worker_events.py` remains within the authorized remediation scope but requires no semantic change unless validation exposes one.
- VPS: NONE / deployment NOT REQUIRED.
- Ubuntu Worker: REQUIRED exact-main release because production Worker source changes.
- Public interfaces: NONE; internal framed child response gains only optional diagnostics data.
- Road: two-argument `detect_vehicles` calls remain valid because the monkey patch defaults `diagnostics=None`; Road detector/class/tracker semantics do not change.

## Validation

- Static/CI: SDD validation, Change Contract validation, Python syntax, repository behavioral suite, exact changed-file review.
- Unit/integration: accepted detection serialization equality; class-map reject visibility only in diagnostics; parent optional sink compatibility; one `model.track` source call; existing bounded log tests; Road regressions.
- Runtime acceptance: protected exact-main Ubuntu Worker must complete AI self-test, enter `Worker started`, advance frame/state counters and satisfy `frame_and_state_progression=PASS`. VPS must skip. Real-vessel diagnostic sampling may remain deferred while no representative traffic exists.

## Risk profile

- Risk profile: NOT REQUIRED

The remediation changes an internal supervised inference response and call signature but does not change security boundaries, schemas/migrations, destructive behavior, detector/tracker/ROI decisions, calibration/speed formulas or topology. IPC is already framed and capped at 4 MiB; no second inference is added. Production rollout remains transactional with automatic restoration of the prior runtime-verified Worker on activation failure.

## Test design

- TEST-074-001 | Covers: AC-001,NFR-001 | Level: unit | Priority: P0 | Evidence: `tests/test_worker_tracking_overlay.py::test_recall_diagnostics_sink_does_not_change_detector_result`
- TEST-074-002 | Covers: AC-002,AC-003,NFR-003,NFR-004 | Level: unit | Priority: P0 | Evidence: `tests/test_worker_tracking_overlay.py::test_water_recall_diagnostics_are_bounded_and_stage_explicit`
- TEST-074-003 | Covers: AC-004,NFR-002 | Level: unit | Priority: P0 | Evidence: bounded interval/truncation assertions and one-pass source contract
- TEST-074-004 | Covers: AC-005,AC-008 | Level: integration | Priority: P0 | Evidence: exact base-to-head changed-file comparison and protected-path review
- TEST-074-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact-head PR Validation/quality-integration and exact-main push checks
- TEST-074-006 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: protected Ubuntu Worker deployment manifest, exact release artifact and execution audit with runtime progression PASS
- TEST-074-007 | Covers: daytime evidence collection | Level: runtime-manual | Priority: P1 | Evidence: representative `WATER_RECALL_DIAGNOSTIC` log samples when vessel traffic is available; explicitly deferrable in Task 3A
- TEST-074-008 | Covers: FR-009,FR-010,AC-009,NFR-001,NFR-002,NFR-003,NFR-004 | Level: integration | Priority: P0 | Evidence: `tests/test_water_recall_ubuntu_ipc.py`

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #346 Task 3A remains evidence-only; production rollout of the first implementation failed twice and automatically restored the accepted Worker.
- Specification impact: production Ubuntu child/parent IPC is now explicitly part of the observability contract.
- Plan impact: add only the internal child diagnostics field and optional parent sink plumbing; keep detector/tracker/ROI behavior protected.
- Tasks impact: add remediation implementation/test/gates before retrying deployment.
- Authorization impact: a fresh six-field remediation Scope was approved from protected main `7b9902adca65d43151de629d15e526a5f79d3899`; the additional Ubuntu source paths are therefore admitted. Recall tuning remains unauthorized.
- Root cause: `ubuntu_worker_entrypoint.py` replaced `detect_vehicles` with a two-argument function, while Water invoked `diagnostics=...`; `ubuntu_ai_inference_worker.py` also discarded class-map rejects before the parent could observe them.
- Follow-up: after a runtime-verified remediation, use daytime evidence to decide whether any later recall change concerns class mapping, ROI, resolution/confidence or tracker configuration.

## Deployment transaction audit

- TX-074-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: current production Worker unchanged | Retry: after authorization/contract evidence is corrected | Rollback: NOT REQUIRED because mutation has not started | Evidence: #346 exact `OUTCOME APPROVED` receipts
- TX-074-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: current production Worker unchanged | Retry: after exact-head/exact-main gates are green | Rollback: NOT REQUIRED | Evidence: protected main and Quality evidence
- TX-074-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate release must not be accepted on deployment failure | Retry: protected exact-source deploy after bounded diagnosis | Rollback: previous runtime-verified Ubuntu Worker release | Evidence: Ubuntu deployment protocol
- TX-074-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate remains non-terminal if runtime/source verification fails | Retry: after remediation or rollback | Rollback: previous accepted Worker release | Evidence: deployment manifest and runtime gate
- TX-074-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded accepted | Retry: exact same verified source only | Rollback: restore prior release pointer/runtime | Evidence: accepted deployment manifest/audit
- TX-074-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime state preserved | Retry: independently | Rollback: NOT REQUIRED solely for housekeeping failure | Evidence: cleanup warning if any
- TX-074-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed instrumentation remains valid while representative vessel evidence is deferred | Retry: collect logs when traffic exists | Rollback: only if runtime verification or boundedness fails | Evidence: exact deployment evidence plus later diagnostic sample
- TX-074-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open until previous Worker release is verified | Retry: protected rollback after diagnosis | Rollback: previous accepted Ubuntu Worker release | Evidence: rollback manifest/audit if invoked

- Adjacent-stage review: COMPLETE
- Production-learning root cause: the Ubuntu production entrypoint exposed an incompatible two-argument detector monkey-patch and the child IPC removed class-map rejects before Task 3A diagnostics could observe them.
- Production-learning adjacent-stage findings: deployment transport, source protection and AI self-test all passed; failure occurred only when the first actual Water frame entered the incompatible monkey-patched detector call. Deployment tooling therefore remains protected and unchanged.

## Rollout and rollback

- Rollout: remediation exact-head PR gates -> fresh merge probe -> exact-green-head merge -> exact-main Repository/Quality -> protected Ubuntu Worker exact-main deployment; VPS skipped. Representative vessel log sampling may occur later without a new deployment.
- Rollback: protected updater automatically restores the previous runtime-verified Ubuntu Worker release if activation/runtime progression fails. Prior accepted production source before remediation is `739947c11471c746e74af0dfee4d9a5edd0d7bac`; no data migration is involved.

## Runtime feedback

- Actual architecture learned from failed rollout: Ubuntu production inference is isolated in `ubuntu_ai_inference_worker.py`, with `ubuntu_worker_entrypoint.py` replacing the generic detector function.
- First 3A candidate `7b9902adca65d43151de629d15e526a5f79d3899` failed twice with `no_exact_running_baseline` after `ai_inference_ready=true`; both attempts restored `739947c11471c746e74af0dfee4d9a5edd0d7bac`.
- Remediation architecture: PENDING exact-head validation and exact-main deployment.
- Deferred cleanup: representative Water vessel diagnostic samples remain intentionally deferred until traffic exists; no threshold/class/ROI/tracker tuning is admitted by that deferral.
