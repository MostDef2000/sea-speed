# Implementation Plan: Water media-time provenance

- Specification: `specs/073-water-media-time-provenance/spec.md`
- Issue: #346
- Branch: `issue-346-water-media-time-provenance`
- Authorization base main: `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e`
- Scope: Task 1B authorized ceiling MIXED; implementation narrowed to VPS-only because no Worker mutation is required.

## Architecture

Accepted data flow remains:

```text
Camera -> relay/HLS -> one browser HLS player
Camera -> Water Worker -> normalized bbox metadata -> API -> Water live buffer
```

The Worker envelope truthfully retains `timestamp_semantics=worker_receive_utc`. The browser no longer requires that timestamp to equal HLS Program Date Time. For Water only, shared sync math obtains playback distance from the HLS live edge and projects it onto the metadata timeline:

```text
newest Worker capture timestamp - current HLS playback latency = target Worker capture timestamp
```

The existing same-generation bracket then interpolates around that target. `hls.latency` is preferred and `video.seekable.end(last)-video.currentTime` is the bounded native fallback. If neither yields a finite value in `[0,30s]`, resolution fails closed. Road does not enter this Water-specific branch.

The Water page's existing `getMediaMs()` can return early if optional `getStartDate()` is absent. Since the selector now supports a relative target that does not require absolute media time, `live-sync.js` installs an instance-local compatibility probe on `waterMainVideo`: it preserves a native start date when available and otherwise returns an invalid-Date sentinel. This allows control to reach the selector; the sentinel itself is never used as a target because the shared resolver rejects non-finite absolute media time.

## Decisions

- Do not modify Worker source: `worker_receive_utc` remains honest telemetry, not fabricated camera PTS.
- Do not add or change API fields.
- Prefer relative HLS live-edge latency for Water buffer targeting.
- Bound accepted playback latency to 30 seconds; outside that range fail closed.
- Preserve Road absolute-media-time selection exactly by gating relative mapping on Water envelope identity (`camera_id=cam1`, non-road domain).
- Preserve same-generation interpolation and existing maximum gap.
- Preserve the explicit no-unconditional-latest contract.
- No additional polling/render loops.
- Narrow actual deployment from authorized MIXED ceiling to VPS-only because the source fix is entirely within shared frontend live-sync math and Water tests.

## Affected contours

- VPS frontend: REQUIRED (`frontend/sea-speed/live-sync.js`).
- Ubuntu Worker: NOT REQUIRED; zero source diff.
- VPS API: NOT REQUIRED.
- Road: shared module loaded, but Water-only branch is data-gated and Road regression remains required.
- Detection/tracking/ROI/speed/passages: protected / unchanged.
- MediaMTX/nginx/Auth/ZeroTier/camera topology: protected / unchanged.

## Risk profile

- Risk profile: NOT REQUIRED

The derived Change Contract impact is VPS-only with no security, schema, destructive, detection/speed-formula, or other high-risk trigger. Production-learning concerns are still covered explicitly by the test design, deployment transaction audit, rollback target, and authenticated runtime acceptance rather than by policy `RISK-*` records.

## Test design

- TEST-073-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: synthetic Water buffer plus 500ms latency resolves 10.1s target and 50% bracket interpolation
- TEST-073-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: add one-day offset to every Worker timestamp; selected IDs/fraction stay identical
- TEST-073-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: missing/negative/>30s latency returns no relative target
- TEST-073-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: Water instance media-time probe preserves native date or returns invalid sentinel; selector rejects non-finite absolute time and may use relative target
- TEST-073-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: latest-buffer draw remains absent and bounded closest-earlier markers remain
- TEST-073-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: Road file zero-diff plus existing Road/live-sync tests
- TEST-073-007 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, protected VPS runtime_verified
- TEST-073-008 | Covers: AC-008 | Level: runtime-manual | Priority: P0 | Evidence: authenticated Water observation with positive detections/tracks and visible aligned moving bbox

## Deployment transaction audit

- Adjacent-stage review: COMPLETE
- Production-learning root cause: Water metadata is timestamped in Worker receive UTC while the frontend depended on browser HLS absolute media time being available and semantically comparable; positive detections could therefore be rejected before rendering.
- Production-learning adjacent-stage findings: detector/tracker, API ingress, HLS health, source protection, CI, deployment and runtime verification remained healthy; the failure was isolated to frontend temporal selection and was visible only in authenticated product acceptance.
- TX-073-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source or production mutation admitted | Retry: repair authorization or contract evidence and re-evaluate | Rollback: not required because no mutation occurred | Evidence: Issue #346 Task 1B OUTCOME APPROVED receipt
- TX-073-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: production remains on `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e` | Retry: after exact-head and exact-main quality gates are green | Rollback: not required because production is unchanged | Evidence: protected source and exact Quality evidence
- TX-073-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior VPS release remains or is restored | Retry: after bounded deployment diagnosis | Rollback: deploy `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e` | Evidence: protected VPS deployment log
- TX-073-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: verify after remediation or rollback | Rollback: restore prior exact VPS release if runtime is degraded | Evidence: deployment manifest and authenticated browser acceptance
- TX-073-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: candidate must not be recorded as accepted | Retry: repeat state commit only for the same verified exact source | Rollback: restore previous current-release pointer | Evidence: deployment runtime state
- TX-073-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: serving verified runtime remains active and cleanup warning is recorded | Retry: cleanup independently | Rollback: not required for housekeeping-only failure | Evidence: deployment cleanup output
- TX-073-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: delivery remains non-terminal | Retry: recollect exact evidence without source change | Rollback: not required unless verification itself failed | Evidence: CI, deployment artifact and Issue checkpoint
- TX-073-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: incident remains open and runtime state is reported explicitly | Retry: after exact rollback failure diagnosis | Rollback: previous accepted exact-main release | Evidence: protected rollback audit if invoked

## Validation

- Validate SDD structure and PR Change Contract.
- Run `tests/test_water_live_sync_guard.py` and `tests/test_water_overlay_sync.py` plus full repository suite through CI.
- Verify changed source is frontend live-sync only; Water Worker and Road page are zero-diff.
- Require exact-head Repository validation and quality-integration.
- Merge exact green head only after fresh base/head/scope review.
- Require exact-main Quality.
- Deploy VPS exact-main; Ubuntu Worker deployment NOT REQUIRED after narrowed implementation.
- Require `runtime_verified` and authenticated moving-vessel acceptance before Task 1 is terminal.

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: #346 Task 1 remains open because authenticated production acceptance still has positive detections with no bbox.
- Specification impact: refine temporal provenance from absolute cross-clock comparison to Water relative live-edge mapping without changing the product outcome.
- Plan impact: narrow implementation to frontend-only VPS deployment and preserve Worker/Road/API protected contours.
- Tasks impact: add deterministic relative-timeline and clock-offset regressions, then repeat exact delivery/runtime acceptance gates.
- Authorization impact: no expansion beyond the approved Task 1B ceiling; implementation is narrower than authorized.
- Follow-up: complete authenticated Water bbox acceptance before starting Task 2 unified speed semantics.

## Runtime feedback

- Production `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e` is runtime_verified and HLS advances, but authenticated UI shows `AI active`, `DETECTIONS=3`, `TRACKS=3` with no bbox.
- This falsified the prior assumption that bounded absolute timestamp lookup alone was sufficient and refined the root cause to incompatible/optional absolute media-time provenance.
- Expected post-deploy evidence is a visible aligned bbox for positive detections while no-match cases remain fail-closed.
