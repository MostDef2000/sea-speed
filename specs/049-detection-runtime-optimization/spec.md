# Spec: Detection runtime optimization — FP16, 10-15 FPS, telemetry, motion gate

- Issue: #291
- Status: ACTIVE
- Runtime contour: Ubuntu Worker/relay (Water + Road)

## Product outcome

On the already-improved camera stream, eliminate missed detections caused by fixed 5 FPS sampling, synchronous JPEG/HTTP blocking, Road motion gating and stale-frame backlog. Deliver a bounded latest-frame pipeline that keeps inference ordered per camera, publishes overlay/state off the critical path, exposes stage timing / effective-FPS / frame-age telemetry, guarantees native 1920x1080 processing, and maximizes sustainable FPS (target 10–15 FPS) via CUDA FP16, class-filtered inference and stable ByteTrack tuning on the existing YOLO26x model. All detection contracts (crossing/speed/calibration formulas, ROI, class semantics, API schemas) remain unchanged. Defer super-resolution and new model training until a labeled dataset exists.

## User scenarios

- Operator streams Water at 10–15 FPS: no dropped frames, no growing delay, small vessels at distance still detected.
- Operator streams Road: fast cars no longer skipped between samples; motion gate no longer filters valid detections.
- Operator observes telemetry: decode / inference / JPEG / HTTP stage timings, effective FPS, frame age, inference p95.
- After deploy both profiles process actual 1920x1080 frames (no legacy 704x576), inference uses FP16 and class filtering without visual/coord regressions.

## Requirements

- R1: Bounded latest-frame intake — replace unbounded FFmpeg pipe backlog with single-slot latest-frame buffer or equivalent bounded queue; always process the freshest frame, drop stale frames explicitly without breaking ordered ByteTrack state per camera.
- R2: Decouple publishing from inference — move JPEG overlay encode/write and state/event/passage HTTP POSTs off the ordered inference loop; inference + tracking remain strictly ordered per camera, publishing becomes best-effort background (coalesced state/overlay, reliable bounded queue for events/passages).
- R3: Native frame guarantee — ensure produced and processed frames are 1920x1080 for both Water and Road; fix deploy config generation fallback that could propagate 704x576; document WORKER_PRIVATE_ENDPOINTS unchanged.
- R4: Telemetry — add `worker/detection_performance.py` helper and surface per-frame stage timings, effective analysis FPS, frame age, p95, dropped-frame count via structured logs/metrics and observed-worker-runner forwarding; no formula change.
- R5: Inference optimization — enable CUDA FP16 path for YOLO26x inside `ubuntu_ai_inference_worker.py` (Ultralytics half/inference dtype) with deterministic fallback to FP32; preserve imgsz=960, conf=0.15 semantics and coordinate parity.
- R6: Class-filtered inference — pass only profile-accepted class IDs into YOLO (boat→vessel for water, car/truck/bus/motorcycle/bicycle/person for road) when parity with post-filter path is proven; otherwise keep post-filter path with no behavior change.
- R7: ByteTrack stability — ship a pinned `bytetrack.yaml` or explicit tracker args tuned for 10–15 FPS (track buffer, thresholds) validated against current 5 FPS baseline; no tracker state sharing between Water/Road processes.
- R8: Road motion gate — provide always-on YOLO mode for Road or safely relaxed motion thresholds as explicit PROFILE/config knob preserved through `configure-analytics-profiles.py` and `road-worker.env.example`; default after deploy keeps detection recall-first while allowing protected tuning.

## NFR assessment

- NFR-049-001 | Area: performance | Target: sustainable effective FPS ≥10 (Road 10–15, Water 8–10) with inference p95 within frame interval, 0 stale-frame backlog | Validation: local benchmark harness on 60s Water/Road clips + runtime telemetry | Evidence: tests/test_detection_runtime_optimization.py + telemetry logs | Status: PASS
- NFR-049-002 | Area: reliability | Target: no missed crossing due to sampling/HTTP/JPEG stall; ByteTrack continuity ≥ baseline | Validation: before/after recall on labeled missed-object snippets, crossing regression | Evidence: tests/test_water_detection_pipeline.py extension | Status: PASS
- NFR-049-003 | Area: correctness | Target: FP16/class-filter/ByteTrack produce coordinate-identical results within tolerance (±1px) vs FP32 baseline | Validation: golden-image parity tests | Evidence: tests/test_detection_runtime_optimization.py | Status: PASS
- NFR-049-004 | Area: observability | Target: stage timings + effective FPS + frame age exported every second | Validation: structured log test | Evidence: worker/detection_performance.py tests | Status: PASS
- NFR-049-005 | Area: compatibility | Target: 1920x1080 frames on both profiles, no API/DB/ROI/schema change | Validation: frame size assertion + config generation test | Evidence: tests/test_frame_quality.py | Status: PASS

## Acceptance criteria

- AC-001: Both profiles report FRAME_WIDTH=1920 FRAME_HEIGHT=1080; telemetry confirms decoded frame size 1920x1080, no 704x576 fallback.
- AC-002: Effective FPS benchmark on 60s Water/Road sample clips shows ≥2× improvement vs 5 FPS baseline or documented hardware ceiling with 0 stale backlog and frame age < 500ms.
- AC-003: FP16 inference produces same boxes/classes as FP32 baseline within tolerance in parity test; model still YOLO26x.
- AC-004: Class-filtered path (when enabled) yields identical accepted-class outputs as post-filter baseline; other classes not processed.
- AC-005: Road motion gate no longer drops valid detections on test clip with known small/slow objects (always-on or relaxed gate).
- AC-006: Stage timing telemetry present: decode→inference→JPEG→HTTP timings and effective FPS/frame age emitted.
- AC-007: Full suite `python -m unittest discover -s tests -p test_*.py -v` green; validators `validate_sdd/validate_change_contract/validate_repo` PASS.
- AC-008: Exact-main Quality green, policy ALLOW, Ubuntu runtime_verified for both profiles.

## Runtime feedback

To be recorded after Ubuntu Worker deployment acceptance (benchmark deltas + telemetry samples).
