# Implementation Plan: Water live overlay sync correctness

- Specification: `specs/071-water-live-overlay-sync-correctness/spec.md`
- Issue: #346
- Branch: `issue-346-water-sync`
- Authorization base main: `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a`
- Approved scope identity: `issue-346-water-live-overlay-sync-task1-v1`

## Architecture

The accepted Water architecture remains unchanged:

```text
protected Water HLS -> one Hls instance -> waterMainVideo
Water live metadata -> SSE/poll buffer -> timestamp match -> liveOverlayCanvas
```

Task 1 changes only the final rendering decision. A bbox is drawn only from a valid same-generation bracket or from a closest-earlier envelope whose capture time is within 2000 ms of compensated media time. If current media time is unavailable or no trustworthy envelope exists, the canvas is cleared. Video playback, worker control, passage/speed semantics and shared transport remain independent.

## Decisions

- Keep `frontend/sea-speed/live-sync.js` unchanged; its bracket and closest-earlier primitives remain valid.
- Add an explicit `LIVE_NEAR_MAX_AGE_MS=2000` bound in the Water page.
- Treat unresolved HLS media time as `clearLive(); return` rather than arrival-order fallback.
- Keep the existing gross desynchronization guard and bracket interpolation.
- In the no-bracket path, permit only closest-earlier metadata with capture time inside the explicit bounded window and never later than compensated media time.
- Remove all newest-buffer fallback drawing from Water `renderForVideoFrame()`.
- Update both the new Task 1 guard contract and the existing Water overlay-sync regression so historical tests no longer assert the retired newest-envelope fallback.
- Do not modify Road, worker, detection/tracking, speed/passages, API/storage, HLS topology or auth.

## Affected contours

- VPS frontend: REQUIRED — Water operator source only.
- VPS API: NOT REQUIRED.
- Ubuntu Worker/relay: NOT REQUIRED.
- Road operator: protected / unchanged.
- Water worker and passage/speed computation: protected / unchanged.
- nginx/Auth/MediaMTX/ZeroTier/Camera topology: protected / unchanged.

## Risk profile

- Risk profile: NOT REQUIRED

The change is a bounded frontend reliability correction. Failure mode intentionally becomes conservative: omit an AI box when temporal provenance is insufficient rather than show a wrong box. No persistence, schema, security, worker or media-source mutation is introduced.

## Test design

- TEST-071-001 | Covers: AC-001, AC-003 | Level: unit | Priority: P0 | Evidence: deterministic source contract proves unresolved media time and unmatched metadata clear the canvas and that newest-buffer fallback markers are absent.
- TEST-071-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: source contract and legacy Water sync regression prove closest-earlier envelope requires capture time within `[mediaTime-2000, mediaTime]`, future-only metadata clears, and >2s-old metadata clears.
- TEST-071-003 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: existing frontend contracts prove bracket interpolation, one-HLS lifecycle and metadata-only Worker control remain present.
- TEST-071-004 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: exact changed-file review and repository Quality prove protected contours are zero-diff.
- TEST-071-005 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality and protected VPS runtime_verified.
- TEST-071-006 | Covers: AC-008 | Level: runtime-manual | Priority: P0 | Evidence: authenticated production observation of moving Water vessels.

## Deployment transaction audit

- TX-071-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source or production mutation admitted | Retry: repair authorization/contract evidence then re-evaluate | Rollback: not required | Evidence: Issue #346 Task 1 authorization receipt.
- TX-071-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on prior accepted exact-main | Retry: after exact-main Quality and policy are green | Rollback: not required | Evidence: source protection, exact-main Quality, production-policy evidence.
- TX-071-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: deployment retains/restores prior accepted release | Retry: after exact failure diagnosis/prerequisites | Rollback: protected VPS rollback to `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a` | Evidence: VPS deployment log.
- TX-071-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate is not accepted as runtime-verified | Retry: re-verify after bounded remediation or rollback | Rollback: prior accepted exact release | Evidence: deployment manifest, health checks, authenticated Water observation.
- TX-071-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded as accepted | Retry: repeat only for same verified exact source | Rollback: restore previous current-release pointer | Evidence: deployment state evidence.
- TX-071-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime remains serving and cleanup warning is recorded | Retry: cleanup may be retried independently | Rollback: not required | Evidence: workflow cleanup/prune output.
- TX-071-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: delivery remains non-terminal | Retry: recollect exact evidence without source change | Rollback: not required | Evidence: Issue checkpoint, CI and deployment artifact.
- TX-071-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open and state is reported explicitly | Retry: after exact rollback failure diagnosis | Rollback: previous accepted exact-main | Evidence: protected rollback audit if invoked.

## Validation

- Validate SDD structure/linkage and Change Contract.
- Run `tests/test_water_live_sync_guard.py`, the existing `tests/test_water_overlay_sync.py`, and existing frontend/repository tests.
- Verify diff is limited to `frontend/sea-speed/index.html`, `tests/test_water_live_sync_guard.py`, `tests/test_water_overlay_sync.py` and SDD 071 files.
- Require exact-head Repository validation and `quality-integration` green.
- Fresh-read main/head/scope/reviews before exact-green-head merge.
- Require exact-main Quality before production deployment.
- Deploy protected VPS exact-main; Ubuntu Worker source deployment is NOT REQUIRED.
- Runtime acceptance: moving Water vessels never receive a knowingly unmatched bbox; temporary no-box is accepted when metadata cannot be matched.

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: #346 owns sequential Water runtime-quality work; this delivery is Task 1 only.
- Specification impact: SDD 071 admits frontend sync correctness only.
- Plan impact: no worker/media topology change; rendering becomes fail-safe on unmatched metadata.
- Tasks impact: T001-T007 track Task 1 through runtime acceptance.
- Authorization impact: `issue-346-water-live-overlay-sync-task1-v1` is authorized by the immediately-following `OUTCOME APPROVED` receipt; inclusion of the existing Water sync regression is within the approved "corresponding frontend/live-sync tests" test scope and does not widen runtime or protected boundaries.
- Follow-up: after Task 1 terminal acceptance, Task 2 receives a separate six-field Scope/authorization.

## Runtime feedback

- Current production issue: displaced Water bbox can occur when the renderer falls back to latest buffered metadata without a media-time match.
- Desired conservative behavior: aligned bbox or no bbox.
- Task 2 speed semantics and Task 3 recall are deferred.
