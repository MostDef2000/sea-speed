# Plan: Water overlay tools fix — restore AI overlay and ROI/speed/crossing editing

- Issue: #318
- Specification: specs/061-water-overlay-tools-fix/spec.md

## Risk profile

- Risk profile: NOT REQUIRED

## Architecture

- Frontend: `frontend/sea-speed/index.html` — waterMainVideo opacity handling (not display:none), liveOverlayCanvas uses waterMainVideo/ROI rect for contentRect, median lag compensation reuse, hi passages stable; ROI/speed/crossing editors keep overlayImg visible via opacity.

## Decisions

- D1: Use opacity instead of display:none to preserve getBoundingClientRect for editors.
- D2: Reuse Road 059 lag compensation and bracket logic for Water.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: NOT REQUIRED

## Validation

- Unit: frontend contract, sync math, editor save-verify.
- Runtime-manual: Water AI visible, ROI/Speed/Crossing editable, clean preview both cards, Road no regression.

## Test design

- TEST-061-001 | Covers: R1,R2 | Level: unit | Priority: P0 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- TEST-061-002 | Covers: R1 | Level: unit | Priority: P0 | Evidence: tests/test_road_overlay_sync.py | Coverage: COVERED
- TEST-061-003 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: VPS manifests + visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware

## Correct-course check

- Trigger: NONE
- Issue impact: frontend display/opacity fix without worker/API
- Specification impact: clarify opacity vs display
- Plan impact: VPS frontend only
- Tasks impact: AC-001..AC-003 → TASK-061-01..02
- Authorization impact: NONE — initial SDD for src-auth-061
- Follow-up: none

## Runtime feedback

- 060 merged but water overlay hidden due to display:none.

## Deployment transaction audit

- TX-061-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-061-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-061-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy da9d70c | Evidence: deployment-manifest VPS runtime_verified
- TX-061-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: da9d70c | Evidence: manifest + visual
- TX-061-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-061-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-061-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-061-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy da9d70c | Rollback: itself | Evidence: rollbackTarget hash
