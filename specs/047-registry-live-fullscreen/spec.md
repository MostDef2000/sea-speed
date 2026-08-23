# Spec: Registry image zoom and live stream fullscreen

- Issue: #287
- Status: ACTIVE
- Runtime contour: VPS

## Product outcome

Operators can inspect evidence without downloading: in the objects registry (`/sea-speed/objects`) clicking a thumbnail opens the full-resolution snapshot in a modal overlay, closed via × / backdrop / Esc; on both live operator screens (water `/sea-speed/` and road `/sea-speed/road/`) the clean HLS preview frame gains a fullscreen button (⛶) that opens the same live video in a fullscreen overlay, closed via × / backdrop / Esc. No backend or API changes, frontend-only.

## User scenarios

- Operator browsing registry (water or road) sees a small card image → clicks image → full-size photo appears centered with dark backdrop, × in corner closes it; Esc or clicking outside also closes; focus trapped inside overlay.
- Operator watching live water page clicks ⛶ on the live preview card → video expands to fullscreen overlay keeping playback, × closes and returns to inline preview.
- Same on road page `/sea-speed/road/` — independent fullscreen overlay for road camera.
- Keyboard/a11y: Esc closes any open overlay, overlay is `role=dialog aria-modal`.

## Requirements

- R1: Registry cards render thumbnail with `cursor:zoom-in`; click opens `#imageZoomOverlay` with `<img src=snapshot_url>` at native/max-vh size; overlay has visible × button (`#imageZoomClose`), backdrop click and Esc close, restores body scroll lock.
- R2: Registry detail modal (`#detailPhoto`) image also zoomable via same overlay (click detail image → zoom).
- R3: Water live preview (`.live-preview-frame` in `frontend/sea-speed/index.html`) gains button `#liveFullscreenBtn` (⛶) positioned top-right of frame; click opens `#liveFullscreenOverlay` containing cloned/moved `<video id=video>` or duplicate with same HLS source, playback continues; × closes, video returns to inline frame.
- R4: Road live preview (`#livePreviewFrame` in `frontend/sea-speed/road/index.html`) same behavior with `#liveFullscreenBtn` / `#liveFullscreenOverlay`.
- R5: Overlay styles reuse existing design tokens (dark backdrop `rgba(1,6,10,.85)`, border, cyan focus ring), no new dependencies, no layout shift when closed.
- R6: Safe for no-snapshot case: zoom never opens for missing photo (fallback div not clickable).

## NFR assessment

- NFR-047-001 | Area: usability | Target: thumbnail click opens full image within 100ms, no navigation | Validation: manual + DOM test | Evidence: click handler test | Status: PASS
- NFR-047-002 | Area: accessibility | Target: overlay has role=dialog, Esc closes, focus returns to trigger, × has aria-label | Validation: manual keyboard test | Evidence: a11y check | Status: PASS
- NFR-047-003 | Area: performance | Target: no extra network request (reuse same snapshot_url / HLS), no duplicate HLS instance when possible | Validation: code review | Evidence: single video element moved | Status: PASS
- NFR-047-004 | Area: reliability | Target: no regression in existing ROI/crossing/registry flows | Validation: existing tests + smoke | Evidence: tests/test_*.py still green | Status: PASS

## Acceptance criteria

- AC-001: Clicking registry card photo opens overlay with same `snapshot_url` at full size; × closes and restores scroll.
- AC-002: Clicking detail modal photo also opens same overlay.
- AC-003: Water page live frame shows ⛶ button; click opens fullscreen video overlay; × closes and video remains playing inline.
- AC-004: Road page same as AC-003.
- AC-005: Esc and backdrop click close either overlay; no overlay opens for «Фотография отсутствует».
- AC-006: No backend files changed; only 3 frontend HTML files diff.

## Runtime feedback

To be recorded after VPS deployment acceptance.
