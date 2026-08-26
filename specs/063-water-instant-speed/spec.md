# Spec: Water instant speed — per-pixel median on full track + average between lines

- Issue: #322
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Water speed is instantaneous per-pixel bottom_center → progress_m → inst_kmh → median(last 5) on every frame and assigned to det/live, while between lines overall median/average of full passage is stored in passage/event as summary, without breaking live path.

## User scenarios

- Operator watches Water live: speed appears instantly after 3 samples, updates every frame, smooth median, no lag.
- Passage completes: event shows speed_kmh (median) and avg/min/max between lines.

## Requirements

- R1: Per-pixel instantaneous: bottom_center, dt 0.05..1.5s, progress_m via line A/B and distance_m, inst_kmh = |dm/dt|*3.6, filter 1..180, samples ≤120, median last 5, display hold 2s.
- R2: Live envelope water_live_v2 carries speed_kmh on every frame after min_samples, deep-immutable.
- R3: Passage stores speed_kmh_avg/min/max and speed_sample_count between lines as median/mean of samples within 0..distance_m.
- R4: No Road regression, same FIONREAD drain and capture_time.

## NFR assessment

- NFR-063-001 | Area: performance | Target: Water live p95 inst ≤150ms stable, no extra HLS | Validation: unit + runtime manual | Evidence: tests/test_road_overlay_sync.py | Status: PASS
- NFR-063-002 | Area: reliability | Target: Passage average correctly computed from samples within gates | Validation: unit | Evidence: tests/test_worker_tracking_overlay.py | Status: PASS

## Acceptance criteria

- AC-001: Water live shows instantaneous speed every frame after 3 samples, median smoothed.
- AC-002: Passage event contains speed_kmh (median) and avg/min/max between lines.
- AC-003: No Road regression, MIXED runtime_verified.

## Runtime feedback

- Water previously only two-gate single shot; now needs per-frame median as Road.
