# Implementation Plan: Road operator Water-interface parity

- Specification: `specs/070-road-water-interface-parity/spec.md`
- Issue: #343
- Branch: `issue-343-road-water-interface-parity`
- Authorization base main: `01eec30cf162b922fc076dd5545ae8a2b114df4e`
- Approved scope identity: `issue-343-road-water-interface-parity-v1`

## Architecture

The change remains inside the authenticated Road frontend. Road keeps its existing preview-start API and `road1` analytics/control endpoints but adopts the Water visual hierarchy and one-player media architecture:

```text
POST /sea-speed/api/cameras/road1/preview/start
        -> protected Road HLS URL
        -> one Hls instance
        -> roadMainVideo
        -> liveOverlayCanvas (Road AI metadata only)
```

Road Worker control remains fixed to `/sea-speed/api/worker/control/road1`. Worker OFF does not affect HLS; it clears Road live AI buffer/canvas state. Worker ON does not reconnect HLS; fresh SSE/poll metadata is synchronized over the already-playing video. `frontend/sea-speed/live-sync.js` is unchanged.

## Decisions

- Replace the historical three-column Road layout with the current two-column Water dashboard composition.
- Remove the separate `LIVE CAMERA / Чистый поток` card and `cleanPreviewVideo` pipeline completely.
- Use `<video id="roadMainVideo">` as the sole Road media element and HLS target.
- Keep exactly one Hls.js object and bind playback progress/watchdog/recovery to `roadMainVideo`.
- Preserve Road preview start/stop API semantics and automatic startup/retry behavior.
- Road Worker Start/Stop never calls stream connect/disconnect or replaces HLS media.
- Clear Road live metadata buffer/canvas on worker inactive state and reject stale envelopes while stopped.
- Poll Road state/events as before, but only use `last_overlay_url` as a changed-URL fallback while HLS is unhealthy.
- Move existing Road ROI, speed lines, counting line, calibration and diagnostics into one default-closed control area below the camera.
- Render Road crossing totals/class breakdown from existing Road state in a dedicated right card; keep up to three Road events in a separate card.
- Keep Water/API/worker/live-sync/media topology unchanged.

## Affected contours

- VPS frontend: REQUIRED — `frontend/sea-speed/road/index.html` only.
- VPS API: NOT REQUIRED.
- Ubuntu Worker/relay: NOT REQUIRED.
- Water operator: protected / unchanged.
- nginx/Auth/MediaMTX/ZeroTier/Camera/FFmpeg topology: protected / unchanged.
- Frontend contract and new SDD 070: updated inside authorized scope.

## Risk profile

- Risk profile: NOT REQUIRED

The source change is a bounded VPS frontend composition/reliability change. It does not change API schemas, worker source, security boundaries, migrations or production media topology. Runtime deployment still uses the protected exact-main VPS transaction.

## Test design

- TEST-070-001 | Covers: AC-001, AC-007, AC-008 | Level: unit | Priority: P0 | Evidence: static frontend contract verifies Water-parity layout, default-collapsed control area, independent Road crossing/events cards and required IDs.
- TEST-070-002 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: static contract proves exactly one Road video/HLS constructor and sole attach target `roadMainVideo`.
- TEST-070-003 | Covers: AC-004 | Level: runtime-manual | Priority: P0 | Evidence: authenticated production Road Worker OFF->ON->OFF observation proves overlay clear/resume while the same video advances continuously.
- TEST-070-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: static contract proves healthy-playback guard and cached fallback URL around `last_overlay_url`.
- TEST-070-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: fixed Road endpoint constants, exact changed-file review and full repository Quality.
- TEST-070-006 | Covers: AC-009 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, VPS runtime_verified and authenticated Road continuity/visual acceptance.

## Deployment transaction audit

- TX-070-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source or production mutation admitted | Retry: repair authorization/contract evidence then re-evaluate | Rollback: not required | Evidence: Issue #343 authorization receipt.
- TX-070-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on prior accepted exact-main | Retry: after exact-main Quality and policy are green | Rollback: not required | Evidence: source protection, exact-main Quality, production-policy evidence.
- TX-070-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: deployment retains/restores prior accepted release | Retry: after exact failure diagnosis/prerequisites | Rollback: protected VPS rollback to prior accepted exact-main | Evidence: VPS deployment log.
- TX-070-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate is not accepted as runtime-verified | Retry: re-verify after bounded remediation or rollback | Rollback: prior accepted exact release | Evidence: deployment manifest, health checks, authenticated Road continuity acceptance.
- TX-070-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded as accepted | Retry: repeat only for same verified exact source | Rollback: restore previous current-release pointer | Evidence: deployment manifest/state evidence.
- TX-070-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: accepted runtime remains serving and cleanup warning is recorded | Retry: cleanup may be retried independently | Rollback: not required | Evidence: workflow cleanup/prune output.
- TX-070-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: delivery remains non-terminal | Retry: recollect exact evidence without source change | Rollback: not required | Evidence: Issue checkpoint, CI and deployment artifact.
- TX-070-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open and state is reported explicitly | Retry: after exact rollback failure diagnosis | Rollback: previous accepted exact-main | Evidence: protected rollback audit if invoked.

## Validation

- Validate SDD structure/linkage and Change Contract.
- Run `tests/test_frontend_contract.py` and repository tests required by current main.
- Verify diff is limited to Road frontend, frontend contract and three SDD 070 files.
- Require exact-head Repository validation and `quality-integration` green.
- Fresh-read main/head/scope/reviews before exact-green-head merge.
- Require exact-main Quality before production deployment.
- Deploy protected VPS exact-main; Ubuntu Worker source deployment is not part of this change.
- Runtime acceptance: Road video advances continuously through Worker OFF->ON->OFF, AI canvas clears/resumes, and Road visually matches the accepted Water hierarchy on desktop/mobile.

## Correct-course check

- Trigger: MATERIAL_SCOPE_CHANGE
- Issue impact: new canonical Issue #343 owns Road parity.
- Specification impact: SDD 070 admits Road visual parity and single-HLS lifecycle.
- Plan impact: historical Road clean-preview/two-player layout is replaced by Water-parity composition and one-player lifecycle.
- Tasks impact: T001-T010 track source through production acceptance.
- Authorization impact: `issue-343-road-water-interface-parity-v1` is authorized by the immediately-following `OUTCOME APPROVED` receipt.
- Follow-up: exact-head CI, merge, exact-main Quality, protected VPS deployment and authenticated Road continuity/visual evidence.

## Runtime feedback

- Water reference: accepted production baseline.
- Road parity: pending production acceptance.
- CPU/transcoding topology: explicitly outside #343.
