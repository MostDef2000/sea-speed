# Specification: ROI-bounded motion and AI inference

Status: Active
Issue: #168
Runtime contour: Ubuntu Worker

## Problem

The Worker currently detects motion across the full camera frame and can activate AI because of movement outside the operator-selected ROI. It also sends the full visual frame into inference and renders yellow technical motion rectangles into the operator image. ROI filtering happens only after inference, so irrelevant areas can still drive motion, AI work, and operator-visible noise.

## Product outcome

Make the saved operator ROI the actual processing boundary for motion and AI while preserving the original camera coordinate system and the existing detection/tracking/speed/event semantics for accepted objects. Real AI detections inside ROI remain visibly boxed and labeled. Technical motion rectangles are not part of the operator display.

## Functional requirements

1. The Worker obtains one effective ROI snapshot for each processed frame.
2. An ROI is effective only when the remote ROI is enabled and contains at least three valid points.
3. With an effective ROI, the Worker creates a same-size processing frame whose pixels outside the ROI polygon are black and whose pixels inside the polygon are unchanged.
4. Motion detection runs on that processing frame, not on the unmasked full frame.
5. AI inference runs on that same processing frame while preserving original width, height and pixel coordinates. Cropping or coordinate rebasing is not allowed by this feature.
6. Movement outside an effective ROI must not create motion boxes, motion area, or AI activation.
7. Movement inside an effective ROI continues to drive the existing `MOTION_ACTIVE_SECONDS` AI-active window.
8. The existing motion-intersection filter remains in the detection path.
9. The existing ROI detection filter remains as a final fail-safe, using the same ROI snapshot captured for that frame rather than refetching a different ROI during the same frame.
10. A change between effective ROI processing signatures resets the motion baseline and active window before processing the first frame under the new ROI. The mask transition itself must not be treated as motion.
11. When ROI is disabled or invalid, processing remains full-frame, preserving existing motion/AI behavior.
12. Yellow technical motion rectangles are not rendered into `latest_overlay.jpg` or event snapshots derived from that overlay.
13. Actual AI detection boxes and labels for accepted detections remain rendered with existing track ID, class, confidence and speed semantics.

## Protected behavior

This feature must not change:

- ROI persistence or API schema;
- frontend ROI/speed-line editing behavior;
- Ultralytics model choice, confidence threshold, allowed class set or ByteTrack configuration;
- persistent tracking semantics;
- speed calculations, speed-line calibration, event cooldown or event schema;
- RTSP/HLS transport or bounded media reader behavior;
- Ubuntu AI child supervision/protocol;
- authentication, nginx or network topology.

## Failure and fallback behavior

- ROI fetch failures continue to use the existing cached ROI behavior.
- Disabled/invalid ROI fails open to the existing full-frame processing mode rather than stopping the Worker.
- ROI changes fail safe by resetting only motion baseline/AI-active timing; they do not mutate persisted calibration or model state.

## Acceptance criteria

- Focused tests prove disabled ROI leaves the frame unchanged for processing.
- Focused tests prove an enabled ROI creates a same-size polygon mask and black-outside inference input contract.
- Focused tests prove a changed ROI resets motion baseline/active timing only once per signature change.
- Source contract proves both motion and AI consume the ROI processing frame and final ROI filtering uses the frame snapshot.
- Source contract proves yellow motion boxes are absent while green AI detection boxes/labels remain.
- Existing Worker tests remain green.
- PR Validation and Quality integration are green on the exact final head.
- Production acceptance, after separate exact-SHA approval, confirms advancing Worker frames/state/AI plus operator-visible AI detection boxes without yellow motion rectangles.
