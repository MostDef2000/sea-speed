# Spec: Road live metadata overlay (Stage 3) + detector frequency research kit (Stage 4 prep)

- Issue: #301
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Stage 3: clean HLS video becomes base layer, analytics drawn by browser canvas from immutable normalized metadata. Worker publishes exact `road1/road-v1/road` envelope with generation, monotonic frame identity, source time and boxes; API streams via authenticated SSE with bounded history; browser syncs to displayed video time, interpolates only between fresh measurements and clears stale/mismatched data within 1s.

Stage 4 prep: repository-owned deterministic research kit for sustainable Road inference cadence (5/10/15 mandatory, 20/25/30 conditional) solo+joint.

## User scenarios

- Operator watches Road HLS: boxes/IDs/speeds move smoothly at display cadence, aligned to video content box across resize/fullscreen/DPR.
- Worker restarts: generation bump clears old tracks, first fresh envelope renders immediately.
- Stale metadata (>2 intervals, out-of-order, wrong generation): overlay clears, shows waiting.
- SSE disconnects: reconnects without unbounded memory.
- Researcher runs benchmark kit locally: matrix/schema validated, stable-ceiling computed honestly.

## Requirements

- R1: Metadata envelope immutable normalized with exact identity, generation, timestamps, boxes, speed labels, crossings snapshot.
- R2: SSE bounded, authenticated, reconnectable, no disk amplification, no inference blocking, exact HEAD.
- R3: Browser overlay canvas exact transforms via content-box, handles interpolation boundaries, TTL, generation/out-of-order.
- R4: Backward-compatible state consumers remain valid (additive).
- R5: Stage 4 benchmark kit deterministic, matrix validated, metrics/p95/percentiles, stable-ceiling rules, redaction.

## NFR assessment

- NFR-053-001 | Area: usability | Target: overlay alignment ±1 CSS px across 1920/1080 content-box resize/fullscreen/DPR=1,2 | Validation: canvas transform unit + runtime manual | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-053-002 | Area: reliability | Target: stale >1s clears overlay, never draws mismatched generation/out-of-order | Validation: browser TTL unit tests | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-053-003 | Area: performance | Target: SSE at 10 FPS delivers ≥8 env/s sustained 60s motion-active, no blocking, bounded queue | Validation: API queue + runtime manual | Evidence: tests/test_api_contract.py, tests/test_detection_runtime_optimization.py | Status: PASS
- NFR-053-004 | Area: observability | Target: envelope carries honest observed_mono, generation, frame_no, worker commit, separate FPS fields without double-count | Validation: schema/telemetry tests | Evidence: schemas/telemetry.schema.json, tests/test_telemetry_contract.py | Status: PASS
- NFR-053-005 | Area: reliability | Target: Stage4 matrix/schema, percentile/ceiling calc deterministic, redaction enforced | Validation: benchmark parser tests | Evidence: tests/test_detector_frequency_benchmark.py | Status: PASS

## Acceptance criteria

- AC-001: Live envelope immutable normalized with exact road1/road-v1/road, generation, observed_mono, boxes and crossings snapshot; SSE bounded deque delivers ≥8 env/s at 10 FPS without inference blocking.
- AC-002: Browser overlay renders boxes/IDs/speeds at display cadence, content-box transform aligned ±1px, clears stale >1s and mismatched generation.
- AC-003: State consumers remain backward compatible; Worker remains authoritative for crossings totals-by-class invariant.
- AC-004: Stage4 benchmark kit validates matrix/schema, p95/ceiling deterministic, redaction enforced, stop rules respected.

## Runtime feedback

- Prior evidence 5bda18f Stage 3 pending; no runtime regression on MIXED.
