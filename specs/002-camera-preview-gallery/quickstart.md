# Quickstart: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Original Issue: #103
- Prior extension: #109
- Current Issue: #112
- Browser security migration: Issue #115

## Repository validation

Run the focused checks before PR publication:

```bash
python3 -m py_compile api/app/main.py
python3 -m unittest tests.test_camera_preview_gallery
```

The normal repository PR Validation and Quality integration gate remain mandatory for any later compatibility/security change such as Issue #115.

## Snapshot storage boundary

Issue #112 adds exactly one durable last-good JPEG per successful catalog camera:

```text
/opt/sea-speed-api/data/camera-preview-snapshots/<camera_id>.jpg
```

The directory is under existing durable `/opt/sea-speed-api/data/`. It is not the temporary HLS media tree and is not a history/archive. Normal code deployment and the Issue #115 authentication migration must not delete or migrate it.

Browser persistence remains forbidden for this feature: no `localStorage`, `sessionStorage`, IndexedDB, Cache API, or browser-side application snapshot store.

## API behavior

- `GET /api/cameras` includes safe snapshot metadata for each camera: availability, versioned API image URL, and update timestamp.
- `GET /api/cameras/{camera_id}/snapshot` returns the current JPEG only for a camera still present in the runtime catalog and uses `Cache-Control: no-store`.
- `POST /api/cameras/{camera_id}/snapshot/commit?session_id=<id>` succeeds only when both camera ID and session ID match the current managed active preview.
- The commit endpoint never accepts RTSP URL, relay source, arbitrary filesystem path, or image upload bytes.

After Issue #115, these browser-facing resources are reached under the authenticated `/sea-speed/**` nginx contour. Their FastAPI route semantics do not change.

## Last-good update semantics

A successful commit:

1. resolves the managed HLS playlist from server state;
2. extracts one JPEG from the HLS tail with bounded FFmpeg execution;
3. verifies JPEG structure/minimum size;
4. measures conservative luma spread with FFmpeg `signalstats`;
5. writes only a temporary dotfile until all checks pass;
6. atomically replaces `<camera_id>.jpg` with `os.replace`.

Any stale session, timeout, extraction error, malformed/too-small JPEG, or near-uniform frame is rejected and leaves the previous final JPEG unchanged.

## Manual product acceptance

1. Authenticate to Sea Speed after Issue #115 rollout.
2. Verify Camera 1 live is healthy through `/sea-speed/media/cam1/index.m3u8`.
3. Open `/sea-speed/cameras/` and confirm no live preview starts automatically.
4. Play a known-good camera until the picture is formed, then press Stop.
5. Confirm the card shows a persistent `последний кадр` image and update time.
6. Reload the page; confirm the same image remains without starting preview.
7. Open the Cameras page from another authenticated browser/device; confirm the same image is visible.
8. Preview the camera again and confirm only a successful new commit changes the image/version.

## Preview All acceptance

1. Press `Предпросмотр всех`.
2. Confirm cameras are visited sequentially and only one card is live at a time.
3. Confirm stable good cameras update their VPS snapshots after actual playback progression.
4. If a camera fails to start/stabilize or its candidate snapshot is rejected, confirm later cameras are still processed.
5. Confirm a camera with an existing good image keeps that old image when a new commit is rejected.
6. Press `Остановить все` during another pass and confirm no later batch cameras start after cancellation settles.
7. Run a full pass and confirm backend preview state returns to idle while stored images remain.
8. Reload and confirm stored images persist.
9. Re-check protected Camera 1 live.

## Auth v1 compatibility acceptance

Under separately approved Issue #115 production rollout:

```text
anonymous /cams/                                -> 404/410
anonymous /cams/hls/cam1/index.m3u8             -> 404/410
anonymous /sea-speed/cameras/                    -> authentication redirect/deny
anonymous gallery API/preview/snapshot resources -> authentication redirect/deny
authenticated /sea-speed/cameras/                -> gallery works
protected /sea-speed/media/cam1/index.m3u8       -> advancing H.264 Camera 1
```

The authentication migration must not change snapshot API payloads, preview `max_active=1`, persistent JPEG semantics, Ubuntu relay or AI behavior.

## Production rollout boundary

Issue #112 production is historical and accepted. Issue #115 has its own source authorization and requires a separate exact-SHA production safety envelope. Follow `docs/operations/SEA_SPEED_AUTH_V1.md`; do not infer Auth v1 production permission from the earlier gallery rollout.

## Acceptance evidence

For Issue #115 record only sanitized evidence relevant to this gallery compatibility check:

- exact merged/deployed main SHA;
- PR Validation and Quality integration results;
- anonymous/authenticated gallery boundary verdicts;
- representative existing snapshot still visible after rollout;
- Preview All serial/Stop All/final idle result;
- Camera 1 protected H.264 before/after result;
- explicit confirmation that snapshot data, Ubuntu relay, credentials and AI behavior were unchanged.
