# Plan: Water overlay fallback fix

- Issue: #320
- Specification: specs/062-water-overlay-fallback-fix/spec.md

## Risk profile

- Risk profile: NOT REQUIRED

## Architecture

- Frontend: expose HLS instances to window, fallback to latest live envelope when PDT unavailable, keep overlayImg opacity handling.

## Decisions

- D1: Frontend-only, no worker/API change.
- D2: Fallback to latest ensures immediate visibility, still fail-closed after.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: NOT REQUIRED

## Validation

- Unit: frontend contract, sync math.
- Runtime-manual: Water AI visible immediately, ROI tools functional.

## Test design

- TEST-062-001 | Covers: R1,R2 | Level: unit | Priority: P0 | Evidence: tests/test_frontend_contract.py | Coverage: COVERED
- TEST-062-002 | Covers: runtime | Level: runtime-manual | Priority: P1 | Evidence: VPS manifests + visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware

## Correct-course check

- Trigger: NONE
- Issue impact: frontend fallback fix
- Specification impact: add fallback contract
- Plan impact: VPS frontend only
- Tasks impact: AC-001..AC-002 → TASK-062-01
- Authorization impact: NONE — initial SDD for src-auth-062
- Follow-up: none

## Runtime feedback

- Prior 061 water overlay hidden when PDT null.

## Deployment transaction audit

- TX-062-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-062-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-062-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 7896779 | Evidence: deployment-manifest VPS runtime_verified
- TX-062-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 7896779 | Evidence: manifest + visual
- TX-062-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-062-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-062-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-062-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 7896779 | Rollback: itself | Evidence: rollbackTarget hash
