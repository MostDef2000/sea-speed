# Spec: Native frame quality for Water and Road (HD analysis + sharpness-aware best frame)

- Issue: #285
- Status: ACTIVE
- Runtime contour: Ubuntu Worker/relay

## Product outcome

Water and Road analytics run on native HD resolution instead of the legacy 704x576 daownscale. Frames sampled from HLS are kept at 1920x1080 (or stream native) and YOLO inference continues at imgsz 960 without pre-downscale information loss. Passage and event snapshots are written from full-resolution frames. Best-frame selection considers sharpness (Laplacian variance) alongside confidence and bbox area so blurry snapshots are not persisted.

## User scenarios

- Water vessel at distance is tracked — higher-res frame provides more pixels per vessel, small/ slow vessels are detected more reliably.
- Road vehicle/person crossing is counted — same HD improvement for road domain.
- Operator views passage/event registry — snapshots are high-resolution crops from HD frames, visibly sharper.
- Blurry frame during vessel passage does not overwrite a previously sharp best snapshot.

## Requirements

- R1: Analytics profiles MUST define per-profile frame dimensions (FRAME_WIDTH/FRAME_HEIGHT) defaulting to 1920x1080 for both water-v1 and road-v1, overridable via env.
- R2: Worker HLS reader MUST produce frames at the profile-configured resolution, not hard-coded 704x576.
- R3: Passage snapshot MUST be written from the full-resolution frame (1920x1080), JPEG quality 90 preserved.
- R4: Overlay and event snapshots MUST use the same HD source frames.
- R5: Worker.env.example MUST document new defaults.
- R6: Best-snapshot scoring MUST incorporate sharpness (Laplacian variance) — a candidate with low sharpness does not replace a sharper stored snapshot even if confidence*area is higher within improvement ratio threshold.

## NFR assessment

- NFR-046-001 | Area: accuracy | Target: effective input pixels per vessel increase ~7x (0.4 MP -> 2.07 MP) without changing YOLO imgsz | Validation: unit assertion of frame size defaults + sampling test | Evidence: tests/test_analytics_profiles.py, tests/test_frame_quality.py | Status: PASS
- NFR-046-002 | Area: performance | Target: YOLO inference time unchanged (imgsz 960), rawvideo pipe throughput increase to ~31 MB/s at 5 FPS accepted | Validation: profile test + sampler fps not regressed | Evidence: tests/test_analytics_profiles.py | Status: PASS
- NFR-046-003 | Area: correctness | Target: best snapshot not degraded by blur; sharpness metric prevents blurry overwrite | Validation: unit test with synthetic sharp/blurry crops | Evidence: tests/test_frame_quality.py | Status: PASS

## Acceptance criteria

- AC-001: water-v1 profile defaults FRAME_WIDTH=1920 FRAME_HEIGHT=1080.
- AC-002: road-v1 profile defaults FRAME_WIDTH=1920 FRAME_HEIGHT=1080.
- AC-003: HLS reader constructs ffmpeg scale filter from profile/env-resolved frame size.
- AC-004: Passage/event snapshots are crops from HD frames (sharpness-aware selection).
- AC-005: Sharpness metric (Laplacian variance) computed for candidate crops; low-sharpness candidate does not overwrite sharper stored snapshot.
- AC-006: worker.env.example documents new defaults.
- AC-007: Existing HLS/Tracker/YOLO behavior unchanged; no regression in tracking or event counts.

## Runtime feedback

To be recorded after Ubuntu Worker/relay deployment acceptance.
