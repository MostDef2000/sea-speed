# Implementation Plan: Water detection recall evidence

- Specification: `specs/074-water-detection-recall-evidence/spec.md`
- Issue: #346
- Status: Active - Task 3A complete; Task 3B classified; Task 3C implementation in progress
- Task 3C branch: `issue-346-water-low-confidence-recall`
- Task 3C authorization base: `b5555c82d0c97fff4542de6776496fb57d7b57ad`
- Task 3C scope identity: `issue-346-task3c-water-low-confidence-recall-tuning-v1`
- Task 3C contour: Ubuntu Worker REQUIRED after exact-main merge; VPS NOT REQUIRED.

## Architecture

The production Water decision path remains:

```text
ROI mask before inference
  -> one model.track(... conf=water-v1 confidence, tracker=bytetrack.yaml)
  -> profile class mapping (`boat` -> `vessel`)
  -> bbox-center ROI post-filter
  -> Water live/passage processing
```

Road uses the same profile abstraction but a separate `road-v1` profile. Task 3C changes only the Water profile default:

```text
water-v1 confidence: 0.15 -> 0.10
road-v1 confidence:  0.15 -> 0.15
imgsz:                960  -> 960
tracker:              bytetrack.yaml unchanged
class map:            unchanged
ROI:                  unchanged
```

Ubuntu parent supervision already resolves the selected analytics profile and passes its confidence to the existing single persistent inference child. No new inference path, second pass or alternate tracker is introduced.

## Decisions

### D-074-006 - Dominant loss stage from Task 3B

- Healthy passage `P-20260829T231340-5d4b1ffb` held `track_id=4183`, confidence around `0.82`, class mapping accepted and ROI accepted.
- Unstable passage `P-20260829T232107-c5dcf174` produced intermittent small detections including `boat` confidence `0.1781`, bbox `20x8`, class mapping accepted and ROI accepted, but no track assignment; surrounding frames repeatedly had zero detections.
- Conclusion: dominant stage is `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; tracker non-assignment is secondary to intermittent detector visibility.
- Class-map and ROI tuning are not supported by the evidence.

### D-074-007 - One-variable Water-only threshold experiment

- Decision: lower `water-v1.confidence` from `0.15` to `0.10`.
- Road remains `0.15`.
- Reason: current evidence shows detections close to the active threshold and repeated zero-detection frames for a real small/distant vessel.
- Constraint: diagnostics cannot see candidates below current threshold, so the experiment is evaluated by post-deploy continuity and false-positive behavior rather than claiming direct visibility into hidden below-threshold candidates.
- Alternatives rejected for this task: imgsz increase, tracker tuning, ROI changes, class-map widening, model replacement, second/shadow inference.

## Affected contours

### Repository

Authorized paths only:

- `worker/analytics_profiles.py`
- `tests/test_analytics_profiles.py`
- `specs/074-water-detection-recall-evidence/spec.md`
- `specs/074-water-detection-recall-evidence/plan.md`
- `specs/074-water-detection-recall-evidence/tasks.md`

### Runtime

- Ubuntu Worker: REQUIRED after merge because `water-v1` inference confidence changes.
- VPS: NOT REQUIRED.
- Road runtime behavior: protected; `road-v1.confidence` remains `0.15`.
- No deployment-tooling changes.

## Validation

### Source validation

- Assert `water-v1.confidence == 0.10`.
- Assert `road-v1.confidence == 0.15`.
- Retain existing model/imgsz/tracker/sample FPS/class-map assertions.
- Exact base-to-head compare must contain only the five authorized paths.
- Protected-path review must confirm no model, tracker, ROI, speed, API, frontend, Road runtime or deployment change.

### Delivery validation

1. Require exact-head `Repository validation` PASS.
2. Require exact-head `quality-integration` PASS.
3. Perform a fresh merge probe: protected main, exact green head, exact diff and review threads.
4. Merge only the exact green head.
5. Require exact-main `Repository validation` and `quality-integration` PASS.
6. Deploy exact main through the protected Ubuntu Worker contour; VPS skipped.
7. Require runtime readiness/frame/state/inference progression PASS.

### Production acceptance

Representative Water traffic must be observed after the new source is active. Small/distant vessels should remain detected across more consecutive sampled frames and should obtain stable track assignment when geometry/time permits. Completed passage behavior must remain valid. False positives must remain controlled by visual/operator review and diagnostic counts.

Acceptance result is PASS only when continuity improves without materially uncontrolled false positives. If representative traffic is insufficient, remain evidence-deferred. If continuity does not improve or false positives materially increase, restore Water confidence to `0.15`.

## Risk profile

- Risk profile: NOT REQUIRED

The change is one bounded production threshold value with no destructive migration, security boundary, API/schema or mixed-contour change. False-positive risk is controlled by exact-head/exact-main gates, protected Ubuntu deployment, representative acceptance and a one-value rollback.

## Test design

- TEST-074-001 | Covers: AC-001,AC-010 | Level: unit | Priority: P0 | Evidence: `tests/test_analytics_profiles.py::AnalyticsProfilesTests::test_profile_defaults_are_exact`
- TEST-074-002 | Covers: AC-002,AC-003,AC-011 | Level: integration | Priority: P0 | Evidence: exact base-to-head connector compare and protected-path review
- TEST-074-003 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: exact-head `Repository validation` and `quality-integration` Actions runs
- TEST-074-004 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: fresh main/head/diff/review merge probe plus expected-head merge
- TEST-074-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact-main `Repository validation` and `quality-integration` Actions runs
- TEST-074-006 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: protected Ubuntu deployment audit and runtime progression gate
- TEST-074-007 | Covers: AC-008,AC-009 | Level: runtime-manual | Priority: P1 | Evidence: representative post-deploy `WATER_RECALL_DIAGNOSTIC`, Worker inference/state/passages and visual false-positive review

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Task 3 representative evidence now identifies detector visibility instability as the dominant observed loss stage.
- Specification impact: Task 3B evidence verdict and Task 3C one-variable Water threshold acceptance were added.
- Plan impact: rollout, rollback and representative acceptance now target only the Water confidence value.
- Tasks impact: Task 3B evidence gates are complete and Task 3C delivery/runtime gates are added.
- Authorization impact: a new Task 3C six-field Scope and fresh literal `OUTCOME APPROVED` were required and recorded before source mutation.
- Follow-up: finish exact-head CI, exact-green-head merge, exact-main CI, protected Ubuntu deployment and representative post-deploy recall/false-positive acceptance.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: representative small/distant Water vessels show intermittent post-threshold detector visibility near the current confidence boundary while class mapping and ROI acceptance remain healthy.
- Production-learning adjacent-stage findings: tracker non-assignment follows intermittent detector visibility; evidence does not support class-map or ROI rejection as the dominant loss stage.
- TX-074-009 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: source admission remains closed and production remains at Water confidence 0.15 | Retry: re-read six-field Scope and exact authorization receipt before any source write | Rollback: no runtime rollback because admission performs no mutation | Evidence: Issue #346 Task 3C authorization receipt
- TX-074-010 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: branch remains based on accepted protected main without production change | Retry: repeat exact base/scope inspection | Rollback: no runtime rollback because production is unchanged | Evidence: exact protected main `b5555c82d0c97fff4542de6776496fb57d7b57ad`
- TX-074-011 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate branch is not mergeable and production remains at Water confidence 0.15 | Retry: remediate only inside the authorized five paths | Rollback: discard or supersede unmerged candidate commits | Evidence: PR #360 exact changed-file set
- TX-074-012 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate remains unmerged and production remains unchanged | Retry: rerun or remediate failed exact-head validation with evidence | Rollback: no production rollback before merge | Evidence: required exact-head Repository validation and quality-integration
- TX-074-013 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: protected main is not treated as accepted until exact-main quality passes | Retry: only merge an exact green head after a fresh merge probe | Rollback: restore prior protected main behavior through the authorized Water confidence rollback if post-merge acceptance fails | Evidence: expected-head PR merge plus exact-main checks
- TX-074-014 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime/source state remains authoritative even if non-critical cleanup is incomplete | Retry: repeat only bounded non-mutating cleanup evidence collection | Rollback: no behavior rollback for housekeeping-only failure | Evidence: deployment audit housekeeping records
- TX-074-015 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed candidate remains under explicit evidence-deferred acceptance until representative traffic is available | Retry: collect bounded representative Water diagnostics when suitable traffic is present | Rollback: restore Water confidence 0.15 if evidence shows no continuity gain or materially uncontrolled false positives | Evidence: post-deploy `WATER_RECALL_DIAGNOSTIC` plus visual/operator acceptance
- TX-074-016 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: production must return to Water confidence 0.15 with Road unchanged | Retry: execute the protected repository-owned rollback delivery until runtime source and progression are verified | Rollback: rollback target is the prior accepted Water confidence 0.15 | Evidence: protected rollback deployment audit if Task 3C acceptance fails

## Rollout and rollback

Rollout order: authorized source -> exact-head CI -> fresh merge probe -> exact-green-head merge -> exact-main CI -> protected Ubuntu Worker deployment -> representative production acceptance.

Rollback target is the immediately previous Water profile confidence `0.15`. Road remains `0.15` throughout. No rollback changes to tracker, ROI, class map, image size, model, speed, API or frontend are allowed under this scope.

## Runtime feedback

- Task 3A production diagnostics: COMPLETE.
- Task 3B SDD reconciliation PR #359 merged to `b5555c82d0c97fff4542de6776496fb57d7b57ad`; exact-main checks PASS.
- Task 3B evidence: healthy `boat` detection around `0.82` with stable track versus unstable small `boat` detection at `0.1781` with `track_id=null` and repeated surrounding zero-detection frames.
- Task 3B verdict: `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; `TRACKER_NON_ASSIGNMENT` secondary.
- Task 3C authorization base: `b5555c82d0c97fff4542de6776496fb57d7b57ad`.
- Task 3C implementation: lower Water profile confidence only to `0.10`; Road stays `0.15`.
