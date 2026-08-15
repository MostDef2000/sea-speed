# Implementation Plan: Calibration Overlay Ownership

- Specification: specs/007-calibration-overlay-ownership/spec.md
- Issue: #159
- Status: Accepted / completed

## Architecture

```text
persisted calibration -> frontend canvas -> visible ROI/A-B
persisted calibration -> Worker compute path -> ROI/speed semantics
Worker overlay pixels -> detections/status only, no calibration geometry
```

## Decisions

### D-001 - One visual owner
Frontend owns calibration presentation; Worker owns AI annotations/computation.

### D-002 - Preserve computation
Removing drawing does not alter ROI/speed formulas or state schemas.

### D-003 - Mixed rollout
Production learning required both Ubuntu Worker and VPS frontend acceptance.

## Affected contours

- VPS: frontend calibration presentation.
- Ubuntu Worker/relay: Worker overlay generation.
- Windows AI Worker: shared-source compatibility only when derived by exact task paths; Issue #159 accepted production target was Ubuntu + VPS.
- Public interfaces: unchanged.

## Validation

Focused frontend/Worker tests plus exact runtime Worker progression and browser visual acceptance.

## Rollout and rollback

Separately authorized Worker/VPS rollout with exact rollback targets.

## Runtime feedback

Final Issue #159 acceptance records Worker/runtime and browser behavior as accepted; Issue closed completed.
