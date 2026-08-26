# Plan: Water instant speed — per-pixel median on full track + average between lines

- Issue: #322
- Specification: specs/063-water-instant-speed/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-063-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: per-pixel progress_m median last 5, clamped, hold 2s, same as Road | Validation: unit tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-063-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: passage average from samples within gates, no live break | Validation: passage unit | Residual risk: 1 | Owner: api | Status: MITIGATED

## Architecture

- Worker: reuse Road update_speed_lines_estimate logic for Water (bottom_center, progress_m, median), assign to det/live every frame; passage engine keeps average as summary.
- API: store passage speed avg/min/max, no schema change, live already v2.
- No frontend/nginx change.

## Decisions

- D1: Water instantaneous same as Road — bottom_center, projection, median.
- D2: Keep two-gate for passage average as summary, not for live.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: per-pixel median, passage average, live envelope.
- Runtime-manual: Water live speed every frame, passage event average, Road unchanged.

## Test design

- TEST-063-001 | Covers: R1,R2 | Level: unit | Priority: P0 | Evidence: tests/test_worker_tracking_overlay.py | Coverage: COVERED
- TEST-063-002 | Covers: R1,R3 | Level: unit | Priority: P0 | Evidence: tests/test_road_overlay_sync.py | Coverage: COVERED
- TEST-063-003 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware

## Correct-course check

- Trigger: NONE
- Issue impact: additive Water per-pixel live without breaking Road
- Specification impact: new per-frame median contract
- Plan impact: MIXED worker live + passage average
- Tasks impact: AC-001..AC-003 → TASK-063-01..02
- Authorization impact: NONE — initial SDD for src-auth-063
- Follow-up: none

## Runtime feedback

- Water previously two-gate only.

## Deployment transaction audit

- TX-063-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-063-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-063-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 2baa0c0 | Evidence: deployment-manifest MIXED runtime_verified
- TX-063-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 2baa0c0 | Evidence: manifest + live speed
- TX-063-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-063-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-063-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-063-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 2baa0c0 | Rollback: itself | Evidence: rollbackTarget hash
