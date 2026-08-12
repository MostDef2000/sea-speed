# Feature Specification: Camera Preview Gallery

- Feature: 002-camera-preview-gallery
- Issue: #112
- Original Issue: #103
- Prior extension: #109
- Status: Approved persistent last-good snapshot extension
- Parent capability: specs/001-camera-live-pipeline/spec.md

## Product outcome

An operator can open `/sea-speed/cameras/`, see every camera candidate from the sanitized runtime catalog, preview cameras one at a time, run a bounded sequential Preview All pass, and see the last good image for each camera even after reload or from another device. Sea Speed stores exactly one replaceable JPEG per camera on the VPS. A failed, stale, or visually unusable new attempt never removes or overwrites the previous good snapshot.

## User scenarios

### Scenario 1 - Open the camera gallery without starting live work

Given the runtime camera catalog is installed, when an operator opens the Cameras page, then every catalog camera is rendered without starting FFmpeg preview work. If a VPS last-good snapshot exists for a camera, that image and its update time are displayed immediately.

### Scenario 2 - Preview and persist a good frame

Given a camera preview is active and has produced stable playback, when the operator or Preview All commits the current snapshot, then the VPS extracts a JPEG from that exact managed preview session, validates it, and atomically replaces only that camera's prior JPEG.

### Scenario 3 - Preserve the prior image on a bad attempt

Given a camera already has a stored snapshot, when a later preview start fails, the session is stale, extraction fails, or the extracted frame is near-uniform/startup garbage, then the previous JPEG remains unchanged and visible.

### Scenario 4 - Preview all cameras

Given multiple catalog cameras, when the operator presses `Предпросмотр всех`, then the browser visits cameras sequentially, keeps server `max_active=1`, waits for decodable and progressing video, requests a snapshot commit for the exact active session, and continues even if one camera cannot produce a usable snapshot.

### Scenario 5 - Stop all

Given Preview All is running, when the operator presses `Остановить все`, then the current live preview is stopped and no later camera from that batch generation is intentionally started. Already persisted VPS snapshots remain untouched.

### Scenario 6 - Open another device or reload

Given one or more last-good snapshots exist on the VPS, when the operator reloads the page or opens it on another browser/device, then the same server snapshots are loaded without starting live camera previews.

## Requirements

- FR-001: The gallery MUST obtain camera identities and display labels from the sanitized runtime catalog and MUST NOT embed populated LAN inventory, native RTSP URLs, or credentials in frontend source.
- FR-002: Opening the Cameras page MUST start zero camera preview FFmpeg processes and zero source pulls.
- FR-003: Preview start MUST accept a catalog `camera_id` only. Browser-supplied RTSP URLs MUST NOT be accepted.
- FR-004: The existing private credential-free Ubuntu relay input, H.264 HLS preview output, one-active-preview lock, and hard preview TTL MUST remain unchanged.
- FR-005: `Предпросмотр всех` MUST traverse the catalog sequentially and MUST NOT intentionally create parallel per-camera previews.
- FR-006: Automatic snapshot commit MUST occur only after bounded browser playback readiness and measurable media-time progression.
- FR-007: The VPS MUST store snapshots under durable Sea Speed data storage at `/opt/sea-speed-api/data/camera-preview-snapshots/`.
- FR-008: The persistent snapshot store MUST retain at most one JPEG per catalog camera. Snapshot history/archive MUST NOT be created.
- FR-009: Snapshot commit MUST be bound to both a catalog `camera_id` and the exact currently active managed preview `session_id`.
- FR-010: Snapshot commit MUST derive its input only from the managed local HLS output directory for that active session. The browser MUST NOT provide a filesystem path, source URL, or RTSP URL.
- FR-011: Snapshot extraction MUST be bounded in time and MUST use the current managed HLS tail rather than opening another native camera/relay stream.
- FR-012: A candidate JPEG MUST pass structural and conservative non-AI visual-quality checks before it can replace the prior snapshot.
- FR-013: Near-uniform/startup garbage MUST be rejected conservatively; rejection MUST preserve the prior snapshot byte-for-byte.
- FR-014: Snapshot replacement MUST be atomic: write a temporary candidate in the snapshot directory, validate it, then `os.replace()` the final `<camera_id>.jpg` only after success.
- FR-015: Snapshot retrieval MUST validate that the requested camera is still present in the current catalog.
- FR-016: Snapshot responses MUST be served through the API contour as JPEG and MUST use `Cache-Control: no-store` so browsers do not become the durable source of truth.
- FR-017: `/api/cameras` MUST expose only safe snapshot metadata (`available`, versioned API URL, `updated_at`) in addition to existing public camera fields. It MUST NOT expose relay sources or credentials.
- FR-018: Manual Play/Switch/Stop SHOULD update the persistent snapshot when the active browser video is decodable; failed commit MUST leave the old snapshot intact.
- FR-019: Preview All MUST continue to later cameras after start/readiness/stability/snapshot-quality failure of one camera.
- FR-020: Browser persistent storage MUST NOT be used for camera snapshots: no `localStorage`, `sessionStorage`, IndexedDB, Cache API, or equivalent application persistence.
- FR-021: The accepted Camera 1 public identity `/cams/hls/cam1/index.m3u8` and its direct H.264 browser path MUST remain unchanged.
- FR-022: Ubuntu MediaMTX preview relay configuration, camera credential inventory, AI/detection/tracking, recording, Objects Registry, and server preview concurrency MUST remain out of scope.
- FR-023: Existing VPS exact-release deployment and rollback mechanism MUST be reused without nginx/deploy-script changes.

## Acceptance criteria

- AC-001: Opening `/sea-speed/cameras/` with stored snapshots shows them immediately while `/api/cameras/preview` remains idle.
- AC-002: Reloading the page keeps the same last-good images visible from VPS storage.
- AC-003: Opening the page from a second browser/device shows the same stored snapshots without running Preview All first.
- AC-004: A successful manual or batch preview produces a new JPEG for that camera and changes its versioned snapshot URL/update time.
- AC-005: Starting a different preview, pressing Stop, or finishing Preview All leaves successfully committed snapshots available after the live HLS session is deleted.
- AC-006: A stale/wrong `session_id` returns a bounded error and does not modify the stored JPEG.
- AC-007: A failed extraction or rejected low-information/near-uniform candidate leaves the previous JPEG unchanged.
- AC-008: Snapshot commit accepts no browser source URL or filesystem path and operates only on the current catalog camera + managed active session.
- AC-009: Snapshot GET is catalog-bound, returns `image/jpeg`, and includes no-store cache headers.
- AC-010: The persistent directory contains no historical per-camera sequence: only one final `<camera_id>.jpg` per successful camera plus transient dotfiles during an in-progress commit.
- AC-011: Preview All remains serial with `max_active=1`, isolates per-camera failure, and stops the final live preview on normal completion.
- AC-012: Browser source contains none of `localStorage`, `sessionStorage`, IndexedDB, or Cache API snapshot persistence.
- AC-013: Camera 1 remains healthy before and after production rollout; Ubuntu relay and AI remain unchanged.
- AC-014: Required PR Validation and Quality integration gate pass for the exact seven-file Issue #112 source diff.

## Compatibility and boundaries

- Stable Camera 1 interface: `/cams/hls/cam1/index.m3u8`.
- Existing camera preview start/stop/status API and `max_active=1` remain compatible; Issue #112 adds snapshot metadata, snapshot GET, and session-bound snapshot commit endpoints.
- Snapshot persistence is gallery presentation state, not AI evidence, recording, or an image archive.
- Browser cache is not authoritative; VPS durable data is authoritative.
- Existing `/opt/sea-speed-api/data/` survives normal exact deploy/rollback code changes and is therefore the persistence contour for the last-good JPEGs.

## Runtime feedback

- 2026-08-12: Original Camera Preview Gallery (#103) was accepted in production with representative start/switch/stop and visible moving video while Camera 1 remained healthy.
- 2026-08-12: Preview All extension (#109) added sequential traversal and page-local retained frames. Technical rollout succeeded, but visual acceptance showed startup-gray/partial frames could still be retained on some cameras even after browser media progression.
- 2026-08-12: Operator requested durable cross-device last-good images and explicit preservation of the previous good image when a new preview is unusable. Issue #112 supersedes the page-only persistence boundary while preserving one-active-preview, Camera 1, Ubuntu relay, credentials, and AI boundaries.
