# Spec: Unify live-sync overlay and passage engine for Road and Water

- Issue: #327
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Road and Water share a single live-sync overlay implementation and a
single passage/tracking engine. Frontend duplication is eliminated via
`live-sync.js`; worker duplication is eliminated via a generic
`PassageEngine` (parametrized from `water_passage.py`) usable by both
domains. A tracking fix in one contour automatically helps the other.

## User scenarios

- Operator watches Road or Water live: overlay boxes follow objects with
  the same lag clamp (0..1200ms), bracketing and closest-earlier fallback.
- A fast vehicle on either domain with ByteTrack fragmentation forms one
  continuous passage with stitched fragments, swept gate crossings and
  measured speed/snapshot.

## Requirements

- R1: Frontend — `frontend/sea-speed/live-sync.js` owns median, lag
  compensation clamp, bracket, closest-earlier fallback, interpolation
  and render scheduling; both HTMLs include it and contain near-zero
  duplicated sync math.
- R2: Worker — `water_passage.WaterPassageEngine` becomes a generic
  `PassageEngine` (alias preserved); `hls_motion_yolo_worker_events.py`
  uses it for both Water and Road domains via profile-provided speed
  lines / distance.
- R3: Velocity-predicted stitching with capped dynamic radius applies to
  both contours; slow-object behaviour unchanged.
- R4: No schema / auth / standing-delegation change; event payloads keep
  their existing shape (passage vs legacy track-event).

## NFR assessment

- NFR-065-001 | Area: performance | Target: O(1) per detection stitching, no extra inference; frontend arithmetic-only | Validation: unit | Evidence: tests/test_water_passage.py, tests/test_live_overlay_sync.py | Status: PASS
- NFR-065-002 | Area: reliability | Target: capped radius + claimed-set prevents over-merge; closest-earlier bounded to 2s | Validation: unit | Evidence: same tests | Status: PASS
- NFR-065-003 | Area: security | Target: no new endpoints/secrets/boundary changes | Validation: review | Evidence: exact diff scope | Status: PASS

## Acceptance criteria

- AC-001: `live-sync.js` exists, exports shared helpers, and both
  `index.html` files include it with < 15% remaining duplicated sync math
  (marker-based).
- AC-002: Water fast fragment churn (IDs change every frame) forms one
  passage with all fragments, both gates crossed, speed measured — via the
  generic engine.
- AC-003: Same fast churn scenario parameterized as Road profile also forms
  one passage with measured speed (road speed lines config).
- AC-004: Dynamic radius cap and same-batch claim safety hold for the
  generic engine.
- AC-005: Slow-vessel existing passage tests pass unchanged.
- AC-006: MIXED runtime_verified deployment via canonical protected pipeline
  (policy ALLOW).

## Runtime feedback

- Prior duplication (058–064) required separate frontends fixes; Road was
  missing velocity stitching now proven on Water.
