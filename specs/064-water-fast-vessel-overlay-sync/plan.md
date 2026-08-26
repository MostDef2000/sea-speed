# Plan: Water fast vessel tracking + live overlay sync alignment

- Issue: #324
- Specification: specs/064-water-fast-vessel-overlay-sync/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-064-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: dynamic stitch radius capped by stitch_distance_max_px; nearest-predicted-anchor wins; claimed-set per batch unchanged | Validation: unit tests cap+claim | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-064-002 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: prediction falls back to static radius until 2 observations exist; effective gap bounded by stitch window | Validation: unit tests slow-vessel unchanged | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-064-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: closest-earlier fallback bounded to 2s, never future envelopes | Validation: sync-math unit tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED

## Architecture

- Worker: `WaterPassageEngine._resolve` predicts the passage anchor from the last two observations (velocity extrapolation) and admits fragments within a speed-scaled radius capped by `stitch_distance_max_px`.
- Frontend (Water only): lag clamp 600→1200ms; bracket failure renders closest-earlier envelope within 2s instead of stale latest.
- API/schemas/nginx: no change.

## Decisions

- D1: Fix at passage-stitching layer, not ByteTrack yaml — deterministic, testable, keeps tracker config untouched.
- D2: Radius scales with `speed * min(gap, stitch_window) * velocity_stitch_factor`, capped — prevents long-gap over-merge.
- D3: Overlay fallback prefers closest-earlier envelope (bounded age) over arbitrary latest.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: fast fragment churn → single measured passage; radius cap; claim safety; slow-vessel unchanged.
- Sync math: clamp 1200ms; closest-earlier vs stale-latest fallback.
- Runtime-manual: jet ski passage with speed and snapshot; overlay alignment.

## Test design

- TEST-064-001 | Covers: R1,R3,AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_water_passage.py::FastVesselStitchTests | Coverage: COVERED
- TEST-064-002 | Covers: R2,AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_water_passage.py::FastVesselStitchTests | Coverage: COVERED
- TEST-064-003 | Covers: R5,AC-003 | Level: unit | Priority: P0 | Evidence: existing PassageEngineTests pass unchanged | Coverage: COVERED
- TEST-064-004 | Covers: R4,AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_water_overlay_sync.py | Coverage: COVERED
- TEST-064-005 | Covers: AC-005 | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware

## Correct-course check

- Trigger: NONE
- Issue impact: additive stitching/fallback behavior without contract changes
- Specification impact: none beyond initial SDD
- Plan impact: none
- Tasks impact: AC-001..AC-005 → TASK-064-01..04
- Authorization impact: NONE — initial SDD for src-auth-064
- Follow-up: ByteTrack yaml tuning deferred (recorded in tasks DoD)

## Runtime feedback

- Production report after 063: fast vessel missed end-to-end; overlay offset.
- Root causes addressed: static stitch radius; 600ms clamp + stale-latest fallback.

## Deployment transaction audit

- TX-064-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-064-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-064-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 7c52d20 | Evidence: deployment-manifest MIXED runtime_verified
- TX-064-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 7c52d20 | Evidence: manifest + live visual
- TX-064-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-064-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-064-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-064-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 7c52d20 | Rollback: itself | Evidence: rollbackTarget hash
