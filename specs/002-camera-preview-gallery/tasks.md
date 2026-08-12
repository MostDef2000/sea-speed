# Tasks: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Plan: specs/002-camera-preview-gallery/plan.md
- Original Issue: #103
- Prior extension: #109
- Current Issue: #112
- Status: Persistent last-good snapshot implementation under Outcome Authorization

## Delivery tasks

### Accepted foundation

- [x] T001 Deliver on-demand Camera Preview Gallery from sanitized runtime catalog.
- [x] T002 Preserve Camera 1 accepted browser path and AI independence.
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
- [ ] T112-18 Verify exact seven-file diff against source main.
- [ ] T112-19 PR Validation succeeds on exact head.
- [ ] T112-20 Quality integration gate succeeds on exact head.
- [ ] T112-21 Confirm zero unresolved review threads and fresh head/base.
- [ ] T112-22 Merge exact green head under Outcome Authorization.

### Production and runtime acceptance

- [ ] T112-23 Obtain separate exact-SHA production safety envelope.
- [ ] T112-24 Deploy VPS API + Cameras frontend only; no Ubuntu/Camera1 path/AI mutation.
- [ ] T112-25 Verify Camera 1 before and after rollout.
- [ ] T112-26 Commit representative good snapshots and verify durable files/API metadata.
- [ ] T112-27 Verify reload and another browser/device show the same persisted images while page load starts zero preview.
- [ ] T112-28 Verify stale/wrong session and a rejected candidate leave a previous good JPEG unchanged.
- [ ] T112-29 Verify Preview All remains serial, failure-isolated, and returns backend preview state to idle.
- [ ] T112-30 Record runtime/visual evidence and close Issue #112 only after operator acceptance.

## Completion gate

- [ ] Exact seven-file source diff only.
- [ ] Required CI green on exact merged source.
- [ ] Persistent store contains at most one final JPEG per camera and no historical archive.
- [ ] Snapshot commit is catalog + exact active-session bound and accepts no arbitrary path/source.
- [ ] Failed/rejected update demonstrably preserves the prior last-good JPEG.
- [ ] Reload and another device show the same VPS snapshot without starting preview.
- [ ] Browser persistent storage is unused.
- [ ] Preview All remains `max_active=1` and isolated failures do not abort later cameras.
- [ ] Camera 1, Ubuntu relay, credentials and AI remain unchanged.
- [ ] Production rollout separately authorized and runtime evidence recorded before COMPLETE.
