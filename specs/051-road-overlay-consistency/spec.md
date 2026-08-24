# Spec: Road overlay consistency, UI fit and FPS evidence

- Issue: #296
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay + Frontend)

## Product outcome

Road operator sees stable AI overlay that is atomically synchronized with crossing counter and frame-bound state, speed lines A/B remain visible at calibrated road positions on 1920x1080, processed resolution is displayed like Water, main image fits naturally without large empty bands, and configured vs measured FPS are explicitly reported instead of assuming 15.

## User scenarios

- Operator sets Road speed lines A/B on HD preview — lines remain visible after reload and render with A/B labels at same lane positions where speed is measured; speed events keep working.
- Operator opens Road — header meta shows processed resolution 1920x1080 alongside frame number/time like Water does.
- Road receives many vehicles — AI overlay CROSSINGS number advances in lockstep with crossing counter panel; no frozen overlay while counter grows.
- Operator on desktop or narrow viewport — main Road 16:9 stage fills its panel without large top/bottom empty bands, but canvas overlays stay aligned.
- Operator asks about detection FPS — UI/state shows configured sample FPS (from profile/env) and measured effective inference FPS separately.

## Requirements

- R1: Fix Road speed-lines coordinate contract: worker measurement prefers normalized `line_a_norm`/`line_b_norm` (already done in 050), frontend store/edit/persist normalized, render via `x_norm * displayWidth`; legacy absolute fallback must use 1920x1080 reference not 704x576; labels A/B visible outside edit mode.
- R2: Show processed image resolution on Road like Water: publish `frame_width`/`frame_height` (and overlay revision) in `/state` for both cam1 and road1, frontend displays `1920×1080` or natural overlay size.
- R3: Ensure atomic overlay/state/crossing synchronization: worker computes one crossing snapshot per published frame, encodes overlay, then queues immutable bytes + metadata + frame_no/revision atomically; VPS overlay replacement is atomic (temp + rename); frontend preloads image and swaps only after load, versioned by `overlay_rev`/`frame_no`.
- R4: Fix Road main image letterboxing: stage/panel fills available height without centering empty bands; image uses `object-fit: contain` or `cover` policy consistent with worker's 1920x1080 forced scale, while `roiCanvas`/`speedLinesCanvas` transforms remain aligned.
- R5: Expose FPS evidence: `SAMPLE_FPS` (configured) and measured `effective_fps`/`p95_inference_ms` from PerformanceTracker; include in state/telemetry and surface in Road UI diagnostics; verified on 1920x1080 processing.
- R6: No detection/tracking/calibration/speed/crossing formula change; single road regression source is presentation/publish.

## NFR assessment

- NFR-051-001 | Area: correctness | Target: normalized speed lines roundtrip HD position ±1px and remain visible after reload | Validation: unit test norm→abs→display | Evidence: tests/test_roi_normalization.py, test_frontend_contract.py | Status: PASS
- NFR-051-002 | Area: reliability | Target: overlay/counter never diverge >1 frame; no stale mutable path race | Validation: queue immutability + atomic replace test | Evidence: tests/test_detection_runtime_optimization.py | Status: PASS
- NFR-051-003 | Area: usability | Target: Road main stage has no >40px empty top/bottom bands at 720px width, canvas alignment preserved | Validation: pixel/layout assertion + visual | Evidence: frontend contract test | Status: PASS
- NFR-051-004 | Area: observability | Target: state exposes both sample_fps and effective_fps with p95 | Validation: schema + state test | Evidence: tests/test_ubuntu_worker_observability.py | Status: PASS
- NFR-051-005 | Area: compatibility | Target: old absolute payloads still rendered correctly via 1920 fallback | Validation: legacy absolute draw test | Evidence: test_roi_normalization.py | Status: PASS

## Acceptance criteria

- AC-001: Road normalized speed lines save→GET→reload stay at same lane and are drawn with A/B labels even when not editing; legacy 704 absolute lines still map correctly after inference fix.
- AC-002: Road frameMeta/stateJson show `1920×1080` (or naturalWidth×naturalHeight) alongside frame_no; Water parity.
- AC-003: Crossing summary in overlay JPEG increments together with `/state` crossings and crossings panel; queue holds immutable bytes, VPS uses atomic replace, frontend swaps only after image load with revision guard.
- AC-004: Main Road image fills panel without large letterboxing; canvases scale with same transform; no regression in ROI drawing.
- AC-005: State contains `sample_fps`, `effective_fps`, `p95_inference_ms`, `frame_width/height`, `overlay_rev`; Road UI surfaces configured vs measured; 15 FPS claim validated as not default.
- AC-006: Suite + validators PASS; MIXED runtime_verified.

## Runtime feedback

To be recorded after MIXED deployment acceptance (visual A/B, resolution, sync, fit, FPS).
