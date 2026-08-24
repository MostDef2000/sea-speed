# Spec: Stage 3 visual finish — live canvas rendering from SSE

- Issue: #303
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Wire live path to visible smooth overlay: Worker publishes immutable live envelope per processed frame, API streams via bounded Authentik SSE, browser renders on liveOverlayCanvas at display cadence with content-box alignment and stale/generation safety, fallback to overlay.jpg until first live.

## User scenarios

- Operator sees HLS clean video with boxes/IDs/speeds moving smoothly at ~60 FPS, aligned to video content-box across resize/fullscreen/DPR 1/2.
- Stale >1s, generation change or out-of-order discards overlay within 1s and shows waiting.
- SSE reconnects without leak; ≥8 env/s at 10 FPS sustained.

## Requirements

- R1: Worker builds immutable normalized envelope (road1/road-v1/road, generation, observed_mono, boxes, crossings) and publishes via bounded queue without blocking inference.
- R2: API validates, stores deque 120, streams SSE with reconnect and no disk amplification, exact HEAD.
- R3: Browser renders live boxes at display cadence with content-box math, interpolation between fresh frames, TTL 1s, generation/out-of-order discard.

## NFR assessment

- NFR-054-001 | Area: usability | Target: alignment ±1 CSS px content-box resize/fullscreen/DPR 1,2 | Validation: canvas unit + manual | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-054-002 | Area: reliability | Target: stale >1s clears <1s, no mismatched generation draw | Validation: TTL unit | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-054-003 | Area: performance | Target: SSE ≥8 env/s @10 FPS 60s, no blocking, bounded | Validation: API + runtime | Evidence: tests/test_api_contract.py | Status: PASS
- NFR-054-004 | Area: observability | Target: envelope honest observed_mono/generation/worker commit normalized | Validation: telemetry | Evidence: schemas/telemetry.schema.json | Status: PASS

## Acceptance criteria

- AC-001: Live envelope immutable normalized with exact identity, generation, observed_mono, boxes, crossings; SSE bounded deque streams ≥8 env/s without blocking.
- AC-002: Browser canvas renders at display cadence, content-box aligned ±1px, clears stale/generation within 1s, interpolates between fresh.
- AC-003: Backward compatible state consumers, Water/events no regression, crossings totals==sum by_class.

## Runtime feedback

- Skeleton 9eebc5c deployed MIXED, visual wiring pending.
