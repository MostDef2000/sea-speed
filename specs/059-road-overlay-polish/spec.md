# Spec: Road overlay polish — lag compensation, clean preview restore, stable crossings

- Issue: #314
- Status: ACTIVE
- Runtime contour: VPS (frontend)

## Product outcome

Road main window AI overlay lag-compensated to match displayed HLS frame (p95 ≤150ms, max ≤250ms, no extrapolation, minimal jitter). LIVE CAMERA clean preview card restores same protected HLS picture (duplicate Hls.js instance). Crossing counter renders stable from last confirmed bracket without per-frame jitter, while clean HLS remains sole source and Water stays unchanged.

## User scenarios

- Operator watches Road main: boxes track objects with ~0 lag, smooth interpolation, no lead/lag, clear after 1s of uncertain/stale.
- Operator glances at clean preview card: same protected HLS picture plays independently, no AI boxes, no frozen placeholder.
- Crossing totals increment monochromatically and do not flicker between frames.

## Requirements

- R1: Measure HLS PDT lag as median(`playingDate - capture_time_unix_ms`) over 10s warmup (≥20 samples) and subtract it from media UTC before bracket search; clamp compensation to 0..600ms; fail-closed if compensation unavailable or `|delta|>600ms` or `gap>500ms`.
- R2: Main canvas uses existing `sea_speed_road_live_v2` + `program_date_time` + 15s buffer + `requestVideoFrameCallback` bracket-only interpolation (same generation/track, gap ≤500ms); never extrapolate; stale >1s or uncertain → clear.
- R3: Clean preview card contains `<video id="cleanPreviewVideo">` with independent `Hls@1.5.7` instance loading same `preview.hls_url`; plays on preview start, pauses on stop, independent of main canvas lifecycle.
- R4: Crossings rendered only from upper bracket `hi` (or last confirmed `hi` when bracket valid) — not interpolated, not animated per detection; totals update only when `hi.crossings` changes.

## NFR assessment

- NFR-059-001 | Area: usability | Target: main overlay alignment ±1px, no perceptible lag (p95 ≤150ms) | Validation: sync math unit + runtime manual | Evidence: tests/test_road_overlay_sync.py | Status: PASS
- NFR-059-002 | Area: usability | Target: clean preview card shows advancing HLS within 3s of preview start | Validation: frontend contract unit | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-059-003 | Area: reliability | Target: crossings counter never flickers between two values within same bracket | Validation: crossing stability unit | Evidence: tests/test_road_overlay_sync.py | Status: PASS

## Acceptance criteria

- AC-001: Lag compensation measured and applied (median delta), bracket skew p95 ≤150ms / max ≤250ms verified via synthetic timestamps; otherwise canvas cleared.
- AC-002: Clean preview `<video id="cleanPreviewVideo">` exists, loads same `hls_url`, plays independently, placeholder hidden when playing.
- AC-003: Crossing totals rendered from stable `hi` bracket only, monotonic, no jitter across interpolated frames.

## Runtime feedback

- Prior `93798bd` MIXED verified but lag ~150ms, clean preview empty, crossings jitter observed.
