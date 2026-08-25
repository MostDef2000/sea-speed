# Spec: Water video overlay sync — clean HLS + timestamped AI canvas

- Issue: #316
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Water main window shows synchronized composition of protected clean HLS and timestamped AI canvas (p95 ≤150ms, max ≤250ms, lag-compensated median 0..600ms, no extrapolation, minimal jitter). Clean preview restored (duplicate Hls.js). Passages/crossings stable from last confirmed bracket, Water formulas unchanged, Road remains DONE.

## User scenarios

- Operator watches Water main: boxes/IDs/passages track smoothly with HLS, no lag, no jitter, clear on stale.
- Clean preview card shows same protected HLS advancing independently.
- Passages update monotonic without flicker.

## Requirements

- R1: Water worker honest `capture_time_unix_ms` per-frame (latest-complete-frame FIONREAD drain, as Road 058) and `sea_speed_water_live_v2` immutable envelope with `timestamp_semantics=worker_receive_utc`.
- R2: API `POST /api/cam1/live` exact private allowlist + Bearer auth + schema/size validation + `live_seq` + SSE `id:` replay (rollover-proof) + HLS `program_date_time` already present for cam1 preview (reuse).
- R3: Frontend `frontend/sea-speed/index.html` mirrors Road polish: 15s buffer, `playingDate/requestVideoFrameCallback` bracket-only interpolation, median lag compensation, `cleanPreviewVideo` duplicate HLS, crossings/passages from `hi` stable.
- R4: Fail-closed: valid video + valid bracket → draw; otherwise clean HLS with empty canvas; no extrapolation.

## NFR assessment

- NFR-060-001 | Area: usability | Target: Water overlay ±1px, p95 ≤150ms | Validation: sync math unit + runtime manual | Evidence: tests/test_road_overlay_sync.py | Status: PASS
- NFR-060-002 | Area: usability | Target: clean preview advancing within 3s | Validation: frontend unit | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-060-003 | Area: reliability | Target: passages not flickering | Validation: stability unit | Evidence: tests/test_road_overlay_sync.py | Status: PASS

## Acceptance criteria

- AC-001: Water envelope v2 with honest capture_time, deep-immutable, validated.
- AC-002: Private Water live POST authenticated 200/403, SSE monotonic beyond 120, HLS PDT advancing.
- AC-003: Water main canvas lag-compensated, bracket-only, stable passages, clean preview both cards, ±1px, Water/Road no regression.

## Runtime feedback

- Road 058/059 verified; Water currently uses legacy overlay path and needs same sync transfer.
