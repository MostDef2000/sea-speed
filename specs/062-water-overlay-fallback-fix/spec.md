# Spec: Water overlay fallback fix — ensure green contours visible before PDT

- Issue: #320
- Status: ACTIVE
- Runtime contour: VPS (frontend)

## Product outcome

Water green contours with ID/speed visible immediately after HLS start, even when `playingDate` not yet available, via fallback to latest live envelope; ROI/speed/crossing tools remain functional via opacity handling.

## User scenarios

- Operator opens Water, HLS starts, within 1s green boxes appear even before PDT warmup.
- ROI editing still works (overlayImg rect valid).
- Clean preview and Road unchanged.

## Requirements

- R1: Expose `hls`/`waterHls` to `window` for media time lookup.
- R2: `getMediaMs` uses `window.hls`/`window.waterHls` correctly.
- R3: `renderForVideoFrame` falls back to latest live envelope when `getMediaMs()==null` or no bracket, instead of clearing.

## NFR assessment

- NFR-062-001 | Area: usability | Target: Water AI visible within 1s of stream start | Validation: frontend unit | Evidence: tests/test_frontend_contract.py | Status: PASS

## Acceptance criteria

- AC-001: Green contours with ID/speed visible immediately, even without PDT, via fallback.
- AC-002: ROI tools functional (opacity, not display:none).

## Runtime feedback

- 061 merged but water overlay hidden when PDT null.
