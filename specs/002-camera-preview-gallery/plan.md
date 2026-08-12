# Implementation Plan: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Original Issue: #103
- Extension Issue: #109
- Status: Approved extension implementation

## Architecture

Original runtime contour remains unchanged:

```text
protected Ubuntu camera inventory
  -> dedicated MediaMTX preview relay on private ZeroTier address
     -> one source-on-demand path per camera candidate
        -> sanitized VPS catalog with credential-free relay URLs
           -> Sea Speed API validates catalog camera_id
              -> one temporary VPS FFmpeg process at a time
                 -> reduced H.264 / no-audio HLS under /sea-speed/media/camera-preview/
                    -> /sea-speed/cameras/ active card
```

Issue #109 adds browser-only orchestration above the existing one-active-preview API:

```text
Preview All button
  -> sequential catalog iterator
     -> existing start(camera_id)
        -> existing one active HLS preview
           -> wait for decodable browser frame
              -> canvas.drawImage(video)
                 -> stop/replace preview
                    -> next camera

Stop All
  -> invalidate batch generation
  -> existing preview stop endpoint
  -> retained canvases stay on current page only
```

The accepted Camera 1 production path is a separate contour and is not modified:

```text
physical Camera 1 -> accepted Ubuntu relay -> VPS Camera 1 H.264 compatibility service
-> exact nginx /cams/hls/cam1/ route -> browser
```

## Decisions

### D-001 - On-demand instead of a permanent camera wall

Keep zero preview processes at rest and one temporary VPS transcode only when selected. Issue #109 does not introduce a multi-stream wall.

### D-002 - Dedicated Ubuntu preview relay contour

The existing standalone source-on-demand preview relay remains unchanged. Issue #109 does not require Ubuntu mutation.

### D-003 - Credentials stay on Ubuntu

Native camera credentials remain protected on Ubuntu. The browser continues to operate only on sanitized camera identities and HLS URLs.

### D-004 - Browser normalization remains on the VPS

Existing VPS FFmpeg continues to normalize the selected source to reduced H.264 HLS. No additional codec pipeline is introduced.

### D-005 - One active preview plus hard TTL

The existing API lock, replacement semantics and bounded TTL remain unchanged. Sequential batch mode deliberately reuses this constraint rather than increasing concurrency.

### D-006 - Runtime catalog rather than committed LAN inventory

Preview All iterates only the already-sanitized catalog returned by `/api/cameras`; no LAN inventory is embedded in frontend source.

### D-007 - Exact VPS artifact covers the Cameras page

The existing exact-artifact requirement for `frontend/sea-speed/cameras/index.html` remains in force.

### D-008 - Sequential preview-all instead of parallel fan-out

- Decision: batch identification runs one catalog entry at a time through the existing start endpoint.
- Reason: this preserves `max_active=1`, caps VPS CPU/relay load at the already accepted envelope, and avoids opening dozens of camera sessions simultaneously.
- Rejected: `Promise.all` or server changes that allow many concurrent FFmpeg preview processes.

### D-009 - Last frame is volatile DOM presentation state

- Decision: capture the latest successfully decoded `<video>` frame into a `<canvas>` in that same camera card before switch/stop.
- Reason: the operator needs a visual contact sheet only while identifying cameras; persistence would add storage lifecycle, privacy and cleanup complexity without product value.
- Persistence explicitly rejected: `localStorage`, `sessionStorage`, IndexedDB, Cache API, server snapshot files and database rows.
- Reload/close is the cleanup mechanism for retained frames.

### D-010 - Keep card DOM stable while frames are retained

- Decision: render the camera-card structure once after catalog load and update state/classes/player elements without rebuilding the whole grid on every preview transition.
- Reason: canvas pixels are DOM-resident volatile state and would be lost by repeated `innerHTML` replacement.

### D-011 - Batch cancellation uses generation invalidation

- Decision: each Preview All pass receives a generation token. Stop All increments the generation and calls the existing stop endpoint.
- Reason: a camera start request can already have reached the server when the user cancels. A late response from an invalidated generation must issue stop and must not continue traversal.
- This is browser orchestration only; no backend cancellation protocol is added.

### D-012 - Failure is per camera

- Decision: start/playback readiness failure is recorded on that card and iteration continues.
- Reason: identification of the remaining catalog should not depend on one offline or misconfigured candidate.

## Frontend state model

Volatile variables only:

- `cameras`: sanitized catalog for the current page;
- `active`: current public preview state;
- `activeVideo` / `activeHls`: current live browser player;
- `snapshotIds`: identities whose card canvas currently contains a captured frame;
- `cameraErrors`: per-card transient errors;
- `batchRunning`, `batchGeneration`, `batchIndex`: batch control/progress.

No retained-frame bytes are serialized into storage.

## Batch algorithm

1. User presses `Предпросмотр всех`.
2. Mark batch active and allocate a new generation token.
3. For each catalog camera in order:
   - update progress/current-camera label;
   - start that camera through the existing API;
   - if the generation became stale, stop any late-started preview and return;
   - attach HLS player;
   - wait bounded time for a decodable video frame;
   - if successful, allow a short dwell then draw the current frame into that card canvas;
   - if unsuccessful, show local error and continue.
4. On normal completion call the existing stop endpoint for the final server preview.
5. Leave all successful card canvases visible.

## Manual preview behavior

Manual Play/Switch/Stop uses the same `captureActiveFrame()` path. If the browser has a decodable frame, it is retained before the live player is destroyed. If no frame exists, the prior retained canvas (if any) is not fabricated or overwritten.

## Affected contours

- VPS frontend: changed.
- VPS API: unchanged.
- VPS deployment script: unchanged; it already installs/smokes the Cameras page.
- Ubuntu preview relay: unchanged.
- Windows worker: unchanged.
- Camera 1 accepted live path: unchanged.
- AI/detection/tracking: unchanged.

Production impact derives as `VPS` because `frontend/**` changes. Production rollout remains separately authorized after exact-green source merge.

## Validation

- Focused static tests assert global batch controls, sequential iteration markers, generation cancellation, volatile canvas capture and forbidden persistent browser storage APIs.
- Existing tests continue to assert one-active backend policy, credential safety, source-on-demand relay separation, Camera 1 stability markers and deployment integration.
- Required PR Validation and `Quality integration gate / quality-integration` must pass for the exact PR head.
- Exact diff must remain the approved six Issue #109 files.

## Rollout

1. Complete exact six-file source implementation under the recorded Outcome Authorization.
2. Open bounded PR linked to Issue #109 and this specification.
3. Remediate CI only inside the approved outcome/scope.
4. Merge the exact green head without a separate merge token while Outcome Authorization remains valid.
5. Obtain a separate production safety-envelope authorization for the exact merged main commit.
6. Deploy only the VPS frontend release contour using existing exact release/deploy controls; no Ubuntu mutation.
7. Runtime acceptance:
   - Camera 1 baseline healthy before;
   - idle Cameras page starts no preview;
   - Preview All visibly progresses across representative cameras and leaves last frames;
   - at least one failed/unusable camera does not abort later cameras when such a candidate is available;
   - Stop All stops current preview and prevents further batch starts;
   - manual switch/stop retains prior frame;
   - reload clears retained frames;
   - backend reports no active preview after normal batch completion/Stop All;
   - Camera 1 healthy after.

## Rollback

Use the existing exact VPS release rollback mechanism if separately authorized in the production safety envelope. No Ubuntu rollback is applicable because Ubuntu source/config is unchanged.

## Runtime feedback

- 2026-08-12: Original gallery and HLS permission remediation were accepted in production on exact main with representative cam18/cam20 start/switch/stop and visible moving-video confirmation.
- Issue #109 is intentionally a frontend-only identification workflow layered over that accepted runtime contour.
