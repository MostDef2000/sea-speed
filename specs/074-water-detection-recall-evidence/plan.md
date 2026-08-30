# Implementation Plan: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Issue: #346
- Status: Active - Task 3C merged/deployed; production config contradiction found; Task 3C1 remediation in progress
- Task 3C1 branch: `issue-346-task3c1-water-confidence-reconcile`
- Task 3C1 authorization base: `cf85d610311e2a0d9100b0851b20aed99f7aa9c3`
- Task 3C1 scope identity: `issue-346-task3c1-ubuntu-water-confidence-reconciliation-v1`
- Task 3C1 contour: Ubuntu Worker REQUIRED after exact-main merge; VPS application contour NOT REQUIRED.

## Architecture

The production Water decision path remains:

```text
ROI mask before inference
  -> one model.track(... conf=Water runtime confidence, tracker=bytetrack.yaml)
  -> profile class mapping (`boat` -> `vessel`)
  -> bbox-center ROI post-filter
  -> Water live/passage processing
```

The canonical profile and protected runtime configuration must converge:

```text
worker/analytics_profiles.py
  water-v1 confidence: 0.10
  road-v1 confidence:  0.15

protected Ubuntu reconciliation
  worker.env YOLO_CONFIDENCE:      0.10
  road-worker.env YOLO_CONFIDENCE: 0.15
  YOLO_IMAGE_SIZE:                 960 for both
```

Task 3C source changed the canonical Water profile, but the Ubuntu reconciliation helper still forced Water `0.15`. Task 3C1 changes only that protected configuration value and adds deterministic resulting-env assertions. No inference architecture, second pass, tracker, ROI, class-map, image-size, speed or public interface changes are introduced.

## Decisions

### D-074-006 - Dominant loss stage from Task 3B

- Healthy passage `P-20260829T231340-5d4b1ffb` held `track_id=4183`, confidence around `0.82`, class mapping accepted and ROI accepted.
- Unstable passage `P-20260829T232107-c5dcf174` produced intermittent small detections including `boat` confidence `0.1781`, bbox `20x8`, class mapping accepted and ROI accepted, but no track assignment; surrounding frames repeatedly had zero detections.
- Conclusion: dominant stage is `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; tracker non-assignment is secondary to intermittent detector visibility.
- Class-map and ROI tuning are not supported by the evidence.

### D-074-007 - One-variable Water-only threshold experiment

- Decision: lower Water confidence from `0.15` to `0.10`.
- Road remains `0.15`.
- Reason: evidence shows detections close to the active threshold and repeated zero-detection frames for a real small/distant vessel.
- Constraint: diagnostics cannot see candidates below current threshold, so the experiment is evaluated by post-deploy continuity and false-positive behavior rather than claiming direct visibility into hidden below-threshold candidates.
- Alternatives rejected: imgsz increase, tracker tuning, ROI changes, class-map widening, model replacement, second/shadow inference.

### D-074-008 - Runtime configuration is part of threshold acceptance

- Production evidence after PR #360 reported `confidence_threshold: 0.15`, despite canonical `water-v1.confidence=0.10`.
- Source inspection identified `deploy/worker/ubuntu/configure-analytics-profiles.py` forcing Water `YOLO_CONFIDENCE=0.15` during protected deployment.
- Decision: Task 3C1 changes that reconciled Water value to `0.10` and adds an executable test that inspects resulting `worker.env` and `road-worker.env`.
- Acceptance is blocked until a post-deploy Water diagnostic reports `confidence_threshold: 0.10`.

## Affected contours

### Repository

Authorized Task 3C1 paths only:

- `deploy/worker/ubuntu/configure-analytics-profiles.py`
- `tests/test_analytics_profiles.py`
- `specs/074-water-detection-recall-evidence/spec.md`
- `specs/074-water-detection-recall-evidence/plan.md`
- `specs/074-water-detection-recall-evidence/tasks.md`

### Runtime

- Ubuntu Worker: REQUIRED after merge because protected Water `worker.env` must change from `0.15` to `0.10`.
- VPS application contour: NOT REQUIRED.
- Road runtime behavior: protected; Road confidence remains `0.15` and operator desired state must be preserved.
- `worker/analytics_profiles.py`: protected and unchanged because it already contains the canonical values.
- Systemd topology and deployment transaction semantics: unchanged.

## Validation

### Source validation

- Assert canonical `water-v1.confidence == 0.10` and `road-v1.confidence == 0.15` remain unchanged.
- Execute `configure-analytics-profiles.py` in the existing isolated test fixture.
- Assert resulting Water `worker.env`: `ANALYTICS_PROFILE=water-v1`, `YOLO_CONFIDENCE=0.10`, `YOLO_IMAGE_SIZE=960`.
- Assert resulting Road `road-worker.env`: `ANALYTICS_PROFILE=road-v1`, `YOLO_CONFIDENCE=0.15`, `YOLO_IMAGE_SIZE=960`.
- Retain private Road M2M/source and mode-600 assertions.
- Exact base-to-head compare must contain only the five authorized Task 3C1 paths.
- Protected-path review must confirm no model, tracker, ROI, speed, API, frontend, Road behavior, systemd topology or media/auth change.

### Delivery validation

1. Require exact-head `Repository validation` PASS.
2. Require exact-head `quality-integration` PASS.
3. Perform a fresh merge probe: protected main, exact green head, exact diff and review threads.
4. Merge only the exact green head.
5. Require exact-main `Repository validation` and `quality-integration` PASS.
6. Allow repository-owned autonomous protected Ubuntu Worker deployment; VPS application contour skipped.
7. Require runtime readiness/frame/state/inference progression PASS.
8. Require first bounded post-deploy Water diagnostic to report `confidence_threshold: 0.10` before evaluating recall improvement.

### Production acceptance

After the runtime threshold is proven to be `0.10`, representative Water traffic must be observed. Small/distant vessels should remain detected across more consecutive sampled frames and should obtain stable track assignment when geometry/time permits. Completed passage behavior must remain valid. False positives must remain controlled by visual/operator review and diagnostic counts.

Acceptance result is PASS only when the runtime threshold is confirmed at `0.10` and continuity improves without materially uncontrolled false positives. If representative traffic is insufficient, remain evidence-deferred. If continuity does not improve or false positives materially increase, restore Water confidence to `0.15` through a freshly authorized rollback delivery if required by delivery policy.

## Risk profile

- Risk profile: NOT REQUIRED

The remediation is one bounded production configuration value already authorized as the intended Task 3C behavior. It has no destructive migration, security-boundary, API/schema or mixed-contour change. False-positive risk remains controlled by exact-head/exact-main gates, protected Ubuntu deployment, explicit runtime-threshold proof, representative acceptance and a one-value rollback.

## Test design

- TEST-074-001 | Covers: AC-001,AC-010 | Level: unit | Priority: P0 | Evidence: `tests/test_analytics_profiles.py::AnalyticsProfilesTests::test_profile_defaults_are_exact`
- TEST-074-008 | Covers: AC-012 | Level: integration | Priority: P0 | Evidence: `tests/test_analytics_profiles.py::AnalyticsProfilesTests::test_configure_profiles_writes_private_road_m2m_urls_and_mode_600` resulting Water/Road env assertions
- TEST-074-009 | Covers: AC-002,AC-003,AC-011 | Level: integration | Priority: P0 | Evidence: exact Task 3C1 base-to-head connector compare and protected-path review
- TEST-074-010 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: exact-head `Repository validation` and `quality-integration` Actions runs
- TEST-074-011 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: fresh main/head/diff/review merge probe plus expected-head merge
- TEST-074-012 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact-main `Repository validation` and `quality-integration` Actions runs
- TEST-074-013 | Covers: AC-007,AC-013 | Level: end-to-end | Priority: P0 | Evidence: protected Ubuntu deployment audit, runtime progression gate and post-deploy `WATER_RECALL_DIAGNOSTIC` threshold
- TEST-074-014 | Covers: AC-008,AC-009 | Level: runtime-manual | Priority: P1 | Evidence: representative post-deploy `WATER_RECALL_DIAGNOSTIC`, Worker inference/state/passages and visual false-positive review

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Task 3C source/CI/deployment completed, but representative diagnostic proved the intended `0.10` Water runtime threshold was not active.
- Specification impact: runtime configuration convergence and threshold-proof acceptance were added.
- Plan impact: protected config reconciliation is now an explicit Task 3C1 affected contour; post-deploy threshold proof precedes recall acceptance.
- Tasks impact: Task 3C delivery gates are recorded complete, the configuration contradiction is recorded, and Task 3C1 remediation gates are added.
- Authorization impact: a fresh Task 3C1 six-field Scope and literal `OUTCOME APPROVED` were required and recorded before file/source mutation; a branch-ref sequencing deviation occurred before durable receipt but before any file mutation and is durably recorded.
- Follow-up: finish Task 3C1 exact-head CI, exact-green-head merge, exact-main CI, protected Ubuntu deployment, confirm runtime threshold `0.10`, then resume representative recall/false-positive acceptance.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Task 3C canonical source and protected runtime config diverged because the Ubuntu reconciler hard-coded Water `YOLO_CONFIDENCE=0.15`.
- Production-learning adjacent-stage findings: model/tracker/ROI/class-map were not implicated; deployment completed successfully but did not verify the intended detector threshold.
- TX-074-017 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source admission remains closed and production remains Water 0.15 | Retry: require the exact six-field Task 3C1 scope and authorization receipt | Rollback: none because admission performs no runtime mutation | Evidence: Issue #346 generation 25 authorization checkpoint
- TX-074-018 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: remediation branch remains based on accepted protected main | Retry: repeat exact base/scope inspection | Rollback: none because production is unchanged | Evidence: protected main `cf85d610311e2a0d9100b0851b20aed99f7aa9c3`
- TX-074-019 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate remains unmergeable and production stays Water 0.15 | Retry: remediate only inside the five Task 3C1 paths | Rollback: discard/supersede unmerged candidate commits | Evidence: exact branch changed-file set
- TX-074-020 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate remains unmerged | Retry: remediate bounded exact-head findings only | Rollback: no production rollback before merge | Evidence: required exact-head checks
- TX-074-021 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: merged source is not accepted until exact-main checks pass | Retry: merge only exact green head after fresh probe | Rollback: use authorized source correction/rollback if post-merge gates fail | Evidence: expected-head merge and exact-main checks
- TX-074-022 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed candidate remains pending until Water diagnostic proves `confidence_threshold: 0.10` and representative traffic is available | Retry: bounded diagnostic sampling | Rollback: restore Water `0.15` if experiment fails acceptance | Evidence: post-deploy diagnostic plus operator visual evidence
- TX-074-023 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: production returns to Water `0.15`, Road unchanged | Retry: protected repository-owned rollback delivery | Rollback: target Water `0.15` | Evidence: rollback deployment audit if required

## Rollout and rollback

Rollout order: authorized Task 3C1 source -> exact-head CI -> fresh merge probe -> exact-green-head merge -> exact-main CI -> protected Ubuntu Worker deployment -> prove runtime Water threshold `0.10` -> representative production acceptance.

Rollback target for the experiment remains Water confidence `0.15`. Road remains `0.15` throughout. No rollback changes to tracker, ROI, class map, image size, model, speed, API or frontend are allowed under this scope.

## Runtime feedback

- Task 3A production diagnostics: COMPLETE.
- Task 3B verdict: `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; `TRACKER_NON_ASSIGNMENT` secondary.
- Task 3C PR #360 exact-head checks: Repository validation `33285244727` PASS; quality-integration `33285244723` PASS.
- Task 3C protected main `cf85d610311e2a0d9100b0851b20aed99f7aa9c3`: exact-main Repository validation `33285295734` PASS; quality-integration `33285295735` PASS.
- Task 3C autonomous deployment run `33285316835` PASS with Ubuntu runtime progression PASS and VPS application contour skipped.
- First representative post-deploy diagnostic still reported Water `confidence_threshold: 0.15`; therefore Task 3C production acceptance is BLOCKED, not PASS.
- Source-confirmed cause: Ubuntu protected configuration reconciliation forced Water `YOLO_CONFIDENCE=0.15` despite canonical profile `0.10`.
- Task 3C1 authorization base: `cf85d610311e2a0d9100b0851b20aed99f7aa9c3`; remediation changes only protected Water config convergence, resulting-env regression coverage and SDD bookkeeping.
