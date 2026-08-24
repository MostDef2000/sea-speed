# Plan: Stage 3 clean-overlay — hide baked boxes, live canvas only

- Issue: #305
- Specification: specs/055-road-clean-overlay/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-055-001 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: clean JPEG without AI boxes, frontend hides overlayImg when live present, content-box math, TTL | Validation: worker overlay + frontend tests | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-055-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: fallback to clean overlay.jpg until first live, no duplicate | Validation: frontend contract | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-055-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: Water path unchanged, additive only | Validation: tracking overlay tests | Residual risk: 1 | Owner: worker | Status: MITIGATED

## Architecture

- Worker: draw_overlay for Road returns clean frame (ROI/lines only, no AI boxes/IDs/speeds) when ROAD_CLEAN_OVERLAY=1 (default for Road).
- Frontend: liveOverlayCanvas is sole box source when live present; overlayImg hidden (opacity 0) while live active, shown clean otherwise; stale clears <1s.

## Decisions

- D1: Clean overlay JPEG for Road, Water keeps baked boxes.
- D2: Frontend hides overlayImg only when live envelope present, fallback retains clean.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: clean overlay has no AI boxes, frontend hide/show logic, TTL.
- Integration: live SSE still streams, overlay remains clean.
- Runtime-manual: HLS + live canvas smooth, no duplicate, resize/fullscreen.

## Test design

- TEST-055-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: test_worker_tracking_overlay | Coverage: COVERED
- TEST-055-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: test_frontend_contract | Coverage: COVERED
- TEST-055-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: test_telemetry_contract | Coverage: COVERED
- TEST-055-004 | Covers: AC-002 | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + manual visual | Coverage: RUNTIME-MANUAL | Reason: visual clean-overlay

## Correct-course check

- Trigger: NONE
- Issue impact: removes duplicate baked boxes, makes live canvas visible
- Specification impact: adds clean-overlay semantics
- Plan impact: adds Road clean-overlay flag and frontend fallback
- Tasks impact: AC-001..AC-003 → TASK-055-01..TASK-055-03
- Authorization impact: NONE — initial for src-auth-055
- Follow-up: Stage4 frequency still separate

## Runtime feedback

- Prior 7240413 live wiring present but overlay still baked, duplicate visual.

## Deployment transaction audit

- TX-055-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-055-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-055-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 7240413 | Evidence: deployment-manifest MIXED runtime_verified
- TX-055-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 7240413 | Evidence: manifest + visual clean check
- TX-055-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-055-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-055-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-055-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 7240413 | Rollback: itself | Evidence: rollbackTarget hash
