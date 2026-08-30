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

Ubuntu parent supervision already resolves the selected analytics profile and passes its confidence to the existing single persistent inference child. No new code path, second inference pass or alternate tracker is introduced.

## Evidence decision

### D-074-006 - Dominant loss stage from Task 3B

- Healthy passage `P-20260829T231340-5d4b1ffb` held `track_id=4183`, confidence around `0.82`, class mapping accepted and ROI accepted.
- Unstable passage `P-20260829T232107-c5dcf174` produced intermittent small detections including `boat` confidence `0.1781`, bbox `20x8`, class mapping accepted and ROI accepted, but no track assignment; surrounding frames repeatedly had zero detections.
- Conclusion: dominant stage is `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; tracker non-assignment is secondary to intermittent detector visibility.
- Class-map and ROI tuning are not supported by the evidence.

### D-074-007 - One-variable Water-only threshold experiment

- Decision: lower `water-v1.confidence` from `0.15` to `0.10`.
- Road remains `0.15`.
- Reason: current evidence shows detections close to the active threshold and repeated zero-detection frames for a real small/distant vessel.
- Constraint: diagnostics cannot see candidates below current threshold, so the experiment must be evaluated by post-deploy continuity and false-positive behavior rather than claiming direct evidence for a specific hidden confidence distribution.
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

- Unit assertion: `water-v1.confidence == 0.10`.
- Unit assertion: `road-v1.confidence == 0.15`.
- Existing profile model/imgsz/tracker/sample FPS/class-map assertions remain unchanged.
- Exact base-to-head compare must contain only the five authorized paths.
- Protected-path review must confirm no model, tracker, ROI, speed, API, frontend, Road runtime or deployment change.

### Delivery validation

1. Open one bounded PR from the authorized branch.
2. Require exact-head `Repository validation` PASS.
3. Require exact-head `quality-integration` PASS.
4. Perform a fresh merge probe: current protected main, exact green head, exact diff and review threads.
5. Merge only the exact green head.
6. Require exact-main `Repository validation` and `quality-integration` PASS.
7. Deploy exact main through the protected Ubuntu Worker contour; VPS skipped.
8. Require runtime progression/readiness gates PASS.

### Production acceptance

Representative Water traffic must be observed after the new source is active.

Compare against Task 3B evidence:

- small/distant vessels should remain detected across more consecutive sampled frames;
- stable `track_id` should form when geometry/time permits;
- completed passage behavior should remain valid;
- false positives must remain controlled by visual/operator review and diagnostic counts.

Acceptance result:

- PASS: continuity meaningfully improves without materially uncontrolled false positives;
- FAIL: continuity does not improve or false positives materially increase; restore Water confidence to `0.15`;
- INCONCLUSIVE: insufficient representative traffic; keep explicit evidence wait, do not widen tuning.

## Risk profile

Task 3C changes a production inference acceptance threshold and therefore has runtime behavior impact limited to Ubuntu Water inference. Primary risk is increased false positives. Controls:

- one-variable change only;
- Road confidence explicitly tested at `0.15`;
- exact-head/exact-main gates;
- protected transactional Ubuntu deployment;
- explicit rollback value `0.15`;
- representative production acceptance before Task 3 is considered complete.

No destructive/data migration, public API schema, auth, media topology or model binary risk is introduced.

## Test design

- TEST-074-001 | Unit | Assert Water profile confidence `0.10` and Road profile confidence `0.15` | P0
- TEST-074-002 | Unit/integration | Existing analytics profile mapping/runtime-boundary tests remain green | P0
- TEST-074-003 | Integration | Exact changed-file scope contains only authorized paths | P0
- TEST-074-004 | CI | Exact-head Repository validation and quality-integration PASS | P0
- TEST-074-005 | CI | Exact-main Repository validation and quality-integration PASS | P0
- TEST-074-006 | Runtime | Protected Ubuntu deployment and frame/state/inference progression PASS | P0
- TEST-074-007 | Production | Representative small/distant vessel continuity and false-positive review | P1

## Correct-course check

- Task 3A observability is complete and healthy.
- Task 3B collected temporally overlapping representative evidence and classified the dominant stage.
- Task 3C does not reuse Task 3A/3B authorization; fresh `OUTCOME APPROVED` was recorded immediately after a new six-field Scope.
- The source change follows the evidence-supported detector stage and intentionally avoids simultaneous tracker/ROI/class/imgsz tuning.
- If the experiment fails, rollback to Water confidence `0.15` is the only admitted corrective behavior inside the authorized result boundary; any different tuning direction requires a fresh scope.

## Deployment transaction audit

- TX-074-009 | Stage: TASK3C ADMISSION | Mutation: NO | Evidence: six-field Scope + literal `OUTCOME APPROVED` + Issue receipt | Status: PASS
- TX-074-010 | Stage: TASK3C SOURCE | Mutation: YES | Scope: five authorized paths only | Status: IN PROGRESS
- TX-074-011 | Stage: TASK3C PR QUALITY | Mutation: NO | Required: exact-head Repository validation + quality-integration | Status: PENDING
- TX-074-012 | Stage: TASK3C MERGE | Mutation: YES | Required: fresh merge probe + exact-green-head merge | Status: PENDING
- TX-074-013 | Stage: TASK3C EXACT-MAIN | Mutation: NO | Required: exact-main Repository validation + quality-integration | Status: PENDING
- TX-074-014 | Stage: TASK3C UBUNTU DEPLOY | Mutation: YES | Protected deployment, VPS skipped | Status: PENDING
- TX-074-015 | Stage: TASK3C PRODUCTION ACCEPTANCE | Mutation: NO | Representative continuity/false-positive evidence | Status: PENDING
- TX-074-016 | Stage: TASK3C ROLLBACK | Mutation: YES | Water confidence `0.10 -> 0.15` if acceptance FAIL | Status: CONDITIONAL

## Rollout and rollback

Rollout order: authorized source -> exact-head CI -> fresh merge probe -> exact-green-head merge -> exact-main CI -> protected Ubuntu Worker deployment -> representative production acceptance.

Rollback target is the immediately previous Water profile confidence `0.15`. Road remains `0.15` throughout. No rollback changes to tracker, ROI, class map, image size, model, speed, API or frontend are allowed under this scope.

## Runtime feedback

- Task 3A production diagnostics: COMPLETE.
- Task 3B SDD reconciliation PR #359: merged to `b5555c82d0c97fff4542de6776496fb57d7b57ad`; exact-main checks PASS.
- Task 3B evidence: healthy `boat` detection around `0.82` with stable track versus unstable small `boat` detection at `0.1781` with `track_id=null` and repeated surrounding zero-detection frames.
- Task 3B verdict: `DETECTOR_POST_THRESHOLD_VISIBILITY_INSTABILITY`; `TRACKER_NON_ASSIGNMENT` secondary.
- Task 3C authorization base: `b5555c82d0c97fff4542de6776496fb57d7b57ad`.
- Task 3C implementation: lower Water profile confidence only to `0.10`; Road stays `0.15`.
