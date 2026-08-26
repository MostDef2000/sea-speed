# Spec: Water overlay tools fix — restore AI overlay and ROI/speed/crossing editing

- Issue: #318
- Status: ACTIVE
- Runtime contour: VPS (frontend)

## Product outcome

Water main window AI overlay visible and synchronized (median lag 0..600ms, bracket-only, fail-closed, ±1px) and ROI polygon, Speed lines A/B, Crossing line tools editable, undoable, savable with POST→GET verification, without breaking Road or clean HLS.

## User scenarios

- Operator clicks ROI “Изменить ROI”, draws polygon, saves — POST succeeds, GET verifies, overlay draws, status shows saved.
- Same for Speed lines A/B and Crossing line; undo/clear work; save failure keeps draft and shows error.
- Water HLS plays in both main (waterMainVideo) and clean preview; AI boxes glide over main without lag, crossings stable.

## Requirements

- R1: Water `waterMainVideo` visible with `opacity` (not `display:none` for overlayImg) so `getBoundingClientRect` remains valid for ROI/speed/crossing editors.
- R2: `liveOverlayCanvas` contentRect uses `waterMainVideo`/`roiEditorWrap` dimensions correctly; brackets use median lag compensation; `crossings/passages` from `hi` stable.
- R3: Clean preview `cleanPreviewVideo`/`#video` continues independent HLS; main and preview lifecycles independent.
- R4: No regression for Road page (`frontend/sea-speed/road/index.html`) — keeps lag compensation, clean preview, stable crossings.

## NFR assessment

- NFR-061-001 | Area: usability | Target: Water AI overlay ±1px, p95 ≤150ms, no lag | Validation: sync math unit | Evidence: tests/test_road_overlay_sync.py | Status: PASS
- NFR-061-002 | Area: usability | Target: ROI/Speed/Crossing edit/save verify within 2s, draft preserved on failure | Validation: frontend contract | Evidence: tests/test_frontend_contract.py | Status: PASS

## Acceptance criteria

- AC-001: Water AI overlay visible, lag-compensated, bracket-only, fail-closed, ±1px.
- AC-002: ROI, Speed lines, Crossing line tools editable, undoable, POST→GET verified, draft preserved on error.
- AC-003: Clean HLS advances in both main and clean preview, Road unchanged.

## Runtime feedback

- 060 merged but water AI hidden due to `display:none` and ROI broken; needs display/opacity fix and rect correction.
