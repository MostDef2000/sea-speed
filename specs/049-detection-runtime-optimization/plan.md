# Plan: Detection runtime optimization — FP16, 10-15 FPS, telemetry, motion gate

- Issue: #291
- Specification: specs/049-detection-runtime-optimization/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-049-001 | Category: PERF | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: bounded queue + FP16 parity guard + fallback to FP32 | Validation: effective FPS benchmark + telemetry | Residual risk: 2 | Owner: worker | Status: MITIGATED
- RISK-049-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: class-filter flag off by default + coordinate parity test | Validation: parity unit test | Residual risk: 1 | Owner: worker | Status: MITIGATED
- RISK-049-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: motion gate always_on gated mode preserved via env allowlist | Validation: road gate unit test | Residual risk: 1 | Owner: worker | Status: ACCEPTED

## Architecture

Ubuntu Worker shared executable `worker/**` behind bounded media/optimised inference:

- `worker/analytics_profiles.py` — raise default `sample_fps` to 10.0 (water 10, road selectable 10–15 via env), keep `image_size=960`, `confidence=0.15`, ensure `frame_width/height 1920x1080`; add `YOLO_HALF`/`YOLO_CLASSES` knobs and Road `MOTION_GATE_MODE` flag.
- `worker/ubuntu_worker_entrypoint.py` — implement single-slot latest-frame reader for both RTSP FFmpeg and core reader (bounded queue=1, drop-oldest), add frame ingest timestamp, compute frame-age; launch inference strictly ordered per camera. Offload JPEG/HTTP to background thread-pool/queue; keep ByteTrack ordered.
- `worker/ubuntu_ai_inference_worker.py` — add `YOLO_HALF=true` path (`model.half()` / `half=True` in track), optional class list injection when `YOLO_CLASSES` set after validating `model.names` mapping; fallback to FP32 on error.
- `worker/hls_motion_yolo_worker_events.py` — integrate `detection_performance` timers around decode/inference/JPEG/HTTP stages; expose `MOTION_GATE_MODE` (`always_on` vs `gated`) and wire `prepare_roi_processing_frame` unchanged; road gate relaxed via `MOTION_THRESHOLD/MIN_AREA/ACTIVE_SECONDS` allowlist.
- `worker/detection_performance.py` (new) — lightweight stage timer, sliding-window effective FPS, frame-age gauge, p95 calc, structured log emitter; no external deps.
- `deploy/worker/ubuntu/configure-analytics-profiles.py` — fix HD reconciliation: never propagate 704×576 to Road, force 1920×1080 unless protected explicit override differs; preserve motion/FPS/image-size allowlist into generated `road-worker.env`/`water env`.
- `deploy/worker/ubuntu/observed-worker-runner.py` — forward new telemetry counters to health endpoint.
- `deploy/worker/ubuntu/road-worker.env.example` — update to 1920×1080 10–15 FPS example with motion/ FP16 knobs documented.

Preparation `prepare-yolo-model.py` optionally probes FP16 availability but does not change artifact.

## Decisions

- D1: One model per Water/Road process kept (two copies on same GPU). Sharing via scheduler deferred — out-of-scope for this bounded scope.
- D2: FP16 with parity guard: if `model.half()` parity fails in unit test, runtime auto-falls back to FP32 and logs warning — no accuracy regression.
- D3: Class filtering behind feature flag `YOLO_CLASSES_FILTER=true`; off by default until parity test passes on target GPU.
- D4: Latest-frame queue is size=1 overwrite semantics, not unbounded — prevents FFmpeg pipe growing latency.
- D5: Background publishing uses coalesced overlay/state (latest wins) + reliable bounded queue for events/passages — avoids blocking inference on 10s HTTP timeout.

## Affected contours

- VPS: NOT REQUIRED
- Ubuntu Worker/relay: REQUIRED (Water + Road)

## Validation

- Unit: `detection_performance` timers + parity (FP16 vs FP32 coords), frame size/timing, motion gate modes, bounded-queue drop, class filter mapping.
- Integration: existing `test_frame_quality`, `test_ubuntu_worker_ai_supervision`, `test_water_detection_pipeline` extended with effective FPS assumptions.
- Manual benchmark: 60s Water + 60s Road local clips (not committed) before/after telemetry via helper script (docs only).
- Validators + discover green; exact-head CI.

## Test design

- TEST-049-001 | Covers: AC-001, R3 | Level: unit | Priority: P0 | Evidence: `test_frame_quality` — 1920×1080 guarantee + config generation 704×576 regression | Coverage: COVERED
- TEST-049-002 | Covers: AC-002, R1, R2 | Level: unit | Priority: P0 | Evidence: `test_detection_runtime_optimization` — bounded queue drops stale, publishing off critical path, effective FPS calc | Coverage: COVERED
- TEST-049-003 | Covers: AC-003, R5 | Level: unit | Priority: P0 | Evidence: `test_detection_runtime_optimization` — FP16 parity ±1px vs FP32 mock | Coverage: COVERED
- TEST-049-004 | Covers: AC-004, R6 | Level: unit | Priority: P0 | Evidence: parity class-filter vs post-filter | Coverage: COVERED
- TEST-049-005 | Covers: AC-005, R8 | Level: unit | Priority: P0 | Evidence: road gate always_on vs gated behavior | Coverage: COVERED
- TEST-049-006 | Covers: AC-006, R4 | Level: unit | Priority: P0 | Evidence: `detection_performance` stage timing telemetry test | Coverage: COVERED
- TEST-049-007 | Covers: AC-007 | Level: unit | Priority: P0 | Evidence: `python -m unittest discover` + validators | Coverage: COVERED
- TEST-049-008 | Covers: AC-008 | Level: runtime-manual | Priority: P1 | Evidence: benchmark Water/Road before/after + deployment manifest runtime_verified | Coverage: RUNTIME-MANUAL | Reason: hardware + clips

## Correct-course check

- Adjacent-stage review: COMPLETE (media reader, inference worker, frame quality, prepare-model, observed runner, road env)
- Trigger: NONE
- Issue impact: #291 replaces implicit 5 FPS with measurable 10–15 FPS telemetry-driven pipeline
- Specification impact: R1–R8 codify bounded intake, decoupled publishing, HD guarantee, FP16/class filtering/ByteTrack, motion gate
- Plan impact: Ubuntu REQUIRED, 8-stage transaction audit required, token rotation tracked as separate follow-up
- Tasks impact: traceability AC-001..008 → TASK-049-01/02
- Authorization impact: NONE — fresh receipt src-auth-049 covers listed worker/deploy/test files
- Follow-up: benchmark on local clips, runtime acceptance on both profiles

## Runtime feedback

To be recorded after Ubuntu Worker deployment acceptance (effective FPS, dropped, inference_ms, HD confirmed).

## Deployment transaction audit

Required: runtime deployment REQUIRED (Ubuntu Worker Water+Road).

- TX-049-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous worker serving | Retry: after policy/state correction | Rollback: NOT REQUIRED | Evidence: autonomous workflow log + policy decision id
- TX-049-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection/Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED | Evidence: verify_source_protection.py output
- TX-049-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous worker keeps serving on health gate failure | Retry: rerun failed contour | Rollback: redeploy rollbackTarget 8b94640 | Evidence: deployment-manifest Ubuntu runtime_verified
- TX-049-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks DONE | Retry: rerun verification | Rollback: rollback target | Evidence: manifest checks array (frame size, telemetry, inference)
- TX-049-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing blocks completion | Retry: rerun evidence upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json, quality-evidence.json
- TX-049-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp remains | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-049-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deploy without audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED | Evidence: typed execution audit v1
- TX-049-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual decision + redeploy known-good 8b94640 | Rollback: itself is rollback path | Evidence: rollbackTarget hash
