# Feature Specification: Water live overlay sync correctness

- Feature: 071-water-live-overlay-sync-correctness
- Issue: #346
- Status: ACTIVE
- Owner outcome: Water AI boxes are rendered only when their metadata is temporally matched to the current HLS media time; unmatched metadata clears the canvas instead of drawing a confidently wrong box.
- Authorization: `issue-346-water-live-overlay-sync-task1-v1`, base `b1bb74eabb6af7e5d1c9ba59f77a33ad91aa6d9a`.

## Product outcome

`/sea-speed/` keeps the accepted single-HLS Water architecture and metadata-only AI canvas, but tightens the rendering fail-safe. The frontend may interpolate a valid same-generation bracket or use a bounded closest-earlier envelope, but it MUST NOT fall back to the newest buffered envelope when that envelope cannot be matched to the visible HLS media time. When media time is unavailable, metadata is stale/future/unmatched, or no valid bracket/near envelope exists, the AI canvas is cleared until synchronized evidence resumes.

## User scenarios

### Scenario 1 - Valid bracket

Given Water HLS is advancing and the live buffer contains same-generation envelopes bracketing the compensated media time, the frontend interpolates the matching detections and draws them over the corresponding video frame.

### Scenario 2 - Bounded earlier envelope

Given no interpolation bracket exists but a closest-earlier envelope is at most 2000 ms behind compensated media time, the frontend may draw that envelope as a bounded continuity fallback.

### Scenario 3 - Stale or future-only metadata

Given only stale metadata, only future metadata, or no envelope that can be mapped to the visible media time, the frontend clears `liveOverlayCanvas`. It does not draw the latest buffer item merely because a buffer item exists.

### Scenario 4 - Media timestamp unavailable

Given the browser cannot resolve current HLS media time, Water video continues independently but the AI canvas is cleared. The frontend does not infer alignment from arrival order alone.

### Scenario 5 - Worker lifecycle

Worker OFF clears metadata state while the same HLS video continues. Worker ON accepts only fresh envelopes and resumes synchronized drawing without HLS reconnect/source switch.

## Requirements

- R1: Water MUST retain exactly one HLS player attached to `waterMainVideo`.
- R2: `renderForVideoFrame()` MUST clear AI overlay when current media time is unavailable.
- R3: Valid same-generation brackets within the existing maximum interpolation gap MAY be interpolated and drawn.
- R4: Without a bracket, only a closest-earlier envelope with capture time in `[mediaTime-2000ms, mediaTime]` MAY be drawn.
- R5: The newest buffered envelope MUST NOT be used as an unconditional fallback for unmatched media time.
- R6: Metadata more than the existing gross desynchronization guard from current raw media time MUST clear the canvas.
- R7: Worker Start/Stop, Water speed/passages, detection/tracking, API/storage and media topology MUST remain unchanged.
- R8: Road frontend behavior MUST remain unchanged.

## Acceptance criteria

- AC-001: `raw==null` path clears Water live canvas and returns; it does not draw the latest envelope.
- AC-002: no-bracket path computes closest-earlier metadata and draws it only when capture time is no more than 2000 ms old and not later than compensated media time.
- AC-003: stale/future/unmatched metadata clears the canvas; there is no `else if(liveBuffer.length) draw latest` fallback in Water rendering.
- AC-004: valid `SeaSpeedLiveSync.bracketForMedia` interpolation remains active and unchanged in purpose.
- AC-005: Water remains one continuous HLS player and Worker lifecycle remains metadata-only.
- AC-006: Road, worker, API, speed/passages, detection/tracking and camera/MediaMTX/nginx/Auth/ZeroTier source are unchanged.
- AC-007: exact-head Repository validation + quality-integration, exact-green-head merge, exact-main Quality and protected VPS `runtime_verified` complete.
- AC-008: authenticated production observation confirms a moving vessel either has an aligned bbox or temporarily no bbox; known unmatched frames no longer show a box displaced beside the vessel.

## NFR assessment

- NFR-071-001 | Area: RELIABILITY | Target: prefer no AI box over a knowingly unmatched AI box | Validation: deterministic source contract plus production observation | Evidence: Water rendering guard and runtime acceptance | Status: CONCERNS
- NFR-071-002 | Area: COMPATIBILITY | Target: preserve one-HLS lifecycle, worker lifecycle and shared live-sync semantics | Validation: existing frontend contracts and exact diff | Evidence: CI and source review | Status: PASS
- NFR-071-003 | Area: PERFORMANCE | Target: no additional polling/decoder/render loop | Validation: source inspection | Evidence: existing SSE/poll/render loops reused | Status: PASS
- NFR-071-004 | Area: SECURITY | Target: no auth/API/topology change | Validation: exact changed-file scope | Evidence: PR diff and Quality | Status: PASS

## Runtime feedback

- Reported production symptom: Water bbox can appear beside a moving vessel while Road is visually stable.
- Root cause for Task 1: Water render fallback can draw the newest metadata envelope when no media-time match exists.
- Task 2 (canonical passage speed semantics) and Task 3 (Water detector/tracker recall) remain explicitly deferred within #346.
