# Implementation Plan: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Issue: #346
- Status: Active - Task 3A complete; Task 3B evidence interpretation in progress
- Original branch: `issue-346-water-recall-evidence`
- Original authorization base: `739947c11471c746e74af0dfee4d9a5edd0d7bac`
- Remediation branch: `issue-346-water-recall-ipc-remediation`
- Remediation authorization base: `7b9902adca65d43151de629d15e526a5f79d3899`
- Task 3B branch: `issue-346-water-recall-evidence-interpretation`
- Task 3B authorization base: `ea6f1e9d15252840d27721f004817ba35f11d0c6`
- Task 3B scope identity: `issue-346-task3b-water-recall-evidence-interpretation-v1`
- Task 3B contour: Ubuntu Worker READ-ONLY EVIDENCE REQUIRED; VPS NOT REQUIRED; deployment NOT REQUIRED; repository changes limited to SDD 074.

## Architecture

The Water decision path remains authoritative:

```text
ROI mask before inference
  -> one model.track(... conf=current threshold, tracker=current tracker)
  -> profile class mapping (`boat` -> `vessel`)
  -> bbox-center ROI post-filter
  -> Water passage/live processing
```

Task 3A adds a decision-neutral side-channel. Production Ubuntu carries the same split through its existing bounded framed IPC:

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

The diagnostic term `post_threshold_raw` is deliberately precise: Ultralytics has already applied the configured `conf` threshold inside the existing `model.track` call. Task 3B does not run shadow inference at a lower threshold because a second inference/tracker pass could change GPU load or persistent tracker state. If representative evidence cannot explain misses, the result is `INCONCLUSIVE` and a separate authorized experiment is required.

## Decisions

### D-074-001 - Optional detector diagnostic sink

- Decision: extend `detect_vehicles` with an optional list sink that records model outputs while returning the same accepted detections.
- Reason: exposes class/confidence/bbox/track evidence with no second inference and no API/schema change.
- Status: IMPLEMENTED and production accepted in Task 3A.

### D-074-002 - Reuse the existing ROI predicate

- Decision: compute diagnostic ROI relation with `detection_inside_road_roi(..., roi_points)` and derive final acceptance from the actual post-filter list.
- Reason: diagnostics describe current semantics rather than implement a parallel approximation.
- Status: IMPLEMENTED and production accepted in Task 3A.

### D-074-003 - Bounded local structured logging

- Decision: emit `WATER_RECALL_DIAGNOSTIC <compact-json>` at most once per configurable interval, default 10 seconds, and cap records per emission, default 12 and hard-capped at 50.
- Reason: evidence is retrievable from Worker runtime logs without increasing API/storage surface or unbounded log volume.
- Status: IMPLEMENTED and production accepted in Task 3A.

### D-074-004 - Carry diagnostics through the existing Ubuntu inference IPC

- Decision: the Ubuntu AI child serializes the exact pre-existing accepted detection list and a separate diagnostic list from the same single `model.track()` result. The parent validates both inside the existing <=4 MiB framed response and forwards diagnostics only when an optional sink is supplied.
- Reason: production executes inference in `ubuntu_ai_inference_worker.py`; the original 3A implementation instrumented only the in-process path and its monkey-patch call signature was incompatible with the new keyword argument.
- Status: IMPLEMENTED by PR #358 and production accepted at exact main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.

### D-074-005 - Task 3B is read-only evidence interpretation

- Decision: do not change Worker code, detector parameters, class map, ROI or tracker in Task 3B. Observe only existing bounded diagnostic records from the accepted Worker, reconcile SDD 074 with completed Task 3A delivery evidence, and classify the dominant observed loss stage or `INCONCLUSIVE`.
- Reason: the Issue requires evidence before tuning, and Task 3A already provides the production-safe observability surface.
- Alternatives rejected: tuning from visual intuition; adding a diagnostic deployment; adding a second inference pass; widening SDD-only source scope.

## Affected contours

### Task 3A completed contours

- Repository original 3A: `worker/hls_motion_yolo_worker_events.py`, `tests/test_worker_tracking_overlay.py`, SDD 074.
- Repository remediation: `worker/ubuntu_worker_entrypoint.py`, `worker/ubuntu_ai_inference_worker.py`, `tests/test_water_recall_ubuntu_ipc.py`, and SDD 074.
- Ubuntu Worker: exact-main release REQUIRED and completed.
- VPS: NOT REQUIRED and skipped.
- Public interfaces: unchanged.
- Road: two-argument detector compatibility preserved; Road desired runtime state remained stopped during rollout.

### Task 3B current contours

- Repository: only `specs/074-water-detection-recall-evidence/spec.md`, `plan.md`, `tasks.md`.
- Ubuntu Worker: read-only evidence observation of accepted source `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- VPS: none.
- Deployment/runtime mutation: none.
- Protected source: all `worker/**`, detector/tracker/ROI configuration, speed/PassageEngine, API/storage/frontend, Road and deployment tooling.

## Validation

### Completed Task 3A validation

- Exact remediation head: `dd341242e54f4e01382e2322e9571ec407cd295a`.
- PR Validation run `33251179588`: PASS.
- Quality integration run `33251179586`: PASS.
- Exact-green-head merge: PR #358 -> protected main `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- Exact-main Repository validation run `33251243227`: PASS.
- Exact-main quality-integration run `33251243310`: PASS.
- Autonomous production deployment run `33251264466`: PASS.
- Ubuntu Worker contour: REQUIRED/executed/PASS; VPS contour: SKIPPED.
- Runtime gate: frames `17 -> 33`, successful state posts `4 -> 9`, AI inference successes `29 -> 54`, `frame_and_state_progression=PASS`.
- Deployment artifact ID `9714438874`; evidence ZIP digest `sha256:66556adea96476163403a1440fd7bdb1aa3c24a07945dce02ab36699e708c1e5`.

### Task 3B validation

- Source review: branch diff must contain only the three SDD 074 paths.
- SDD validation and normal repository CI remain authoritative for the documentation-only PR.
- Runtime observation: bounded read-only `WATER_RECALL_DIAGNOSTIC` records from `sea-speed-worker.service` while representative Water traffic is visible.
- Evidence interpretation: compare accepted and missed/unstable examples across post-threshold detector visibility, class mapping acceptance, ROI-center relation/final acceptance and track continuity.
- Honest terminal state: classify a supported dominant stage or record `INCONCLUSIVE`.
- Tuning gate: no detector/tracker/ROI/class-map behavior change inside this task.

## Risk profile

- Task 3A remediation risk profile: NOT REQUIRED; completed under the existing transactional Ubuntu rollout.
- Task 3B risk profile: NOT REQUIRED. Repository changes are SDD-only and production observation is read-only, bounded and secret-free. No deployment, restart, schema, destructive operation, inference configuration change or public API change is admitted.

## Test design

- TEST-074-001 | Covers: AC-001,NFR-001 | Level: unit | Priority: P0 | Evidence: `tests/test_worker_tracking_overlay.py::test_recall_diagnostics_sink_does_not_change_detector_result` | Status: PASS
- TEST-074-002 | Covers: AC-002,AC-003,NFR-003,NFR-004 | Level: unit | Priority: P0 | Evidence: `tests/test_worker_tracking_overlay.py::test_water_recall_diagnostics_are_bounded_and_stage_explicit` | Status: PASS
- TEST-074-003 | Covers: AC-004,NFR-002 | Level: unit | Priority: P0 | Evidence: bounded interval/truncation assertions and one-pass source contract | Status: PASS
- TEST-074-004 | Covers: AC-005,AC-008 | Level: integration | Priority: P0 | Evidence: exact base-to-head changed-file comparison and protected-path review | Status: PASS for Task 3A; Task 3B scope review pending PR
- TEST-074-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact-head PR Validation/quality-integration and exact-main push checks | Status: PASS for Task 3A
- TEST-074-006 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: protected Ubuntu Worker deployment manifest, exact release artifact and execution audit with runtime progression PASS | Status: PASS
- TEST-074-007 | Covers: AC-011 daytime evidence interpretation | Level: runtime-manual | Priority: P1 | Evidence: representative `WATER_RECALL_DIAGNOSTIC` log samples and durable stage classification or `INCONCLUSIVE` | Status: PENDING
- TEST-074-008 | Covers: FR-009,FR-010,AC-009,NFR-001,NFR-002,NFR-003,NFR-004 | Level: integration | Priority: P0 | Evidence: `tests/test_water_recall_ubuntu_ipc.py` | Status: PASS
- TEST-074-009 | Covers: AC-010 | Level: delivery-control | Priority: P0 | Evidence: SDD records exact-head/main/deployment evidence from canonical Issue #346 | Status: IN PROGRESS in Task 3B

## Correct-course check

- Trigger: PRODUCTION_LEARNING followed by durable-state reconciliation.
- Original learning: first Task 3A source passed source/quality and AI self-test but failed when the first Water frame invoked an incompatible two-argument detector monkey-patch; Ubuntu child IPC also dropped class-map rejects.
- Remediation result: PR #358 fixed only the production child/parent IPC path and passed exact source, quality and protected Ubuntu runtime progression.
- Current production source: `ea6f1e9d15252840d27721f004817ba35f11d0c6` accepted.
- SDD reconciliation impact: stale PENDING statements for Task 3A are replaced with exact completed evidence. This does not reopen the completed remediation or authorize further Worker changes.
- Task 3B authorization impact: only representative evidence interpretation and three SDD paths are admitted. Recall tuning remains unauthorized.
- Current external dependency: representative Water traffic plus access to the existing Worker journal. The deployment workflow does not export service journal contents, so its lack of `WATER_RECALL_DIAGNOSTIC` lines cannot classify recall.

## Deployment transaction audit

- TX-074-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | Evidence: #346 exact `OUTCOME APPROVED` receipts | Status: PASS
- TX-074-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | Evidence: exact protected source and quality | Status: PASS
- TX-074-003 | Stage: TASK3A MUTATION | Mutation: YES | Failure disposition: FATAL | Rollback: previous runtime-verified Worker | Status: PASS after remediation
- TX-074-004 | Stage: TASK3A VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | Evidence: deployment manifest/runtime gate | Status: PASS
- TX-074-005 | Stage: TASK3A STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | Evidence: accepted deployment manifest/audit | Status: PASS
- TX-074-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | Status: RESOLVED / non-blocking
- TX-074-007 | Stage: TASK3B EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State while unavailable: accepted Worker remains unchanged; retry observation when representative traffic exists | Evidence: bounded diagnostic sample | Status: PENDING
- TX-074-008 | Stage: ROLLBACK | Mutation: YES | Applies only to Task 3A deployment failure; no rollback is relevant to Task 3B read-only observation | Status: NOT REQUIRED for Task 3B

## Rollout and rollback

### Task 3A

Completed: exact-head gates -> fresh merge probe -> exact-green-head merge -> exact-main Repository/Quality -> protected Ubuntu Worker deployment -> runtime progression PASS. VPS skipped. Accepted source is `ea6f1e9d15252840d27721f004817ba35f11d0c6`.

### Task 3B

There is no production rollout. Merge only the SDD reconciliation after required PR checks. Production observation reads existing bounded diagnostic output from the already accepted Worker. No rollback target is needed because Task 3B performs no runtime mutation.

## Runtime feedback

- First 3A candidate `7b9902adca65d43151de629d15e526a5f79d3899` failed twice at runtime progression and restored `739947c11471c746e74af0dfee4d9a5edd0d7bac`.
- PR #358 remediation exact head `dd341242e54f4e01382e2322e9571ec407cd295a` passed PR Validation `33251179588` and quality-integration `33251179586`.
- Remediation merged to `ea6f1e9d15252840d27721f004817ba35f11d0c6`; exact-main runs `33251243227` and `33251243310` passed.
- Deployment run `33251264466` passed with Ubuntu required/executed and VPS skipped. `frame_and_state_progression=PASS`; Worker active; accepted runtime source is `ea6f1e9d15252840d27721f004817ba35f11d0c6`.
- Task 3A is source/deployment/runtime COMPLETE.
- Task 3B representative diagnostic sampling is PENDING. The existing deployment Actions log reports gate counters but does not export `sea-speed-worker.service` journal lines.
- No threshold/class/ROI/tracker tuning is admitted until representative evidence is reviewed and a separate tuning Scope is approved.
