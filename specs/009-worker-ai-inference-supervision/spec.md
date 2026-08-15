# Specification: Worker AI inference supervision

- Feature: 009-worker-ai-inference-supervision
- Issue: #159
- Status: Accepted supporting runtime remediation

## Product outcome

A stuck/unbootable YOLO tracking call cannot freeze media, overlay or state progression. Ubuntu AI inference runs in a persistent supervised child with bounded write/read deadlines, startup self-test and restart/backoff. Exact deployment accepts only a real AI-ready child plus subsequent frame/state progression.

## User scenarios

1. Healthy inference preserves existing detections/tracking/ROI/speed/events.
2. Stalled inference restarts only the AI child while media/state continues.
3. Activation requires two bounded startup inferences on the same retained child plus frame/state progression.
4. Runtime dependencies are closed before service start; service-time auto-install is disabled.
5. Failed candidate clears systemd start-limit state as needed and restores prior exact release.

## Requirements

- inference runs in a dedicated persistent child;
- `model.track(... persist=True ...)` behavior/data shape remains compatible;
- one absolute bounded deadline covers request write and response read;
- failure returns empty detections for that frame and recreates child with bounded backoff;
- startup proves two calls on the same retained child;
- heartbeat exposes non-secret AI readiness/success/failure/restart counters;
- runtime packages include lazy tracker dependency closure and disable service-time auto-install;
- updater activation waits longer than bounded startup and requires AI readiness + frame/state progression;
- automatic restore resets candidate-induced systemd failed/start-limit state;
- YOLO/ByteTrack/ROI/speed/event/API semantics remain unchanged.

## Acceptance criteria

Focused tests cover child supervision/deadlines/same-child self-test/dependency closure/restore semantics. Production Issue #159 ultimately established an exact Ubuntu Worker with `ai_inference_ready=true`, advancing frame/state counters and no acceptance-window AI failures.

## Runtime feedback

Several candidates failed closed before acceptance, revealing pipe boundedness, startup-budget, retained-child, lazy `lap` dependency and systemd start-limit defects. Corrections remained inside the approved Worker reliability outcome. Final Issue #159 runtime was accepted and the Issue closed completed.
