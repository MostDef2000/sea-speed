# Implementation Plan: Water live overlay sync guard

- Specification: `specs/071-water-live-overlay-sync-guard/spec.md`
- Issue: #346
- Branch: `issue-346-water-live-sync`
- Authorization base main: `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a`
- Approved scope identity: `issue-346-task1-water-live-overlay-sync-v1`

## Architecture

The task remains entirely in the authenticated Water frontend. HLS video and AI metadata stay separate:

```text
/sea-speed/media/cam1/index.m3u8
        -> one Hls instance
        -> waterMainVideo

/sea-speed/api/cam1/live
        -> bounded metadata buffer
        -> media-time bracket / closest-earlier match
        -> liveOverlayCanvas
```

The renderer becomes fail-closed. Unknown media time or unmatched metadata clears `liveOverlayCanvas`; it never substitutes the newest buffered envelope. Existing interpolation, lag compensation, generation ordering and one-HLS lifecycle remain unchanged.

## Decisions

- Keep `frontend/sea-speed/live-sync.js` unchanged because its bracketing/interpolation primitives are correct for this task.
- Change only Water `renderForVideoFrame()` fail-open branches.
- Unknown media time clears the AI canvas.
- No-bracket rendering may use only the closest earlier envelope within the existing 2000 ms tolerance.
- If that envelope is unavailable or too old, clear the canvas.
- Preserve Worker OFF clearing and Worker ON fresh-metadata behavior without reconnecting HLS.
- Do not alter detector, tracker, speed, passage, API/storage, Road, camera or network/security topology.

## Affected contours

- VPS frontend: REQUIRED — `frontend/sea-speed/index.html`.
- VPS API: NOT REQUIRED.
- Ubuntu Worker/relay: NOT REQUIRED.
- Road operator: protected / unchanged.
- Shared live-sync module: protected / unchanged for Task 1.
- Detection/tracking/speed/PassageEngine: protected / unchanged.
- nginx/Auth/MediaMTX/ZeroTier/camera topology: protected / unchanged.
- Tests and SDD 071: added inside authorized scope.

## Risk profile

- Risk profile: NOT REQUIRED

This is a bounded frontend reliability correction. It intentionally prefers temporary absence of AI boxes over displaying metadata known not to match the current HLS frame. No API, worker, security or topology mutation is introduced.

## Test design

- TEST-071-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: static contract proves raw-null media time clears canvas and does not draw latest buffer.
- TEST-071-002 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: static contract proves no-bracket path accepts only closest-earlier <=2000 ms and otherwise clears canvas; unmatched latest fallback is absent.
- TEST-071-003 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: static contract preserves shared bracket call, 500 ms interpolation gap and interpolation path.
- TEST-071-004 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: frontend contract proves one HLS constructor/media target and metadata-only Worker stop semantics.
- TEST-071-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact changed-file review and full repository Quality prove protected contours unchanged.
- TEST-071-006 | Covers: AC-007 | Level: runtime-manual | Priority: P0 | Evidence: exact-head CI, exact-main Quality, VPS runtime_verified and authenticated visual observation that moving-vessel boxes no longer jump to unmatched positions.

## Deployment transaction audit

- TX-071-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source or production mutation admitted | Retry: repair authorization/contract evidence then re-evaluate | Rollback: not required | Evidence: Issue #346 Task 1 authorization receipt.
- TX-071-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on prior accepted exact-main | Retry: after exact-main Quality and policy are green | Rollback: not required | Evidence: source protection, exact-main Quality and production-policy evidence.
- TX-071-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: deployment retains/restores prior accepted release | Retry: after exact failure diagnosis/prerequisites | Rollback: protected VPS rollback to `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a` | Evidence: VPS deployment log.
- TX-071-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate is not accepted as runtime-verified | Retry: re-verify after bounded remediation or rollback | Rollback: prior accepted exact release | Evidence: deployment manifest, health checks and authenticated Water visual acceptance.
- TX-071-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded as accepted | Retry: repeat only for same verified exact source | Rollback: restore previous current-release pointer | Evidence: deployment manifest/state evidence.
- TX-071-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime remains serving and cleanup warning is recorded | Retry: cleanup independently | Rollback: not required | Evidence: workflow cleanup/prune output.
- TX-071-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: delivery remains non-terminal | Retry: recollect exact evidence without source change | Rollback: not required | Evidence: Issue checkpoint, CI and deployment artifact.
- TX-071-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open and state is reported explicitly | Retry: after exact rollback failure diagnosis | Rollback: previous accepted exact-main | Evidence: protected rollback audit if invoked.

## Validation

- Validate SDD structure/linkage and Change Contract.
- Run `tests/test_water_live_sync_guard.py`, existing frontend contracts and repository tests required by current main.
- Verify exact source diff is limited to Water frontend, new Task 1 test and three SDD 071 files.
- Require exact-head Repository validation and `quality-integration` green.
- Fresh-read main/head/scope/reviews before exact-green-head merge.
- Require exact-main Quality before protected VPS deployment.
- Ubuntu Worker/relay deployment is NOT REQUIRED.
- Authenticated runtime acceptance: during normal moving-vessel playback, an unmatched envelope must result in a temporarily empty AI canvas rather than a visibly displaced bbox; HLS continuity remains unaffected.

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: #346 owns ordered Water runtime-quality work; only Task 1 is authorized in this delivery.
- Specification impact: SDD 071 admits fail-closed Water overlay matching only.
- Plan impact: fail-open latest-envelope rendering is replaced by bounded match-or-clear behavior.
- Tasks impact: T001-T007 track Task 1 from source through runtime acceptance.
- Authorization impact: `issue-346-task1-water-live-overlay-sync-v1` is authorized by the immediately-following `OUTCOME APPROVED` receipt.
- Follow-up: Task 2 unified speed semantics requires a separate six-field Scope and fresh authorization after Task 1 completion.

## Runtime feedback

- Water bbox displacement is the runtime defect addressed here.
- Task 2 speed semantics and Task 3 detector/ROI recall remain pending in #346 and are not admitted by this scope.
