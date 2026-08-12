# Quickstart: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Original Issue: #103
- Extension Issue: #109

## Repository validation

Run the focused checks before PR publication:

```bash
python3 -m py_compile api/app/main.py
bash -n deploy/worker/ubuntu/camera-preview-relay.sh
bash -n deploy/vps/deploy.sh
python3 -m unittest tests.test_camera_preview_gallery
```

The normal repository PR/quality workflows remain mandatory.

## Runtime inventory boundary

Do not commit a populated inventory. Camera credentials remain only in the protected Ubuntu runtime inventory. Issue #109 does not change the Ubuntu inventory, sanitized VPS catalog, relay service, API endpoints or Camera 1 path.

## Issue #109 browser-state boundary

Retained last frames are intentionally page-local only:

- live HLS is decoded by the existing browser player;
- before switch/stop, the latest decodable video frame is drawn into that camera card's `<canvas>`;
- the canvas remains visible while the current page stays loaded;
- no `localStorage`, `sessionStorage`, IndexedDB, Cache API, server snapshot file or database row is written;
- reload or close clears the retained frames naturally.

This is a temporary visual contact sheet for identifying cameras, not recording or evidence storage.

## Manual product acceptance

1. Open `/sea-speed/` and verify existing Camera 1 live is healthy.
2. Open `/sea-speed/cameras/`.
3. Confirm all configured catalog cameras appear and no preview is active before any action.
4. Press Play on one known-good camera and wait for moving video.
5. Press Stop; confirm the live player stops but the last frame remains visible in that card.
6. Press Play on another camera; confirm the prior card still shows its last frame while the new camera is live.
7. Stop the second camera and confirm its last frame remains too.

## Preview All acceptance

1. Press `Предпросмотр всех`.
2. Confirm the progress indicator advances through the catalog sequentially and identifies the current camera.
3. Confirm only one card is live at a time and successful cards accumulate a `последний кадр` canvas as the batch moves forward.
4. If an offline/invalid candidate is encountered, confirm its card shows an error and later cameras are still attempted.
5. During a second pass, press `Остановить все` while traversal is running.
6. Confirm no later cameras from that pass begin after cancellation settles, the current server preview is stopped, and already captured canvases remain visible.
7. Run Preview All to normal completion and confirm the backend returns to no active preview after the final camera.
8. Reload the page and confirm every retained frame disappears.
9. Re-check Camera 1 live.

## Production rollout boundary

Issue #109 changes only the Cameras frontend plus SDD/tests in repository source. After exact-green merge, production requires a separate safety-envelope authorization bound to the final merged main SHA. VPS deployment uses the existing exact release mechanism. Ubuntu preview relay activation/configuration is not part of this rollout.

## Acceptance evidence

Record in Issue #109:

- exact merged/deployed main SHA;
- PR Validation and Quality integration success for exact source;
- Preview All sequential progress result;
- representative successful last-frame camera IDs;
- Stop All result and final active-preview state;
- reload-clears-frames result;
- Camera 1 before/after result;
- confirmation that Ubuntu relay, camera credentials and AI contours were not changed.
