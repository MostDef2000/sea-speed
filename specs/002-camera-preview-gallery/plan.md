# Implementation Plan: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Original Issue: #103
- Prior extension: #109
- Current Issue: #112
- Status: Accepted persistent last-good snapshot capability; browser security identity updated by Issue #115

## Architecture

The accepted live-preview contour remains:

```text
protected Ubuntu camera inventory
  -> source-on-demand private preview relay
     -> sanitized VPS catalog
        -> API start(camera_id)
           -> one managed VPS FFmpeg H.264 HLS session
              -> authenticated browser live preview under /sea-speed/**
```

Issue #112 added a VPS last-good snapshot contour that consumes only the already-managed local HLS session:

```text
browser confirms stable playback
  -> POST /api/cameras/{camera_id}/snapshot/commit?session_id=<active>
     -> validate catalog camera + exact active managed session
        -> FFmpeg extracts one JPEG from local HLS tail
           -> structural + luma-spread quality gate
              -> temporary dotfile
                 -> atomic os.replace(<camera_id>.jpg)
                    -> GET snapshot through API with no-store headers
```

At page load:

```text
GET /api/cameras
  -> safe snapshot metadata per camera
     -> <img> loads /api/cameras/{camera_id}/snapshot?v=<mtime_ns>
        -> no preview start
```

Camera 1 remains a separate clean-live media contour. Issue #115 changes only its browser-facing security identity:

```text
physical Camera 1
-> accepted Ubuntu relay
-> VPS Camera 1 H.264 compatibility service
-> nginx /sea-speed/media/cam1/
-> Authentik-protected browser
```

The historical `/cams/hls/cam1/` browser route is retired.

## Decisions

### D-001 - Durable VPS data, not browser persistence

Store last-good images under `/opt/sea-speed-api/data/camera-preview-snapshots/`. Browser `localStorage`, `sessionStorage`, IndexedDB and Cache API remain unused. Reload and other devices read the same VPS copy.

### D-002 - One file per camera, no history

The final path is `<camera_id>.jpg`. Successful updates atomically replace that file. No timestamped filenames, index of historical snapshots, database history, or recording timeline is introduced.

### D-003 - Commit from managed HLS, not from browser pixels

The browser never uploads image bytes. Snapshot commit takes only catalog `camera_id` plus public `session_id`, then the server resolves the exact current managed HLS directory from its own state. This avoids a general binary upload endpoint and prevents arbitrary filesystem/source selection.

### D-004 - Exact active-session binding

Snapshot commit is rejected unless the supplied camera and session exactly match `active_camera_preview_locked()`. This makes stale responses or cross-camera requests non-destructive.

### D-005 - Preserve prior last-good on any failure

Extraction and quality validation occur on a temporary candidate. The final JPEG is touched only after every check passes. Timeout, decode failure, too-small JPEG, malformed JPEG, or low luma spread leaves the prior final file unchanged.

### D-006 - Conservative non-AI quality gate

Use FFmpeg `signalstats` on the extracted JPEG and require a minimum percentile luma spread. The gate is deliberately simple and non-semantic: it rejects obvious near-uniform startup garbage without enabling AI or trying to classify scene content.

### D-007 - HLS-tail extraction

FFmpeg reads the active local playlist with `-live_start_index -1` and extracts one scaled JPEG. It does not connect to the private RTSP relay and therefore does not create a second camera source session.

### D-008 - No-store HTTP delivery with versioned URL

The catalog publishes a versioned snapshot URL using the final file mtime. The image endpoint sends `Cache-Control: no-store, max-age=0`. The VPS file is authoritative; a new successful commit changes the URL version and page state.

### D-009 - Preview All remains sequential

The browser retains the #109 media-time stability gate. After stable playback it asks the server to commit. Whether commit succeeds or is quality-rejected, the loop continues to the next camera. Server `max_active=1` is unchanged.

### D-010 - Manual preview uses the same commit endpoint

Before manual switch/stop, if the active browser video is decodable, the frontend attempts the same session-bound commit. Failure is isolated and preserves the prior server snapshot.

### D-011 - Auth v1 is a separate browser security migration

Issue #115 does not change the gallery API payloads, persistent store, source-on-demand relay or concurrency. It wraps browser-facing `/sea-speed/**` in Authentik, retires `/cams/**`, moves the separate Camera 1 clean-live path to `/sea-speed/media/cam1/`, and updates VPS code-deploy health so authenticated public health is not required to prove FastAPI is healthy.

## Affected contours

For the accepted Issue #112 capability:

- VPS API: additive snapshot metadata, GET, commit, extraction/quality/atomic-store helpers.
- Cameras frontend: persistent `<img>` snapshot rendering, update time, commit calls, removal of page-only canvas persistence.
- Durable data: `/opt/sea-speed-api/data/camera-preview-snapshots/`.
- Ubuntu preview relay, camera credentials/runtime inventory, AI/detection/tracking/recording and Objects Registry: unchanged.

For the separate Issue #115 security migration:

- browser authentication for `/sea-speed/**`: Authentik;
- Camera 1 browser identity: `/sea-speed/media/cam1/index.m3u8`;
- `/cams/**`: retired;
- VPS deploy health: loopback origin health + public auth smoke;
- snapshot storage/API semantics: unchanged.

## Validation

Repository/focused validation must continue to cover:

- Python syntax and existing preview/relay/deploy invariants;
- API snapshot routes and safe metadata;
- active session binding and no arbitrary path/source input;
- persistent path under `DATA_DIR`;
- temporary candidate + quality gate + atomic `os.replace` ordering;
- no-store JPEG response;
- frontend `<img>` persistence loaded from catalog metadata;
- no browser persistent storage APIs;
- sequential Preview All and media-time stability gate retained;
- Camera 1 media and Ubuntu relay behavior unchanged;
- after Issue #115, protected Camera 1 browser path and Authentik boundary are asserted rather than the retired `/cams/**` route;
- PR Validation and aggregate Quality integration success for the applicable task head.

## Rollout

Issue #112 rollout is historical and accepted. Issue #115 must use its own exact merged main SHA and separate production authorization.

For Auth v1 acceptance relevant to the gallery:

1. Prove Camera 1 media and existing gallery baseline before the security cutover.
2. Prove Authentik and the combined nginx candidate under Issue #115.
3. After cutover, anonymous `/sea-speed/cameras/**`, gallery API, preview HLS and snapshot endpoints are authentication-gated.
4. Authenticated gallery loads existing durable snapshots without starting preview.
5. Representative Preview/Preview All/Stop behavior remains serial and functional.
6. Camera 1 authenticated H.264 live remains healthy.
7. Existing snapshot files under `/opt/sea-speed-api/data/camera-preview-snapshots/` remain unchanged except by normal successful snapshot commits.

## Runtime feedback

- #103 established the accepted on-demand preview architecture and Camera 1 separation.
- #109 established sequential Preview All and exposed a visual limitation of page-only snapshot timing.
- #112 moved only the last-good image state to durable VPS data while keeping live preview topology and concurrency unchanged.
- #115 later changes only browser authentication/URL and deploy-health boundaries; it does not replace the accepted gallery snapshot architecture.
