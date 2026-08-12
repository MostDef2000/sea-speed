# Implementation Plan: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Original Issue: #103
- Prior extension: #109
- Current Issue: #112
- Status: Persistent last-good snapshot implementation under Outcome Authorization

## Architecture

The accepted live-preview contour stays unchanged:

```text
protected Ubuntu camera inventory
  -> source-on-demand private preview relay
     -> sanitized VPS catalog
        -> API start(camera_id)
           -> one managed VPS FFmpeg H.264 HLS session
              -> browser live preview
```

Issue #112 adds a VPS last-good snapshot contour that consumes only the already-managed local HLS session:

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

The accepted Camera 1 path remains a separate contour:

```text
physical Camera 1 -> accepted Ubuntu relay -> VPS Camera 1 compatibility service
-> nginx /cams/hls/cam1/ -> browser
```

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

## Affected contours

- VPS API: additive snapshot metadata, GET, commit, extraction/quality/atomic-store helpers.
- Cameras frontend: persistent `<img>` snapshot rendering, update time, commit calls, removal of page-only canvas persistence.
- SDD/tests: updated for Issue #112.
- VPS deploy script: unchanged.
- nginx: unchanged.
- Ubuntu preview relay: unchanged.
- camera credentials/runtime inventory: unchanged.
- Camera 1 path: unchanged.
- AI/detection/tracking/recording: unchanged.
- Objects Registry: unchanged.

## Validation

Repository/focused validation must cover:

- Python syntax and existing preview/relay/deploy invariants;
- exact seven-file source scope;
- API snapshot routes and safe metadata;
- active session binding and no arbitrary path/source input;
- persistent path under `DATA_DIR`;
- temporary candidate + quality gate + atomic `os.replace` ordering;
- no-store JPEG response;
- frontend `<img>` persistence loaded from catalog metadata;
- no browser persistent storage APIs;
- sequential Preview All and media-time stability gate retained;
- Camera 1 and Ubuntu relay markers unchanged;
- PR Validation and aggregate Quality integration success.

## Rollout

1. Implement exact seven-file source change under Issue #112 Outcome Authorization.
2. Open bounded PR linked to `specs/002-camera-preview-gallery/spec.md`.
3. Remediate CI only inside the approved seven-file scope.
4. Merge exact green head without a separate merge token while the Outcome Authorization remains valid.
5. Obtain a fresh production safety envelope for the exact merged main SHA.
6. VPS-only exact deployment using existing restart/smoke and separately authorized safe rollback.
7. Runtime acceptance:
   - Camera 1 healthy before;
   - existing accepted preview/catalog baseline healthy;
   - initial page load starts no preview;
   - commit at least two representative good cameras;
   - verify final JPEGs exist under durable data and API metadata reflects them;
   - verify reload preserves images and a second browser/device sees the same images;
   - verify stale session and a rejected candidate do not replace an existing good JPEG;
   - verify Preview All remains serial and final preview is idle;
   - Camera 1 healthy after;
   - Ubuntu relay and AI unchanged.

## Runtime feedback

- #103 established the accepted on-demand preview architecture and Camera 1 separation.
- #109 established sequential Preview All and exposed a visual limitation of page-only snapshot timing.
- #112 deliberately moves only the last-good image state to durable VPS data while keeping live preview topology and concurrency unchanged.
