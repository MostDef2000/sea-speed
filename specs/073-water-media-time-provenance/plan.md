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

- Risk profile: REQUIRED
- RISK-073-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: relative mapping uses only bounded player latency and existing metadata timestamps; no arbitrary newest draw | Validation: deterministic clock-offset invariance + runtime vessel observation | Residual risk: 2 | Owner: frontend | Status: MITIGATED.
- RISK-073-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: hls.js latency preferred, native seekable latency fallback, invalid/out-of-range values fail closed | Validation: source contract + unit tests | Residual risk: 1 | Owner: frontend | Status: MITIGATED.
- RISK-073-003 | Category: COMPATIBILITY | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: Water-specific buffer gate; Road code untouched | Validation: existing Road/live-sync regression suite and exact diff | Residual risk: 1 | Owner: frontend | Status: MITIGATED.
- RISK-073-004 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: actual runtime narrowed to VPS-only; prior exact release is rollback target | Validation: protected deployment/runtime_verified | Residual risk: 1 | Owner: delivery | Status: MITIGATED.

## Test design

- TEST-073-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: synthetic Water buffer plus 500ms latency resolves 10.1s target and 50% bracket interpolation.
- TEST-073-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: add one-day offset to every Worker timestamp; selected IDs/fraction stay identical.
- TEST-073-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: missing/negative/>30s latency returns no relative target.
- TEST-073-004 | Covers: AC-004 | Level: contract | Priority: P0 | Evidence: Water instance media-time probe preserves native date or returns invalid sentinel; selector rejects non-finite absolute time and may use relative target.
- TEST-073-005 | Covers: AC-005 | Level: contract | Priority: P0 | Evidence: latest-buffer draw remains absent and bounded closest-earlier markers remain.
- TEST-073-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: Road file zero-diff plus existing Road/live-sync tests.
- TEST-073-007 | Covers: AC-007 | Level: end-to-end | Priority: P0 | Evidence: exact-head CI, exact-main Quality, protected VPS runtime_verified.
- TEST-073-008 | Covers: AC-008 | Level: runtime-manual | Priority: P0 | Evidence: authenticated Water observation with positive detections/tracks and visible aligned moving bbox.

## Deployment transaction audit

- Adjacent-stage review: COMPLETE.
- TX-073-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure: FATAL | State: no mutation | Retry: after authorization/contract repair | Evidence: #346 Task 1B OUTCOME APPROVED receipt.
- TX-073-PRE | Stage: PRE-MUTATION | Mutation: NO | Failure: FATAL | State: production remains `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e` | Retry: exact-head/main quality green | Evidence: protected source + Quality.
- TX-073-MUTATION | Stage: MUTATION | Mutation: YES | Failure: FATAL | State: prior VPS release remains/restored | Retry: bounded diagnosis | Rollback: `4ed8c5e39c7d1e5fe5c9bf1fbd84bb87835e835e` | Evidence: VPS deploy log.
- TX-073-VERIFY | Stage: VERIFICATION | Mutation: NO | Failure: FATAL | State: candidate not accepted | Retry: verify/remediate/rollback | Evidence: deployment manifest + authenticated browser.
- TX-073-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure: FATAL | State: candidate not recorded accepted | Retry: same exact verified source | Evidence: deployment state.
- TX-073-HOUSE | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure: BEST-EFFORT | State: serving runtime retained | Retry: independent cleanup | Evidence: deploy cleanup output.
- TX-073-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure: FATAL | State: task non-terminal | Retry: recollect exact evidence | Evidence: CI/deploy artifact/Issue checkpoint.
- TX-073-ROLLBACK | Stage: ROLLBACK | Mutation: YES | Failure: FATAL | State: incident remains open | Retry: after diagnosis | Evidence: rollback audit if invoked.

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

- Trigger: PRODUCTION_LEARNING.
- Previous remediation still showed `AI active`, `DETECTIONS=3`, `TRACKS=3` with no bbox.
- Root cause refinement: absolute-media-time availability/semantics are not a valid prerequisite for Water overlay because metadata timestamps are explicitly Worker receive time.
- Scope impact: implementation narrows from authorized MIXED ceiling to VPS-only; no protected boundary expansion.
- Authorization impact: NONE; all source changes are inside the approved Task 1B frontend/test/SDD paths.
- Task 2 remains blocked until Task 1 browser acceptance passes.
