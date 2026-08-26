# Spec: Water fast vessel tracking + live overlay sync alignment

- Issue: #324
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Fast vessels (jet ski) on Water are detected, tracked and measured end-to-end:
one continuous passage with track fragments stitched by velocity prediction,
swept two-gate crossings, measured speed and a snapshot. The Water live AI
overlay stays visually aligned with the object it labels.

## User scenarios

- Operator watches Water live: a fast jet ski crossing the frame appears as
  one passage with speed and a snapshot instead of vanishing.
- Operator watches overlay boxes: boxes follow objects without visible
  stale-latest jumps when bracketing is temporarily unavailable.

## Requirements

- R1: Velocity-aware stitching — new track fragment joins an active passage
  when consistent with the predicted anchor (last two observations
  extrapolated to current ts); dynamic radius scales with passage speed.
- R2: Deterministic boundedness — dynamic radius capped by
  stitch_distance_max_px; claimed-set per batch unchanged.
- R3: Fast-passage completeness — stitched fast passage accumulates swept
  line crossings across fragment boundaries and reaches speed_status=measured
  with a snapshot candidate.
- R4: Overlay alignment — lag clamp extended to 1200ms; on bracket failure
  render closest-earlier envelope within 2s instead of stale latest.
- R5: No regression — slow-object stitching, Road pages, schemas, event
  cadence unchanged.

## NFR assessment

- NFR-064-001 | Area: performance | Target: O(1) per detection stitching, no extra inference | Validation: unit | Evidence: tests/test_water_passage.py | Status: PASS
- NFR-064-002 | Area: reliability | Target: capped radius prevents over-merge of distinct vessels | Validation: unit | Evidence: tests/test_water_passage.py FastVesselStitchTests | Status: PASS
- NFR-064-003 | Area: security | Target: no new endpoints/secrets/boundary changes | Validation: review | Evidence: exact diff scope | Status: PASS

## Acceptance criteria

- AC-001: Synthetic fast vessel (fragment IDs churn every frame) forms one
  passage with all fragments, both gates crossed, speed measured.
- AC-002: Dynamic stitch radius capped; same-batch claim safety preserved.
- AC-003: Slow-vessel behavior unchanged (existing tests pass).
- AC-004: Frontend sync helpers tested: 1200ms clamp, closest-earlier
  fallback over stale latest.
- AC-005: MIXED runtime_verified deployment via canonical protected pipeline.

## Runtime feedback

- Production report after 063: fast water motorcycle missed entirely (no
  track/passage/snapshot/speed); overlay boxes occasionally offset from
  objects. Root causes: static 120px stitch radius vs fast displacement;
  600ms lag clamp + stale-latest fallback rendering.
