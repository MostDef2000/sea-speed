# Specification: ROI-bounded motion and AI inference

Status: Accepted / completed in production
- Feature: 010-roi-bounded-motion-inference
- Issue: #168
Runtime contour: Ubuntu Worker

## Product outcome

Saved operator ROI is the real processing boundary for motion and AI while preserving original camera coordinates and existing detection/tracking/speed/event semantics. Pixels outside a valid enabled ROI are blacked out for motion/inference; technical yellow motion rectangles are absent from the operator overlay while real accepted AI detections remain boxed/labeled.

## User scenarios

1. Motion outside enabled ROI does not trigger motion/AI.
2. Motion inside ROI drives the existing AI-active window.
3. ROI change resets motion baseline rather than synthesizing motion.
4. Disabled/invalid ROI returns to full-frame processing.

## Requirements

- one effective ROI snapshot per frame;
- same-size black-outside processing frame, no crop/rebase;
- motion and AI consume that processing frame;
- final ROI guard uses the same frame snapshot;
- ROI signature changes reset motion baseline/active window;
- yellow technical motion rectangles are not rendered;
- green AI detections/labels and ByteTrack/speed/event semantics remain unchanged;
- API/frontend/auth/media/supervisor topology unchanged.

## Acceptance criteria

Focused tests prove masking, baseline reset, exact snapshot usage and preserved AI boxes. Issue #168 production acceptance established exact Worker source `8cdf7d5d0a4b2b03ec26500bbfa15a20922c5fb4`, sustained frame/state progression, `ai_inference_ready=true`, no yellow motion rectangles and preserved frontend calibration geometry. Issue closed completed.

## Runtime feedback

Acceptance result: COMPLETE. Ubuntu Worker only; VPS deployment was not required for the source diff.
