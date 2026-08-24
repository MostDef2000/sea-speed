# Spec: Stage 3 clean-overlay — hide baked boxes, live canvas only

- Issue: #305
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Switch Road to clean overlay: worker writes latest_overlay.jpg as clean frame without AI boxes/IDs/speeds, frontend hides overlayImg when live envelope present and renders only liveOverlayCanvas at display cadence with content-box alignment and stale/generation safety, fallback to clean overlay.jpg until first live.

## User scenarios

- Operator sees HLS clean video; before first live — clean overlay.jpg; after — liveOverlayCanvas draws boxes/IDs/speeds smoothly at ~60 FPS, no duplicate baked boxes, aligned ±1px across resize/fullscreen/DPR 1/2.
- Stale >1s, generation change or out-of-order clears live canvas within 1s and shows clean fallback.

## Requirements

- R1: Worker clean overlay — no AI boxes/IDs/speeds baked into JPEG for Road, ROI/lines optionally preserved.
- R2: Frontend hides overlayImg when live present, draws only liveOverlayCanvas at display cadence with content-box, interpolation between fresh, TTL 1s, generation discard.
- R3: Backward compatible state/events, Water no regression, ROI server-owned.

## NFR assessment

- NFR-055-001 | Area: usability | Target: alignment ±1 CSS px content-box resize/fullscreen/DPR 1,2 | Validation: canvas unit + manual | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-055-002 | Area: reliability | Target: stale >1s clears <1s, no duplicate boxes | Validation: TTL unit | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-055-003 | Area: performance | Target: live canvas 60 FPS without blocking, overlay JPEG remains clean and light | Validation: frontend + worker | Evidence: tests/test_worker_tracking_overlay.py | Status: PASS

## Acceptance criteria

- AC-001: Road latest_overlay.jpg contains no AI boxes/IDs/speeds (clean frame).
- AC-002: Frontend shows overlay.jpg clean until first live, then hides it and renders only liveOverlayCanvas at display cadence, content-box ±1px, clears stale/generation <1s, no duplicates.
- AC-003: Water/events/ROI no regression, crossings still authoritative.

## Runtime feedback

- Prior 7240413 has live wiring but still bakes boxes into overlay.jpg, causing duplicate visual.
