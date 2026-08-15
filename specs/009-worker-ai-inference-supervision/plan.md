# Plan: Worker AI inference supervision

Specification: `specs/009-worker-ai-inference-supervision/spec.md`

## Architecture

Keep the bounded FFmpeg RTSP reader as the media boundary and retain an
independent AI execution boundary:

- `worker/ubuntu_ai_inference_worker.py` owns the real `YOLO` model and
  persistent `model.track` state. It accepts raw BGR frames over a private
  length-prefixed stdin/stdout protocol and returns JSON detections only.
- `worker/ubuntu_worker_entrypoint.py` owns `BoundedYoloSupervisor`. It sends one
  frame at a time and now applies one absolute deadline across both pipe writes
  and response reads, so a child that has not yet drained stdin cannot block the
  parent before timeout accounting starts.
- The same child that passes the two startup inference calls remains in service
  for production frames. Runtime replacement children receive one bounded warm
  call before normal inference deadlines apply.
- The legacy worker module keeps ownership of motion filtering, ROI filtering,
  speed estimation, event generation, overlay rendering, and state posting.
  Only model construction and `detect_vehicles` are substituted by the Ubuntu
  entrypoint.

## Decisions

- Preserve `model.track(... persist=True ...)` and the configured tracker rather
  than replacing tracking with prediction-only inference.
- Use a persistent child so healthy tracking state survives between real frames.
- Bound child stdin backpressure with `select` plus `os.write`; do not use a
  blocking buffered write before establishing the inference deadline.
- Execute two blank-frame startup inferences through the same child to detect
  the observed repeated-call stall class without introducing synthetic vehicle
  tracks. Do not discard that validated child before live frames.
- On timeout, return an empty detection set for that frame and enter bounded
  backoff; fresh frame/state delivery is preferred over freezing the Worker.
- Give a replacement child the startup deadline for its first call, then return
  to the normal inference deadline after a successful warm call.
- Increase the exact activation observation window to 90 seconds so it covers
  the bounded startup sequence plus initial frame/state progression instead of
  racing the allowed AI startup budget.
- Use explicit YOLO device selection (`YOLO_DEVICE`, default `0`) in the Ubuntu
  path.

## Affected contours

Worker runtime only. Files under `worker/` and `deploy/worker/ubuntu/` change,
plus focused tests and this SDD. VPS/frontend source, API schemas, camera/source
configuration, auth topology, ROI/speed formulas, and Windows Worker behavior
are outside scope.

## Validation

- Python compile for the entrypoint, inference child, observed runner, and
  runtime verifier.
- Focused source-contract tests for bounded request writes, same-child startup
  validation, warm-child timeout selection, and activation-gate budget.
- Full repository PR Validation and Quality integration.
- Exact Worker package/provenance workflow.
- No production execution before fresh exact-SHA production approval.

## Runtime feedback

The `c73c6e048399ff5985918348c028d3f9a6a2ca89` activation failed before any AI
success was observed and automatically restored the previous release. The next
merged candidate must establish `ai_inference_ready=true`, at least two AI
successes on the retained child, then increasing frame and state-post counters.
Any failure remains fail-closed and restores the previous release. Only after
sustained Worker/UI acceptance does Issue #159 continue to VPS/frontend rollout
on the same exact SHA.
