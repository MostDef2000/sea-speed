# Plan: Road overlay consistency, UI fit and FPS evidence

- Issue: #296
- Specification: specs/051-road-overlay-consistency/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-051-001 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: normalize all Road geometry to x_norm, 1920 fallback, worker scale on read | Validation: roundtrip + canvas draw test | Residual risk: 1 | Owner: frontend | Status: MITIGATED
- RISK-051-002 | Category: TECH | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: queue immutable overlay bytes + revision + atomic replace, preload swap | Validation: race unit test + state/overlay binding test | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-051-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: adjust panel/stage height to content, preserve canvas transform | Validation: layout test for no empty bands | Residual risk: 1 | Owner: frontend | Status: ACCEPTED
- RISK-051-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: expose sample_fps + effective_fps via PerformanceTracker snapshot in state | Validation: telemetry schema + UI test | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-051-005 | Category: TECH | Probability: 4 | Impact: 3 | Score: 12 | Mitigation: deep-copy nested crossing maps at snapshot creation and deep-copy all metadata at the asynchronous queue boundary | Validation: mutate live source after capture and assert queued totals/classes remain equal and unchanged | Residual risk: 1 | Owner: worker | Status: MITIGATED

## Architecture

MIXED normalized fix on top of 050:

- `frontend/sea-speed/road/index.html` — add `sourceDims()` fallback to 1920x1080 and `naturalWidth` fallback; `toDisplay` handles both `x_norm` and legacy absolute via fallback dimensions; `loadConfig()` converts `line_a/line_b` with norm-first; `drawSpeedLines()` always draws A/B labels even outside edit mode; add resolution badge `1920×1080` or `naturalWidth×naturalHeight`; fix `.camera-stage`/`.camera-panel` CSS to remove `--h`-driven letterboxing (`object-fit:cover/contain` policy, margin removal, stage flex); add atomic preload for overlay `Image` with `overlay_rev` guard and `requestAnimationFrame` swap.
- `api/app/main.py` — add `frame_width/height`, `sample_fps`, `effective_fps`, `p95_inference_ms`, `overlay_rev` to `analytics_state`/`post_analytics_state`; make overlay write atomic via `temp_path.write_bytes` + `os.replace`; expose helper to normalize `frame_width` default 1920.
- `worker/hls_motion_yolo_worker_events.py` — add helpers `_resolve_frame_size`, `_scale_norm_points`, include `sample_fps`/`effective_fps` snapshot in `post_state` metadata; compute single `crossing_snapshot = crossing_overlay_summary()` per frame and reuse for overlay and state; ensure `overlay_rev = frame_no`; expose `effective_fps` via `PerformanceTracker`.
- `worker/ubuntu_worker_entrypoint.py` — change `post_state` queue to hold `(metadata, overlay_bytes)` with immutable copy (read file into bytes before enqueue); background thread writes bytes atomically; fix `_publish_queue` coalescing to keep latest state bytes; record inference timing via `_perf_tracker`.
- `worker/detection_performance.py` — keep windowed FPS, expose `snapshot()` already, ensure thread-safe increment.
- `deploy/worker/ubuntu/configure-analytics-profiles.py` — preserve explicit SAMPLE_FPS=15 if present, otherwise default 10; never fallback to 704; already HD but verify FPS preservation.
- `deploy/worker/ubuntu/road-worker.env.example` / `observed-worker-runner.py` / `schemas/telemetry.schema.json` — document and parse `sample_fps`/`effective_fps`/`overlay_rev`.

## Decisions

- D1: One frame → one crossing snapshot reused for both overlay and state to guarantee sync.
- D2: Queue immutable bytes not path to avoid mutable file race; background thread does atomic temp+rename on VPS via API layer.
- D3: Frontend preloads next overlay into offscreen Image and swaps only on `load` with revision monotonic check.
- D4: Road CSS keeps 1920/1080 aspect but panel height becomes `auto` with stage `aspect-ratio` and no vertical auto margins that create bands.
- D5: FPS: configured `SAMPLE_FPS` shown as `sample_fps`, measured as `effective_fps` from tracker; Road UI shows both.
- D6: A crossing state is a value snapshot, not a live mapping view; both snapshot construction and the asynchronous publisher boundary sever nested references.

## Affected contours

- VPS: REQUIRED
- Ubuntu Worker/relay: REQUIRED

## Validation

- Unit: normalized speed lines roundtrip, legacy fallback scale, atomic publish queue immutability, telemetry schema, layout markers.
- Integration: state contains frame_width/height + sample/effective fps + overlay_rev.
- Manual: Road A/B visible, resolution badge, overlay advances with counter, no bands.

## Test design

- TEST-051-001 | Covers: AC-001, R1 | Level: unit | Priority: P0 | Evidence: `test_roi_normalization` extension — ROAD normalized draw + legacy fallback 704→1920 | Coverage: COVERED
- TEST-051-002 | Covers: AC-002, R5 | Level: unit | Priority: P0 | Evidence: `test_frontend_contract` — Road frameMeta resolution + state fields | Coverage: COVERED
- TEST-051-003 | Covers: AC-003, R2 | Level: unit | Priority: P0 | Evidence: `test_detection_runtime_optimization` + `test_line_crossing` — single snapshot reuse, atomic replace, queue immutability | Coverage: COVERED
- TEST-051-004 | Covers: AC-004, R3 | Level: unit | Priority: P0 | Evidence: frontend layout test — no `--h:748px` fixed bands, stage fit | Coverage: COVERED
- TEST-051-005 | Covers: AC-005, R5 | Level: unit | Priority: P0 | Evidence: `test_ubuntu_worker_observability` — effective_fps published | Coverage: COVERED
- TEST-051-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: `discover` + validators + MIXED Quality | Coverage: COVERED
- TEST-051-007 | Covers: AC-003, AC-004 | Level: runtime-manual | Priority: P1 | Evidence: visual Road after deploy | Coverage: RUNTIME-MANUAL | Reason: visual
- TEST-051-008 | Covers: AC-003, NFR-051-006 | Level: unit | Priority: P0 | Evidence: mutate live per-class counters after snapshot and mutate caller metadata after queue enrichment; captured values must remain unchanged and totals must equal class sums | Coverage: COVERED

## Correct-course check

- Adjacent-stage review: COMPLETE (speed lines coord contract, overlay publish/state, API atomic, FPS telemetry, panel layout)
- Trigger: EVIDENCE_CONTRADICTION — production Road class sums exceeded direction totals after #297 deployment
- Issue impact: #296 restores Road visibility/sync/fit and clarifies FPS without formula change
- Specification impact: R1-R6 add presentation/publish hardening
- Plan impact: MIXED deployment, transaction audit unchanged
- Tasks impact: traceability AC-001..006 → TASK-051-01/02
- Authorization impact: NONE — fresh receipt src-auth-051 covers listed files
- Follow-up: deploy the immutable-snapshot repair and verify the directional sum invariant in production Road state; future optional: merge overlay_rev into persisted telemetry trend

## Runtime feedback

- Initial MIXED deployment succeeded, but runtime acceptance exposed a shallow-copy race in nested crossing metadata. The repair remains inside the original #296 scope and changes no crossing formula.

## Deployment transaction audit

Required: runtime deployment REQUIRED (MIXED).

- TX-051-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport | Retry: after policy correction | Rollback: NOT REQUIRED | Evidence: autonomous log
- TX-051-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: verify_source_protection fails | Retry: after remediate | Rollback: NOT REQUIRED | Evidence: verify_source_protection output
- TX-051-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous VPS/Worker serving | Retry: rerun contour | Rollback: redeploy c170c7c | Evidence: deployment-manifest MIXED runtime_verified
- TX-051-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified false blocks DONE | Retry: rerun verification | Rollback: c170c7c | Evidence: manifest checks
- TX-051-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing | Retry: rerun upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-051-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: tmp stale | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-051-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: audit missing blocks DONE | Retry: rerun audit | Rollback: NOT REQUIRED | Evidence: execution audit v1
- TX-051-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual redeploy c170c7c | Rollback: itself | Evidence: rollbackTarget hash
