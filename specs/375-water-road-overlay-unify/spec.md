# Spec: Unify Water/Road live-overlay contour rendering

- Issue: #375
- Status: ACTIVE
- Specification: specs/375-water-road-overlay-unify/spec.md
- Runtime contour: VPS (frontend served by nginx); Ubuntu Worker/relay NOT required

## Product outcome

Unify the duplicated live-contour (bounding-box + label) rendering for Water (cam1)
and Road (road1) into one shared frontend module, and fix Water showing no contours
during playback while keeping Road stable.

## User scenarios

- Operator opens Water view: green contours with class/track/speed labels track
  vessels on the live HLS frame, regardless of whether the HLS stream carries
  `#EXT-X-PROGRAM-DATE-TIME`.
- Operator opens Road view: behaviour unchanged (contours already stable).
- A single module (`overlay-canvas.js`) owns the rendering math, buffer, SSE/poll
  ingestion and fallback for both cameras; water/road pages only pass camera-specific
  ids/urls.

## Requirements

- R1: Extract shared live-overlay renderer into `frontend/sea-speed/overlay-canvas.js`
  with `SeaSpeedOverlayCanvas.init({cameraId, videoId, canvasId, wrapId, liveUrl,
  livePollUrl, isWater})`.
- R2: Fix vertical centering — `contentRect` must use `(r.height-ch)/2` (Water copy
  had a `/h` typo pushing contours to the top edge).
- R3: Robust fallback — when `getMediaMs()` is null (no HLS wall-clock), draw the most
  recent buffered envelope instead of clearing the canvas every frame.
- R4: Both pages wire `overlay.setWorkerActive(active)` into their worker-control
  handler; no duplicate EventSource / render loop.
- R5: No regression to Road; worker inference and API live endpoints untouched.

## NFR assessment

- NFR-375-001 | Area: correctness | Target: contour vertical centering ±1px content-box | Validation: unit/contract test on contentRect + grep for removed `/h` typo | Evidence: overlay-canvas.js, tests/test_frontend_contract.py | Status: PASS
- NFR-375-002 | Area: reliability | Target: contours visible without HLS PROGRAM-DATE-TIME | Validation: fallback path draws latest envelope when getMediaMs null | Evidence: overlay-canvas.js renderForVideoFrame | Status: PASS
- NFR-375-003 | Area: maintainability | Target: single source for water+road overlay | Validation: both pages call SeaSpeedOverlayCanvas.init; inline IIFEs removed | Evidence: index.html, road/index.html | Status: PASS

## Acceptance criteria

- AC-001: Water and Road live canvases draw green contours with class/track/speed
  labels during playback.
- AC-002: `contentRect` centers vertically (`/2`); no `(r.height-ch)/h` typo remains.
- AC-003: Without HLS wall-clock, Water still shows contours (latest envelope).
- AC-004: Road behaviour unchanged; no duplicate EventSource/render loop.

## Runtime feedback

- Prior duplicated code: Water `contentRect` used `y:(r.height-ch)/h` (misaligned);
  both pages lacked a no-wall-clock fallback, so Water (stream without
  PROGRAM-DATE-TIME) cleared the canvas every frame → no visible contours, while
  Road (stream with wall-clock) worked.
