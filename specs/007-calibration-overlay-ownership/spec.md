# Feature Specification: Calibration Overlay Ownership

- Feature: 007-calibration-overlay-ownership
- Issue: #159
- Status: Accepted / completed in production

## Product outcome

The frontend is the sole visual owner of saved ROI and speed-line calibration on the Operator AI frame. Saved calibration remains visible in normal monitoring and edit mode changes interactivity, while Worker-generated JPEGs do not bake a duplicate calibration copy. Worker ROI filtering and speed computation semantics remain unchanged.

## User scenarios

1. Saved enabled ROI/A-B lines remain visible on reload/normal monitoring.
2. Edit mode adds handles/interactivity without changing ownership.
3. Clear disables persisted calibration through existing API and removes frontend geometry.
4. Worker computation still consumes the same persisted calibration while omitting visual calibration drawing from image pixels.

## Requirements

- frontend owns visible ROI/A-B geometry;
- Worker latest/event JPEG path omits baked calibration shapes;
- ROI filtering/speed calculation paths and formulas unchanged;
- calibration/API schemas unchanged;
- camera/auth/detection/tracking/event semantics unchanged.

## Acceptance criteria

- persistent frontend geometry in normal mode: accepted;
- no Worker-baked calibration copy: accepted;
- edit/clear behavior preserved;
- Worker and VPS exact runtime contours accepted under Issue #159;
- Issue #159 closed completed.

## Runtime feedback

Issue #159 evolved from an initial frontend-only assumption into a mixed Worker+VPS outcome after production exposed two visual owners. Final accepted runtime established a stable supervised Ubuntu Worker release and frontend-owned calibration; Issue closed completed on 2026-08-15.
