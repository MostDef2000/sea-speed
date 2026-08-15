# Plan: Worker AI inference supervision

Specification: `specs/009-worker-ai-inference-supervision/spec.md`

## Architecture

Keep the bounded FFmpeg RTSP reader as the media boundary and retain an
independent AI execution boundary:

- `worker/ubuntu_ai_inference_worker.py` owns the real `YOLO` model and
  persistent `model.track` state. It accepts raw BGR frames over a private
  length-prefixed stdin/stdout protocol and returns JSON detections only.
- `worker/ubuntu_worker_entrypoint.py` owns `BoundedYoloSupervisor`. It sends one
  frame at a time and applies one absolute deadline across both pipe writes and
  response reads, so a child that has not yet drained stdin cannot block the
  parent before timeout accounting starts.
- The same child that passes the two startup inference calls remains in service
  for production frames. Runtime replacement children receive one bounded warm
  call before normal inference deadlines apply.
- The canonical Worker venv contains the ByteTrack linear-assignment dependency
  before activation. The systemd service disables Ultralytics runtime
  auto-install, so inference cannot mutate a release environment on first use.
- The exact updater restores the previous unit fail-closed. Before restart it
  clears the service failed/start-limit state so candidate restart storms cannot
  prevent rollback.
- The legacy worker module keeps ownership of motion filtering, ROI filtering,
  speed estimation, event generation, overlay rendering, and state posting.
  Only model construction and `detect_vehicles` are substituted by the Ubuntu
  entrypoint.

## Decisions

- Preserve `model.track(... persist=True ...)` and ByteTrack rather than
  replacing tracking with prediction-only inference.
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
- Keep the exact activation observation window at 90 seconds so it covers the
  bounded startup sequence plus initial frame/state progression.
- Use explicit YOLO device selection (`YOLO_DEVICE`, default `0`) in the Ubuntu
  path.
- Pin `lap==0.5.13`: it satisfies the Ultralytics ByteTrack runtime requirement
  and has a CPython 3.14 Linux wheel for the production interpreter. Verify its
  version/import with the rest of the canonical runtime.
- Set `YOLO_AUTOINSTALL=false` in the systemd unit. Dependency resolution is a
  preparation concern, not a production service concern.
- Run `systemctl reset-failed` before automatic restore restarts the previous
  exact Worker.

## Affected contours

Worker runtime only. Files under `deploy/worker/ubuntu/` change, plus focused
tests and this SDD. YOLO/ByteTrack algorithms, VPS/frontend source, API schemas,
camera/source configuration, auth topology, ROI/speed formulas, and Windows
Worker behavior are outside scope.

## Validation

- Shell syntax for the exact updater and installer contracts.
- Focused source-contract tests for the pinned tracker dependency, disabled
  Ultralytics auto-install, and reset-before-restart rollback ordering.
- Existing AI supervision tests for bounded request writes, same-child startup
  validation, warm-child timeout selection, and activation-gate budget.
- Full repository PR Validation and Quality integration.
- Exact Worker package/provenance workflow.
- No production execution before fresh exact-SHA production approval.

## Runtime feedback

The `e5d4d25b731328951c7a2178c244b99c5ad64372` activation still failed before
any AI success. Source inspection found the clean runtime omitted the lazily
required ByteTrack `lap` dependency while Ultralytics runtime auto-install was
enabled by default. The same failed candidate consumed the systemd start-rate
budget, so the updater's first automatic restore could not restart the previous
unit until the operator cleared the failed state.

The next merged candidate therefore closes runtime dependencies before service
start, disables runtime package installation, and makes rollback start-limit
safe. It must establish `ai_inference_ready=true`, at least two AI successes on
the retained child, then increasing frame and state-post counters. Only after
sustained Worker/UI acceptance does Issue #159 continue to VPS/frontend rollout
on the same exact SHA.
