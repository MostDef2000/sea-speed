# Plan: Worker AI inference supervision

Specification: `specs/009-worker-ai-inference-supervision/spec.md`

## Architecture

Keep the already merged bounded FFmpeg RTSP reader as the media boundary and add
an independent AI execution boundary:

- `worker/ubuntu_ai_inference_worker.py` owns the real `YOLO` model and
  persistent `model.track` state. It accepts raw BGR frames over a private
  length-prefixed stdin/stdout protocol and returns JSON detections only.
- `worker/ubuntu_worker_entrypoint.py` owns `BoundedYoloSupervisor`. It sends one
  frame at a time, reads responses with `select` and an absolute deadline, and
  can kill/recreate the inference child without terminating the media loop.
- The legacy worker module keeps ownership of motion filtering, ROI filtering,
  speed estimation, event generation, overlay rendering, and state posting.
  Only model construction and `detect_vehicles` are substituted by the Ubuntu
  entrypoint.

## Decisions

- Preserve `model.track(... persist=True ...)` and the configured tracker rather
  than replacing tracking with prediction-only inference.
- Use a persistent child so healthy tracking state survives between real frames.
- On timeout, return an empty detection set for that frame and enter bounded
  backoff; fresh frame/state delivery is preferred over freezing the Worker.
- Execute two synthetic startup inferences through the same child to detect the
  observed second-call stall class, then restart the child before production
  frames to clear synthetic tracker state.
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
- Focused unit tests for source boundary contracts and activation-gate behavior.
- Full repository PR Validation and Quality integration.
- Exact Worker package/provenance workflow.
- No production execution before fresh exact-SHA production approval.

## Runtime feedback

After merge, the existing exact updater must observe `ai_inference_ready=true`,
at least two AI successes, then increasing frame and state-post counters. Any
failure remains fail-closed and restores the previous release. A passing updater
is followed by sustained UI/fresh-frame acceptance and real detections when
motion is available. Only after Worker acceptance does Issue #159 continue to
the VPS/frontend rollout on the same exact SHA.
