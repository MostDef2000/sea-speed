# Feature Specification: Worker RTSP Runtime Resilience

- Feature: 008-worker-rtsp-runtime-resilience
- Issue: #159
- Status: Accepted supporting runtime remediation

## Product outcome

Ubuntu Worker uses bounded FFmpeg RTSP-over-TCP ingestion and exact-release activation cannot become authoritative without real frame/state progression. Failed candidates restore the previous exact release when available.

## User scenarios

1. Production RTSP continuously advances frames/state.
2. Reader timeout/EOF/failure recreates the bounded FFmpeg reader.
3. Exact release commits active only after exact source + frame/state progression.
4. Failed candidate restores previous unit/source.

## Requirements

- RTSP input uses FFmpeg subprocess with TCP and bounded read/restart behavior;
- non-RTSP behavior remains compatible;
- logs redact credential-bearing media data;
- pinned runtime dependencies and CUDA torch/torchvision compatibility are verified;
- updater requires exact heartbeat/frame/state progression and restores prior release on failure;
- ROI/speed/detection/auth/API behavior unchanged.

## Acceptance criteria

Source tests cover reader boundedness, pinned runtime and updater restore/progression gates. Production Issue #159 ultimately reached a stable exact Ubuntu Worker with sustained frame/state/AI progression.

## Runtime feedback

Initial production attempts exposed PyAV/RTSP stalling and activation-gate weaknesses. The accepted Issue #159 Worker runtime incorporated bounded FFmpeg/TCP ingestion plus later AI-supervision corrections. This sub-feature is accepted supporting architecture; Issue #159 is closed completed.
