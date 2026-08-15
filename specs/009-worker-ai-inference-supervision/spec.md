# Specification: Worker AI inference supervision

- Issue: #159

## Product outcome

The Ubuntu Worker must not allow a stuck YOLO inference/tracking call to freeze
media, overlay, or state progression. Production evidence first showed the exact
`e7fb93319c951408a126757ad5554378e5cdce63` candidate stopping at two rendered
frames and one successful state post after RTSP input had already moved to
bounded FFmpeg/TCP. The subsequent AI-supervision candidate
`c73c6e048399ff5985918348c028d3f9a6a2ca89` also failed closed before reaching
an AI-ready runtime baseline and was automatically restored to the previous
Worker. Source inspection of that failed candidate identified boundedness and
activation-budget defects inside the new AI supervisor itself.

## User scenarios

1. When inference is healthy, operators continue receiving the same tracked
   vehicle detections, ROI filtering, speed semantics, events, and annotated
   frames.
2. When a `model.track(...)` call stalls, operators continue receiving fresh
   camera overlays and runtime state instead of the entire Worker freezing.
3. During an exact deployment, the release is not committed active unless two
   consecutive bounded AI startup inferences succeed on the same persistent
   child that will process production frames, and frame/state counters
   subsequently advance.
4. If activation fails, the existing updater restores the previous exact Worker
   release automatically.

## Requirements

1. Ubuntu YOLO inference runs in a dedicated persistent child process rather
   than in the media/state process.
2. The child continues to call `model.track(..., persist=True, tracker=...)` and
   returns the same detection fields consumed by the existing Worker.
3. CUDA device selection is explicit for the Ubuntu production path.
4. Each inference request has one absolute bounded deadline covering both the
   request write and the response read. Pipe backpressure, timeout, child exit,
   protocol failure, or inference exception must not block the parent
   indefinitely.
5. On inference failure the parent terminates/recreates only the AI child,
   enters bounded backoff, and returns an empty detection set for the affected
   frame. Media overlay and state posting continue.
6. Startup executes two consecutive bounded blank-frame inference calls on the
   same child to prove persistent tracking can advance more than once. The
   validated child is retained for production frames so `AI inference ready`
   refers to the process that actually passed the self-test. Blank frames avoid
   introducing synthetic vehicle tracker state.
7. After any runtime child restart, the first inference may use the bounded
   startup timeout while the replacement child warms; subsequent calls use the
   normal inference deadline.
8. Worker heartbeat records AI readiness, successes, failures, and child
   restarts without recording media URLs, API tokens, or protected env values.
9. Exact activation requires AI readiness with at least two successful startup
   inferences plus subsequent frame and successful state-post progression. The
   deployment wait budget must be longer than the bounded two-step AI startup
   budget and initial frame/state progression window.
10. Failure of any activation gate remains fail-closed and the existing updater
    restores the previous exact Worker release.
11. YOLO model architecture, confidence policy, tracker algorithm, vehicle
    allow-list, ROI filtering, speed calculation, event formulas, and API/event/
    storage schemas remain unchanged.

## Acceptance criteria

- Source tests prove the AI process boundary, absolute write/read deadline,
  restart/backoff, persistent tracker call, explicit device, two-step same-child
  self-test, warm-child semantics, and heartbeat contract.
- The activation verifier rejects frame/state progress when fewer than two
  successful AI startup inferences are present.
- The updater gives the bounded AI startup enough time to establish readiness,
  then accepts only after both frame and successful state-post counters grow
  after a baseline.
- Existing RTSP resilience, calibration-overlay ownership, ROI filtering,
  tracking data shape, speed semantics, and API schemas remain unchanged.
- PR Validation, Quality integration, and Worker packaging pass on the exact
  final head.
- Production deployment requires a fresh `PRODUCTION APPROVED <merged-sha>`.

## Runtime feedback

Production attempt `c73c6e048399ff5985918348c028d3f9a6a2ca89` failed with
`reason=no_exact_running_baseline`, `ai_inference_ready=false`, and
`ai_inference_success_count=0`; the updater restored
`50efe6ff687129a90d4a939710d98857cc6bad2c`. The failed implementation started
its inference timeout only after blocking writes to the child pipe, allowed up
to two startup calls whose combined budget exceeded the 45-second activation
window, and discarded the self-tested child before production. Those defects
are corrected within this existing approved outcome. Browser/runtime acceptance
still requires sustained fresh Worker frames and AI progression before Issue
#159 proceeds to VPS/frontend rollout.
