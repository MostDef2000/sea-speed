# Plan: Unify live-sync overlay and passage engine for Road and Water

- Issue: #327
- Specification: specs/065-live-sync-unification/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-065-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: deduplicate frontend via shared module with unit-mirrored math; keep both HTMLs thin wrappers | Validation: sync-math tests + source markers | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-065-002 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: generalize WaterPassageEngine to PassageEngine with alias; Road reuses proven stitching (064) via profile-provided lines; full regression of passage + crossing tests | Validation: unit tests fast/road + distant + claim | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-065-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: capped radius + min(gap, window) + claimed-set preserved | Validation: cap/claim tests | Residual risk: 1 | Owner: worker | Status: MITIGATED

## Architecture

- Frontend: `frontend/sea-speed/live-sync.js` — standalone script exposing
  `SeaSpeedLiveSync` namespace (median, getCaptureMs, clamp, bracket,
  closestEarlierEnvelope, interpolate, render helpers). Both pages include
  it via `<script src="./live-sync.js">` and keep only per-page config
  (video element id, HLS globals, poll URL).
- Worker: `worker/water_passage.py` — add `PassageEngine = WaterPassageEngine`
  alias and export generic params (`stitch_distance_max_px`,
  `velocity_stitch_factor`). `hls_motion_yolo_worker_events.py` instantiates
  the same engine for `is_water` and for Road's speed-line path where
  available, keyed by profile `line_a/line_b/distance_m`.
- No API/schema/nginx/boundary change.

## Decisions

- D1: Shared live-sync.js over per-page copies — single source for fixes.
- D2: Reuse WaterPassageEngine as generic (alias) rather than rename file — preserves exact-artifact history and import paths.
- D3: Road reuse is additive — if speed lines disabled, passage stays disabled; no breaking change to Road event cadence.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: live-sync math (clamp 1200, closest-earlier), Water fast churn,
  Road-churn via same engine, radius cap, claim safety, slow unchanged.
- Integration: source contains live-sync.js include in both HTMLs; worker
  imports PassageEngine alias.
- Runtime-manual: overlay alignment + fast passage on both domains.

## Test design

- TEST-065-001 | Covers: R1,AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_live_overlay_sync.py | Coverage: COVERED
- TEST-065-002 | Covers: R2,R3,AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_water_passage.py::FastVesselStitchTests etc. | Coverage: COVERED
- TEST-065-003 | Covers: R2,R3,AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_water_passage.py Road-churn case | Coverage: COVERED
- TEST-065-004 | Covers: R3,AC-004 | Level: unit | Priority: P0 | Evidence: same passage tests | Coverage: COVERED
- TEST-065-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: existing PassageEngineTests | Coverage: COVERED
- TEST-065-006 | Covers: AC-006 | Level: runtime-manual | Priority: P1 | Evidence: MIXED manifests + visual | Coverage: RUNTIME-MANUAL | Reason: protected hardware MIXED deploy

## Correct-course check

- Trigger: NONE
- Issue impact: additive unification without contract change
- Specification impact: initial SDD for 065
- Plan impact: initial SDD for 065
- Tasks impact: AC-001..AC-006 → TASK-065-01..04
- Authorization impact: NONE — initial SDD for src-auth-065
- Follow-up: consider factoring remaining Road crossing counter into engine in a future task if needed

## Runtime feedback

- Prior duplication required duplicate frontend fixes (058–064); Road lacked velocity stitching now proven on Water.

## Deployment transaction audit

- TX-065-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-065-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-065-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous serving | Retry: rerun contour | Rollback: redeploy 73907b5 | Evidence: deployment-manifest MIXED runtime_verified
- TX-065-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: 73907b5 | Evidence: manifest + live visual
- TX-065-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-065-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-065-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-065-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy 73907b5 | Rollback: itself | Evidence: rollbackTarget hash
