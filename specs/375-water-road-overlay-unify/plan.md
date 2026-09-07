# Plan: Unify Water/Road live-overlay contour rendering (#375)

- Specification: specs/375-water-road-overlay-unify/spec.md
- Issue: #375
- Runtime contour: VPS (frontend served by nginx); Ubuntu Worker/relay NOT required

## Architecture

- New shared module `frontend/sea-speed/overlay-canvas.js` exposes
  `window.SeaSpeedOverlayCanvas = { init }`. `init(opts)` builds one buffer, one
  EventSource, one requestVideoFrameCallback render loop and one poll loop, and
  returns an instance with `setWorkerActive(active)`.
- Water (`index.html`) and Road (`road/index.html`) each call `init` once with
  camera-specific ids/urls, then call `overlay.setWorkerActive` from their existing
  worker-control handler. The previous duplicated inline live-canvas IIFEs are
  removed from both pages.
- `overlay-canvas.js` delegates sync math to `live-sync.js` (SeaSpeedLiveSync), which
  already contains the Water relative-mapping (ssWaterPlaybackLatencyMs / probe)
  logic. No worker or API change.

## Decisions

- Reuse Road's proven contour logic inside the shared module rather than forking a
  second copy; this keeps Road behaviour identical and fixes Water by sharing it.
- Fix the Water `contentRect` vertical-centering typo (`/h` → `/2`) in the shared
  module so both cameras benefit.
- Add a no-wall-clock fallback (draw latest buffered envelope) so contours stay
  visible even when the HLS stream lacks `#EXT-X-PROGRAM-DATE-TIME`.

## Affected contours

- VPS frontend only: `frontend/sea-speed/overlay-canvas.js` (new),
  `frontend/sea-speed/index.html` (Water), `frontend/sea-speed/road/index.html`
  (Road), `tests/test_frontend_contract.py` and the live-overlay sync test files.
- Ubuntu Worker/relay: NOT affected (inference + API live-envelope unchanged).
- Runtime contour: VPS.

## Validation

- `python3 -m unittest discover -s tests -p "test_*.py"` (641 tests, green).
- `python3 scripts/ci/validate_sdd.py`, `validate_repo.py`, `validate_contracts.py`.
- `python3 scripts/quality/build_exact_artifacts.py` and quality validators.
- Contract test asserts `(r.height-ch)/2` present, `(r.height-ch)/h` absent, module
  loaded by both pages, inline IIFEs removed.
- Operator RUNTIME-MANUAL: open Water and Road, confirm contours track vessels.

## Runtime feedback

- Root cause (observed): Water `contentRect` used `y:(r.height-ch)/h` (vertical
  misalignment) and neither page had a no-wall-clock fallback, so Water (HLS without
  PROGRAM-DATE-TIME) cleared the canvas every frame → no contours; Road (with
  wall-clock) worked. Shared module fixes both.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-375-001 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_frontend_contract.py::test_live_overlay_unified_module asserts centering fix and no-wall-clock fallback markers
- TEST-375-002 | Covers: AC-001, AC-004 | Level: integration | Priority: P1 | Evidence: tests/test_live_overlay_sync.py and tests/test_water_live_sync_guard.py assert module delegation and no duplicated inline sync math
- TEST-375-003 | Covers: AC-004 | Level: runtime-manual | Priority: P2 | Evidence: operator opens Water + Road and confirms contours visible with labels

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-375-01 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scope recorded in #375 | Retry: NONE | Rollback: NONE | Evidence: Sea Speed Delivery Checkpoint v2 in #375
- TX-375-02 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: branch unchanged | Retry: NONE | Rollback: NONE | Evidence: branch fix/water-road-overlay-unify from origin/main 626ffd7
- TX-375-03 | Stage: MUTATION | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: working tree revertible | Retry: NONE | Rollback: git revert of feature commit | Evidence: overlay-canvas.js + two HTML edits + tests
- TX-375-04 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: CI red blocks merge | Retry: rerun CI | Rollback: NONE | Evidence: required CI green on PR
- TX-375-05 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: main protected, revert merge | Retry: NONE | Rollback: revert merge commit | Evidence: exact-green-head merge to main
- TX-375-06 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: issue reopened | Retry: NONE | Rollback: NONE | Evidence: #375 closed; #373 noted as predecessor
- TX-375-07 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: re-run evidence collection | Retry: NONE | Rollback: NONE | Evidence: PR linked to #375; Change Contract VPS REQUIRED / Ubuntu NOT
- TX-375-08 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous static frontend restored | Retry: NONE | Rollback: revert merge + VPS redeploy | Evidence: frontend is static; no data migration
