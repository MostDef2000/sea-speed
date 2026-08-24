# Research: Stage 4 detector frequency — decision template

- Parent: specs/053-road-live-metadata-overlay/spec.md
- Issue: #301

## Goal

Provide a reproducible, redacted benchmark to decide later production frequency without changing model in #301.

## Matrix

- Offered: 5,10,15 mandatory; 20,25,30 conditional only if prior stable
- Modes: Water solo, Road solo, joint equal-rate (gated semantics), detector-only capacity bypass as research comparison
- Duration: 30s warmup + 120s measured x3, randomized, cooldown

## Metrics

offered/decoded/admitted/inferred/processed/JPEG/published FPS; p50/p95/p99 decode/IPC/model/track/overlay/JPEG/sink; age trend; drops depth; timeout/restart; GPU util/VRAM/clocks/temp; CPU/RSS; counts

## Stability rule

≥95% target FPS, p95 ≤ interval (200/100/66.7/50 ms), flat age slope, zero timeout/restart, bounded queue, plateau GPU, parity pass.

## Outputs

Stable table, recommended defaults/caps, bottleneck attribution, FP16/class-filter/latest-slot/JPEG isolation/GPU verdict, telemetry contract delta, precise file/risk/rollback for implementation, or honest no-go with measured ceiling.

No production cadence change in #301; raw media never committed.
