# Tasks: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Plan: specs/002-camera-preview-gallery/plan.md
- Original Issue: #103
- Prior extension: #109
- Current Issue: #112
- Status: Accepted persistent last-good snapshot capability; browser security identity updated by Issue #115

## Delivery tasks

### Accepted foundation

- [x] T001 Deliver on-demand Camera Preview Gallery from sanitized runtime catalog.
- [x] T002 Preserve Camera 1 accepted media behavior and AI independence. The original public browser path was later superseded explicitly by Issue #115.
- [x] T003 Enforce one active preview with bounded TTL and credential-free private relay input.
- [x] T004 Deliver sequential Preview All and Stop All controls under #109.
- [x] T005 Add browser media-time progression gate after visual finding that startup frames may be incomplete.

### Issue #112 - Persistent VPS last-good snapshots

- [x] T112-01 Record Outcome Contract and exact seven-file scope in canonical Issue #112.
- [x] T112-02 Create fresh branch from exact main with no production mutation.
- [x] T112-03 Add durable snapshot directory under `DATA_DIR / camera-preview-snapshots`.
- [x] T112-04 Add safe per-camera snapshot metadata to `/api/cameras` without exposing relay source data.
- [x] T112-05 Add catalog-bound JPEG GET endpoint with no-store response headers.
- [x] T112-06 Add catalog + exact active-session-bound snapshot commit endpoint.
- [x] T112-07 Extract one JPEG from the managed local HLS tail without opening another RTSP source.
- [x] T112-08 Validate candidate structure/size and conservative luma spread using non-AI FFmpeg signal statistics.
- [x] T112-09 Preserve the prior final JPEG on every extraction/validation/session failure.
- [x] T112-10 Atomically replace only `<camera_id>.jpg` after a successful quality gate; create no history/archive.
- [x] T112-11 Replace page-only snapshot canvas with server snapshot `<img>` rendering and visible update time.
- [x] T112-12 Make page load/reload consume existing VPS snapshots without starting previews.
- [x] T112-13 Make Preview All commit the active session only after browser media progression, then continue after isolated commit failure.
- [x] T112-14 Make manual switch/stop attempt the same bounded last-good commit when video is decodable.
- [x] T112-15 Keep `localStorage`, `sessionStorage`, IndexedDB and Cache API out of snapshot persistence.
- [x] T112-16 Add focused regression assertions for active-session binding, atomic replacement, quality rejection, no-store delivery, cross-page persistence markers, sequential traversal and protected boundaries.
- [x] T112-17 Update spec/plan/tasks/quickstart for persistent VPS last-good behavior.
- [x] T112-18 Original exact seven-file diff verified and merged under Issue #112.
- [x] T112-19 Original PR Validation succeeded.
- [x] T112-20 Original Quality integration gate succeeded.
- [x] T112-21 Original review/freshness gates completed.
- [x] T112-22 Original exact green head merged and runtime-accepted.

### Issue #115 - Browser security compatibility update

- [x] T115-01 Record that the protected Camera 1 browser identity is `/sea-speed/media/cam1/index.m3u8` and `/cams/hls/cam1/index.m3u8` is retired.
- [x] T115-02 Keep gallery snapshot storage, API payloads, one-active-preview concurrency, Ubuntu relay and AI behavior unchanged while `/sea-speed/**` becomes Authentik-protected.
- [x] T115-03 Update gallery regression assertions so they verify the protected HLS/auth boundary rather than the superseded public path.
- [ ] T115-04 Issue #115 PR Validation and Quality integration pass on exact head.
- [ ] T115-05 Issue #115 exact green head merges under its own Outcome Authorization.
- [ ] T115-06 After separate Issue #115 production approval, prove authenticated gallery behavior and durable snapshots remain healthy.

## Completion gate

Accepted Issue #112 gallery behavior remains:

- one final JPEG per camera and no historical archive;
- snapshot commit catalog + exact active-session bound;
- failed/rejected update preserves prior last-good JPEG;
- reload/another device show the same VPS snapshot without starting preview;
- browser persistent storage unused;
- Preview All remains `max_active=1` and failure-isolated;
- Camera 1 media, Ubuntu relay, credentials and AI behavior unchanged.

After Issue #115 rollout, the additional compatibility gate is:

- `/cams/**` exposes no camera content;
- `/sea-speed/cameras/**`, its API, previews and snapshots are Authentik-gated;
- protected `/sea-speed/media/cam1/index.m3u8` remains healthy for an authenticated operator;
- durable snapshot files are not deleted/migrated by the security change.
