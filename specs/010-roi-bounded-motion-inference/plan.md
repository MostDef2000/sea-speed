# Plan: ROI-bounded motion and AI inference

Status: Active
Issue: #168
Specification: `specs/010-roi-bounded-motion-inference/spec.md`

## Decisions

- Preserve the original frame dimensions and coordinate system and use a polygon mask rather than cropping the ROI. This avoids coordinate translation in detection boxes, ByteTrack state, speed-line geometry, snapshots and API payloads.
- Capture one effective ROI snapshot per processed frame and reuse it for both the processing mask and the final ROI detection guard.
- Treat disabled/invalid ROI as full-frame processing for backward compatibility.
- Reset only the motion detector baseline, technical motion state and AI-active deadline when the effective ROI signature changes. Do not reset ByteTrack/model state or mutate persisted calibration.
- Keep the original unmasked camera frame as the visual base for the operator overlay; use the masked same-size frame only for motion and AI processing.
- Remove yellow technical motion rectangles from the operator overlay while retaining existing AI detection boxes/labels.
- Keep the existing Ubuntu AI supervisor/protocol unchanged; it already receives whichever frame the core Worker passes to `detect_vehicles`.

## Architecture

For every frame:

1. Fetch the existing cached remote ROI once.
2. Convert enabled+valid ROI into an effective point list; otherwise use an empty list for full-frame mode.
3. Compute a deterministic processing signature from that effective ROI.
4. If the signature changed, reset the motion detector baseline, motion boxes/area and AI-active deadline before processing the frame.
5. Build `processing_frame`: original frame unchanged for full-frame mode; otherwise black outside the polygon and unchanged inside it.
6. Feed `processing_frame` to `MotionDetector.process`.
7. If the existing AI-active window is active, feed the same `processing_frame` to the existing `detect_vehicles` / Ubuntu supervisor boundary.
8. Apply existing motion-intersection filtering.
9. Apply final ROI filtering using the same effective ROI point list captured at step 1.
10. Run unchanged tracking/speed/event processing on accepted detections.
11. Draw the operator overlay from the original camera frame and accepted AI detections only; do not draw technical `motion_boxes`.

The core Worker owns ROI masking because it already owns motion filtering and final ROI filtering. The Ubuntu entrypoint continues to supervise the AI subprocess without understanding ROI semantics, so the same processing frame crosses the existing inference boundary without protocol or coordinate changes.

## Implementation

### Worker source

In `worker/hls_motion_yolo_worker_events.py`:

- add `roi_processing_signature`;
- add `mask_frame_to_roi`;
- add `prepare_roi_processing_frame` to bind the cached ROI snapshot to one frame and reset the motion baseline on signature changes;
- allow `detection_inside_road_roi` and `filter_detections_by_roi` to accept an explicit ROI point snapshot while retaining their current default behavior;
- route `main()` motion and AI inference through `processing_frame`;
- keep the original camera `frame` for the final operator overlay;
- stop rendering yellow motion rectangles in `draw_overlay` while retaining green AI detection boxes/labels and status text.

No change is required in `worker/ubuntu_worker_entrypoint.py`: its supervised detection hook receives whichever frame the core Worker passes to `detect_vehicles`, so masking remains inside the core processing contract without changing the child protocol.

## Validation

Create `tests/test_worker_roi_pipeline.py` with dependency-light contract tests that:

- execute the mask helper against fake numpy/OpenCV adapters;
- verify full-frame fallback when ROI is absent;
- verify ROI signature changes reset motion baseline/active window once;
- verify `main()` routes the ROI processing frame into both motion and AI and uses the same ROI snapshot for the final guard;
- verify yellow motion-box rendering is absent while AI detection-box rendering remains.

Run repository CI as the authoritative integration test: PR Validation and Quality integration must both succeed on the exact head.

## Affected contours

- Ubuntu Worker runtime: REQUIRED after separate exact-SHA production authorization.
- Repository policy impact class: `WINDOWS_WORKER` because the changed runtime path is `worker/**`; the commissioned production target remains Ubuntu.
- VPS deployment: NOT REQUIRED by this diff.
- API/frontend/auth/network contours: unchanged.
- Production rollout uses the existing repo-owned Ubuntu Worker exact updater and one largest-safe operator step.

## Runtime feedback

The accepted production Worker release `6bf909c13d48df1d44b87a62d0686b61d8c3af45` established stable RTSP ingestion, bounded supervised AI inference and advancing frame/state counters. The subsequent operator view demonstrated that yellow technical motion rectangles still came from full-frame motion processing even though detections were later ROI-filtered. This plan intentionally changes only that processing boundary and overlay ownership; it relies on the already accepted media and AI-supervision architecture.

## Rollback

Use the existing exact Worker rollback semantics. If candidate activation/runtime progression fails, the updater restores the previous exact Worker release. No data migration or persisted calibration mutation is introduced by this feature.
