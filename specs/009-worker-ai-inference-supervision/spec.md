# Specification: Worker AI inference supervision

- Issue: #159

## Product outcome

The Ubuntu Worker must not allow a stuck YOLO inference/tracking call to freeze
media, overlay, or state progression. Production evidence shows the exact
`e7fb93319c951408a126757ad5554378e5cdce63` candidate still stopped at two
rendered frames and one successful state post after RTSP input had already moved
to bounded FFmpeg/TCP. The updater rejected that candidate and restored the
previous release, localizing the remaining synchronous barrier to the AI
inference/tracking execution path after motion activation.

## User scenarios

1. When inference is healthy, operators continue receiving the same tracked
   vehicle detections, ROI filtering, speed semantics, events, and annotated
   frames.
2. When a `model.track(...)` call stalls, operators continue receiving fresh
   camera overlays and runtime state instead of the entire Worker freezing.
3. During an exact deployment, the release is not committed active unless two
   consecutive bounded AI startup inferences succeed and frame/state counters
   subsequently advance.
4. If activation fails, the existing updater restores the previous exact Worker
   release automatically.

## Requirements

1. Ubuntu YOLO inference runs in a dedicated persistent child process rather
   than in the media/state process.
2. The child continues to call `model.track(..., persist=True, tracker=...)` and
   returns the same detection fields consumed by the existing Worker.
3. CUDA device selection is explicit for the Ubuntu production path.
4. Each inference request has a bounded deadline. Timeout, child exit, protocol
   failure, or inference exception must not block the parent media loop.
5. On inference failure the parent terminates/recreates only the AI child,
   enters bounded backoff, and returns an empty detection set for the affected
   frame. Media overlay and state posting continue.
6. Startup executes two consecutive bounded synthetic inference calls to prove
   that persistent tracking can advance more than once. The tracker child is
   reset after this self-test so synthetic state cannot leak into production
   tracks.
7. Worker heartbeat records AI readiness, successes, failures, and child
   restarts without recording media URLs, API tokens, or protected env values.
8. Exact activation requires AI readiness with at least two successful startup
   inferences plus subsequent frame and successful state-post progression.
9. Failure of any activation gate remains fail-closed and the existing updater
   restores the previous exact Worker release.
10. YOLO model architecture, confidence policy, tracker algorithm, vehicle
    allow-list, ROI filtering, speed calculation, event formulas, and API/event/
    storage schemas remain unchanged.

## Acceptance criteria

- Source tests prove the AI process boundary, deadline, restart/backoff,
  persistent tracker call, explicit device, two-step self-test, and heartbeat
  contract.
- The activation verifier rejects frame/state progress when fewer than two
  successful AI startup inferences are present.
- The verifier accepts only after AI startup progression is present and both
  frame and successful state-post counters grow after a baseline.
- Existing RTSP resilience, calibration-overlay ownership, ROI filtering,
  tracking data shape, speed semantics, and API schemas remain unchanged.
- PR Validation, Quality integration, and Worker packaging pass on the exact
  final head.
- Production deployment requires a fresh `PRODUCTION APPROVED <merged-sha>`.

## Runtime feedback

Production acceptance is performed only after merge and fresh exact-SHA
production authorization. The repo-owned updater is authoritative: it must
report a passing runtime gate or restore the previous release. Browser/runtime
acceptance then verifies fresh frames remain live and detections can progress
when motion is available before Issue #159 proceeds to VPS/frontend rollout.
